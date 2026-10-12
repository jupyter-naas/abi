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
