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
    # A READY module serves it: installed, as a loaded module's app is, so the
    # Apps pages and the workspace settings list it.
    assert info.installed is True


def test_a_discovery_outage_still_lists_the_local_apps(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    from naas_abi.apps.nexus.apps.api.app.services.apps.remote import factory

    class Down:
        async def list_apps(self):
            raise ConnectionError("nats down")

    monkeypatch.setattr(factory, "get_remote_app_directory", lambda: Down())

    assert asyncio.run(adapter._remote_apps_catalog()) == ()


def _granting(monkeypatch: pytest.MonkeyPatch, enabled: set[str]):
    """The workspaces the app opens in (access.py), which the grant names."""
    from fastapi import HTTPException
    from naas_abi.apps.nexus.apps.api.app.services.apps.remote import access

    asked = []

    async def remote_app_workspace(user_id, app_id, workspace_id):
        asked.append((user_id, app_id, workspace_id))
        if workspace_id not in enabled:
            raise HTTPException(status_code=403, detail="You may not use this app here")
        return workspace_id

    monkeypatch.setattr(access, "remote_app_workspace", remote_app_workspace)
    return asked


@pytest.mark.asyncio
async def test_a_remote_app_opens_under_a_grant_for_the_user(
    team, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from naas_abi.apps.nexus.apps.api.app.services.apps.remote.grant import (
        read_remote_app_grant,
    )
    from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
    from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
    from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
    from naas_abi_core.services.iam.IAMService import IAMService

    # No role holds an app: a policy grants this one to the admin.
    team.allow_scope(
        "admin", ModuleScope("app", "acme.research", "console"), team.workspace("org-1", "ws-1")
    )
    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    monkeypatch.setattr(credentials, "IAM", lambda: iam)
    asked = _granting(monkeypatch, enabled={"ws-1"})
    body = adapter.RemoteAppGrantRequest(
        workspace_id="ws-1", module_id="acme.research", app="console"
    )

    answer = await adapter.create_remote_app_grant(body, SimpleNamespace(id="admin"))

    _, prefix, grant, rest = answer.path.split("/", 3)
    assert (prefix, rest) == ("app-remote", "acme.research/console/")
    opened = read_remote_app_grant(grant)
    assert opened is not None
    assert (opened.user_id, opened.module_id, opened.app, opened.workspace_id) == (
        "admin",
        "acme.research",
        "console",
        "ws-1",
    )
    assert asked == [("admin", "remote/acme.research:console", "ws-1")]
    # Eight hours at most, whatever the configuration says.
    assert (
        answer.expires_in
        == min(adapter.nexus_config.settings.remote_app_grant_expire_minutes, 8 * 60) * 60
    )


@pytest.mark.asyncio
async def test_a_remote_app_opens_only_in_a_workspace_the_user_may_open_it_in(
    team, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The grant names a workspace the user may use the app in."""
    from types import SimpleNamespace

    from fastapi import HTTPException

    _granting(monkeypatch, enabled={"ws-1"})
    body = adapter.RemoteAppGrantRequest(
        module_id="acme.research", app="console", workspace_id="ws-2"
    )

    with pytest.raises(HTTPException) as refused:
        await adapter.create_remote_app_grant(body, SimpleNamespace(id="admin"))

    assert refused.value.status_code == 403
    with pytest.raises(ValueError):
        adapter.RemoteAppGrantRequest(module_id="acme.research", app="console")


def test_a_user_can_end_their_remote_app_grants(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    from types import SimpleNamespace

    ended = []

    async def revoke(user_id: str) -> int:
        ended.append(user_id)
        return 1

    monkeypatch.setattr(adapter.links, "arevoke_remote_app_links", revoke)

    answer = asyncio.run(adapter.revoke_remote_app_grants(SimpleNamespace(id="u-1")))

    assert answer.status_code == 204
    assert ended == ["u-1"]


@pytest.mark.parametrize(
    ("module_id", "app"), [("..", "console"), ("acme/x", "console"), ("acme", "a.b"), ("acme", "")]
)
def test_a_grant_names_one_path_segment_each(module_id: str, app: str) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        adapter.RemoteAppGrantRequest(workspace_id="ws-1", module_id=module_id, app=app)


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
    adapter._scan_apps_html_assets.cache_clear()
    adapter._scan_apps_html_paths.cache_clear()
    try:
        with caplog.at_level(logging.WARNING):
            catalog = adapter._scan_apps_catalog()
            paths = adapter._scan_apps_html_paths()
    finally:
        adapter._scan_apps_catalog.cache_clear()
        adapter._scan_apps_html_assets.cache_clear()
        adapter._scan_apps_html_paths.cache_clear()

    assert [app.module_path for app in catalog] == ["acme.ops"]
    assert set(paths) == {"acme/ops/board/index.html", "acme/ops/board/manifest.json"}
    assert "Module remote: its apps are not served" in caplog.text
