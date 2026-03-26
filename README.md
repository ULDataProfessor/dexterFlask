# Dexter 🤖

Dexter is an autonomous financial research agent that thinks, plans, and learns as it works. It performs analysis using task planning, self-reflection, and real-time market data. Think Claude Code, but built specifically for financial research.

<img width="1098" height="659" alt="Screenshot 2026-01-21 at 5 25 10 PM" src="https://github.com/user-attachments/assets/3bcc3a7f-b68a-4f5e-8735-9d22196ff76e" />

## Table of Contents

- [🐍 Python / Flask](#-python--flask)
- [👋 Overview](#-overview)
- [✅ Prerequisites](#-prerequisites)
- [💻 How to Install](#-how-to-install)
- [🚀 How to Run](#-how-to-run)
- [📊 How to Evaluate](#-how-to-evaluate)
- [🐛 How to Debug](#-how-to-debug)
- [📱 How to Use with WhatsApp](#-how-to-use-with-whatsapp)
- [🤝 How to Contribute](#-how-to-contribute)
- [📄 License](#-license)

## 🐍 Python / Flask

The research agent is implemented in Python (`dexter_flask/`) with a Flask HTTP API, LangChain providers, Financial Datasets tools, memory, cron (APScheduler), and optional Exa/Tavily/X search.

More docs: `docs/PYTHON_QUICKSTART.md`, `docs/API.md`, `docs/DEV_AND_TESTING.md`, `docs/TODO.md`.

**Quick start**

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp env.example .env           # add API keys
python -m dexter_flask.app  # default http://127.0.0.1:5050
```

**Endpoints**

- `GET /health` — liveness
- `POST /api/agent/run` — JSON body: `sessionKey`, `query`, `model`, `modelProvider`, optional `maxIterations`, `isolatedSession`, `channel`, `groupContext`, `isHeartbeat`; returns `{ "answer": "..." }`
- `POST /api/agent/stream` — same JSON body; `text/event-stream` with JSON `data:` lines mirroring agent events (including `type: "tool_progress"`)

Set `DEXTER_DISABLE_CRON=1` to run without the background scheduler (e.g. in tests).

**WhatsApp gateway:** run Flask, then set `FLASK_AGENT_URL=http://127.0.0.1:5050` (or `DEXTER_FLASK_URL`) in `.env`. The Bun gateway (`bun run gateway`) delegates `runAgentForMessage` to Flask via [src/gateway/flask-agent.ts](src/gateway/flask-agent.ts).

The Bun/TypeScript project remains for the terminal UI (`bun start`), evals, and the Baileys WhatsApp client.

## 🧰 Python Port: Tooling & Added Tools

The Flask service (`dexter_flask/`) is the core agent runtime. It registers a concrete set of tools that the agent can call during planning/execution (see `dexter_flask/tools/registry.py`).

### Finance tools
- `get_financials`: routes to income statements, balance sheets, cash flow, earnings, key ratios, analyst estimates, and segmented revenues.
- `get_market_data`: routes to stock/crypto price snapshots + price history, available tickers, company news, and insider trades.
- `read_filings`: plans which SEC filings to read, then reads specific 10-K / 10-Q / 8-K items.
- `stock_screener`: converts natural-language criteria into screener filters and returns matching tickers.

### Web + browsing
- `web_fetch`: fetches a URL and returns extracted readable text (cached on disk).
- `web_search` (optional): current web search via Exa or Tavily (cached on disk).
- `x_search` (optional): recent public posts on X/Twitter (requires `X_BEARER_TOKEN`).
- `browser`: headless Playwright helper for JS-heavy pages (returns page title + body text).

### Memory + skills
- `memory_search`: keyword/BM25 + fuzzy scoring over persistent memory files under `.dexter/memory/`.
- `memory_get` / `memory_update`: read/edit append/delete memory file segments.
- `skill` (optional): loads `SKILL.md`-based workflows from `dexter_flask/skills/`.

### Filesystem sandbox + agent control
- `read_file` / `write_file` / `edit_file`: sandboxed read/write/edit under `.dexter/workspace/` (prevents escaping to arbitrary paths).
- `heartbeat`: view/update the monitoring checklist in `.dexter/HEARTBEAT.md`.
- `cron`: create/list/update/remove/run scheduled jobs (persisted at `.dexter/cron/jobs.json`).

### Persistent data locations
- `.dexter/cache/`: disk cache for `web_fetch`, `web_search`, and selected financial-data endpoint results.
- `.dexter/scratchpad/`: per-query JSONL trace of tool calls + agent thinking (also covered in “How to Debug” below).
- `.dexter/memory/`: `MEMORY.md` plus daily memory files used for long-term recall.
- `.dexter/workspace/`: sandbox root used by the filesystem tools.
- `.dexter/cron/jobs.json`: cron scheduler persistence.


## 👋 Overview

Dexter takes complex financial questions and turns them into clear, step-by-step research plans. It runs those tasks using live market data, checks its own work, and refines the results until it has a confident, data-backed answer.  

**Key Capabilities:**
- **Intelligent Task Planning**: Automatically decomposes complex queries into structured research steps
- **Autonomous Execution**: Selects and executes the right tools to gather financial data
- **Self-Validation**: Checks its own work and iterates until tasks are complete
- **Real-Time Financial Data**: Access to income statements, balance sheets, and cash flow statements
- **Safety Features**: Built-in loop detection and step limits to prevent runaway execution

[![Twitter Follow](https://img.shields.io/twitter/follow/virattt?style=social)](https://twitter.com/virattt) [![Discord](https://img.shields.io/badge/Discord-Join%20Server-5865F2?style=social&logo=discord)](https://discord.gg/jpGHv2XB6T)

<img width="1042" height="638" alt="Screenshot 2026-02-18 at 12 21 25 PM" src="https://github.com/user-attachments/assets/2a6334f9-863f-4bd2-a56f-923e42f4711e" />


## ✅ Prerequisites

- Python >= 3.10
- `FINANCIAL_DATASETS_API_KEY` (get [here](https://financialdatasets.ai))
- LLM API key (set one of: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `XAI_API_KEY`, `OPENROUTER_API_KEY`, or run with `OLLAMA_BASE_URL`)
- Optional web search: `EXASEARCH_API_KEY` (preferred, get [here](https://exa.ai)) and/or `PERPLEXITY_API_KEY` / `TAVILY_API_KEY`
- Optional X/Twitter search: `X_BEARER_TOKEN` (enables the `x_search` tool)

## 💻 How to Install

1. Clone the repository:
```bash
git clone https://github.com/virattt/dexter.git
cd dexter
```

2. Set up Python (virtualenv) and install deps:
```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

3. Set up your environment variables:
```bash
# Copy the example environment file
cp env.example .env

# Edit .env and add your API keys (if using cloud providers)
# OPENAI_API_KEY=your-openai-api-key
# ANTHROPIC_API_KEY=your-anthropic-api-key (optional)
# GOOGLE_API_KEY=your-google-api-key (optional)
# XAI_API_KEY=your-xai-api-key (optional)
# OPENROUTER_API_KEY=your-openrouter-api-key (optional)

# Institutional-grade market data for agents; AAPL, NVDA, MSFT are free
# FINANCIAL_DATASETS_API_KEY=your-financial-datasets-api-key

# (Optional) If using Ollama locally
# OLLAMA_BASE_URL=http://127.0.0.1:11434

# Web Search (Exa preferred, Tavily fallback)
# EXASEARCH_API_KEY=your-exa-api-key
# TAVILY_API_KEY=your-tavily-api-key
```

## 🚀 How to Run

Run the Python/Flask server:
```bash
export PORT=5050
export DEXTER_DISABLE_CRON=1
python -m dexter_flask.app
```

Then hit:
```bash
curl -s http://127.0.0.1:5050/health
```

Optional (production): run behind Gunicorn:
```bash
export PORT=5050
# If you want the APScheduler background jobs enabled, do not set DEXTER_DISABLE_CRON=1
gunicorn -w 2 -k gthread -b 0.0.0.0:$PORT dexter_flask.app:app
```

## Optional: Run the Bun gateway (terminal UI / WhatsApp)

If you want the existing terminal UI and/or WhatsApp gateway, keep using Bun.

Run the terminal UI:
```bash
bun start
```

For WhatsApp:
```bash
bun run gateway:login
bun run gateway
```

## 📊 How to Evaluate

The full evaluation suite currently lives in the Bun/TypeScript codebase.

For Python/Flask parity, there is also a pytest suite (`tests/`) that covers the Flask routes and agent/tool execution plumbing without making external API calls.

**Run on all questions:**
```bash
bun run src/evals/run.ts
```

**Run on a random sample of data:**
```bash
bun run src/evals/run.ts --sample 10
```

The eval runner displays a real-time UI showing progress, current question, and running accuracy statistics. Results are logged to LangSmith for analysis.

## 🐛 How to Debug

Dexter logs all tool calls to a scratchpad file for debugging and history tracking. Each query creates a new JSONL file in `.dexter/scratchpad/`.

**Scratchpad location:**
```
.dexter/scratchpad/
├── 2026-01-30-111400_9a8f10723f79.jsonl
├── 2026-01-30-143022_a1b2c3d4e5f6.jsonl
└── ...
```

Each file contains newline-delimited JSON entries tracking:
- **init**: The original query
- **tool_result**: Each tool call with arguments, raw result, and LLM summary
- **thinking**: Agent reasoning steps

**Example scratchpad entry:**
```json
{"type":"tool_result","timestamp":"2026-01-30T11:14:05.123Z","toolName":"get_income_statements","args":{"ticker":"AAPL","period":"annual","limit":5},"result":{...},"llmSummary":"Retrieved 5 years of Apple annual income statements showing revenue growth from $274B to $394B"}
```

This makes it easy to inspect exactly what data the agent gathered and how it interpreted results.

## 📱 How to Use with WhatsApp

Chat with Dexter through WhatsApp by linking your phone to the gateway. The gateway delegates agent execution to the Flask service.

Start Flask first:
```bash
export DEXTER_DISABLE_CRON=1
python -m dexter_flask.app
```

**Quick start:**
```bash
# Link your WhatsApp account (scan QR code)
bun run gateway:login

# Start the gateway
bun run gateway
```

Then open WhatsApp, go to your own chat (message yourself), and ask Dexter a question.

For detailed setup instructions, configuration options, and troubleshooting, see the [WhatsApp Gateway README](src/gateway/channels/whatsapp/README.md).

## 🤝 How to Contribute

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

**Important**: Please keep your pull requests small and focused.  This will make it easier to review and merge.


## 📄 License

This project is licensed under the MIT License.
