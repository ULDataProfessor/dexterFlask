# Dev & Testing (Python/Flask)

## Install dev dependencies

```bash
uv venv .venv
source .venv/bin/activate
uv sync --dev
```

## Run the server locally

```bash
export DEXTER_DISABLE_CRON=1
python -m dexter_flask.app
```

Environment variables used by the Flask entrypoint:

- `PORT` (default: `5050`)
- `FLASK_DEBUG` (`1` enables debug mode)
- `DEXTER_DISABLE_CRON=1` prevents background scheduler startup

## Run tests

Tests are Python/pytest-based.

```bash
pytest
```

You can also run with:

```bash
pytest -q
```

For deterministic test runs, you can export:

```bash
export DEXTER_DISABLE_CRON=1
pytest
```

## What’s covered (high-level)

- `/health` endpoint
- `/api/agent/run` JSON response shape
- `/api/agent/stream` SSE response + history save behavior for `isolatedSession`
- agent loop and tool executor behavior
- cron scheduling helper logic

