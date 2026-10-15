from __future__ import annotations

from datetime import datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.auth.avatar_store import (
    ORG_AVATAR_BASENAME,
    avatar_prefix,
    avatar_url,
    read_avatar,
    remove_avatar,
    save_avatar,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions

T1 = datetime(2026, 10, 14, 9, 30, 0)
T2 = datetime(2026, 10, 14, 10, 0, 5)


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def get_object(self, prefix: str, key: str) -> bytes:
        try:
            return self.objects[(prefix, key)]
        except KeyError:
            raise Exceptions.ObjectNotFound(f"{prefix}/{key}") from None

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self.objects[(prefix, key)] = content

    def delete_object(self, prefix: str, key: str) -> None:
        self.objects.pop((prefix, key), None)

    def paths(self) -> set[str]:
        return {f"{prefix}/{key}" for prefix, key in self.objects}


def test_layout_is_in_the_personal_drive() -> None:
    assert avatar_prefix("user-1") == "naas_abi/my-drive/user-1/.settings/avatar"
    assert avatar_url("user-1", "abcdef0123456789") == "/api/auth/avatar/user/user-1?v=abcdef012345"


def test_first_upload_stores_the_current_picture() -> None:
    storage = MemoryStorage()

    result = save_avatar(storage, "user-1", b"png-1", ".PNG", T1)

    assert result.changed is True and result.archived_key is None
    assert storage.paths() == {"naas_abi/my-drive/user-1/.settings/avatar/avatar.png"}
    assert read_avatar(storage, "user-1").content == b"png-1"


def test_same_bytes_change_nothing() -> None:
    storage = MemoryStorage()
    first = save_avatar(storage, "user-1", b"png-1", ".png", T1)

    again = save_avatar(storage, "user-1", b"png-1", ".png", T2)

    assert again.changed is False and again.digest == first.digest
    assert len(storage.paths()) == 1


def test_new_picture_archives_the_previous_one() -> None:
    storage = MemoryStorage()
    save_avatar(storage, "user-1", b"png-1", ".png", T1)

    result = save_avatar(storage, "user-1", b"jpg-2", ".jpg", T2)

    assert result.changed is True
    assert result.archived_key == "20261014T100005Z_avatar.png"
    assert storage.paths() == {
        "naas_abi/my-drive/user-1/.settings/avatar/avatar.jpg",
        "naas_abi/my-drive/user-1/.settings/avatar/archives/20261014T100005Z_avatar.png",
    }
    current = read_avatar(storage, "user-1")
    assert (current.key, current.content) == ("avatar.jpg", b"jpg-2")


def test_remove_archives_then_deletes() -> None:
    storage = MemoryStorage()
    save_avatar(storage, "user-1", b"png-1", ".png", T1)

    assert remove_avatar(storage, "user-1", T2) == "20261014T100005Z_avatar.png"
    assert read_avatar(storage, "user-1") is None
    assert storage.paths() == {
        "naas_abi/my-drive/user-1/.settings/avatar/archives/20261014T100005Z_avatar.png"
    }
    assert remove_avatar(storage, "user-1", T2) is None


def test_rejects_other_extensions() -> None:
    with pytest.raises(ValueError):
        save_avatar(MemoryStorage(), "user-1", b"x", ".svg", T1)


def test_works_with_the_filesystem_storage(tmp_path) -> None:
    from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
        ObjectStorageSecondaryAdapterFS,
    )
    from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

    storage = ObjectStorageService(adapter=ObjectStorageSecondaryAdapterFS(base_path=str(tmp_path)))
    save_avatar(storage, "user-1", b"png-1", ".png", T1)
    save_avatar(storage, "user-1", b"webp-2", ".webp", T2)

    assert read_avatar(storage, "user-1").content == b"webp-2"
    root = tmp_path / "naas_abi" / "my-drive" / "user-1" / ".settings" / "avatar"
    assert (root / "avatar.webp").read_bytes() == b"webp-2"
    assert (root / "archives" / "20261014T100005Z_avatar.png").read_bytes() == b"png-1"
    assert not (root / "avatar.png").exists()


def test_org_picture_lives_next_to_the_account_picture() -> None:
    storage = MemoryStorage()
    save_avatar(storage, "user-1", b"account", ".png", T1)

    save_avatar(storage, "user-1", b"org-1", ".png", T1, basename=ORG_AVATAR_BASENAME)
    result = save_avatar(storage, "user-1", b"org-2", ".jpg", T2, basename=ORG_AVATAR_BASENAME)

    assert result.archived_key == "20261014T100005Z_avatar_org.png"
    assert storage.paths() == {
        "naas_abi/my-drive/user-1/.settings/avatar/avatar.png",
        "naas_abi/my-drive/user-1/.settings/avatar/avatar_org.jpg",
        "naas_abi/my-drive/user-1/.settings/avatar/archives/20261014T100005Z_avatar_org.png",
    }
    assert read_avatar(storage, "user-1").content == b"account"
    assert read_avatar(storage, "user-1", ORG_AVATAR_BASENAME).extension == ".jpg"
    assert avatar_url("user-1", "abcdef0123456789", ORG_AVATAR_BASENAME) == (
        "/api/auth/avatar/user/user-1/org?v=abcdef012345"
    )
    assert remove_avatar(storage, "user-1", T2, basename=ORG_AVATAR_BASENAME)
    assert read_avatar(storage, "user-1", ORG_AVATAR_BASENAME) is None
    assert read_avatar(storage, "user-1").content == b"account"
