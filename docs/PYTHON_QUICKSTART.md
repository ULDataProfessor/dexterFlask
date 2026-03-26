# Python / Flask Quickstart

Dexter’s research agent is implemented in Python (`dexter_flask/`) behind a small Flask HTTP API.

## Prerequisites

- Python >= 3.10
- API keys (at minimum):
  - `OPENAI_API_KEY`
  - `FINANCIAL_DATASETS_API_KEY`
- Optional web search keys:
  - `EXASEARCH_API_KEY` (preferred), or `PERPLEXITY_API_KEY` / `TAVILY_API_KEY`

## Setup

```bash
uv venv .venv
source .venv/bin/activate
uv sync --dev
cp env.example .env
# edit .env and add your keys
```

## Run the server

```bash
export PORT=5050
# recommended for local dev/tests so the background scheduler doesn't start
export DEXTER_DISABLE_CRON=1

python -m dexter_flask.app
```

Default base URL: `http://127.0.0.1:5050`

### Health check

```bash
curl -s http://127.0.0.1:5050/health
# {"status":"ok"}
```

## Run the agent (non-streaming)

```bash
curl -s -X POST http://127.0.0.1:5050/api/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "sessionKey":"s1",
    "query":"What is the outlook for Apple (AAPL) over the next 12 months?",
    "model":"gpt-5.4",
    "modelProvider":"openai",
    "maxIterations":3,
    "isolatedSession":false
  }'
```

Response:

```json
{ "answer": "..." }
```

## Run the agent (SSE stream)

Use `-N` to disable curl buffering so you see events as they arrive.

```bash
curl -N -X POST http://127.0.0.1:5050/api/agent/stream \
  -H "Content-Type: application/json" \
  -d '{
    "sessionKey":"s1",
    "query":"Plan research steps to evaluate AAPL.",
    "modelProvider":"openai",
    "isolatedSession":false
  }'
```

You’ll receive `text/event-stream` messages like:

- `data: {"type":"thinking","message":"..."}`
- `data: {"type":"tool_progress","tool":"...","message":"..."}`
- `data: {"type":"tool_start", ...}`
- `data: {"type":"done","answer":"..."}`

## Notes on session history + memory

- `isolatedSession=true` disables persistent chat history and disables memory integration for the run.
- Otherwise, chat history is kept in-process per `sessionKey` (not shared across multiple server processes).

## Performance notes

- `web_fetch` and `web_search` responses are cached on disk under `.dexter/cache/`.
- Memory search uses BM25 + fuzzy scoring over memory files for better recall.
