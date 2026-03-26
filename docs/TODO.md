# Repo TODOs (Python/Flask-first)

This file tracks remaining follow-ups for the Python-only Dexter rebuild.

Each item includes an explicit acceptance check so it’s clear when a gap is fixed.

## Milestone 0 — Baseline: request validation

Status: already done.

Acceptance:

- `/api/agent/run` and `/api/agent/stream` validate request bodies with Pydantic and return `{ "error": "invalid_request", ... }` on failure.

## Milestone 1 — Streaming polish

1. Emit `tool_progress` events with consistent `tool` field

   Status: done.

   Acceptance:

   - All `tool_progress` events include a non-empty `tool` field when the message originates from tool execution.

## Milestone 2 — SSE “done” parity for heartbeat pruning (`isHeartbeat`)

1. Add heartbeat pruning parity to `/api/agent/stream`

   Status: done.

   Acceptance:

- For the same input and `isHeartbeat=true`, both `/api/agent/run` and `/api/agent/stream` produce identical history state (no last turn retained when the heartbeat token is present).

## Milestone 3 — Memory event schema parity (`memory_recalled`)

1. Emit `memory_recalled` from Flask

   Status: done.

   Acceptance:

- Streaming SSE includes a `type: "memory_recalled"` event (before any tool events) whenever memory integration is enabled.
- Event payload includes `filesLoaded: string[]` and `tokenCount: number`.

## Milestone 4 — Approval + control parity over HTTP

1. Expose tool approval flow over HTTP/SSE

   Status: done.

   Acceptance:

- When a tool requires approval, the run pauses and waits for an operator decision.
- Operator decision is reflected in subsequent tool execution (or immediate turn termination for `deny`).

1. Add cancellation parity (AbortSignal -> disconnect/cancel)

   Status: partially done.
   - Implemented: run-id cancellation endpoint + cooperative cancellation in the agent loop.
   - Remaining: disconnect-driven cancellation (SSE client disconnect) and hard cancellation for long-running tool invocations (if needed).

   Acceptance:

- If the client disconnects or requests cancellation mid-run, Flask stops execution promptly.
- No further SSE events are emitted after cancellation.

## Milestone 5 — Validation + tests (regressions)

1. Add/extend tests to cover the parity items above

   Status: in progress.
   - Flask: extend `tests/test_routes_agent_api.py` to cover custom tool progress messages including a non-empty `tool`.

   Acceptance:

- Tests fail on regressions and pass after the parity items are implemented.
