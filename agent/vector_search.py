"""
Semantic case retrieval via CockroachDB Distributed Vector Indexing.

Flow: embed narrative -> query narrative_embedding vector index -> return
top-k similar historical cases. Every query against the vector index is
logged (audit trail), same discipline as memory_client.py.

Status: interface + logging scaffolding only. Vector index queries are
stubbed pending Checkpoint 3 (live cluster migrations).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger("casemind.vector_search")
logging.basicConfig(level=logging.INFO)


class VectorSearchNotConfigured(RuntimeError):
    pass


@dataclass
class SimilarCase:
    case_id: str
    narrative: str
    similarity: float


class VectorSearchClient:
    def __init__(self) -> None:
        self.connection_string = os.environ.get("COCKROACHDB_CONNECTION_STRING")

    def _require_config(self) -> None:
        if not self.connection_string:
            raise VectorSearchNotConfigured(
                "COCKROACHDB_CONNECTION_STRING must be set (see .env.example)."
            )

    def embed(self, narrative: str) -> list[float]:
        """Produce a narrative embedding. Model TBD — likely a Bedrock
        embedding model to keep the whole reasoning path on AWS + CockroachDB.
        """
        raise NotImplementedError("embedding call — implement in Phase 2")

    def find_similar_cases(self, narrative: str, top_k: int = 5) -> list[SimilarCase]:
        self._require_config()
        logger.info(
            "[VECTOR_AUDIT] ts=%s op=QUERY top_k=%s narrative_preview=%r",
            datetime.now(timezone.utc).isoformat(),
            top_k,
            narrative[:80],
        )
        raise NotImplementedError(
            "Distributed Vector Indexing query — implement in Phase 2 against live cluster"
        )
