"""
AWS Lambda entry point — event-driven agent execution loop.

Trigger: a new case object landing in S3.
Loop: embed narrative -> vector search for similar cases -> MCP read of
entity/decision history -> Bedrock reasoning -> MCP write of decision +
retrieved_case_ids (the audit trail).

Status: interface only. Depends on memory_client, vector_search, and
reasoning modules, all currently stubbed pending Phase 0 credentials and
their respective checkpoints (3 and 4).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from agent.memory_client import MemoryClient
from agent.reasoning import BedrockReasoner
from agent.vector_search import VectorSearchClient

logger = logging.getLogger("casemind.lambda_handler")
logging.basicConfig(level=logging.INFO)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    logger.info(
        "[LAMBDA_AUDIT] ts=%s op=INVOKE event_keys=%s",
        datetime.now(timezone.utc).isoformat(),
        list(event.keys()),
    )

    # Full loop wiring — left as NotImplementedError until Phase 3/4, since
    # every step below depends on live CockroachDB + Bedrock access.
    memory = MemoryClient()
    vectors = VectorSearchClient()
    reasoner = BedrockReasoner()

    raise NotImplementedError(
        "Full agent loop — implement in Phase 3/4 once memory_client, "
        "vector_search, and reasoning are live (Checkpoint 4 approved)"
    )
