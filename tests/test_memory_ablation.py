"""
Memory ablation test — Phase 6 deliverable.

Runs the same synthetic case narrative through BedrockReasoner twice:

  1. "blind" — no retrieved similar cases, no entity decision history
     (memory disabled)
  2. "informed" — real vector-search retrieval + real entity history from
     the live CockroachDB cluster (memory enabled, the normal agent path)

Both runs hit the real Bedrock Claude Haiku model. This is not a mocked
comparison — it demonstrates, with a live model call in each branch,
whether CaseMind's memory layer (CockroachDB vector search + structured
decision history) measurably changes the agent's decision, confidence, or
reasoning quality versus a stateless LLM call with the same prompt.

Run: python -m tests.test_memory_ablation  (from repo root, with .env loaded)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.memory_client import MemoryClient
from agent.reasoning import BedrockReasoner, ReasoningInput
from agent.vector_search import VectorSearchClient
from agent.lambda_handler import _format_entity_history, _format_similar_cases

# A case narrative deliberately similar to the "structuring" synthetic seed
# case (a1111111-0000-0000-0000-000000000002) so retrieval has something
# real to find, and referencing the same entity type pattern used in the
# entity history seed data.
ABLATION_CASE_NARRATIVE = (
    "SYNTHETIC CASE. Individual opened a personal account and over nine days "
    "made 14 separate cash deposits ranging from $9,100 to $9,700, each just "
    "under the $10,000 currency transaction reporting threshold, across three "
    "different branch locations. No stated business purpose for the pattern."
)
ABLATION_ENTITY_ID = "22222222-2222-2222-2222-222222222222"  # Priya Chandrasekaran (synthetic) — prior structuring escalation


def run_blind(reasoner: BedrockReasoner) -> dict:
    """No retrieval, no history — the model reasons from the narrative alone."""
    result = reasoner.reason(
        ReasoningInput(
            case_narrative=ABLATION_CASE_NARRATIVE,
            similar_cases=[],
            entity_history="",
        )
    )
    return {
        "decision": result.decision,
        "confidence": result.confidence,
        "reasoning": result.reasoning,
    }


def run_informed(reasoner: BedrockReasoner, vectors: VectorSearchClient, memory: MemoryClient) -> dict:
    """Real retrieval: vector search over live cases + real entity history."""
    similar = vectors.find_similar_cases(ABLATION_CASE_NARRATIVE, top_k=5)
    retrieved_case_ids = [c.case_id for c in similar]
    entity_history = memory.get_entity_history(ABLATION_ENTITY_ID)

    result = reasoner.reason(
        ReasoningInput(
            case_narrative=ABLATION_CASE_NARRATIVE,
            similar_cases=_format_similar_cases(similar),
            entity_history=_format_entity_history(entity_history),
        )
    )
    return {
        "decision": result.decision,
        "confidence": result.confidence,
        "reasoning": result.reasoning,
        "retrieved_case_ids": retrieved_case_ids,
    }


def main() -> None:
    reasoner = BedrockReasoner()
    vectors = VectorSearchClient()
    memory = MemoryClient()

    print("=" * 78)
    print("CaseMind Phase 6 — Memory Ablation Test")
    print(f"Run at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 78)
    print(f"\nCase narrative:\n  {ABLATION_CASE_NARRATIVE}\n")

    print("--- Run 1: BLIND (no memory retrieval) ---")
    blind = run_blind(reasoner)
    print(json.dumps(blind, indent=2))

    print("\n--- Run 2: INFORMED (live vector search + entity history) ---")
    informed = run_informed(reasoner, vectors, memory)
    print(json.dumps(informed, indent=2))

    print("\n" + "=" * 78)
    print("COMPARISON")
    print("=" * 78)
    print(f"Blind decision:    {blind['decision']} (confidence {blind['confidence']})")
    print(f"Informed decision: {informed['decision']} (confidence {informed['confidence']})")
    same_decision = blind["decision"] == informed["decision"]
    print(f"Same decision: {same_decision}")
    print(
        f"Confidence delta: {informed['confidence'] - blind['confidence']:+.2f} "
        "(informed - blind)"
    )
    print(
        f"Retrieved {len(informed.get('retrieved_case_ids', []))} similar cases "
        f"and grounded the informed reasoning in entity {ABLATION_ENTITY_ID}'s prior history."
    )
    print(
        "\nQualitative note: the informed run's reasoning text should cite specific "
        "retrieved case IDs and/or the entity's prior decision — the blind run's "
        "reasoning cannot, since it only has the raw narrative to work with."
    )

    with open("tests/ablation_result.json", "w") as f:
        json.dump({"blind": blind, "informed": informed}, f, indent=2)
    print("\nFull results written to tests/ablation_result.json")


if __name__ == "__main__":
    main()
