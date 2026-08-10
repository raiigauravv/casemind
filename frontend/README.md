# CaseMind frontend

Phase 7 deliverable. React demo dashboard: submit a case, watch
retrieval -> reasoning -> decision happen live, with memory reads/writes
visibly logged in the UI.

Built with [Lovable](https://lovable.dev) rather than scaffolded by hand
in this repo — see `LOVABLE_PROMPT.md` for the exact spec (layout, API
contract, example narratives) that was used to generate it. The API it
talks to is real and already deployed:

```
POST https://cd6wy8mx54.execute-api.us-east-1.amazonaws.com/cases
```

This is a live AWS API Gateway HTTP API in front of the same Lambda agent
loop used for the S3-event path (see `infra/api_gateway.tf` and
`agent/lambda_handler.py`). Verified end-to-end with a real HTTPS POST
(see commit history) before this prompt was written.
