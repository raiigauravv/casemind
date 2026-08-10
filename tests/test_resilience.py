"""
Resilience test — Phase 5 deliverable.

See agent/resilience_monitor.py for the full disclosure on scope: the
CockroachDB Standard plan is fully managed / multi-tenant with no
customer-facing node control, so this verifies application-layer
connection resilience (the agent's next memory operation succeeds even
after a connection is forcibly severed mid-session) rather than a literal
node/region kill.

Run: python -m tests.test_resilience  (from repo root, with .env loaded)
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.resilience_monitor import HealthMonitor, run_connection_drop_test


def main() -> None:
    print("=" * 78)
    print("CaseMind Phase 5 — Resilience Test")
    print("=" * 78)

    print("\n--- Step 1: connection drop + recovery ---")
    drop_result = run_connection_drop_test()
    print(json.dumps(drop_result, indent=2))
    assert drop_result["drop_simulated"], "failed to simulate a connection drop"
    assert drop_result["recovery_succeeded"], (
        "next memory operation did NOT succeed after connection drop: "
        f"{drop_result.get('error')}"
    )
    print("PASS: next memory operation succeeded after a forced connection drop.")

    print("\n--- Step 2: 30s continuous health check against the live cluster ---")
    monitor = HealthMonitor()
    monitor.run(duration_seconds=30, interval_seconds=3.0)
    summary = monitor.summary()
    print(json.dumps(summary, indent=2))
    assert summary["success_rate"] == 1.0, f"health check success rate was {summary['success_rate']}, expected 1.0"
    print("PASS: 100% of health checks against the live cluster succeeded.")

    with open("tests/resilience_result.json", "w") as f:
        json.dump({"connection_drop_test": drop_result, "health_check_summary": summary}, f, indent=2)
    print("\nFull results written to tests/resilience_result.json")


if __name__ == "__main__":
    main()
