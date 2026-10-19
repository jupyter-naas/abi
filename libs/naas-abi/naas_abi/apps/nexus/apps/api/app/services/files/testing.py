"""Test support for the drives a user owns.

My drive (``naas_abi/my-drive/<user>``) and the storage ``abi-platform`` moves
data through (``users/<user>``) belong to no workspace, so a user reaches them
through rows of ``roles.PLATFORM_TYPES``: viewers read them, members write them.
``personal_drive_rows`` are those rows, for a test of a router that serves them
against a real IAM.
"""

from __future__ import annotations

from naas_abi_core.services.iam import roles

_READ = ("ListObjects", "ListObjectsRecursive", "GetObject", "GetObjectMetadata", "GetObjectStream")
_WRITE = ("PutObject", "PutObjectStream", "DeleteObject")


def _row(service: str, base: str, viewer: tuple[str, ...], member: tuple[str, ...]):
    return roles._PlatformRow(service, (base, f"{base}/*"), viewer=viewer, member=member)


def personal_drive_rows() -> tuple[roles._PlatformRow, ...]:
    mine = "${principal.id}"
    return (
        _row(
            "nexus", f"my_file/{mine}", ("ListMyFiles", "GetMyFile"), ("PutMyFile", "DeleteMyFile")
        ),
        _row(
            "nexus",
            f"user_storage/{mine}",
            ("ListUserStorage", "GetUserStorage"),
            ("PutUserStorage",),
        ),
        _row("object_storage", f"object/naas_abi/my-drive/{mine}", _READ, _WRITE),
        _row("object_storage", f"object/users/{mine}", _READ, _WRITE),
    )


def with_personal_drive_rows() -> tuple[roles._PlatformRow, ...]:
    """``roles.PLATFORM_TYPES`` plus the rows above it does not carry yet."""
    present = {(row.service, row.resources) for row in roles.PLATFORM_TYPES}
    return (
        *roles.PLATFORM_TYPES,
        *(row for row in personal_drive_rows() if (row.service, row.resources) not in present),
    )
