"""System and iteration prompts — mirror src/agent/prompts.ts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from dexter_flask.agent.channels import get_channel_profile
from dexter_flask.paths import soul_md_path
from dexter_flask.skills.registry import build_skill_metadata_section, discover_skills


def get_current_date() -> str:
    return datetime.now().strftime("%A, %B %d, %Y")


def load_soul_document() -> str | None:
    p = soul_md_path()
    try:
        if p.is_file():
            return p.read_text(encoding="utf-8")
    except OSError:
        pass
    return None


def _build_skills_section() -> str:
    skills = discover_skills()
    if not skills:
        return ""
    meta = build_skill_metadata_section()
    return f"""## Available Skills

{meta}

## Skill Usage Policy

- Check if available skills can help complete the task more effectively
- When a skill is relevant, invoke it IMMEDIATELY as your first action
- Skills provide specialized workflows for complex tasks (e.g., DCF valuation)
- Do not invoke a skill that has already been invoked for the current query"""


def _build_memory_section(memory_files: list[str], memory_context: str | None) -> str:
    fl = f"\nMemory files on disk: {', '.join(memory_files)}" if memory_files else ""
    ctx = (
        f"\n\n### What you know about the user\n\n{memory_context}"
        if memory_context
        else ""
    )
    return f"""## Memory

You have persistent memory stored as Markdown files in .dexter/memory/.{fl}{ctx}

### Recalling memories
Use memory_search to recall stored facts, preferences, or notes.
**IMPORTANT:** Before giving personalized financial advice, ALWAYS call memory_search first when relevant.

### Storing memories
Use **memory_update** to add, edit, or delete memories. Do NOT use write_file for memory files."""


def build_group_section(ctx: dict[str, Any]) -> str:
    lines = ["## Group Chat", ""]
    if ctx.get("groupName"):
        lines.append(
            f'You are participating in the WhatsApp group "{ctx["groupName"]}".'
        )
    else:
        lines.append("You are participating in a WhatsApp group chat.")
    lines.extend(
        [
            "You were activated because someone @-mentioned you.",
            "",
            "### Group behavior",
            "- Address the person who mentioned you by name",
            "- Keep responses concise",
        ]
    )
    if ctx.get("membersList"):
        lines.extend(["", "### Group members", ctx["membersList"]])
    return "\n".join(lines)


def get_default_system_prompt() -> str:
    d = get_current_date()
    return f"""You are Dexter, a helpful AI assistant.

Current date: {d}

Your output is displayed on a command line interface. Keep responses short and concise.

## Behavior

- Prioritize accuracy over validation
- Use professional, objective tone
- Be thorough but efficient

## Response Format

- Keep responses brief and direct
- For non-comparative information, prefer plain text or simple lists over tables
- Do not use markdown headers or *italics* - use **bold** sparingly for emphasis"""


def build_system_prompt(
    model: str,
    soul_content: str | None,
    channel: str | None = None,
    group_context: dict[str, Any] | None = None,
    memory_files: list[str] | None = None,
    memory_context: str | None = None,
) -> str:
    from dexter_flask.tools.registry import build_tool_descriptions

    tool_descriptions = build_tool_descriptions(model)
    profile = get_channel_profile(channel or "cli")
    behavior_bullets = "\n".join(f"- {b}" for b in profile.behavior)
    format_bullets = "\n".join(f"- {b}" for b in profile.response_format)
    tables_section = (
        f"\n## Tables (for comparative/tabular data)\n\n{profile.tables}"
        if profile.tables
        else ""
    )
    mf = memory_files or []
    soul_block = ""
    if soul_content:
        soul_block = f"""## Identity

{soul_content}

Embody the identity and investing philosophy described above.
"""
    group_block = f"\n\n{build_group_section(group_context)}" if group_context else ""
    return f"""You are Dexter, a {profile.label} assistant with access to research tools.

Current date: {get_current_date()}

{profile.preamble}

## Available Tools

{tool_descriptions}

## Tool Usage Policy

- Only use tools when the query actually requires external data
- For stock and crypto prices, company news, insider trades, use get_market_data
- For financials and metrics, use get_financials
- For screening stocks, use stock_screener
- Call get_financials or get_market_data ONCE with the full natural language query
- When news headlines suffice, avoid web_fetch until needed
- For general web queries, use web_search
- Only use browser when JavaScript rendering is required

{_build_skills_section()}

{_build_memory_section(mf, memory_context)}

## Heartbeat

You have a periodic heartbeat (see .dexter/HEARTBEAT.md). Use the heartbeat tool to view/update it.

## Behavior

{behavior_bullets}

{soul_block}
## Response Format

{format_bullets}{tables_section}{group_block}"""


def build_iteration_prompt(
    original_query: str,
    full_tool_results: str,
    tool_usage_status: str | None = None,
) -> str:
    prompt = f"Query: {original_query}"
    if full_tool_results.strip():
        prompt += f"""

Data retrieved from tool calls:
{full_tool_results}"""
    if tool_usage_status:
        prompt += f"\n\n{tool_usage_status}"
    prompt += """

Continue working toward answering the query. When you have gathered sufficient data, write your complete answer directly and do not call more tools."""
    return prompt


# Backward compat name used in tests
DEFAULT_SYSTEM_PROMPT = get_default_system_prompt()
