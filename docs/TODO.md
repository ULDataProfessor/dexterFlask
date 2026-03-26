# Repo TODOs (Python/Flask-first)

This file tracks remaining follow-ups for the Python-only Dexter rebuild.

Each item includes an explicit acceptance check so it’s clear when a gap is fixed.

## Milestone 0 — Baseline: request validation

Status: already done.

Acceptance:

- `/api/agent/run` and `/api/agent/stream` validate request bodies with Pydantic and return `{ "error": "invalid_request", ... }` on failure.

## Milestone 1 — Streaming polish

1. Emit `tool_progress` events with consistent `tool` field

   - Gap: `tool_progress` is emitted, but the `tool` field may be empty if the progress message does not match the `Running <tool>...` pattern.

   Acceptance:

   - All `tool_progress` events include a non-empty `tool` field when the message originates from tool execution.

## Milestone 2 — SSE “done” parity for heartbeat pruning (`isHeartbeat`)

1. Add heartbeat pruning parity to `/api/agent/stream`

   - Gap: `/api/agent/run` prunes the last turn when `isHeartbeat=true` and final answer contains the heartbeat token. `/api/agent/stream` currently saves the final answer but doesn’t apply the pruning logic.
   - Next step:
     - Implement the same pruning logic server-side in `dexter_flask/routes/agent_api.py` after the generator observes the final `done` event.

   Acceptance:

- For the same input and `isHeartbeat=true`, both `/api/agent/run` and `/api/agent/stream` produce identical history state (no last turn retained when the heartbeat token is present).

## Milestone 3 — Memory event schema parity (`memory_recalled`)

1. Emit `memory_recalled` from Flask

   - Gap: TypeScript’s `AgentEvent` union includes `memory_recalled`, but Python currently only emits `memory_flush`.
   - Next step:
     - Add a new event type to `dexter_flask/agent/types.py` for `memory_recalled`.
     - Emit `memory_recalled` when the server loads session memory context (hook in `dexter_flask/agent/loop.py` around the memory context load).
     - Ensure the event payload matches TS expectations (`filesLoaded`, `tokenCount`).

   Acceptance:

- Streaming SSE includes a `type: "memory_recalled"` event (before any tool events) whenever memory integration is enabled.
- Event payload includes `filesLoaded: string[]` and `tokenCount: number`.

## Milestone 4 — Approval + control parity over HTTP

1. Expose tool approval flow over HTTP/SSE

   - Gap: TypeScript supports tool approval interactively, and Python can emit `tool_approval` / `tool_denied`, but the HTTP routes currently don’t expose a pause -> operator decision -> resume mechanism.
   - Next step (protocol design, then implementation):
     - Introduce a run-id.
     - Stream `tool_approval` / `tool_denied` events.
     - Add an HTTP follow-up endpoint for operator decisions (allow-once, allow-session, deny).
     - Implement the pause/resume logic in Python so tool execution blocks until a decision arrives.
     - Wire the TS gateway/runner to send approval decisions back to Python.

   Acceptance:

- When a tool requires approval, the run pauses and waits for an operator decision.
- Operator decision is reflected in subsequent tool execution (or immediate turn termination for `deny`).

1. Add cancellation parity (AbortSignal -> disconnect/cancel)

   - Gap: TypeScript supports cancelling runs via `AbortSignal`, but Python HTTP endpoints have no cancellation mechanism.
   - Next step:
     - Implement cancellation when the SSE client disconnects OR via a run-id cancellation endpoint.
     - Ensure Python stops long-running loops and does not continue emitting events after cancellation.

   Acceptance:

- If the client disconnects or requests cancellation mid-run, Flask stops execution promptly.
- No further SSE events are emitted after cancellation.

## Milestone 5 — Validation + tests (regressions)

1. Add/extend tests to cover the parity items above

   - Next step:
     - Flask: extend `tests/test_routes_agent_api.py` to cover
       - heartbeat pruning parity on `/api/agent/stream`
       - presence/shape of `memory_recalled` event
       - (later) approval and cancellation flow regression coverage once endpoints exist

   Acceptance:

- Tests fail on regressions and pass after the parity items are implemented.
