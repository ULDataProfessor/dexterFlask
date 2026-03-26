# Python / Flask API

Base URL: `http://127.0.0.1:5050`

## GET /health

Liveness endpoint.

Response JSON:

```json
{ "status": "ok" }
```

## POST /api/agent/run

Runs the agent and returns the final answer once complete.

### Request body (JSON) (stream)

Common fields (some are optional; server uses defaults when missing):

- `sessionKey` (string, default: `"default"`): key for in-process chat history
- `query` (string): user question
- `model` (string, default: `"gpt-5.4"`)
- `modelProvider` (string, optional): e.g. `"openai"`, `"anthropic"`, `"google"`
- `maxIterations` (number, default: `10`)
- `isolatedSession` (boolean, optional):
  - when `true`, disables chat history + memory for this run
- `channel` (string, optional): affects response formatting via prompts
- `groupContext` (object, optional):
  - `groupName` (string)
  - `membersList` (string)
  - `activationMode` (only `"mention"` is currently modeled)
- `isHeartbeat` (boolean, optional):
  - when `true`, the route may prune the last turn after the final answer (used to avoid polluting session history)

### Response JSON

```json
{ "answer": "..." }
```

## POST /api/agent/stream

Runs the agent and streams events via Server-Sent Events (SSE).

### Request body (JSON)

Same JSON shape as `/api/agent/run`.

### Response (stream)

- `Content-Type: text/event-stream`
- Event messages are streamed as:

  - `data: { ...event JSON... }\n\n`

Typical `event` objects include:

- `type: "thinking"` (field: `message`)
- `type: "tool_progress"` (fields: `tool`, `message`)
- `type: "tool_start"` / `type: "tool_end"` / `type: "tool_error"`
- `type: "tool_limit"`
- `type: "context_cleared"`
- `type: "memory_flush"`
- `type: "done"` (final result)

The `done` event includes (when present):

- `answer` (string)
- `toolCalls` (array of `{ tool, args, result }`)
- `iterations`, `totalTime`
- `tokenUsage` (optional)
- `tokensPerSecond` (optional)

### History behavior

- `isolatedSession=false`: the route saves the user query and persists the final answer once the generator emits `done`.
- `isolatedSession=true`: the route does not save any chat history.

### Note on `isHeartbeat`

Unlike `/api/agent/run`, the current `/api/agent/stream` implementation does not yet apply heartbeat pruning logic.

### Validation errors

If the request JSON does not match the expected shape, the route returns:

```json
{
  "error": "invalid_request",
  "details": [ ... ]
}
```
