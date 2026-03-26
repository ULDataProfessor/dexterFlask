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

   Status: mostly done.
   - Implemented: run-id cancellation endpoint, cooperative cancellation in the agent loop, and disconnect-driven cancellation handling in the SSE stream route.
   - Remaining: hard cancellation for long-running blocking LLM/tool invocations (if needed).

   Acceptance:

- If the client disconnects or requests cancellation mid-run, Flask stops execution promptly.
- No further SSE events are emitted after cancellation.

## Milestone 5 — Validation + tests (regressions)

1. Add/extend tests to cover the parity items above

   Status: in progress.
   - Flask route tests now cover custom `tool_progress` tool attribution and approval/cancel endpoint validation.
   - Remaining: add end-to-end stream approval wait/resume and cancel-while-waiting regression coverage.

   Acceptance:

- Tests fail on regressions and pass after the parity items are implemented.

## Milestone 6 — Session durability + concurrency hardening

1. Use persistent storage for chat sessions

   Status: done.
   - Implemented: SQLite-backed chat session storage in `dexter_flask/services/sessions.py`.
   - Config: defaults to `.dexter/sessions.db` and can be overridden with `DEXTER_SESSIONS_DB_PATH`.

   Acceptance:

- Session history persists across in-process cache reloads and survives process restarts.

2. Harden session store concurrency behavior

   Status: in progress.
   - Implemented: lock-protected session history object creation to avoid same-session races in `_sessions`.
   - Remaining: add stronger SQLite contention handling (`busy_timeout`/WAL) if needed under multi-process write load.

   Acceptance:

- Concurrent requests do not create conflicting session history objects for the same session key.
