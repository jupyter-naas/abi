from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.services.apps.remote import access
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AuthzDenied, ModuleScope

APP = "remote/acme.research:console"


class Registry:
    """The workspaces a user can open and those where IAM lets them open the app."""

    def __init__(self, members: dict[str, list[str]], granted: dict[str, set[str]]):
        self.members, self.granted = members, granted
        self.workspaces = SimpleNamespace(list_workspaces=self._list)
        # IAM's ``module:OpenApp`` on the app: the workspaces granting it.
        self.authz = SimpleNamespace(require_scope=self._require, allowed_scope=self._allowed)

    async def _allowed(self, scope: ModuleScope, *, user: str, workspace: str) -> bool:
        assert scope == ModuleScope("app", "acme.research", "console")
        return workspace in self.granted.get(user, set())

    async def _require(self, scope: ModuleScope, *, user: str, workspace: str) -> None:
        if not await self._allowed(scope, user=user, workspace=workspace):
            raise AuthzDenied(403, detail="You may not use this app here")

    async def _list(self, user_id: str):
        return [SimpleNamespace(id=w, slug=w) for w in self.members.get(user_id, [])]


REGISTRY = Registry({"u-1": ["ws-a", "ws-b", "ws-c"]}, {"u-1": {"ws-b", "ws-c"}})


@pytest.fixture(autouse=True)
def iam(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(access, "authz", REGISTRY.authz)


@pytest.mark.asyncio
async def test_the_named_workspace_is_where_iam_lets_the_user_open_the_app() -> None:
    assert await access.choose_workspace(REGISTRY, "u-1", APP, "ws-c") == "ws-c"
    for workspace_id in ("ws-a", "ws-z"):
        with pytest.raises(HTTPException) as refused:
            await access.choose_workspace(REGISTRY, "u-1", APP, workspace_id)
        assert refused.value.status_code == 403


@pytest.mark.asyncio
async def test_without_a_workspace_the_first_where_iam_allows_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert await access.choose_workspace(REGISTRY, "u-1", APP, None) == "ws-b"
    # The same one whatever order the store lists them in.
    shuffled = Registry({"u-1": ["ws-c", "ws-a", "ws-b"]}, REGISTRY.granted)
    monkeypatch.setattr(access, "authz", shuffled.authz)
    assert await access.choose_workspace(shuffled, "u-1", APP, None) == "ws-b"
    monkeypatch.setattr(access, "authz", REGISTRY.authz)
    with pytest.raises(HTTPException) as refused:
        await access.choose_workspace(REGISTRY, "u-2", APP, None)
    assert refused.value.status_code == 403


@pytest.mark.asyncio
async def test_unknown_app_is_not_found() -> None:
    with pytest.raises(HTTPException) as refused:
        await access.choose_workspace(REGISTRY, "u-1", "no-scope", "ws-b")
    assert refused.value.status_code == 404
