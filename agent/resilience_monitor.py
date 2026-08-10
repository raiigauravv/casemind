"""
ccloud CLI-based cluster health monitor — the demo's hero moment.

Loop: check cluster health / backup status on an interval via the ccloud
CLI, surface node/region failure events cleanly. Per roadmap rule 7, this
must be rehearsed and proven reliable before it is ever presented as
demo-ready — not improvised live on camera.

Status: interface only. Requires a live CockroachDB cluster (Phase 0/2)
and ccloud CLI auth before this can run for real.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger("casemind.resilience_monitor")
logging.basicConfig(level=logging.INFO)


class CcloudCliNotAvailable(RuntimeError):
    pass


@dataclass
class ClusterHealth:
    healthy: bool
    node_count: int
    regions_up: list[str]
    last_backup_ok: bool
    raw: str


class ResilienceMonitor:
    def __init__(self, cluster_id: str | None = None) -> None:
        self.cluster_id = cluster_id

    def _require_cli(self) -> None:
        if shutil.which("ccloud") is None:
            raise CcloudCliNotAvailable(
                "ccloud CLI not found on PATH. Install + authenticate before "
                "Phase 5 (see CockroachDB Cloud docs)."
            )

    def check_health(self) -> ClusterHealth:
        """Runs `ccloud cluster health` (or equivalent) and parses the result.

        Every check is logged for the demo's health-check-surfaces-the-event
        narrative, whether the cluster is healthy or degraded.
        """
        self._require_cli()
        logger.info(
            "[RESILIENCE_AUDIT] ts=%s op=HEALTH_CHECK cluster_id=%s",
            datetime.now(timezone.utc).isoformat(),
            self.cluster_id,
        )
        raise NotImplementedError(
            "ccloud CLI invocation + parsing — implement in Phase 5 against live cluster"
        )

    def watch(self, interval_seconds: int = 30) -> None:
        """Blocking loop; intended to run alongside the agent process during
        the demo so a failover event is caught and logged in near-real-time.
        """
        raise NotImplementedError("Phase 5 — implement after single-check path is proven reliable")
