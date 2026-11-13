"""Every GitHub call of the Support agent stays in its configured repository."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from naas_abi_marketplace.applications.github.integrations import (
    GitHubIntegration as github_mod,
)
from naas_abi_marketplace.domains.operations.modules.support.agents.SupportAgent import (
    SupportAgent,
)

WORKFLOWS = "naas_abi_marketplace.domains.operations.modules.support.workflows"


@pytest.fixture
def tools(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    # The workflow modules read the module instance at import: stand-ins.
    for name in ("ReportBugWorkflow", "FeatureRequestWorkflow"):
        fake = ModuleType(f"{WORKFLOWS}.{name}")

        class _Workflow:
            def __init__(self, *args: object, **kwargs: object) -> None:
                pass

            def as_tools(self) -> list:
                return []

        setattr(fake, name, _Workflow)
        setattr(fake, f"{name}Configuration", lambda **kwargs: kwargs)
        monkeypatch.setitem(sys.modules, f"{WORKFLOWS}.{name}", fake)
    return {t.name: t for t in SupportAgent.get_tools("token", "my-org/support")}


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    urls: list[str] = []

    def request(method: str, url: str, **kwargs: Any) -> Any:
        urls.append(url)
        return SimpleNamespace(content=b"", raise_for_status=lambda: None)

    monkeypatch.setattr(github_mod.requests, "request", request)
    return urls


def test_support_tools_keep_to_the_configured_repository(
    tools: dict[str, Any], sent: list[str]
) -> None:
    assert "github_list_organization_repositories" not in tools

    tools["github_get_issue"].invoke({"repo_name": "my-org/support", "issue_id": "7"})
    for repo in ("my-org/private", "other/support"):
        with pytest.raises(ValueError):
            tools["github_get_issue"].invoke({"repo_name": repo, "issue_id": "1"})
        with pytest.raises(ValueError):
            tools["github_create_issue_comment"].invoke(
                {"repo_name": repo, "issue_number": 1, "body": "copied"}
            )

    assert sent == ["https://api.github.com/repos/my-org/support/issues/7"]
