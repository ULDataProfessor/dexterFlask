"""Agent types — mirror src/agent/types.ts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, TypedDict

ApprovalDecision = Literal["allow-once", "allow-session", "deny"]


@dataclass
class AgentConfig:
    model: str | None = None
    model_provider: str | None = None
    max_iterations: int = 10
    channel: str | None = None
    group_context: dict[str, Any] | None = None
    request_tool_approval: Any | None = None
    session_approved_tools: set[str] | None = None
    memory_enabled: bool = True


class GroupContext(TypedDict, total=False):
    groupName: str
    membersList: str
    activationMode: Literal["mention"]


class ThinkingEvent(TypedDict):
    type: Literal["thinking"]
    message: str


class ToolStartEvent(TypedDict):
    type: Literal["tool_start"]
    tool: str
    args: dict[str, Any]


class ToolEndEvent(TypedDict):
    type: Literal["tool_end"]
    tool: str
    args: dict[str, Any]
    result: str
    duration: int


class ToolErrorEvent(TypedDict):
    type: Literal["tool_error"]
    tool: str
    error: str


class ToolProgressEvent(TypedDict):
    type: Literal["tool_progress"]
    tool: str
    message: str


class ToolLimitEvent(TypedDict):
    type: Literal["tool_limit"]
    tool: str
    warning: str | None
    blocked: bool


class ToolApprovalEvent(TypedDict):
    type: Literal["tool_approval"]
    tool: str
    args: dict[str, Any]
    approved: ApprovalDecision


class ToolDeniedEvent(TypedDict):
    type: Literal["tool_denied"]
    tool: str
    args: dict[str, Any]


class ContextClearedEvent(TypedDict):
    type: Literal["context_cleared"]
    clearedCount: int
    keptCount: int


class MemoryFlushEvent(TypedDict, total=False):
    type: Literal["memory_flush"]
    phase: Literal["start", "end"]
    filesWritten: list[str]


class MemoryRecalledEvent(TypedDict):
    type: Literal["memory_recalled"]
    filesLoaded: list[str]
    tokenCount: int


class TokenUsage(TypedDict):
    inputTokens: int
    outputTokens: int
    totalTokens: int


class DoneEvent(TypedDict, total=False):
    type: Literal["done"]
    answer: str
    toolCalls: list[dict[str, Any]]
    iterations: int
    totalTime: int
    tokenUsage: TokenUsage | None
    tokensPerSecond: float | None


AgentEvent = (
    ThinkingEvent
    | ToolStartEvent
    | ToolProgressEvent
    | ToolEndEvent
    | ToolErrorEvent
    | ToolApprovalEvent
    | ToolDeniedEvent
    | ToolLimitEvent
    | ContextClearedEvent
    | MemoryRecalledEvent
    | MemoryFlushEvent
    | DoneEvent
)
