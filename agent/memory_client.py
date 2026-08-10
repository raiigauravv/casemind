"""
CockroachDB MCP Server wrapper — agent's structured memory interface.

Every read and write in this module is logged explicitly (stdout / CloudWatch
in Lambda), per roadmap rule: "Every memory read/write in agent code should
be logged explicitly — this is required for the demo and for the audit-trail
story in judging."

This module intentionally does NOT connect to anything at import time.
Connection is lazy and only happens when a method is called, so this file
can be imported/linted/tested without live credentials. If required env
vars are missing, calls raise a clear MemoryClientNotConfigured error
rather than failing silently or with an opaque connection error.

Status: interface + logging scaffolding only. MCP Server calls are stubbed
pending Checkpoint 3 approval (migrations against the live cluster) and the
CockroachDB connection string being supplied via .env.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("casemind.memory_client")
logging.basicConfig(level=logging.INFO)


class MemoryClientNotConfigured(RuntimeError):
    """Raised when required CockroachDB / MCP env vars are missing."""


@dataclass
class DecisionRecord:
    case_id: str
    decision: str  # escalate / clear / monitor
    confidence: float
    reasoning: str
    retrieved_case_ids: list[str] = field(default_factory=list)


class MemoryClient:
    """Thin wrapper around the CockroachDB Managed MCP Server.

    All reads and writes are logged with a timestamp, operation type, and
    row identifiers touched — this log is the audit trail referenced in the
    judging criteria and demo script.
    """

    def __init__(self) -> None:
        self.mcp_url = os.environ.get("COCKROACHDB_MCP_URL")
        self.connection_string = os.environ.get("COCKROACHDB_CONNECTION_STRING")

    def _require_config(self) -> None:
        if not self.mcp_url or not self.connection_string:
            raise MemoryClientNotConfigured(
                "COCKROACHDB_MCP_URL and COCKROACHDB_CONNECTION_STRING must be "
                "set (see .env.example). Not configured yet — Phase 0 credential "
                "handoff is a prerequisite for this module to run against a live cluster."
            )

    def _log_op(self, op: str, table: str, row_id: str, detail: str = "") -> None:
        logger.info(
            "[MEMORY_AUDIT] ts=%s op=%s table=%s id=%s %s",
            datetime.now(timezone.utc).isoformat(),
            op,
            table,
            row_id,
            detail,
        )

    # ---- reads ----

    def get_entity_history(self, entity_id: str) -> dict[str, Any]:
        """Read entity + prior decisions for entity_id from structured memory."""
        self._require_config()
        self._log_op("READ", "entities+decisions", entity_id)
        raise NotImplementedError("MCP Server read call — implement in Phase 2 against live cluster")

    def get_decision_history(self, case_id: str) -> list[DecisionRecord]:
        """Read prior decisions tied to a case_id."""
        self._require_config()
        self._log_op("READ", "decisions", case_id)
        raise NotImplementedError("MCP Server read call — implement in Phase 2 against live cluster")

    # ---- writes ----

    def write_decision(self, record: DecisionRecord) -> str:
        """Write a new decision record. Returns the generated decision_id.

        retrieved_case_ids on the record IS the audit trail: it must always
        be populated with whichever case_ids were used as retrieval context
        for this decision, even if the list is empty (explicit, not omitted).
        """
        self._require_config()
        decision_id = str(uuid.uuid4())
        self._log_op(
            "WRITE",
            "decisions",
            decision_id,
            detail=(
                f"case_id={record.case_id} decision={record.decision} "
                f"confidence={record.confidence} "
                f"retrieved_case_ids={record.retrieved_case_ids}"
            ),
        )
        raise NotImplementedError("MCP Server write call — implement in Phase 2 against live cluster")

    def upsert_case(self, case_id: str, narrative: str, status: str = "open") -> str:
        self._require_config()
        self._log_op("WRITE", "cases", case_id, detail=f"status={status}")
        raise NotImplementedError("MCP Server write call — implement in Phase 2 against live cluster")
