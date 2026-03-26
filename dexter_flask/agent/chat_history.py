"""In-memory chat history — mirror src/utils/in-memory-chat-history.ts (subset)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from dexter_flask.agent.history_context import (
    DEFAULT_HISTORY_LIMIT,
    FULL_ANSWER_TURNS,
    build_history_context,
)
from dexter_flask.llm.client import DEFAULT_MODEL, call_llm


class SelectedMessages(BaseModel):
    message_ids: list[int] = Field(default_factory=list)


@dataclass
class _Message:
    id: int
    query: str
    answer: str | None
    summary: str | None


MESSAGE_SUMMARY_SYSTEM = (
    "You are a concise summarizer. Generate brief summaries of conversation answers."
)
MESSAGE_SELECTION_SYSTEM = (
    "You are a relevance evaluator. Select which previous conversation messages "
    "are relevant to the current query."
)


class InMemoryChatHistory:
    def __init__(self, model: str = DEFAULT_MODEL, max_turns: int = DEFAULT_HISTORY_LIMIT) -> None:
        self.model = model
        self.max_turns = max_turns
        self._messages: list[_Message] = []
        self._relevant_cache: dict[str, list[_Message]] = {}

    def _hash_q(self, q: str) -> str:
        return hashlib.md5(q.encode()).hexdigest()[:12]

    def set_model(self, model: str) -> None:
        self.model = model

    def save_user_query(self, query: str) -> None:
        self._relevant_cache.clear()
        self._messages.append(
            _Message(id=len(self._messages), query=query, answer=None, summary=None)
        )

    def _generate_summary(self, query: str, answer: str) -> str:
        prompt = f'Query: "{query}"\nAnswer: "{answer[:1500]}"\n\nGenerate a brief 1-2 sentence summary.'
        try:
            text, _ = call_llm(prompt, model=self.model, system_prompt=MESSAGE_SUMMARY_SYSTEM)
            return str(text).strip() if not isinstance(text, str) else text.strip()
        except Exception:
            return f"Answer to: {query[:100]}"

    def save_answer(self, answer: str) -> None:
        if not self._messages:
            return
        last = self._messages[-1]
        if last.answer is not None:
            return
        last.answer = answer
        last.summary = self._generate_summary(last.query, answer)

    def select_relevant_messages(self, current_query: str) -> list[_Message]:
        completed = [m for m in self._messages if m.answer is not None]
        if not completed:
            return []
        key = self._hash_q(current_query)
        if key in self._relevant_cache:
            return self._relevant_cache[key]
        messages_info = [{"id": m.id, "query": m.query, "summary": m.summary} for m in completed]
        prompt = (
            f'Current user query: "{current_query}"\n\nPrevious conversations:\n'
            f"{messages_info}\n\nSelect message IDs relevant to the current query."
        )
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from dexter_flask.llm.client import get_chat_model
            from dexter_flask.providers import resolve_provider

            model_name = self.model
            llm = get_chat_model(model_name)
            structured = llm.with_structured_output(SelectedMessages)
            provider = resolve_provider(model_name)
            if provider.id == "anthropic":
                msgs = [
                    SystemMessage(content=MESSAGE_SELECTION_SYSTEM),
                    HumanMessage(content=prompt),
                ]
                out = structured.invoke(msgs)
            else:
                from langchain_core.prompts import ChatPromptTemplate

                tpl = ChatPromptTemplate.from_messages(
                    [("system", MESSAGE_SELECTION_SYSTEM), ("user", "{p}")]
                )
                out = (tpl | structured).invoke({"p": prompt})
            ids = out.message_ids if isinstance(out, SelectedMessages) else []
            selected = [
                self._messages[i]
                for i in ids
                if 0 <= i < len(self._messages) and self._messages[i].answer is not None
            ]
            self._relevant_cache[key] = selected
            return selected
        except Exception:
            return []

    def get_recent_turns(self, limit: int | None = None) -> list[dict]:
        lim = limit if limit is not None else self.max_turns
        completed = [m for m in self._messages if m.answer is not None]
        recent = completed[-lim:] if lim else []
        turns: list[dict] = []
        for i, m in enumerate(recent):
            is_recent = i >= len(recent) - FULL_ANSWER_TURNS
            content = m.answer if is_recent else (m.summary or m.answer or "")
            turns.append({"role": "user", "content": m.query})
            turns.append({"role": "assistant", "content": content or ""})
        return turns

    def has_messages(self) -> bool:
        return len(self._messages) > 0

    def prune_last_turn(self) -> None:
        if self._messages:
            self._messages.pop()
            self._relevant_cache.clear()
