"""Where a person's portrait is kept, and how it is read back.

    <datastore_path>/<slug>/portraits/<slug>.<ext>

One portrait per person: storing a new one removes the previous one in another
format. The graph's abi:Portrait records the stored path and the address the
module's API serves it at (``read_portrait``).
"""

from __future__ import annotations

import re

from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)

MEDIA_TYPES = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
}
EXTENSIONS = {media_type: ext for ext, media_type in MEDIA_TYPES.items()}
EXTENSIONS["image/jpg"] = "jpeg"
SLUG = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


class InvalidPortraitError(ValueError):
    """The content is not an image a portrait can be stored as."""


def portraits_prefix(datastore_path: str, slug: str) -> str:
    return f"{datastore_path.rstrip('/')}/{slug}/portraits"


def extension_for(media_type: str) -> str:
    extension = EXTENSIONS.get(media_type.split(";")[0].strip().lower())
    if extension is None:
        raise InvalidPortraitError(f"not a portrait image: {media_type or 'no content type'}")
    return extension


def _stored_names(storage: ObjectStorageService, prefix: str) -> list[str]:
    try:
        return [key.rsplit("/", 1)[-1] for key in storage.list_objects(prefix)]
    except Exceptions.ObjectNotFound:
        return []


def write_portrait(
    storage: ObjectStorageService,
    datastore_path: str,
    slug: str,
    content: bytes,
    extension: str,
) -> str:
    """Store the portrait as ``<slug>.<extension>``; return its object-storage path."""
    if not SLUG.match(slug):
        raise ValueError(f"invalid person slug: {slug!r}")
    if extension not in MEDIA_TYPES or not content:
        raise InvalidPortraitError(f"cannot store a portrait as .{extension}")
    prefix = portraits_prefix(datastore_path, slug)
    name = f"{slug}.{extension}"
    for stored in _stored_names(storage, prefix):
        if stored != name and stored.rsplit(".", 1)[0] == slug:
            storage.delete_object(prefix, stored)
    storage.put_object(prefix, name, content)
    return f"{prefix}/{name}"


def read_portrait(
    storage: ObjectStorageService, datastore_path: str, name: str
) -> tuple[bytes, str] | None:
    """``(bytes, media type)`` of portrait ``<slug>.<ext>``, or ``None`` if not stored."""
    slug, _, extension = name.rpartition(".")
    if not SLUG.match(slug) or extension not in MEDIA_TYPES:
        return None
    try:
        content = storage.get_object(portraits_prefix(datastore_path, slug), name)
    except Exceptions.ObjectNotFound:
        return None
    return content, MEDIA_TYPES[extension]
