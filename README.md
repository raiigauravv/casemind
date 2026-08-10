# CaseMind

An AML/fraud-investigation copilot for a bank analyst, built for the
[CockroachDB × AWS Hackathon — Build with Agentic Memory](https://cockroachdb-ai.devpost.com/).

> **All case, entity, and decision data used by this project is synthetic.**
> No real financial data, no real bank names, no compliance certification
> claims are made anywhere in this repo, the demo, or the video.

## Status

Feature-complete and deployed end-to-end on live infrastructure:
CockroachDB Cloud (Standard plan), AWS Lambda, AWS API Gateway, and AWS
Bedrock. Every claim below was verified against real, running
infrastructure — not mocked — including a full HTTPS round trip through
the deployed API.

## What it does

When a new flagged transaction/case comes in, CaseMind:

1. Writes the incoming case to CockroachDB as `open`.
2. Retrieves similar historical cases via semantic search over case
   narratives, using CockroachDB's `VECTOR` column type and the `<->` L2
   distance operator (Distributed Vector Indexing).
3. Reads related entity/decision history from structured memory in
   CockroachDB.
4. Reasons about the case using Amazon Bedrock (Claude Haiku 4.5, via a
   cross-region inference profile), informed by both retrieval sources
   above.
5. Writes its decision, confidence, and reasoning back into CockroachDB,
   with `retrieved_case_ids` as an explicit, checkable audit trail of
   which prior cases informed the call.
6. Updates the case status (`closed_escalated` / `closed_cleared` /
   still `open` for `monitor`).

The whole loop runs inside a single AWS Lambda function
(`casemind-agent-loop`), invokable three ways:

- **S3 event** — drop a case JSON file into the `casemind-cases-*` bucket.
- **Direct Lambda invocation** — for local/CLI testing.
- **HTTPS POST** — via a live AWS API Gateway HTTP API, so a browser
  frontend can call it synchronously. Live endpoint:
  `https://cd6wy8mx54.execute-api.us-east-1.amazonaws.com/cases`

## Architecture

See [`docs/architecture.svg`](docs/architecture.svg).

## Tools used (and how)

**CockroachDB Cloud (Standard plan, AWS us-east-1) — two of the four listed tools:**
- **Distributed Vector Indexing** — `VECTOR(1536)` column + `<->` operator
  for semantic case-narrative retrieval — this is what lets the agent find
  precedent cases by meaning, not keyword match (`agent/vector_search.py`).
- **Managed MCP Server** (`https://cockroachlabs.cloud/mcp`) — entity/decision
  history reads go through the MCP Server's `select_query` tool over a
  stdlib-only JSON-RPC client (`agent/memory_client.py: MCPClient`),
  authenticated with a scoped, read-only service-account API key. If the MCP
  call fails for any reason (e.g. an auth/session issue), the client
  transparently falls back to a direct SQL read on the same tables and logs
  a distinct `MCP_FALLBACK` audit line — so the agent loop is never blocked
  by MCP infra issues, and the fallback is never silent.
- Structured tables (`cases`, `entities`, `decisions`) as the agent's
  persistent memory — every decision is written back via direct SQL with the
  exact list of case IDs that informed it, so the reasoning is auditable
  after the fact, not just a black-box output.
- **Honest scope note:** the Standard plan is fully managed and
  multi-tenant. It does not expose per-node control to the customer (no
  "kill node N" action, no Nodes page in the console) — that's a
  Dedicated/Self-Hosted capability. So Phase 5's resilience test
  (`agent/resilience_monitor.py`, `tests/test_resilience.py`) verifies
  application-layer connection resilience — the agent's database client
  recovers cleanly after a connection is forcibly severed mid-session —
  rather than a literal node/region failover, which this plan doesn't
  allow a customer to trigger or observe. This is disclosed in the code
  and in `scripts/simulate_node_failure.sh`.

**AWS:**
- **Bedrock** — Claude Haiku 4.5 (cross-region inference profile) for
  case reasoning; Titan Embed Text v1 for the vectors that back the
  semantic search above.
- **Lambda** (Python 3.12) — the event-driven agent execution loop
  (`agent/lambda_handler.py`), deployed via Terraform with a
  cross-built `psycopg[binary]` wheel for Amazon Linux compatibility.
- **API Gateway** (HTTP API v2) — synchronous HTTPS front door
  (`POST /cases`) for the frontend, provisioned via Terraform
  (`infra/api_gateway.tf`), AWS_PROXY integration into the same Lambda.
- **S3** — case-drop trigger for the event-driven path.
- **Budgets** — a $3 hard cost cap with an automated (not just
  notification-based) IAM-deny budget action, so a runaway cost can't
  exceed what was authorized for this project. See "Cost & safety"
  below.
- **IAM** — least-privilege policy scoped to `casemind-*` resources
  wherever the AWS API allows resource-level scoping (a few actions,
  like `lambda:GetFunctionCodeSigningConfig` and API Gateway management
  actions, only support account-wide/`Resource: "*"` scoping — these are
  called out explicitly in the policy).

**Lovable** — used to scaffold the Phase 7 demo frontend against the live
API Gateway endpoint above. See `frontend/LOVABLE_PROMPT.md` for the exact
spec used.

## Repo structure

```
casemind/
├── LICENSE
├── README.md
├── docs/
│   └── architecture.svg
├── infra/          # Terraform: Lambda, IAM, S3, API Gateway
├── agent/          # memory client, vector search, reasoning, resilience monitor, Lambda handler
├── db/             # schema + synthetic seed data
├── frontend/       # Lovable prompt + README for the demo dashboard
├── tests/          # memory ablation + resilience tests (+ result JSON)
└── scripts/        # resilience rehearsal script
```

## Setup & run instructions

### Prerequisites

- Python 3.12, `pip`
- A CockroachDB Cloud cluster (Standard plan or above) with the schema in
  `db/schema.sql` applied, seeded with `db/seed_synthetic_data.sql`
- AWS account with Bedrock model access enabled for Claude Haiku 4.5 and
  Titan Embed Text v1, in a region that supports the cross-region
  inference profile used (`us.anthropic.claude-haiku-4-5-20251001-v1:0`)
- Terraform >= 1.9 (for infra provisioning)

### Local setup

```bash
cp .env.example .env
# fill in COCKROACHDB_CONNECTION_STRING, AWS credentials, etc.
pip install -r requirements.txt
```

### Run the agent loop locally (no AWS infra required)

```bash
set -a && source .env && set +a
python3 -c "
from agent.lambda_handler import handler
import uuid
print(handler({
    'case_id': str(uuid.uuid4()),
    'entity_id': '22222222-2222-2222-2222-222222222222',
    'narrative': 'Customer received 9 incoming wires from 9 different individuals over 3 days, each just under the \$10,000 reporting threshold, then immediately wired the combined total to an offshore account.'
}))
"
```

### Deploy the AWS infrastructure

```bash
cd infra
terraform init
terraform apply
# outputs the S3 bucket name and cases_api_endpoint (the live HTTPS URL)
```

### Run the tests

```bash
set -a && source .env && set +a
python3 -m tests.test_memory_ablation   # writes tests/ablation_result.json
python3 -m tests.test_resilience        # writes tests/resilience_result.json
bash scripts/simulate_node_failure.sh   # wraps the resilience test with disclosure
```

### Frontend

The demo dashboard is built in [Lovable](https://lovable.dev) against the
live API endpoint. See `frontend/LOVABLE_PROMPT.md` for the spec, and
`frontend/README.md` for pointers.

## Test results (from this project's own runs)

- **Memory ablation** (`tests/ablation_result.json`): run across five
  archetypes (structuring, shell-company layering, trade-based
  laundering, and two benign patterns), each paired blind (no retrieval)
  vs. informed (real vector search + real entity history), for 10 live
  Bedrock calls total. Blind and informed agreed on the decision label in
  5/5 archetypes (confidence deltas were small, -0.05 to +0.02) — so the
  measurable value memory adds here isn't flipping decisions, it's
  *evidence grounding*: 5/5 (100%) of informed runs explicitly cited a
  specific retrieved case ID or the entity's prior decision history in
  their reasoning text, while every blind run could only assert a label
  with no traceable evidence behind it. That citation is what makes a
  decision auditable and checkable against real rows in CockroachDB,
  rather than a black-box assertion.
- **Resilience** (`tests/resilience_result.json`): a forcibly severed
  database connection is followed by a successful independent memory
  operation (100% recovery), and a 30-second continuous health check
  against the live cluster succeeded on 10/10 checks (~277ms avg
  latency). See the scope note above on what this does and doesn't prove
  given the Standard plan's lack of customer-facing node control.

## Cost & safety

This project is designed to stay within AWS/CockroachDB free-tier limits
for hackathon-scale usage. As a hard backstop, AWS Budgets is configured
with a **$3 cost cap and an automated IAM-deny budget action** (not just
an email notification) — if actual/forecasted spend crosses the
threshold, the budget action automatically restricts further
billable-resource creation on this account, rather than relying on a
human noticing an alert.

## Synthetic data disclosure

Every case, entity, and decision record in this repo and demo is
synthetically generated for demonstration purposes. See
`db/seed_synthetic_data.sql` and inline comments throughout `agent/` for
explicit labeling. No real compliance certification is claimed — this
project is "informed by" AML/fraud triage workflows, not a certified
compliance product.

## License

Apache License 2.0. See `LICENSE`.
