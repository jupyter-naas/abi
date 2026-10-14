from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.services.apps.remote import access
from naas_abi.apps.nexus.apps.api.app.services.workspaces import WorkspacePermissionError

APP = "remote/acme.research:console"


class Registry:
    """The workspaces a user can open and the apps each enables."""

    def __init__(self, members: dict[str, list[str]], enabled: dict[str, set[str]]):
        self.members, self.enabled = members, enabled
        self.workspaces = SimpleNamespace(
            require_workspace_access=self._require,
            get_workspace=self._get,
            list_workspaces=self._list,
        )
        self.apps = SimpleNamespace(get_enabled_states=self._states)

    async def _require(self, user_id: str, workspace_id: str) -> str:
        if workspace_id not in self.members.get(user_id, []):
            raise WorkspacePermissionError(workspace_id=workspace_id, user_id=user_id)
        return "member"

    async def _get(self, workspace_id: str):
        return SimpleNamespace(id=workspace_id, slug=workspace_id)

    async def _list(self, user_id: str):
        return [SimpleNamespace(id=w, slug=w) for w in self.members.get(user_id, [])]

    async def _states(self, workspace_id: str) -> dict[str, bool]:
        return dict.fromkeys(self.enabled.get(workspace_id, set()), True)


REGISTRY = Registry(
    {"u-1": ["ws-a", "ws-b", "ws-c"]},
    {"ws-b": {APP}, "ws-c": {APP}, "ws-z": {APP}},
)


@pytest.mark.asyncio
async def test_the_named_workspace_must_be_the_users_and_enable_the_app() -> None:
    assert await access.choose_workspace(REGISTRY, "u-1", APP, "ws-c") == "ws-c"
    for workspace_id, reason in (("ws-a", "not enabled"), ("ws-z", "do not have access")):
        with pytest.raises(HTTPException) as refused:
            await access.choose_workspace(REGISTRY, "u-1", APP, workspace_id)
        assert refused.value.status_code == 403
        assert reason in refused.value.detail


@pytest.mark.asyncio
async def test_without_a_workspace_the_first_that_enables_the_app() -> None:
    assert await access.choose_workspace(REGISTRY, "u-1", APP, None) == "ws-b"
    with pytest.raises(HTTPException) as refused:
        await access.choose_workspace(REGISTRY, "u-2", APP, None)
    assert refused.value.status_code == 403


@pytest.mark.asyncio
async def test_a_workspace_seed_enables_an_app_without_a_stored_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        access,
        "workspace_seed_for_slug",
        lambda slug: SimpleNamespace(apps=[APP]) if slug == "ws-a" else None,
    )

    assert await access.choose_workspace(REGISTRY, "u-1", APP, "ws-a") == "ws-a"
