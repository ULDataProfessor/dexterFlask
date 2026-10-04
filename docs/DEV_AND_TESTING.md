# Dev & Testing (Python/Flask)

## Install dev dependencies

```bash
uv venv .venv
source .venv/bin/activate
uv sync --extra dev
```

## Run the server locally

```bash
export DEXTER_DISABLE_CRON=1
# Generate a token for this server session; keep it secret.
export DEXTER_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m dexter_flask.app
```

Environment variables used by the Flask entrypoint:

- `PORT` (default: `5050`) — TCP port to listen on
- `FLASK_HOST` (default: `127.0.0.1`) — bind address; set to `0.0.0.0` only when non-local access is intentional
- `FLASK_DEBUG` (`1` enables Werkzeug debug mode — **never enable on a non-local interface or in production**)
- `DEXTER_API_TOKEN` is required by all agent routes; missing/blank configuration returns 503, and missing/invalid bearer credentials return 401. `/health` remains public.
- Debug startup rejects non-literal or non-loopback `FLASK_HOST` values.
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
