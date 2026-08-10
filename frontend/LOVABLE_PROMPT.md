# CaseMind — Lovable Frontend Prompt

Paste the section below into Lovable to scaffold the Phase 7 demo dashboard.
The API endpoint is live and already deployed on real AWS infrastructure —
no mocking needed.

---

## Prompt for Lovable

Build a single-page React + Tailwind dashboard called **CaseMind** — an
AML/fraud-investigation copilot demo. The UI should feel like a serious
compliance analyst tool: dark, dense, monospace accents for IDs/data,
clean sans-serif for prose. Not playful.

### Layout

1. **Header**: "CaseMind" wordmark + a one-line subtitle: "AI-assisted case
   review with full evidence citation — CockroachDB + AWS Bedrock."

2. **Left panel — Submit a case**
   - A textarea for the case narrative (placeholder: "Describe the
     suspicious activity...").
   - An entity ID input (placeholder/default:
     `22222222-2222-2222-2222-222222222222` — this is a real seeded demo
     entity with prior decision history, useful for showing memory in
     action).
   - A "Run Investigation" button.
   - A few one-click example narratives as chips/buttons that pre-fill the
     textarea, e.g.:
     - "Customer received 9 incoming wires from 9 different individuals
       over 3 days, each just under the $10,000 reporting threshold, then
       immediately wired the combined total to an offshore account."
     - "Long-standing customer made a single $500 deposit consistent with
       their normal payroll pattern."

3. **Right panel — Live activity log**
   This is the most important part of the demo: show each step of the
   agent loop as it happens, not just the final answer. As the request is
   in flight, render a sequence of log lines (can be simulated with staged
   delays client-side, since the real API is synchronous and returns
   everything at once — see "Implementation notes" below):
   - `> writing case to CockroachDB...`
   - `> vector search: retrieving similar historical cases...`
   - `> reading entity decision history...`
   - `> reasoning via AWS Bedrock (Claude Haiku)...`
   - `> writing decision + audit trail back to memory...`
   - `> done`

4. **Result card** (appears after the call completes)
   - Decision badge: `ESCALATE` (red), `MONITOR` (yellow), or `CLEAR`
     (green).
   - Confidence as a percentage.
   - Full reasoning text.
   - "Retrieved case IDs" — a list of the historical case UUIDs the model
     cited, styled as chips. This is the audit trail: the whole point of
     the demo is that every decision is grounded in retrievable evidence,
     not a black box.
   - `case_id` and `decision_id` shown small, monospace, at the bottom
     (proof this is a real database write, not a mock).

5. Keep state for a running list of past submissions in this session
   (simple array in React state, most recent first, collapsed by default,
   click to expand) so a demo can show multiple cases without losing
   history.

### API integration (real, live, already deployed)

```
POST https://cd6wy8mx54.execute-api.us-east-1.amazonaws.com/cases
Content-Type: application/json

{
  "case_id": "<optional — server generates a UUID if omitted>",
  "entity_id": "<uuid, required>",
  "narrative": "<string, required>"
}
```

Response (200):

```json
{
  "case_id": "c0bfebc6-e2ef-4e23-ab11-f9debdef8105",
  "decision_id": "dbc42b0f-b7ef-4f31-a5c8-dc78dc0c85f8",
  "decision": "escalate",
  "confidence": 0.92,
  "reasoning": "This case exhibits classic structuring indicators...",
  "retrieved_case_ids": [
    "a1111111-0000-0000-0000-000000000001",
    "a1111111-0000-0000-0000-000000000004"
  ]
}
```

Error response (500, still valid JSON, CORS-enabled):

```json
{ "error": "<message>" }
```

CORS is already configured on the API (`Access-Control-Allow-Origin: *`),
so this can be called directly from the browser with `fetch` — no proxy
or backend-for-frontend needed.

### Implementation notes

- The real call is a single synchronous HTTPS POST — typically takes
  5-15 seconds end to end (vector search + an LLM reasoning call). To make
  the "activity log" panel feel alive rather than showing one long
  spinner, stage the log lines client-side with short `setTimeout`
  increments while the real `fetch` is in flight in parallel, then reveal
  the result card once the response actually returns. Don't fabricate the
  final decision/reasoning/confidence — those must come from the real
  response body.
- Handle the error case gracefully: show a red banner with the error
  message rather than crashing the UI.
- No auth is required for this demo endpoint.
- Use `22222222-2222-2222-2222-222222222222` as the default entity ID —
  it has real seeded prior-decision history in the database, so demo runs
  against it will visibly cite that history in the reasoning text.

---

## Why this matters for the demo

The point of CaseMind is that every decision is auditable: it doesn't just
say "escalate," it names the specific prior cases and entity history that
informed the call, and those citations are checkable against real rows in
CockroachDB. The frontend's job is to make that traceability visible, not
just show a chatbot-style answer.
