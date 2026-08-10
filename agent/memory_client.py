"""
CockroachDB structured memory interface — reads/writes case, entity, and
decision state for the agent.

Every read and write in this module is logged explicitly (stdout / CloudWatch
in Lambda), per roadmap rule: "Every memory read/write in agent code should
be logged explicitly — this is required for the demo and for the audit-trail
story in judging."

Connection is lazy and only happens when a method is called, so this file
can be imported/linted/tested without live credentials. If required env
vars are missing, calls raise a clear MemoryClientNotConfigured error
rather than failing silently or with an opaque connection error.

IMPLEMENTATION NOTE: this connects directly to CockroachDB over
COCKROACHDB_CONNECTION_STRING (via psycopg) rather than issuing literal
MCP protocol calls to the Managed MCP Server. Functionally it reads/writes
the exact same tables the MCP Server would, with the same audit logging —
but for the submission write-up ("which CockroachDB tools used and how"),
swapping this to route through actual MCP tool calls is a follow-up if the
literal MCP transport matters more than functional equivalence. Flagging
this rather than assuming it doesn't matter.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import psycopg

logger = logging.getLogger("casemind.memory_client")
logging.basicConfig(level=logging.INFO)


class MemoryClientNotConfigured(RuntimeError):
    """Raised when required CockroachDB env vars are missing."""


@dataclass
class DecisionRecord:
    case_id: str
    decision: str  # escalate / clear / monitor
    confidence: float
    reasoning: str
    retrieved_case_ids: list[str] = field(default_factory=list)
    decision_id: str | None = None
    created_at: str | None = None


class MemoryClient:
    """Structured memory reads/writes against CockroachDB.

    All reads and writes are logged with a timestamp, operation type, and
    row identifiers touched — this log is the audit trail referenced in the
    judging criteria and demo script.
    """

    def __init__(self) -> None:
        self.mcp_url = os.environ.get("COCKROACHDB_MCP_URL")
        self.connection_string = os.environ.get("COCKROACHDB_CONNECTION_STRING")

    def _require_config(self) -> None:
        if not self.connection_string:
            raise MemoryClientNotConfigured(
                "COCKROACHDB_CONNECTION_STRING must be set (see .env.example)."
            )

    def _connect(self) -> psycopg.Connection:
        self._require_config()
        return psycopg.connect(self.connection_string, autocommit=True, connect_timeout=10)

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
        """Read entity details + all decisions tied to that entity's cases."""
        self._log_op("READ", "entities+decisions", entity_id)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT entity_id, entity_name, entity_type, risk_notes, created_at "
                "FROM entities WHERE entity_id = %s",
                (entity_id,),
            )
            row = cur.fetchone()
            if row is None:
                return {"entity": None, "decisions": []}
            entity = {
                "entity_id": str(row[0]),
                "entity_name": row[1],
                "entity_type": row[2],
                "risk_notes": row[3],
                "created_at": row[4].isoformat() if row[4] else None,
            }

            cur.execute(
                "SELECT d.decision_id, d.case_id, d.decision, d.confidence, d.reasoning, "
                "d.retrieved_case_ids, d.created_at "
                "FROM decisions d JOIN cases c ON d.case_id = c.case_id "
                "WHERE c.entity_id = %s ORDER BY d.created_at DESC",
                (entity_id,),
            )
            decisions = [
                {
                    "decision_id": str(r[0]),
                    "case_id": str(r[1]),
                    "decision": r[2],
                    "confidence": r[3],
                    "reasoning": r[4],
                    "retrieved_case_ids": [str(x) for x in (r[5] or [])],
                    "created_at": r[6].isoformat() if r[6] else None,
                }
                for r in cur.fetchall()
            ]
            return {"entity": entity, "decisions": decisions}

    def get_decision_history(self, case_id: str) -> list[DecisionRecord]:
        """Read prior decisions tied to a specific case_id."""
        self._log_op("READ", "decisions", case_id)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT decision_id, case_id, decision, confidence, reasoning, "
                "retrieved_case_ids, created_at "
                "FROM decisions WHERE case_id = %s ORDER BY created_at DESC",
                (case_id,),
            )
            return [
                DecisionRecord(
                    decision_id=str(r[0]),
                    case_id=str(r[1]),
                    decision=r[2],
                    confidence=r[3],
                    reasoning=r[4],
                    retrieved_case_ids=[str(x) for x in (r[5] or [])],
                    created_at=r[6].isoformat() if r[6] else None,
                )
                for r in cur.fetchall()
            ]

    # ---- writes ----

    def write_decision(self, record: DecisionRecord) -> str:
        """Write a new decision record. Returns the generated decision_id.

        retrieved_case_ids on the record IS the audit trail: it must always
        be populated with whichever case_ids were used as retrieval context
        for this decision, even if the list is empty (explicit, not omitted).
        """
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
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO decisions "
                "(decision_id, case_id, decision, confidence, reasoning, retrieved_case_ids) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    decision_id,
                    record.case_id,
                    record.decision,
                    record.confidence,
                    record.reasoning,
                    record.retrieved_case_ids,
                ),
            )
        return decision_id

    def upsert_case(self, case_id: str, entity_id: str, narrative: str, status: str = "open") -> str:
        self._log_op("WRITE", "cases", case_id, detail=f"status={status}")
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO cases (case_id, entity_id, narrative, status) "
                "VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (case_id) DO UPDATE SET "
                "narrative = EXCLUDED.narrative, status = EXCLUDED.status, updated_at = now()",
                (case_id, entity_id, narrative, status),
            )
        return case_id
