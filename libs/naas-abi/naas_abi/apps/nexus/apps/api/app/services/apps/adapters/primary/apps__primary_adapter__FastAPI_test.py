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
