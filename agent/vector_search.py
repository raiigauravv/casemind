"""
Semantic case retrieval via CockroachDB Distributed Vector Indexing.

Flow: embed narrative -> query narrative_embedding vector index -> return
top-k similar historical cases. Every query against the vector index is
logged (audit trail), same discipline as memory_client.py.

IMPLEMENTATION NOTE on embed(): the real embedding model is meant to be an
AWS Bedrock embedding model (e.g. amazon.titan-embed-text-v2), which keeps
the whole reasoning path on AWS + CockroachDB as the roadmap intends. AWS
credentials aren't wired up yet (Phase 3), so embed() currently falls back
to a deterministic local hashing embedding — NOT semantically meaningful,
only useful to prove the retrieval pipeline (embed -> store -> ANN query
-> retrieve) works end-to-end against the live vector index. This MUST be
swapped for a real Bedrock embedding call before the demo; the fallback
is clearly labeled below and raises no illusions about being production-ready.
"""

from __future__ import annotations

import hashlib
import logging
import os
import struct
from dataclasses import dataclass
from datetime import datetime, timezone

import psycopg

logger = logging.getLogger("casemind.vector_search")
logging.basicConfig(level=logging.INFO)

EMBEDDING_DIM = 1536


class VectorSearchNotConfigured(RuntimeError):
    pass


@dataclass
class SimilarCase:
    case_id: str
    narrative: str
    similarity: float  # higher is more similar (1 - normalized distance)


class VectorSearchClient:
    def __init__(self) -> None:
        self.connection_string = os.environ.get("COCKROACHDB_CONNECTION_STRING")

    def _require_config(self) -> None:
        if not self.connection_string:
            raise VectorSearchNotConfigured(
                "COCKROACHDB_CONNECTION_STRING must be set (see .env.example)."
            )

    def _connect(self) -> psycopg.Connection:
        self._require_config()
        return psycopg.connect(self.connection_string, autocommit=True, connect_timeout=10)

    def embed(self, narrative: str) -> list[float]:
        """PLACEHOLDER embedding — deterministic feature hashing, NOT semantic.

        Replace with a Bedrock embedding call (agent/reasoning.py's Bedrock
        client can be reused for this) once AWS credentials are available.
        Kept deterministic so repeated calls on the same narrative are
        reproducible for testing.
        """
        vec = [0.0] * EMBEDDING_DIM
        words = narrative.lower().split()
        for word in words:
            h = hashlib.sha256(word.encode()).digest()
            idx = struct.unpack("I", h[:4])[0] % EMBEDDING_DIM
            sign = 1.0 if h[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def backfill_embedding(self, case_id: str, narrative: str) -> None:
        """Compute and store the embedding for a single case row."""
        embedding = self.embed(narrative)
        vec_literal = "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"
        logger.info(
            "[VECTOR_AUDIT] ts=%s op=BACKFILL case_id=%s",
            datetime.now(timezone.utc).isoformat(),
            case_id,
        )
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE cases SET narrative_embedding = %s WHERE case_id = %s",
                (vec_literal, case_id),
            )

    def find_similar_cases(self, narrative: str, top_k: int = 5) -> list[SimilarCase]:
        logger.info(
            "[VECTOR_AUDIT] ts=%s op=QUERY top_k=%s narrative_preview=%r",
            datetime.now(timezone.utc).isoformat(),
            top_k,
            narrative[:80],
        )
        embedding = self.embed(narrative)
        vec_literal = "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT case_id, narrative, narrative_embedding <-> %s AS distance "
                "FROM cases WHERE narrative_embedding IS NOT NULL "
                "ORDER BY distance LIMIT %s",
                (vec_literal, top_k),
            )
            return [
                SimilarCase(
                    case_id=str(row[0]),
                    narrative=row[1],
                    similarity=1.0 - float(row[2]),
                )
                for row in cur.fetchall()
            ]
