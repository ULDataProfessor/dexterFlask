"""Provider registry — mirror src/providers.ts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderDef:
    id: str
    display_name: str
    model_prefix: str
    api_key_env_var: str | None = None
    fast_model: str | None = None


PROVIDERS: list[ProviderDef] = [
    ProviderDef("openai", "OpenAI", "", "OPENAI_API_KEY", "gpt-4.1"),
    ProviderDef(
        "anthropic", "Anthropic", "claude-", "ANTHROPIC_API_KEY", "claude-haiku-4-5"
    ),
    ProviderDef(
        "google", "Google", "gemini-", "GOOGLE_API_KEY", "gemini-3-flash-preview"
    ),
    ProviderDef("xai", "xAI", "grok-", "XAI_API_KEY", "grok-4-1-fast-reasoning"),
    ProviderDef("moonshot", "Moonshot", "kimi-", "MOONSHOT_API_KEY", "kimi-k2-5"),
    ProviderDef(
        "deepseek", "DeepSeek", "deepseek-", "DEEPSEEK_API_KEY", "deepseek-chat"
    ),
    ProviderDef(
        "openrouter",
        "OpenRouter",
        "openrouter:",
        "OPENROUTER_API_KEY",
        "openrouter:openai/gpt-4o-mini",
    ),
    ProviderDef("ollama", "Ollama", "ollama:"),
]

_DEFAULT = PROVIDERS[0]


def resolve_provider(model_name: str) -> ProviderDef:
    for p in PROVIDERS:
        if p.model_prefix and model_name.startswith(p.model_prefix):
            return p
    return _DEFAULT


def get_provider_by_id(pid: str) -> ProviderDef | None:
    for p in PROVIDERS:
        if p.id == pid:
            return p
    return None


def get_fast_model(model_provider: str, fallback_model: str) -> str:
    p = get_provider_by_id(model_provider)
    return p.fast_model if p and p.fast_model else fallback_model
