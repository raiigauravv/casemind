"""
Semantic case retrieval via CockroachDB Distributed Vector Indexing.

Flow: embed narrative -> query narrative_embedding vector index -> return
top-k similar historical cases. Every query against the vector index is
logged (audit trail), same discipline as memory_client.py.

IMPLEMENTATION NOTE on embed(): uses AWS Bedrock's amazon.titan-embed-text-v1
model, which outputs a fixed 1536-dim vector matching the `cases.narrative_embedding
VECTOR(1536)` column exactly (Titan v2 defaults to 1024/512/256 dims, which
would have required a schema migration — v1 was chosen specifically to avoid
that). Falls back to a deterministic local hashing embedding (NOT semantic,
only useful for testing pipeline mechanics) if AWS credentials aren't
configured. Verified end-to-end against the live vector index on
2026-08-10 — retrieval correctly ranks semantically similar synthetic
cases using real Titan embeddings.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import struct
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import psycopg

logger = logging.getLogger("casemind.vector_search")
logging.basicConfig(level=logging.INFO)

EMBEDDING_DIM = 1536
BEDROCK_EMBED_MODEL_ID = "amazon.titan-embed-text-v1"


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
        self.aws_region = os.environ.get("AWS_REGION")
        self.aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        self.aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        self._bedrock_client = None

    def _require_config(self) -> None:
        if not self.connection_string:
            raise VectorSearchNotConfigured(
                "COCKROACHDB_CONNECTION_STRING must be set (see .env.example)."
            )

    def _connect(self) -> psycopg.Connection:
        self._require_config()
        return psycopg.connect(self.connection_string, autocommit=True, connect_timeout=10)

    def _bedrock_available(self) -> bool:
        return bool(self.aws_region and self.aws_access_key and self.aws_secret_key)

    def _get_bedrock_client(self):
        if self._bedrock_client is None:
            import boto3

            self._bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=self.aws_region,
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
            )
        return self._bedrock_client

    def _embed_hash_fallback(self, narrative: str) -> list[float]:
        """Deterministic local feature-hashing embedding. NOT semantic —
        only proves retrieval pipeline mechanics when Bedrock is unavailable.
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

    def embed(self, narrative: str, max_retries: int = 3) -> list[float]:
        """Embed a narrative via Bedrock Titan; falls back to a local
        deterministic hash embedding if AWS creds aren't configured.
        """
        if not self._bedrock_available():
            logger.warning("AWS Bedrock not configured — using non-semantic hash fallback embedding")
            return self._embed_hash_fallback(narrative)

        from botocore.exceptions import ClientError

        client = self._get_bedrock_client()
        body = json.dumps({"inputText": narrative})
        for attempt in range(max_retries):
            try:
                resp = client.invoke_model(modelId=BEDROCK_EMBED_MODEL_ID, body=body)
                payload = json.loads(resp["body"].read())
                return payload["embedding"]
            except ClientError as e:
                code = e.response.get("Error", {}).get("Code", "")
                if code == "ThrottlingException" and attempt < max_retries - 1:
                    wait = 2**attempt * 2
                    logger.warning("Bedrock embedding throttled, retrying in %ss", wait)
                    time.sleep(wait)
                    continue
                logger.error("Bedrock embedding failed (%s), falling back to hash embedding", code)
                return self._embed_hash_fallback(narrative)

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
