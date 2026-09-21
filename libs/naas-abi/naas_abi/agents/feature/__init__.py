"""Nexus feature office agents: open-feature context and shared construction.

One office agent per Nexus section (Slides-parity). See ``SlidesAgent`` for
the reference and ``AppsAgent`` for the first generic one.
"""

from naas_abi.agents.feature.builder import (
    DEFAULT_FEATURE_MODEL,
    FEATURE_GROUNDING_GUIDELINES,
    FEATURE_RECURSION_LIMIT,
    build_feature_agent,
    configured_feature_model,
    feature_handoff_intents,
    feature_system_prompt,
    render_tools_section,
    roster_line,
)
from naas_abi.agents.feature.context import (
    active_feature_resource_id,
    bind_feature_context,
    nexus_feature_context,
    normalize_feature_context,
    render_feature_context_block,
)

__all__ = [
    "DEFAULT_FEATURE_MODEL",
    "FEATURE_GROUNDING_GUIDELINES",
    "FEATURE_RECURSION_LIMIT",
    "active_feature_resource_id",
    "bind_feature_context",
    "build_feature_agent",
    "configured_feature_model",
    "feature_handoff_intents",
    "feature_system_prompt",
    "nexus_feature_context",
    "normalize_feature_context",
    "render_feature_context_block",
    "render_tools_section",
    "roster_line",
]
