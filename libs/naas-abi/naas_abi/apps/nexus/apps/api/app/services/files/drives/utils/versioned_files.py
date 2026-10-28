"""Versioned files in a drive: the current file plus archived previous versions.

Used for settings files and pictures (account avatar, organization member
picture, workspace logo). For a folder ``<prefix>``:

    <prefix>/<name>                          the current file
    <prefix>/archives/<ts>_<name>            previous versions

A write whose bytes match the current file (same SHA-256) changes nothing.
Otherwise the current file is copied to ``archives/`` first, so replacing or
removing a file never loses the old one.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime

from naas_abi_core.services.object_storage.ObjectStoragePort import (
    Exceptions as StorageExceptions,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

ARCHIVES_DIR = "archives"
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")


def archives_prefix(prefix: str) -> str:
    return f"{prefix}/{ARCHIVES_DIR}"


def timestamp(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%SZ")


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def archive(
    storage: ObjectStorageService, prefix: str, key: str, content: bytes, now: datetime
) -> str:
    """Copy ``content`` (the current ``key``) to ``archives/<ts>_<key>``; returns that key."""
    archived_key = f"{timestamp(now)}_{key}"
    storage.put_object(archives_prefix(prefix), archived_key, content)
    return archived_key


@dataclass
class VersionedSaveResult:
    #: False when the stored file already held exactly this content.
    changed: bool
    archived_key: str | None = None


def save_versioned(
    storage: ObjectStorageService, prefix: str, key: str, content: bytes, now: datetime
) -> VersionedSaveResult:
    """Write ``<prefix>/<key>`` if it changed, archiving the previous version."""
    try:
        current = storage.get_object(prefix, key)
    except StorageExceptions.ObjectNotFound:
        current = None
    if current == content:
        return VersionedSaveResult(changed=False)
    archived_key = archive(storage, prefix, key, current, now) if current is not None else None
    storage.put_object(prefix, key, content)
    return VersionedSaveResult(changed=True, archived_key=archived_key)


@dataclass
class StoredImage:
    key: str
    content: bytes

    @property
    def extension(self) -> str:
        return os.path.splitext(self.key)[1]


@dataclass
class ImageSaveResult:
    key: str
    digest: str
    #: False when the upload matched the current picture byte for byte.
    changed: bool
    archived_key: str | None = None


def read_image(
    storage: ObjectStorageService,
    prefix: str,
    basename: str,
    extensions: tuple[str, ...] = IMAGE_EXTENSIONS,
) -> StoredImage | None:
    """The current ``<basename>.<ext>``, whatever its extension, or None."""
    for extension in extensions:
        key = f"{basename}{extension}"
        try:
            return StoredImage(key=key, content=storage.get_object(prefix, key))
        except StorageExceptions.ObjectNotFound:
            continue
    return None


def save_image(
    storage: ObjectStorageService,
    prefix: str,
    basename: str,
    content: bytes,
    extension: str,
    now: datetime,
    extensions: tuple[str, ...] = IMAGE_EXTENSIONS,
) -> ImageSaveResult:
    """Store ``content`` as ``<basename><extension>``, archiving the previous one if it differs."""
    extension = extension.lower()
    if extension not in extensions:
        raise ValueError(f"Unsupported image extension: {extension}")
    content_digest = digest(content)
    current = read_image(storage, prefix, basename, extensions)
    if current is not None and digest(current.content) == content_digest:
        return ImageSaveResult(key=current.key, digest=content_digest, changed=False)

    archived_key = (
        archive(storage, prefix, current.key, current.content, now) if current is not None else None
    )
    key = f"{basename}{extension}"
    storage.put_object(prefix, key, content)
    if current is not None and current.key != key:
        # Different extension: drop the old file, or read_image could still find it first.
        storage.delete_object(prefix, current.key)
    return ImageSaveResult(key=key, digest=content_digest, changed=True, archived_key=archived_key)


def remove_image(
    storage: ObjectStorageService,
    prefix: str,
    basename: str,
    now: datetime,
    extensions: tuple[str, ...] = IMAGE_EXTENSIONS,
) -> str | None:
    """Archive and remove the current picture; returns the archived key, or None if none."""
    current = read_image(storage, prefix, basename, extensions)
    if current is None:
        return None
    archived_key = archive(storage, prefix, current.key, current.content, now)
    storage.delete_object(prefix, current.key)
    return archived_key
