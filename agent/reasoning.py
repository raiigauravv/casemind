"""
Amazon Bedrock case reasoning call.

Takes a case narrative plus retrieved memory (similar historical cases,
entity/decision history) and returns a decision, confidence, and reasoning
text. If ANY part of this call is mocked or simplified for cost reasons in
the final demo, that must be disclosed in the README per roadmap Phase 8
("No overstating what Bedrock/Lambda do... disclose it").

IMPLEMENTATION NOTE: uses the Bedrock Anthropic Messages API format via
invoke_model, routed through a cross-region inference profile (model ID
prefixed "us."), which Bedrock requires for on-demand Claude 4.x models.
Model defaults to Claude Haiku 4.5 for cost efficiency; override with
BEDROCK_MODEL_ID. Verified end-to-end against live Bedrock on 2026-08-10
after the one-time Anthropic use-case form was approved and a Service
Quotas increase (requests/min and tokens/min for this model) was granted.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("casemind.reasoning")
logging.basicConfig(level=logging.INFO)

DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
VALID_DECISIONS = {"escalate", "clear", "monitor"}


class ReasoningNotConfigured(RuntimeError):
    pass


class ReasoningParseError(RuntimeError):
    """Raised when the model's response can't be parsed into a decision."""


@dataclass
class ReasoningInput:
    case_narrative: str
    similar_cases: list[str] = field(default_factory=list)
    entity_history: str = ""


@dataclass
class ReasoningOutput:
    decision: str  # escalate / clear / monitor
    confidence: float
    reasoning: str


SYSTEM_PROMPT = """You are an AML/fraud triage assistant helping a bank analyst \
review a flagged case. All data you are given is SYNTHETIC, used only for a \
hackathon demo. You are informed by the analyst's workflow, not a compliance \
authority — never claim regulatory certification.

Given a case narrative, similar historical cases (with their outcomes), and \
entity decision history, respond with a JSON object only, no other text:
{"decision": "escalate" | "clear" | "monitor", "confidence": <float 0-1>, \
"reasoning": "<2-4 sentence explanation citing which retrieved cases informed this>"}
"""


class BedrockReasoner:
    def __init__(self) -> None:
        self.region = os.environ.get("AWS_REGION")
        self.model_id = os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
        self.access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        self.secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        self.session_token = os.environ.get("AWS_SESSION_TOKEN")
        self._client = None

    def _require_config(self) -> None:
        if not self.region:
            raise ReasoningNotConfigured("AWS_REGION must be set (see .env.example).")

    def _client_or_create(self):
        if self._client is None:
            self._require_config()
            kwargs = {"region_name": self.region}
            # Only override boto3's default credential chain when static
            # (non-session) creds are supplied, e.g. local dev via .env.
            # Inside Lambda, AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY are
            # reserved env vars tied to a temporary session that also
            # requires AWS_SESSION_TOKEN — passing the pair without the
            # token produces "security token invalid". If a session token
            # is present, let boto3's default chain (which handles this
            # correctly) pick the credentials up instead.
            if self.access_key and self.secret_key and not self.session_token:
                kwargs["aws_access_key_id"] = self.access_key
                kwargs["aws_secret_access_key"] = self.secret_key
            self._client = boto3.client("bedrock-runtime", **kwargs)
        return self._client

    def _build_prompt(self, inp: ReasoningInput) -> str:
        similar = "\n".join(f"- {c}" for c in inp.similar_cases) or "(none retrieved)"
        return (
            f"CASE NARRATIVE:\n{inp.case_narrative}\n\n"
            f"SIMILAR HISTORICAL CASES (retrieved via vector search):\n{similar}\n\n"
            f"ENTITY DECISION HISTORY:\n{inp.entity_history or '(none on file)'}\n"
        )

    def reason(self, inp: ReasoningInput, max_retries: int = 3) -> ReasoningOutput:
        client = self._client_or_create()
        logger.info(
            "[REASONING_AUDIT] ts=%s model=%s similar_case_count=%s",
            datetime.now(timezone.utc).isoformat(),
            self.model_id,
            len(inp.similar_cases),
        )

        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": self._build_prompt(inp)}],
            }
        )

        last_err: Exception | None = None
        for attempt in range(max_retries):
            try:
                resp = client.invoke_model(modelId=self.model_id, body=body)
                payload = json.loads(resp["body"].read())
                text = payload["content"][0]["text"]
                return self._parse_response(text)
            except ClientError as e:
                last_err = e
                code = e.response.get("Error", {}).get("Code", "")
                if code == "ThrottlingException" and attempt < max_retries - 1:
                    wait = 2**attempt * 2
                    logger.warning("Bedrock throttled, retrying in %ss (attempt %s)", wait, attempt + 1)
                    time.sleep(wait)
                    continue
                raise
        raise last_err  # pragma: no cover

    def _parse_response(self, text: str) -> ReasoningOutput:
        text = text.strip()
        # tolerate the model wrapping JSON in a code fence
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ReasoningParseError(f"Could not parse model output as JSON: {text!r}") from e

        decision = data.get("decision", "").lower()
        if decision not in VALID_DECISIONS:
            raise ReasoningParseError(f"Model returned invalid decision: {decision!r}")

        return ReasoningOutput(
            decision=decision,
            confidence=float(data.get("confidence", 0.0)),
            reasoning=data.get("reasoning", ""),
        )
