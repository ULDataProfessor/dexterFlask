"""LLM invocation — mirror src/model/llm.ts."""
from __future__ import annotations

import time
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

try:
    from langchain_community.chat_models import ChatOllama
except ImportError:
    ChatOllama = None  # type: ignore[misc, assignment]

from dexter_flask.config import get_settings
from dexter_flask.llm.errors_util import is_non_retryable_error
from dexter_flask.providers import ProviderDef, resolve_provider

DEFAULT_MODEL = "gpt-5.4"
DEFAULT_PROVIDER = "openai"


def _get_api_key(env_var: str) -> str:
    s = get_settings()
    mapping = {
        "OPENAI_API_KEY": s.openai_api_key,
        "ANTHROPIC_API_KEY": s.anthropic_api_key,
        "GOOGLE_API_KEY": s.google_api_key,
        "XAI_API_KEY": s.xai_api_key,
        "OPENROUTER_API_KEY": s.openrouter_api_key,
        "MOONSHOT_API_KEY": s.moonshot_api_key,
        "DEEPSEEK_API_KEY": s.deepseek_api_key,
    }
    val = mapping.get(env_var) or __import__("os").environ.get(env_var)
    if not val:
        raise RuntimeError(f"[LLM] {env_var} not found in environment variables")
    return val


def _with_retry(fn, provider_name: str, max_attempts: int = 3):
    last = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            msg = str(e)
            if is_non_retryable_error(msg):
                raise
            if attempt == max_attempts - 1:
                raise
            time.sleep(0.5 * (2**attempt))
    raise last  # type: ignore[misc]


def get_chat_model(model_name: str = DEFAULT_MODEL, streaming: bool = False) -> BaseChatModel:
    provider = resolve_provider(model_name)
    opts: dict[str, Any] = {"streaming": streaming}

    if provider.id == "anthropic":
        return ChatAnthropic(
            model=model_name,
            api_key=_get_api_key("ANTHROPIC_API_KEY"),
            **opts,
        )
    if provider.id == "google":
        return ChatGoogleGenerativeAI(
            model=model_name.replace("gemini-", "gemini-"),  # keep as-is mostly
            google_api_key=_get_api_key("GOOGLE_API_KEY"),
            **opts,
        )
    if provider.id == "xai":
        return ChatOpenAI(
            model=model_name,
            api_key=_get_api_key("XAI_API_KEY"),
            base_url="https://api.x.ai/v1",
            **opts,
        )
    if provider.id == "openrouter":
        m = model_name.replace("openrouter:", "", 1)
        return ChatOpenAI(
            model=m,
            api_key=_get_api_key("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            **opts,
        )
    if provider.id == "moonshot":
        return ChatOpenAI(
            model=model_name,
            api_key=_get_api_key("MOONSHOT_API_KEY"),
            base_url="https://api.moonshot.cn/v1",
            **opts,
        )
    if provider.id == "deepseek":
        return ChatOpenAI(
            model=model_name,
            api_key=_get_api_key("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
            **opts,
        )
    if provider.id == "ollama":
        if ChatOllama is None:
            raise RuntimeError("langchain-community with ChatOllama is required for Ollama")
        base = get_settings().ollama_base_url or "http://127.0.0.1:11434"
        m = model_name.replace("ollama:", "", 1)
        return ChatOllama(model=m, base_url=base, **opts)

    # openai default
    return ChatOpenAI(
        model=model_name,
        api_key=_get_api_key("OPENAI_API_KEY"),
        **opts,
    )


def _extract_usage(result: Any) -> dict[str, int] | None:
    if result is None:
        return None
    um = getattr(result, "usage_metadata", None)
    if um and isinstance(um, dict):
        return {
            "inputTokens": int(um.get("input_tokens", 0)),
            "outputTokens": int(um.get("output_tokens", 0)),
            "totalTokens": int(um.get("total_tokens", 0)),
        }
    rm = getattr(result, "response_metadata", None) or {}
    u = rm.get("usage") or rm.get("token_usage")
    if isinstance(u, dict):
        inp = int(u.get("prompt_tokens", u.get("input_tokens", 0)))
        out = int(u.get("completion_tokens", u.get("output_tokens", 0)))
        tot = int(u.get("total_tokens", inp + out))
        return {"inputTokens": inp, "outputTokens": out, "totalTokens": tot}
    return None


def call_llm(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    system_prompt: str | None = None,
    tools: list[BaseTool] | None = None,
) -> tuple[AIMessage | str, dict[str, int] | None]:
    """Invoke LLM; returns AIMessage when tools bound, else string content."""
    from dexter_flask.agent.prompts import DEFAULT_SYSTEM_PROMPT

    final_system = system_prompt or DEFAULT_SYSTEM_PROMPT
    llm = get_chat_model(model, streaming=False)
    provider = resolve_provider(model)

    runnable: Runnable = llm
    if tools:
        runnable = llm.bind_tools(tools)

    def _invoke():
        if provider.id == "anthropic":
            messages = [
                SystemMessage(content=final_system),
                HumanMessage(content=prompt),
            ]
            return runnable.invoke(messages)
        tpl = ChatPromptTemplate.from_messages(
            [
                ("system", "{system}"),
                ("user", "{prompt}"),
            ]
        )
        chain = tpl | runnable
        return chain.invoke({"system": final_system, "prompt": prompt})

    result = _with_retry(_invoke, provider.display_name)
    usage = _extract_usage(result)

    if not tools and isinstance(result, AIMessage):
        content = result.content
        if isinstance(content, str):
            return content, usage
        if isinstance(content, list):
            parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
            return "".join(parts), usage
    if not tools:
        return str(result), usage
    return result, usage  # type: ignore[return-value]
