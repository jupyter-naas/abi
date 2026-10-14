from __future__ import annotations

from pathlib import Path

import pytest
from naas_abi.apps.nexus.apps.api.app.services.apps.adapters.primary import (
    apps__primary_adapter__FastAPI as adapter,
)


def test_module_app_dir_follows_the_catalog_asset_map(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Bob swaps the scanner for its nested layout; the lookup must follow."""
    nested = tmp_path / "src/bob/apps/sheets/budget"
    monkeypatch.setattr(
        adapter,
        "_scan_apps_html_paths",
        lambda: {"bob/budget/manifest.json": str(nested / "manifest.json")},
    )

    assert adapter.module_app_dir("bob:budget") == nested
    assert adapter.module_app_dir("bob:missing") is None
    assert adapter.module_app_dir("no-separator") is None


def test_build_app_info_reads_manifest_agent(tmp_path: Path) -> None:
    app_dir = tmp_path / "map"
    app_dir.mkdir()
    info = adapter._build_app_info(
        "operations.counter_uas",
        app_dir,
        {
            "name": "Counter-UAS Map",
            "agent": "operations.counter_uas CounterUASAgent",
        },
    )
    assert info.agent == "operations.counter_uas CounterUASAgent"


def test_remote_module_apps_join_the_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from naas_abi.apps.nexus.apps.api.app.services.apps.remote import factory
    from naas_abi.apps.nexus.apps.api.app.services.apps.remote.adapters.in_memory import (
        InMemoryRemoteAppDirectory,
    )
    from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import RemoteApp

    console = RemoteApp("acme.research", "console", "Console", "Ops", "operations", "🛰")
    monkeypatch.setattr(
        factory,
        "get_remote_app_directory",
        lambda: InMemoryRemoteAppDirectory({console: None}),
    )

    (info,) = asyncio.run(adapter._remote_apps_catalog())

    assert info.app_id == "remote/acme.research:console"
    assert info.module_path == "remote/acme.research"
    assert info.url == "/app-html/remote/acme.research/console/index.html"
    assert (info.name, info.category, info.icon_emoji) == ("Console", "operations", "🛰")


def test_a_discovery_outage_still_lists_the_local_apps(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from naas_abi.apps.nexus.apps.api.app.services.apps.remote import factory

    class Down:
        async def list_apps(self):
            raise ConnectionError("nats down")

    monkeypatch.setattr(factory, "get_remote_app_directory", lambda: Down())

    assert asyncio.run(adapter._remote_apps_catalog()) == ()


def _granting(monkeypatch: pytest.MonkeyPatch, minutes_left: float, enabled: set[str]):
    """The grant endpoint's collaborators: the session token presented (its
    expiry) and the workspaces enabling the app (access.py)."""
    from datetime import UTC, datetime, timedelta

    from fastapi import HTTPException
    from naas_abi.apps.nexus.apps.api.app.services.apps.remote import access, http_routes

    monkeypatch.setattr(http_routes, "current_secret_key", lambda: "s3cret")
    expires = datetime.now(UTC) + timedelta(minutes=minutes_left)
    monkeypatch.setattr(http_routes, "_presented_user", lambda request: ("u-1", expires))
    asked = []

    async def remote_app_workspace(user_id, app_id, workspace_id):
        asked.append((user_id, app_id, workspace_id))
        if workspace_id not in enabled:
            raise HTTPException(status_code=403, detail="This app is not enabled in this workspace")
        return workspace_id

    monkeypatch.setattr(access, "remote_app_workspace", remote_app_workspace)
    return expires, asked


def test_a_remote_app_opens_under_a_grant_for_the_user(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    from types import SimpleNamespace

    from naas_abi.apps.nexus.apps.api.app.services.apps.remote.grant import read_remote_app_grant

    _, asked = _granting(monkeypatch, minutes_left=600, enabled={"ws-1"})
    body = adapter.RemoteAppGrantRequest(
        module_id="acme.research", app="console", workspace_id="ws-1"
    )

    answer = asyncio.run(
        adapter.create_remote_app_grant(body, SimpleNamespace(), SimpleNamespace(id="u-1"))
    )

    _, prefix, grant, rest = answer.path.split("/", 3)
    assert (prefix, rest) == ("app-remote", "acme.research/console/")
    granted = read_remote_app_grant(grant, secret="s3cret")
    assert granted is not None
    assert (granted.user_id, granted.module_id, granted.app, granted.workspace_id) == (
        "u-1",
        "acme.research",
        "console",
        "ws-1",
    )
    assert asked == [("u-1", "remote/acme.research:console", "ws-1")]
    assert answer.expires_in == adapter.nexus_config.settings.remote_app_grant_expire_minutes * 60


def test_a_remote_app_grant_never_outlives_the_session_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#48 review: a 30-minute session token no longer buys an 8-hour grant."""
    import asyncio
    from types import SimpleNamespace

    from jose import jwt

    expires, _ = _granting(monkeypatch, minutes_left=10, enabled={"ws-1"})
    body = adapter.RemoteAppGrantRequest(
        module_id="acme.research", app="console", workspace_id="ws-1"
    )

    answer = asyncio.run(
        adapter.create_remote_app_grant(body, SimpleNamespace(), SimpleNamespace(id="u-1"))
    )

    claims = jwt.get_unverified_claims(answer.path.split("/")[2])
    assert claims["exp"] <= int(expires.timestamp())
    assert 9 * 60 <= answer.expires_in <= 10 * 60


