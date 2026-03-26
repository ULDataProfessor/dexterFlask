# Repository Guidelines

- Repo: https://github.com/virattt/dexter
- Dexter is a CLI/HTTP-based AI agent for deep financial research, built in Python with Flask and LangChain.

## Project Structure

- Source code: `dexter_flask/`
  - Flask app: `dexter_flask/app.py` + routes under `dexter_flask/routes/`
  - Agent core: `dexter_flask/agent/` (loop, prompts, scratchpad, tool executor)
  - LLM providers: `dexter_flask/llm/` + `dexter_flask/providers.py`
  - Tools: `dexter_flask/tools/` (finance/search/fetch/browser/fs/memory/cron/skill)
  - Skills: `dexter_flask/skills/builtin/` (SKILL.md-based workflows)
  - Evals: `dexter_flask/evals/`
  - CLI: `python -m dexter_flask ...` (`dexter_flask/cli.py`)
- Config: `.dexter/settings.json` (persisted model/provider selection)
- Environment: `.env` (API keys; see `env.example`)
- Scripts: `scripts/release.sh`

## Build, Test, and Development Commands (Python-first)

- Runtime: Python. Start the Flask service with `python -m dexter_flask.app`.
- Install deps: `uv venv .venv && source .venv/bin/activate && uv sync --dev`
- Run: `python -m dexter_flask.app`
- Tests: `pytest`
- Evals (end-to-end, optional judge): `python -m dexter_flask.evals.run --sample 10`

## Coding Style & Conventions

- Language: Python (3.10+)
- Keep files concise; extract helpers rather than duplicating code.
- Add brief comments for tricky or non-obvious logic.
- Do not add logging unless explicitly asked.
- Do not create README or documentation files unless explicitly asked.

## LLM Providers

- Supported: OpenAI (default), Anthropic, Google, xAI (Grok), OpenRouter, Ollama (local).
- Default model: `gpt-5.4`.

## Tools

- `financial_search`: primary tool for all financial data queries (prices, metrics, filings). Delegates to multiple sub-tools internally.
- `financial_metrics`: direct metric lookups (revenue, market cap, etc.).
- `read_filings`: SEC filing reader for 10-K, 10-Q, 8-K documents.
- `web_search`: general web search (Exa if `EXASEARCH_API_KEY` set, else Tavily if `TAVILY_API_KEY` set).
- `browser`: Playwright-based web scraping for reading pages the agent discovers.
- `skill`: invokes SKILL.md-defined workflows (e.g. DCF valuation). Each skill runs at most once per query.
- Tool registry: `dexter_flask/tools/registry.py`. Tools are conditionally included based on env vars.

## Skills

- Skills live as `SKILL.md` files with YAML frontmatter (`name`, `description`) and markdown body (instructions).
- Built-in skills: `dexter_flask/skills/builtin/**/SKILL.md`.
- Discovery: `dexter_flask/skills/registry.py` scans for SKILL.md files at startup.
- Skills are exposed to the LLM as metadata in the system prompt; the LLM invokes them via the `skill` tool.

## Agent Architecture

- Agent loop: `dexter_flask/agent/loop.py`. Iterative tool-calling loop with configurable max iterations (default 10).
- Scratchpad: `dexter_flask/agent/scratchpad.py`. Single source of truth for all tool results within a query.
- Context management: Anthropic-style. Full tool results kept in context; oldest results cleared when token threshold exceeded.
- Final answer: generated in a separate LLM call with full scratchpad context (no tools bound).
- Events: agent yields typed events (`tool_start`, `tool_end`, `thinking`, `answer_start`, `done`, etc.) for real-time UI updates.

## Environment Variables

- LLM keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `XAI_API_KEY`, `OPENROUTER_API_KEY`
- Ollama: `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`)
- Finance: `FINANCIAL_DATASETS_API_KEY`
- Search: `EXASEARCH_API_KEY` (preferred), `TAVILY_API_KEY` (fallback)
- Tracing: `LANGSMITH_API_KEY`, `LANGSMITH_ENDPOINT`, `LANGSMITH_PROJECT`, `LANGSMITH_TRACING`
- Never commit `.env` files or real API keys.

## Version & Release

- Version format: CalVer `YYYY.M.D` (no zero-padding). Tag prefix: `v`.
- Release script: `bash scripts/release.sh [version]` (defaults to today's date).
- Release flow: bump version in `pyproject.toml` / `dexter_flask/__init__.py`, create git tag, push tag, create GitHub release via `gh`.
- Do not push or publish without user confirmation.

## Testing

- Framework: `pytest`
- Tests colocated as `tests/*.py` (fast contract/unit tests for routes/tools)

## Security

- API keys stored in `.env` (gitignored). Users can also enter keys interactively via the CLI.
- Config stored in `.dexter/settings.json` (gitignored).
- Never commit or expose real API keys, tokens, or credentials.
