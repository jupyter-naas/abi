from __future__ import annotations

from typing import Any

from naas_abi_core.services.gatekeeper.GatekeeperPort import (
    GatekeeperResource,
    IGatekeeperPolicy,
    Sensitivity,
)

GITHUB_TOOL_PREFIX = "github_"

SENSITIVE_GITHUB_TOOLS: frozenset[str] = frozenset(
    {
        "github_list_repository_secrets",
        "github_get_repository_secret",
        "github_create_or_update_repository_secret",
        "github_delete_repository_secret",
        "github_delete_organization_repository",
    }
)


class GitHubGatekeeperPolicy(IGatekeeperPolicy):
    """Pilot policy: sensitive GitHub tools require an explicit session grant."""

    def classify_tool(self, tool_name: str) -> Sensitivity:
        if tool_name in SENSITIVE_GITHUB_TOOLS:
            return "sensitive"
        return "normal"

    def extract_resources(
        self, tool_name: str, tool_args: dict[str, Any]
    ) -> list[GatekeeperResource]:
        if not tool_name.startswith(GITHUB_TOOL_PREFIX):
            return []

        repo_name = tool_args.get("repo_name")
        if isinstance(repo_name, str) and repo_name.strip():
            return [
                GatekeeperResource(type="github.repo", id=repo_name.strip()),
            ]

        org = tool_args.get("org")
        if isinstance(org, str) and org.strip():
            return [
                GatekeeperResource(type="github.org", id=org.strip()),
            ]

        return []

    def required_action(self, tool_name: str) -> str:
        if tool_name in SENSITIVE_GITHUB_TOOLS:
            if "secret" in tool_name:
                return "read_secrets"
            if tool_name == "github_delete_organization_repository":
                return "delete_repo"
        if tool_name.startswith(GITHUB_TOOL_PREFIX):
            return "invoke"
        return "invoke"
