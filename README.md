# CaseMind

An AML/fraud-investigation copilot for a bank analyst, built for the
[CockroachDB × AWS Hackathon — Build with Agentic Memory](https://cockroachdb-ai.devpost.com/).

> **All case, entity, and decision data used by this project is synthetic.**
> No real financial data, no real bank names, no compliance certification
> claims are made anywhere in this repo, the demo, or the video.

## Status

🚧 Under active development. This README is a skeleton — full setup/run
instructions land in Phase 8 once the agent loop, memory layer, and
resilience test are built and rehearsed.

## What it does

When a new flagged transaction/case comes in, CaseMind:

1. Retrieves similar historical cases via semantic search over case
   narratives (CockroachDB Distributed Vector Indexing).
2. Reads related entity/decision history from structured memory
   (CockroachDB MCP Server).
3. Reasons about the case using Amazon Bedrock, informed by that retrieved
   memory.
4. Writes its decision, confidence, and notes back into memory (MCP
   Server), with a full audit trail of which prior cases informed the call.
5. Continuously monitors the health of its own memory layer via the
   ccloud CLI, and survives a live node/region failure without losing
   memory or stopping.

## Architecture

See [`docs/architecture.svg`](docs/architecture.svg).

## Tools used

**CockroachDB:** Managed MCP Server (primary agent memory interface),
Distributed Vector Indexing (semantic case-narrative search), ccloud CLI
(cluster health / backup / failover monitoring).

**AWS:** Amazon Bedrock (case reasoning), AWS Lambda (event-driven agent
execution loop).

Full write-up of how each tool is used lands in Phase 8.

## Repo structure

```
casemind/
├── LICENSE
├── README.md
├── docs/
│   └── architecture.svg
├── infra/          # Terraform for Lambda, IAM, S3
├── agent/          # memory client, vector search, reasoning, resilience monitor, Lambda handler
├── db/             # schema + synthetic seed data
├── frontend/       # React demo app
├── tests/          # memory ablation + resilience tests
└── scripts/        # node/region failure simulation
```

## Setup & run instructions

_To be filled in during Phase 2–7 as each component comes online._

## Synthetic data disclosure

Every case, entity, and decision record in this repo and demo is
synthetically generated for demonstration purposes. See
`db/seed_synthetic_data.sql` and inline comments throughout `agent/` for
explicit labeling. No real compliance certification is claimed — this
project is "informed by" AML/fraud triage workflows, not a certified
compliance product.

## License

TBD — MIT or Apache 2.0 (see open questions below). See `LICENSE`.

## Open questions

- Which CockroachDB Cloud tier/plan supports the multi-node failure
  simulation needed for Phase 5 (free tier vs. paid cluster).
- Whether AEGIS's existing AWS IAM role/Terraform can be reused directly.
- Final choice of demo frontend hosting (Vercel vs. S3+CloudFront).
- License choice: MIT vs. Apache 2.0.
