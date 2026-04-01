from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam.port import TokenData
from naas_abi.apps.nexus.apps.api.app.services.iam.service import (
    IAMPermissionError,
    IAMService,
)


def _token(scopes: set[str], user_id: str = "user-1") -> TokenData:
    return TokenData(user_id=user_id, scopes=scopes, is_authenticated=True)


def test_exact_scope_allows() -> None:
    service = IAMService()
    assert service.is_allowed(_token({"workspace.members.read"}), "workspace.members.read") is True


def test_wildcard_scope_allows_nested_scope() -> None:
    service = IAMService()
    assert service.is_allowed(_token({"workspace.*"}), "workspace.members.update") is True


def test_wildcard_in_middle_allows() -> None:
    service = IAMService()
    assert service.is_allowed(_token({"workspace.*.read"}), "workspace.members.read") is True


def test_missing_scope_denies() -> None:
    service = IAMService()
    assert (
        service.is_allowed(_token({"workspace.members.read"}), "workspace.members.update") is False
    )


def test_unauthenticated_denies() -> None:
    service = IAMService()
    token = TokenData(user_id="", scopes={"workspace.*"}, is_authenticated=False)
    assert service.is_allowed(token, "workspace.members.read") is False


def test_ensure_raises_on_missing_scope() -> None:
    service = IAMService()
    with pytest.raises(IAMPermissionError) as err:
        service.ensure(_token({"workspace.members.read"}), "workspace.members.update")
    assert err.value.scope == "workspace.members.update"
