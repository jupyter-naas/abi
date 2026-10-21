from __future__ import annotations

from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.auth.avatar_store_test import MemoryStorage
from naas_abi.apps.nexus.apps.api.app.services.workspaces.logo_store import (
    logo_url,
    read_logo,
    remove_logo,
    save_logo,
)

T1 = datetime(2026, 10, 14, 9, 0, 0)
T2 = datetime(2026, 10, 14, 10, 0, 5)
PREFIX = "naas_abi/workspace-drive/ws-1/.settings/logos"


def test_logo_lives_in_the_workspace_drive_with_archives() -> None:
    storage = MemoryStorage()
    first = save_logo(storage, "ws-1", b"<svg/>", ".svg", T1)
    assert save_logo(storage, "ws-1", b"<svg/>", ".svg", T2).changed is False

    second = save_logo(storage, "ws-1", b"png", ".png", T2)

    assert first.changed and second.changed
    assert second.archived_key == "20261014T100005Z_logo.svg"
    assert storage.paths() == {
        f"{PREFIX}/logo.png",
        f"{PREFIX}/archives/20261014T100005Z_logo.svg",
    }
    assert read_logo(storage, "ws-1").extension == ".png"
    assert logo_url("ws-1", second.digest).startswith("/api/workspaces/ws-1/logo?v=")
    assert remove_logo(storage, "ws-1", T2) is not None
    assert read_logo(storage, "ws-1") is None
