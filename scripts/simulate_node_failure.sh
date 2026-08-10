#!/usr/bin/env bash
# Phase 5 resilience rehearsal.
#
# DISCLOSURE: CaseMind's CockroachDB cluster runs on the Standard plan,
# which is fully managed and multi-tenant. CockroachDB Cloud does not
# expose per-node control on this plan (no Nodes page, no "kill node N"
# action available to the customer) -- that's a Dedicated/Self-Hosted
# capability. So this script does not (and cannot) simulate a literal
# node/region failure against this cluster.
#
# What it does instead: runs the real application-layer resilience check
# implemented in agent/resilience_monitor.py -- proving CaseMind's own
# database client recovers cleanly after a forcibly-severed connection,
# and that the live cluster stays responsive under a continuous health
# check. See agent/resilience_monitor.py's module docstring for the full
# writeup, and tests/test_resilience.py for the assertions.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "simulate_node_failure.sh: .env not found. Copy .env.example and fill it in." >&2
  exit 1
fi

set -a
source .env
set +a

python3 -m tests.test_resilience
