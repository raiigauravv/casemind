"""
AWS Lambda entry point — event-driven agent execution loop.

Trigger: a new case object landing in S3 (bucket/key with a JSON body of
shape {"case_id": ..., "entity_id": ..., "narrative": ...}).

Loop: read case -> vector search for similar historical cases -> read
entity/decision history from structured memory -> Bedrock reasoning ->
write decision + retrieved_case_ids (the audit trail) back to memory.

For local testing without a deployed S3 bucket/Lambda (Terraform apply is
still gated on Checkpoint 4), handler() also accepts a direct invocation
payload shaped like {"case_id": ..., "entity_id": ..., "narrative": ...}
so the full loop can be exercised end-to-end against the live CockroachDB
cluster and Bedrock before any AWS infra is provisioned.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from agent.memory_client import DecisionRecord, MemoryClient
from agent.reasoning import BedrockReasoner, ReasoningInput
from agent.vector_search import VectorSearchClient

logger = logging.getLogger("casemind.lambda_handler")
logging.basicConfig(level=logging.INFO)


def _is_apigw_event(event: dict[str, Any]) -> bool:
    """True if this invocation came through API Gateway (HTTP API v2 proxy)."""
    return "requestContext" in event and "http" in event.get("requestContext", {})


def _load_case_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Extract a case payload from an S3 event, an API Gateway HTTP API
    proxy request, or a direct invocation payload."""
    if "Records" in event and event["Records"] and "s3" in event["Records"][0]:
        import boto3

        record = event["Records"][0]["s3"]
        bucket = record["bucket"]["name"]
        key = record["object"]["key"]
        logger.info("[LAMBDA_AUDIT] op=S3_READ bucket=%s key=%s", bucket, key)
        s3 = boto3.client("s3")
        obj = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(obj["Body"].read())

    if _is_apigw_event(event):
        body = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            import base64

            body = base64.b64decode(body).decode()
        logger.info("[LAMBDA_AUDIT] op=APIGW_READ route=%s", event.get("routeKey"))
        return json.loads(body)

    # direct invocation payload (local testing, or a synchronous API path)
    if "case_id" in event or "narrative" in event:
        return event

    raise ValueError(f"Unrecognized event shape, expected S3 record, API Gateway request, or direct case payload: {event!r}")


def _format_similar_cases(similar) -> list[str]:
    return [f"[{c.case_id}] (similarity={c.similarity:.3f}) {c.narrative}" for c in similar]


def _format_entity_history(entity_history: dict[str, Any]) -> str:
    if not entity_history.get("entity"):
        return "(no entity on file)"
    lines = [f"Entity: {entity_history['entity']['entity_name']} ({entity_history['entity']['entity_type']})"]
    if entity_history["entity"].get("risk_notes"):
        lines.append(f"Risk notes: {entity_history['entity']['risk_notes']}")
    for d in entity_history["decisions"]:
        lines.append(f"  Prior decision: {d['decision']} (confidence={d['confidence']}) — {d['reasoning']}")
    return "\n".join(lines)


CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "content-type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
}


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    is_apigw = _is_apigw_event(event)

    if is_apigw:
        try:
            return _handle_case(event)
        except Exception as e:  # noqa: BLE001 — surface errors as JSON to the frontend, not a raw Lambda 500
            logger.exception("[LAMBDA_AUDIT] op=ERROR")
            return {
                "statusCode": 500,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": str(e)}),
            }

    return _handle_case(event)


def _handle_case(event: dict[str, Any]) -> dict[str, Any]:
    logger.info(
        "[LAMBDA_AUDIT] ts=%s op=INVOKE event_keys=%s",
        datetime.now(timezone.utc).isoformat(),
        list(event.keys()),
    )
    is_apigw = _is_apigw_event(event)

    memory = MemoryClient()
    vectors = VectorSearchClient()
    reasoner = BedrockReasoner()

    case = _load_case_payload(event)
    case_id = case.get("case_id") or str(uuid.uuid4())
    entity_id = case["entity_id"]
    narrative = case["narrative"]

    # 1. persist the incoming case as 'open' before reasoning about it
    memory.upsert_case(case_id=case_id, entity_id=entity_id, narrative=narrative, status="open")

    # 2. semantic retrieval — similar historical cases from the vector index
    similar = vectors.find_similar_cases(narrative, top_k=5)
    retrieved_case_ids = [c.case_id for c in similar]

    # 3. structured memory — this entity's decision history
    entity_history = memory.get_entity_history(entity_id)

    # 4. reasoning — Bedrock, informed by both retrieval sources
    reasoning_input = ReasoningInput(
        case_narrative=narrative,
        similar_cases=_format_similar_cases(similar),
        entity_history=_format_entity_history(entity_history),
    )
    result = reasoner.reason(reasoning_input)

    # 5. write the decision back to memory — retrieved_case_ids IS the audit trail
    decision_id = memory.write_decision(
        DecisionRecord(
            case_id=case_id,
            decision=result.decision,
            confidence=result.confidence,
            reasoning=result.reasoning,
            retrieved_case_ids=retrieved_case_ids,
        )
    )

    # 6. update case status to reflect the decision
    new_status = {"escalate": "closed_escalated", "clear": "closed_cleared", "monitor": "open"}[result.decision]
    memory.upsert_case(case_id=case_id, entity_id=entity_id, narrative=narrative, status=new_status)

    logger.info(
        "[LAMBDA_AUDIT] ts=%s op=COMPLETE case_id=%s decision_id=%s decision=%s retrieved=%s",
        datetime.now(timezone.utc).isoformat(),
        case_id,
        decision_id,
        result.decision,
        retrieved_case_ids,
    )

    result_body = {
        "case_id": case_id,
        "decision_id": decision_id,
        "decision": result.decision,
        "confidence": result.confidence,
        "reasoning": result.reasoning,
        "retrieved_case_ids": retrieved_case_ids,
    }

    if is_apigw:
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps(result_body),
        }
    return result_body
