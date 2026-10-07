"""Where an organization's logo is kept, and how it is read back.

    <datastore_path>/<key>/logos/<key>.<ext>

``key`` is the organization's folder in the datastore (its universal name, e.g.
``Accor``). One logo per organization, as one portrait per person: storing a new
logo removes the previous one in another format. The graph records the stored
path and the address the module's API serves it at (``read_logo``).
"""

from __future__ import annotations

from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)

MEDIA_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "svg": "image/svg+xml",
    "ico": "image/x-icon",
    "avif": "image/avif",
}
EXTENSIONS = {media_type: ext for ext, media_type in MEDIA_TYPES.items() if ext != "jpeg"}
EXTENSIONS["image/jpg"] = "jpg"
EXTENSIONS["image/vnd.microsoft.icon"] = "ico"


class InvalidLogoError(ValueError):
    """The content is not an image a logo can be stored as."""


def is_valid_key(key: str) -> bool:
    return bool(key) and "/" not in key and "\\" not in key and key not in {".", ".."}


def logos_prefix(datastore_path: str, key: str) -> str:
    return f"{datastore_path.rstrip('/')}/{key}/logos"


def extension_for(media_type: str) -> str:
    extension = EXTENSIONS.get(media_type.split(";")[0].strip().lower())
    if extension is None:
        raise InvalidLogoError(f"not an image: {media_type or 'no content type'}")
    return extension


def _stored_names(storage: ObjectStorageService, prefix: str) -> list[str]:
    try:
        return [key.rsplit("/", 1)[-1] for key in storage.list_objects(prefix)]
    except Exceptions.ObjectNotFound:
        return []


def write_logo(
    storage: ObjectStorageService,
    datastore_path: str,
    key: str,
    content: bytes,
    extension: str,
) -> str:
    """Store the logo as ``<key>.<extension>``; return its object-storage path."""
    if not is_valid_key(key):
        raise ValueError(f"invalid organization key: {key!r}")
    if extension not in MEDIA_TYPES or not content:
        raise InvalidLogoError(f"cannot store a logo as .{extension}")
    prefix = logos_prefix(datastore_path, key)
    name = f"{key}.{extension}"
    for stored in _stored_names(storage, prefix):
        if stored != name and stored.rsplit(".", 1)[0] == key:
            storage.delete_object(prefix, stored)
    storage.put_object(prefix, name, content)
    return f"{prefix}/{name}"


def read_logo(
    storage: ObjectStorageService, datastore_path: str, key: str, name: str
) -> tuple[bytes, str] | None:
    """``(bytes, media type)`` of logo ``<key>.<ext>``, or ``None`` if it is not stored."""
    stem, _, extension = name.rpartition(".")
    if not is_valid_key(key) or stem != key or extension not in MEDIA_TYPES:
        return None
    try:
        content = storage.get_object(logos_prefix(datastore_path, key), name)
    except Exceptions.ObjectNotFound:
        return None
    return content, MEDIA_TYPES[extension]