def test_a_remote_app_opens_only_in_a_workspace_that_enables_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A15: the grant names a workspace the user can open, where the app is on."""
    import asyncio
    from types import SimpleNamespace

    from fastapi import HTTPException

    _granting(monkeypatch, minutes_left=600, enabled={"ws-1"})
    body = adapter.RemoteAppGrantRequest(
        module_id="acme.research", app="console", workspace_id="ws-2"
    )

    with pytest.raises(HTTPException) as refused:
        asyncio.run(
            adapter.create_remote_app_grant(body, SimpleNamespace(), SimpleNamespace(id="u-1"))
        )

    assert refused.value.status_code == 403
    with pytest.raises(ValueError):
        adapter.RemoteAppGrantRequest(module_id="acme.research", app="console")


def test_a_user_can_end_their_remote_app_grants(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    from types import SimpleNamespace

    from naas_abi.apps.nexus.apps.api.app.services.apps.remote import revocation

    revoked = []

    async def revoke(user_id: str) -> None:
        revoked.append(user_id)

    monkeypatch.setattr(revocation, "revoke_remote_app_grants", revoke)

    answer = asyncio.run(adapter.revoke_remote_app_grants(SimpleNamespace(id="u-1")))

    assert answer.status_code == 204
    assert revoked == ["u-1"]


@pytest.mark.parametrize(
    ("module_id", "app"), [("..", "console"), ("acme/x", "console"), ("acme", "a.b"), ("acme", "")]
)
def test_a_grant_names_one_path_segment_each(module_id: str, app: str) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        adapter.RemoteAppGrantRequest(module_id=module_id, app=app, workspace_id="ws-1")


def test_a_loaded_module_named_remote_does_not_take_remote_app_urls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A26: /app-html/remote/ belongs to remote modules' apps."""
    import json
    import logging

    def module_at(name: str, root: Path):
        app_dir = root / "apps" / "board"
        app_dir.mkdir(parents=True)
        (app_dir / "manifest.json").write_text(json.dumps({"name": "Board"}))
        (app_dir / "index.html").write_text("<h1>board</h1>")
        module_type = type("ABIModule", (), {"__module__": name})
        module = module_type()
        module.module_root_path = str(root)
        return module

    modules = [module_at("remote", tmp_path / "a"), module_at("acme.ops", tmp_path / "b")]
    monkeypatch.setattr(adapter, "_iter_loaded_modules", lambda: iter(modules))
    adapter._scan_apps_catalog.cache_clear()
    adapter._scan_apps_html_paths.cache_clear()
    try:
        with caplog.at_level(logging.WARNING):
            catalog = adapter._scan_apps_catalog()
            paths = adapter._scan_apps_html_paths()
    finally:
        adapter._scan_apps_catalog.cache_clear()
        adapter._scan_apps_html_paths.cache_clear()

    assert [app.module_path for app in catalog] == ["acme.ops"]
    assert set(paths) == {"acme/ops/board/index.html", "acme/ops/board/manifest.json"}
    assert "Module remote: its apps are not served" in caplog.text
