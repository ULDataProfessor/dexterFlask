# Repo TODOs (Python/Flask-first)

This list focuses on parity gaps between the Python/Flask API and the existing TypeScript gateway/UX, plus concrete next steps.

## Streaming + event parity

1. Add/forward `tool_progress` into `/api/agent/stream`
- Gap: Python tools can emit progress via `emit_tool_progress(...)`, but the SSE streaming path does not currently wire a callback to surface these as `type: "tool_progress"` events.
- Next step: connect `dexter_flask.tools.context.set_tool_progress(...)` in the streaming request path so progress messages become SSE events.

2. Fix event schema parity: `memory_recalled`
- Gap: TypeScript’s `AgentEvent` union includes `memory_recalled`, but Python currently only emits `memory_flush`.
- Next step: emit `memory_recalled` when the server loads session memory context (or align TS to the Python-emitted set, if that’s the intended direction).

3. SSE “done” parity for heartbeat pruning (`isHeartbeat`)
- Gap: `/api/agent/run` prunes the last turn when `isHeartbeat=true` and the final answer contains the heartbeat token. `/api/agent/stream` currently saves the final answer but does not apply the pruning logic.
- Next step: apply the same pruning behavior in `/api/agent/stream` after the final `done` event.

## Gateway parity (TypeScript -> Flask)

4. Prefer `/api/agent/stream` when Flask is enabled
- Gap: when `FLASK_AGENT_URL` / `DEXTER_FLASK_URL` is set, the TypeScript gateway delegates to `/api/agent/run` (non-streaming). That loses real-time UI parity even though a stream endpoint exists.
- Next step: update `src/gateway/flask-agent.ts` (and any stream wiring in the gateway runner) to call `/api/agent/stream` and forward SSE events to the existing event UI.

## Approval + control parity

5. Expose tool approval flow over HTTP
- Gap: Python supports tool approval via `request_tool_approval` and can emit `tool_approval` / `tool_denied`, but the HTTP routes don’t provide an approval interaction mechanism (pause -> operator decision -> resume).
- Next step: define an HTTP/SSE interaction pattern (or a follow-up approval endpoint) so the gateway can supply approval decisions and Python can resume execution.

6. Add cancellation parity (AbortSignal -> disconnect/cancel)
- Gap: TypeScript supports cancelling runs via `AbortSignal`, but Python HTTP endpoints currently have no cancellation mechanism.
- Next step: implement cancellation on client disconnect during SSE, and/or add a run-id + cancellation endpoint so the server can stop long-running loops.

## Validation + tests

7. Add request validation and consistent error responses
- Gap: Flask currently parses JSON with `force=True` and accepts arbitrary fields; payload errors aren’t standardized.
- Next step: add Pydantic request models for `/api/agent/run` and `/api/agent/stream` and return consistent 4xx errors.

8. Extend tests to cover parity gaps
- Next step: add tests asserting:
  - heartbeat pruning is consistent across run vs stream
  - SSE includes progress and event types that TS expects
  - event objects match TS naming/shape where appropriate

