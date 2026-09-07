"""Resolve configured X search queries from engine config.

Runtime code must not fall back to a baked-in search query. Queries come from
``search_recent_tweets_workflow`` entries in the deployed x module config, or
from an explicit override.
"""

from __future__ import annotations

from typing import Any

X_MODULE_NAME = "naas_abi_marketplace.applications.x"

# OpenAPI / docstring examples only — never used as a runtime fallback.
EXAMPLE_X_SEARCH_QUERY = "(openai OR anthropic) lang:en -is:retweet"


def resolve_search_recent_tweets_query(
    *,
    workflow_name: str,
    engine_configuration: Any | None = None,
    override: str | None = None,
) -> str:
    """Return the configured query for *workflow_name*, or raise."""
    if override and str(override).strip():
        return str(override).strip()
    if engine_configuration is not None:
        for module in engine_configuration.modules:
            if module.module != X_MODULE_NAME:
                continue
            workflows = (module.config or {}).get("search_recent_tweets_workflow") or []
            for entry in workflows:
                if str(entry.get("name") or "") == workflow_name:
                    query = str(entry.get("query") or "").strip()
                    if query:
                        return query
            for entry in workflows:
                query = str(entry.get("query") or "").strip()
                if query:
                    return query
    raise ValueError(
        f"No X search query configured for workflow {workflow_name!r}. "
        "Set search_recent_tweets_workflow[].query in the x module config."
    )
