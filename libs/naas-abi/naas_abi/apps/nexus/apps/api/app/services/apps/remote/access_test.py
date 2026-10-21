from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.services.apps.remote import access
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AuthzDenied

APP = "remote/acme.research:console"


class Registry:
    """The workspaces a user can open and the apps each enables."""

    def __init__(self, members: dict[str, list[str]], enabled: dict[str, set[str]]):
        self.members, self.enabled = members, enabled
        self.workspaces = SimpleNamespace(get_workspace=self._get, list_workspaces=self._list)
        self.apps = SimpleNamespace(get_enabled_states=self._states)
        # IAM's ``nexus:UseApp``: the workspaces a user is a member of.
        self.authz = SimpleNamespace(require=self._require, allowed=self._allowed)

    async def _allowed(self, action: str, *, user: str, workspace: str, id: str) -> bool:
        assert (action, id) == ("UseApp", APP)
        return workspace in self.members.get(user, [])

    async def _require(self, action: str, *, user: str, workspace: str, id: str) -> None:
        if not await self._allowed(action, user=user, workspace=workspace, id=id):
            raise AuthzDenied(403, detail="You do not have access to this workspace")

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


@pytest.fixture(autouse=True)
def iam(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(access, "authz", REGISTRY.authz)


@pytest.mark.asyncio
async def test_the_named_workspace_must_be_the_users_and_enable_the_app() -> None:
    assert await access.choose_workspace(REGISTRY, "u-1", APP, "ws-c") == "ws-c"
    for workspace_id, reason in (("ws-a", "not enabled"), ("ws-z", "do not have access")):
        with pytest.raises(HTTPException) as refused:
            await access.choose_workspace(REGISTRY, "u-1", APP, workspace_id)
        assert refused.value.status_code == 403
        assert reason in refused.value.detail


@pytest.mark.asyncio
async def test_without_a_workspace_the_first_that_enables_the_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert await access.choose_workspace(REGISTRY, "u-1", APP, None) == "ws-b"
    # The same one whatever order the store lists them in.
    shuffled = Registry({"u-1": ["ws-c", "ws-a", "ws-b"]}, REGISTRY.enabled)
    monkeypatch.setattr(access, "authz", shuffled.authz)
    assert await access.choose_workspace(shuffled, "u-1", APP, None) == "ws-b"
    monkeypatch.setattr(access, "authz", REGISTRY.authz)
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
