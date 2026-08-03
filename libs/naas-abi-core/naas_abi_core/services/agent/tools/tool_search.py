"""On-demand tool discovery for progressive disclosure (Abi context engineering).

When an agent carries a large tool surface, binding every tool schema on every
turn inflates the prompt and degrades routing quality on small models. With
progressive disclosure the agent keeps only an always-on core bound to the
model (sub-agent delegation, workspace tools, and this ``search_tools`` tool)
and *defers* the rest. The model calls ``search_tools`` with keywords describing
what it needs; the matching tools are reported back and become bound on
subsequent turns.

The set of "loaded" tools is derived purely from the transcript (the names a
prior ``search_tools`` result surfaced), so the active tool set is a function of
message history and stays stable across turns and reconstructions.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from langchain_core.messages import AnyMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

# Public name the model calls, and the machine-readable marker appended to a
# successful result so the runtime can recover which tools were loaded.
TOOL_SEARCH_NAME = "search_tools"
_LOADED_MARKER = "[loaded_tools]"

_WORD_RE = re.compile(r"[^a-z0-9]+")


class _ToolSearchInput(BaseModel):
    query: str = Field(
        description=(
            "Keywords describing the capability you need, e.g. 'create workspace', "
            "'edit slides deck', 'query knowledge graph'. Or pass "
            "'select:tool_a,tool_b' to load specific tools by exact name."
        )
    )
    max_results: int = Field(
        default=5, description="Maximum number of tools to load (default 5)."
    )


def _score(query: str, name: str, description: str) -> int:
    terms = [t for t in _WORD_RE.split(query.lower()) if t]
    name_l = name.lower()
    desc_l = (description or "").lower()
    score = 0
    for t in terms:
        if t in name_l:
            score += 10
        if t in desc_l:
            score += 2
    return score


def build_tool_search_tool(deferred: Sequence[tuple[str, str]]) -> StructuredTool:
    """Build the always-on ``search_tools`` tool over a list of (name, description)."""
    specs: list[tuple[str, str]] = list(deferred)
    by_name = dict(specs)

    def search_tools(query: str, max_results: int = 5) -> str:
        q = (query or "").strip()
        select = re.match(r"^select:(.+)$", q, re.IGNORECASE)
        if select:
            wanted = {s.strip() for s in select.group(1).split(",") if s.strip()}
            names = [n for n, _ in specs if n in wanted]
        else:
            scored = [(n, d, _score(q, n, d)) for n, d in specs]
            scored = [x for x in scored if x[2] > 0]
            scored.sort(key=lambda x: x[2], reverse=True)
            names = [n for n, _, _ in scored[: max(1, int(max_results or 5))]]

        if not names:
            catalog = "\n".join(f"- {n}: {d}" for n, d in specs[:30])
            return (
                f"No tools matched '{query}'. Available tools you can load "
                f"(retry with better keywords or select:<name>):\n{catalog}"
            )

        listing = "\n".join(f"- {n}: {by_name.get(n, '')}" for n in names)
        return (
            f"Loaded {len(names)} tool(s); you can now call them directly:\n"
            f"{listing}\n\n{_LOADED_MARKER} {', '.join(names)}"
        )

    return StructuredTool.from_function(
        func=search_tools,
        name=TOOL_SEARCH_NAME,
        description=(
            "Discover and load tools for the current task. To keep responses fast, "
            "most tools are NOT loaded up front — call this first with keywords "
            "describing what you need (e.g. 'manage workspace members', 'edit "
            "slides', 'query the knowledge graph'), then call the tools it returns. "
            "You can also pass 'select:<tool_name>' to load a specific tool by name."
        ),
        args_schema=_ToolSearchInput,
    )


def extract_loaded_tool_names(messages: Iterable[AnyMessage]) -> set[str]:
    """Names surfaced by prior ``search_tools`` results in the transcript."""
    loaded: set[str] = set()
    for message in messages:
        if getattr(message, "name", None) != TOOL_SEARCH_NAME:
            continue
        content = getattr(message, "content", None)
        if not isinstance(content, str) or _LOADED_MARKER not in content:
            continue
        tail = content.split(_LOADED_MARKER, 1)[1]
        for part in tail.replace("\n", " ").split(","):
            candidate = part.strip()
            if candidate:
                loaded.add(candidate)
    return loaded
