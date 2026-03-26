"""Environment-backed settings — mirror env.example."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv(override=False)


def _e(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return v


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    anthropic_api_key: str | None
    google_api_key: str | None
    xai_api_key: str | None
    openrouter_api_key: str | None
    moonshot_api_key: str | None
    deepseek_api_key: str | None
    ollama_base_url: str | None
    financial_datasets_api_key: str | None
    exasearch_api_key: str | None
    perplexity_api_key: str | None
    tavily_api_key: str | None
    x_bearer_token: str | None
    langsmith_api_key: str | None
    langsmith_tracing: bool
    flask_agent_url: str | None  # for Node gateway shim

    @staticmethod
    def load() -> "Settings":
        return Settings(
            openai_api_key=_e("OPENAI_API_KEY"),
            anthropic_api_key=_e("ANTHROPIC_API_KEY"),
            google_api_key=_e("GOOGLE_API_KEY"),
            xai_api_key=_e("XAI_API_KEY"),
            openrouter_api_key=_e("OPENROUTER_API_KEY"),
            moonshot_api_key=_e("MOONSHOT_API_KEY"),
            deepseek_api_key=_e("DEEPSEEK_API_KEY"),
            ollama_base_url=_e("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            financial_datasets_api_key=_e("FINANCIAL_DATASETS_API_KEY"),
            exasearch_api_key=_e("EXASEARCH_API_KEY"),
            perplexity_api_key=_e("PERPLEXITY_API_KEY"),
            tavily_api_key=_e("TAVILY_API_KEY"),
            x_bearer_token=_e("X_BEARER_TOKEN"),
            langsmith_api_key=_e("LANGSMITH_API_KEY"),
            langsmith_tracing=_e("LANGSMITH_TRACING", "false").lower() == "true",
            flask_agent_url=_e("FLASK_AGENT_URL"),  # e.g. http://127.0.0.1:5050
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.load()
