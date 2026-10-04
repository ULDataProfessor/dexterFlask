# Dexter Flask: Python AI Agent for Financial Research

Dexter Flask (`dexterFlask`) is a Python financial research AI agent with a Flask HTTP API and command-line interface. It uses LLM tool calling to gather company financial statements, stock and crypto market data, SEC filings, and web research, then uses those results to answer natural-language questions. The research loop can make multiple tool calls, revisit the evidence, and return an answer within a configurable iteration limit.

This repository is a Python port of [Dexter](https://github.com/virattt/dexter), built for developers who want to integrate financial research into their own applications and researchers who want to inspect or extend an agent's workflow. It combines LangChain model integrations, Financial Datasets API tools, Server-Sent Events (SSE), persistent session history, memory, and scheduled jobs in a Python codebase.

Start with the [Python quickstart](docs/PYTHON_QUICKSTART.md), the [Flask API reference](docs/API.md), or the [development and testing guide](docs/DEV_AND_TESTING.md).

## Table of Contents

- [Financial research overview](#financial-research-overview)
- [Use cases and example questions](#use-cases-and-example-questions)
- [Architecture and rationale](#architecture-and-rationale)
- [Python and Flask quick start](#python-and-flask-quick-start)
- [Financial data and agent tools](#financial-data-and-agent-tools)
- [✅ Prerequisites](#-prerequisites)
- [💻 How to Install](#-how-to-install)
- [🚀 How to Run](#-how-to-run)
- [Python CLI](#python-cli-optional-runs-in-process)
- [📊 How to Evaluate](#-how-to-evaluate)
- [🐛 How to Debug](#-how-to-debug)
- [📱 WhatsApp](#-whatsapp)
- [🤝 How to Contribute](#-how-to-contribute)
- [📄 License](#-license)

## Financial research overview

Financial research often means combining several kinds of evidence: financial statements for business performance, market data for pricing context, SEC filings for disclosures, and news for recent developments. Dexter Flask exposes tools for these sources through one research loop, so a question can lead to a sequence of data requests rather than a single model response.

The implementation supports:

- **Company and equity research:** income statements, balance sheets, cash flow statements, financial ratios, analyst estimates, company news, and insider trades.
- **SEC filing analysis:** tools for locating and reading sections of 10-K, 10-Q, and 8-K filings.
- **Natural-language stock screening:** translation of research criteria into Financial Datasets screener filters.
- **Tool-calling workflows:** model-selected tools, recorded tool results, iteration limits, and warnings for repeated or similar tool calls.
- **HTTP and CLI integration:** JSON answers, SSE research events, and in-process Python command-line execution.
- **Continuity between API requests:** SQLite session history and file-based memory, with an isolated-run option that skips session history and memory integration.
- **Extensible research instructions:** `SKILL.md` workflows, including a built-in discounted cash flow (DCF) valuation workflow.

Results depend on the selected model, enabled tools, data-provider coverage, and API access. Some responses are cached, so check reporting periods, timestamps, sources, and assumptions before relying on an answer. Treat generated analysis as a research aid and review it independently before making financial decisions.

## Use cases and example questions

- **Analysts and individual researchers:** gather financial statements and compare company fundamentals. Example: "Compare AAPL and MSFT revenue growth and operating margins over the last three fiscal years."
- **Developers building research apps:** connect a dashboard or chat interface to the Flask API and display tool activity using the SSE stream.
- **Filing and disclosure research:** start with a question such as "Summarize the risk factors in the latest available NVDA 10-K and identify the filing used."
- **Valuation experiments:** use the DCF workflow to explore cash flow assumptions, discount rates, and sensitivity analysis, then check the inputs and calculations.
- **Agent development and evaluation:** add tools or skills, inspect JSONL research traces, and compare behavior with the included finance-question evaluation runner.

These are example prompts and integration patterns; they do not guarantee data coverage or answer accuracy for every company or model.

## Architecture and rationale

### Python and Flask for a reusable research service

The [agent loop](dexter_flask/agent/loop.py) is separate from the [Flask routes](dexter_flask/routes/agent_api.py) and [Python CLI](dexter_flask/cli.py). Both entry points use the same core agent, allowing developers to try queries locally and then expose that workflow over HTTP. The API can be connected to a frontend without requiring the upstream TypeScript/Node gateway.

### Tool calling for structured financial data

The [tool registry](dexter_flask/tools/registry.py) brings finance, search, browsing, memory, and workspace operations together. The `get_financials` and `get_market_data` tools route natural-language requests to more specific data tools. This keeps the main agent's tool list focused while allowing a query to retrieve multiple statements or data types. Tool results are recorded in a scratchpad and fed into subsequent iterations so later steps can use the evidence already gathered.

### SSE for visible research progress

Multi-step research can involve several external requests. The streaming endpoint emits JSON events over Server-Sent Events, including tool starts, results, progress, and completion. A client can show what is happening while the request runs. Separate approval and cancellation endpoints support interaction with an active streamed run; the current approval flow covers `write_file` and `edit_file`. See the [API reference](docs/API.md) for request and event formats.

### Local persistence for inspection and continuity

SQLite stores API session history, while local files hold memory, tool traces, cached responses, and scheduled-job definitions. This makes research state accessible for debugging and repeated sessions. APScheduler runs configured jobs in the background when enabled. These are shared service resources, so deployments should use a trusted-user boundary and follow the [deployment guidance](#production).

### Model integrations and reusable skills

[LangChain-backed model integrations](dexter_flask/llm/client.py) let the runtime use several model providers through a common invocation layer. Support for tool calling depends on the chosen model and integration. Markdown-based skills keep longer research procedures, such as the [DCF valuation workflow](dexter_flask/skills/builtin/dcf/SKILL.md), alongside the code so they can be reviewed and adapted. Changing a workflow does not require rewriting the HTTP layer.

## Python and Flask quick start

From a clone of [this repository](https://github.com/ULDataProfessor/dexterFlask), with Python 3.10+ and `uv` installed:

```bash
uv venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv sync --extra dev
cp env.example .env        # edit .env and add your API keys
export DEXTER_DISABLE_CRON=1
# Generate a token for this server session; keep it secret.
export DEXTER_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m dexter_flask.app  # default http://127.0.0.1:5050
```

Every `/api/agent/*` request requires `Authorization: Bearer <DEXTER_API_TOKEN>`. Keep the token private. See the [authenticated request examples](docs/PYTHON_QUICKSTART.md#run-the-agent-non-streaming) and [installation instructions](#-how-to-install) for the full setup.

### Flask API endpoints

- `GET /health` — liveness
- `POST /api/agent/run` — JSON body: `sessionKey`, `query`, `model`, `modelProvider`, optional `maxIterations`, `isolatedSession`, `channel`, `groupContext`, `isHeartbeat`; returns `{ "answer": "..." }`
- `POST /api/agent/stream` — same JSON body; `text/event-stream` with JSON `data:` lines mirroring agent events (including `type: "tool_progress"`)
- `POST /api/agent/approval` — JSON body: `runId`, `decision` (`allow-once` | `allow-session` | `deny`); applies tool approval decision for an active streamed run.
- `POST /api/agent/cancel` — JSON body: `runId`; requests cancellation for an active streamed run.

Set `DEXTER_DISABLE_CRON=1` to run without the background scheduler (e.g. in tests).

**WhatsApp / terminal UI note (Python-only mode):**
This repo’s main agent runtime is Python (`dexter_flask/`). WhatsApp + the terminal UI require the original TypeScript/Node gateway and are not included in the Python-only setup.

## Financial data and agent tools

The Flask service (`dexter_flask/`) is the core agent runtime. The [tool registry](dexter_flask/tools/registry.py) defines the tools available during research. Optional search tools depend on configured API keys; browser navigation additionally requires Playwright and Chromium.

### Financial statements, market data, and SEC filings

- `get_financials`: routes to income statements, balance sheets, cash flow, earnings, key ratios, analyst estimates, and segmented revenues.
- `get_market_data`: routes to stock/crypto price snapshots + price history, available tickers, company news, and insider trades.
- `read_filings`: plans which SEC filings to read, then reads specific 10-K / 10-Q / 8-K items.
- `stock_screener`: converts natural-language criteria into screener filters and returns matching tickers.

### Web search and browser research

- `web_fetch`: fetches a URL and returns extracted readable text (cached on disk).
- `web_search` (optional): current web search via Exa or Tavily (cached on disk).
- `x_search` (optional): recent public posts on X/Twitter (requires `X_BEARER_TOKEN`).
- `browser`: headless Playwright helper for JS-heavy pages (returns page title + body text).

### Persistent memory and research skills

- `memory_search`: keyword/BM25 + fuzzy scoring over persistent memory files under `.dexter/memory/`.
- `memory_get` / `memory_update`: read/edit append/delete memory file segments.
- `skill` (when skills are discovered): loads `SKILL.md`-based workflows from `dexter_flask/skills/builtin/` and `.dexter/skills/`.

### Workspace files and scheduled research

- `read_file` / `write_file` / `edit_file`: sandboxed read/write/edit under `.dexter/workspace/` (prevents escaping to arbitrary paths).
- `heartbeat`: view/update the monitoring checklist in `.dexter/HEARTBEAT.md`.
- `cron`: create/list/update/remove/run scheduled jobs (persisted at `.dexter/cron/jobs.json`).

### Persistent data locations

- `.dexter/cache/`: disk cache for `web_fetch`, `web_search`, and selected financial-data endpoint results.
- `.dexter/scratchpad/`: per-query JSONL trace of tool calls + agent thinking (also covered in “How to Debug” below).
- `.dexter/memory/`: `MEMORY.md` plus daily memory files used for long-term recall.
- `.dexter/workspace/`: sandbox root used by the filesystem tools.
- `.dexter/cron/jobs.json`: cron scheduler persistence.
- `.dexter/sessions.db`: SQLite-backed chat history persistence for API sessions (override with `DEXTER_SESSIONS_DB_PATH`).

## ✅ Prerequisites

- Python >= 3.10
- `uv` for the setup commands below
- `FINANCIAL_DATASETS_API_KEY` ([Financial Datasets](https://financialdatasets.ai))
- LLM API key (set one of: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `XAI_API_KEY`, `MOONSHOT_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, or use an Ollama model with `OLLAMA_BASE_URL`)
- Optional web search: `EXASEARCH_API_KEY` (preferred, [Exa](https://exa.ai)) or `TAVILY_API_KEY`
- Optional X/Twitter search: `X_BEARER_TOKEN` (enables the `x_search` tool)
- Optional browser tool: install the `playwright` Python package and Chromium browser binaries

## 💻 How to Install

1. Clone the repository:

```bash
git clone https://github.com/ULDataProfessor/dexterFlask.git
cd dexterFlask
```

1. Set up Python (uv) and install deps:

```bash
uv venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv sync --extra dev
```

1. Set up your environment variables:

```bash
# Copy the example environment file
cp env.example .env

# Edit .env and add your API keys (if using cloud providers)
# OPENAI_API_KEY=your-openai-api-key
# ANTHROPIC_API_KEY=your-anthropic-api-key (optional)
# GOOGLE_API_KEY=your-google-api-key (optional)
# XAI_API_KEY=your-xai-api-key (optional)
# OPENROUTER_API_KEY=your-openrouter-api-key (optional)

# Financial Datasets access; coverage depends on your API plan
# FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key

# (Optional) If using Ollama locally
# OLLAMA_BASE_URL=http://127.0.0.1:11434

# Web Search (Exa preferred; Tavily used when no Exa key is set)
# EXASEARCH_API_KEY=your-exa-api-key
# TAVILY_API_KEY=your-tavily-api-key
```

## 🚀 How to Run

### Local development

The built-in Flask dev server binds to `127.0.0.1` (localhost only) by default,
so it is not reachable from other machines.  **Do not use the dev server in
production** — it is not designed for production security or performance.

```bash
export PORT=5050
export DEXTER_DISABLE_CRON=1
# Generate a token for this server session; keep it secret.
export DEXTER_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m dexter_flask.app
```

Then hit:

```bash
curl -s http://127.0.0.1:5050/health
```

Environment variables accepted by the entrypoint:

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5050` | TCP port to listen on |
| `FLASK_HOST` | `127.0.0.1` | Bind address — override to `0.0.0.0` **only** when non-local binding is intentional (e.g. inside a container) |
| `FLASK_DEBUG` | _(off)_ | Set to `1` to enable Werkzeug debug mode — **never enable in production or on a non-local interface** |
| `DEXTER_API_TOKEN` | _(unset)_ | Required shared bearer token for every `/api/agent/*` route; unset disables these routes with HTTP 503 |
| `DEXTER_DISABLE_CRON` | _(off)_ | Set to `1` to disable the APScheduler background jobs |

Agent clients must send `Authorization: Bearer <DEXTER_API_TOKEN>`, including
stream, approval and cancel requests. `/health` stays public. See [API authentication](docs/API.md#authentication).
Debug startup refuses any host other than a literal loopback IP (`127.0.0.1` or `::1`).
This guard applies to `python -m dexter_flask.app`; never use `flask run --debug` on an exposed interface.

### Production

Set `DEXTER_API_TOKEN` through your deployment secret manager (use a random token of at least 32 bytes).
Use HTTPS at a trusted reverse proxy and keep the backend inaccessible to untrusted networks.
This shared token provides a single trusted-user boundary, not per-user session isolation.
Use a proper WSGI server such as Gunicorn.  Bind to whatever address is
appropriate for your deployment (e.g. `0.0.0.0` inside a container that is
already behind a reverse proxy / firewall):

```bash
export PORT=5050
# If you want APScheduler background jobs, do not set DEXTER_DISABLE_CRON=1
gunicorn -w 1 -k gthread --threads 4 -b 127.0.0.1:$PORT dexter_flask.app:app
```

The example uses one worker because streaming approvals/cancellations are kept in process-local memory.
Only bind Gunicorn externally when your container/proxy network is deliberately isolated.

## Python CLI (optional, runs in-process)

Run the agent directly (no Flask HTTP server):

```bash
python -m dexter_flask run --query "What is the outlook for Apple (AAPL) over the next 12 months?"
```

Event stream:

```bash
python -m dexter_flask stream --query "Plan research steps to evaluate AAPL."
```

## 📊 How to Evaluate

The [pytest suite](tests/) covers Flask routes and agent/tool execution plumbing without making external API calls:

```bash
uv run --extra dev pytest -q
```

For an end-to-end evaluation over the finance dataset, use the Python eval runner:

```bash
python -m dexter_flask.evals.run --sample 10
```

By default, the runner also performs optional LLM-as-judge scoring. You can disable that with `--no-judge`.

## 🐛 How to Debug

Dexter logs all tool calls to a scratchpad file for debugging and history tracking. Each query creates a new JSONL file in `.dexter/scratchpad/`.

**Scratchpad location:**

```text
.dexter/scratchpad/
├── 2026-01-30-111400_9a8f10723f79.jsonl
├── 2026-01-30-143022_a1b2c3d4e5f6.jsonl
└── ...
```

Each file contains newline-delimited JSON entries tracking:

- **init**: The original query
- **tool_result**: Each tool call with arguments and raw result
- **thinking**: Agent reasoning steps

**Example scratchpad entry:**

```json
{"type":"tool_result","timestamp":"2026-01-30T11:14:05.123Z","toolName":"get_financials","args":{"query":"AAPL annual income statements for the last five years"},"result":{"data":"Example financial data omitted"}}
```

This makes it easy to inspect exactly what data the agent gathered and how it interpreted results.

## 📱 WhatsApp

WhatsApp is not included in the Python-only setup. The original WhatsApp integration requires the TypeScript/Node gateway.

## 🤝 How to Contribute

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

**Important**: Please keep your pull requests small and focused.  This will make it easier to review and merge.

## 📄 License

This project is licensed under the MIT License.
