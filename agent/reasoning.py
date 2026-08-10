"""
Amazon Bedrock case reasoning call.

Takes a case narrative plus retrieved memory (similar historical cases,
entity/decision history) and returns a decision, confidence, and reasoning
text. If ANY part of this call is mocked or simplified for cost reasons in
the final demo, that must be disclosed in the README per roadmap Phase 8
("No overstating what Bedrock/Lambda do... disclose it").

Status: interface only. Not yet implemented — needs AWS credentials
(Phase 0) and Bedrock model access confirmed before Phase 3 build.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("casemind.reasoning")
logging.basicConfig(level=logging.INFO)


class ReasoningNotConfigured(RuntimeError):
    pass


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


class BedrockReasoner:
    def __init__(self) -> None:
        self.region = os.environ.get("AWS_REGION")
        self.model_id = os.environ.get("BEDROCK_MODEL_ID")

    def _require_config(self) -> None:
        if not self.region or not self.model_id:
            raise ReasoningNotConfigured(
                "AWS_REGION and BEDROCK_MODEL_ID must be set (see .env.example)."
            )

    def reason(self, inp: ReasoningInput) -> ReasoningOutput:
        self._require_config()
        logger.info(
            "[REASONING_AUDIT] ts=%s model=%s similar_case_count=%s",
            datetime.now(timezone.utc).isoformat(),
            self.model_id,
            len(inp.similar_cases),
        )
        raise NotImplementedError("Bedrock invoke_model call — implement in Phase 3")
