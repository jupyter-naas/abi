"""Object storage keys a Maps record may name (layer data, feed logo).

A key is relative to the environment's object storage prefix, so the same
module manifest works in dev and prod. It always comes from a stored record,
never from a request, and is checked here before it is stored or read.
"""

from __future__ import annotations

import re

MAX_KEY_LENGTH = 300
_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

DATA_EXTENSIONS = (".geojson", ".json")
_IMAGE_TYPES = {
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}
IMAGE_EXTENSIONS = tuple(_IMAGE_TYPES)


def is_storage_key(value: str, extensions: tuple[str, ...]) -> bool:
    """A relative ``a/b/c.ext`` key: no ``..``, no empty or hidden segment, known extension."""
    if not value or len(value) > MAX_KEY_LENGTH:
        return False
    if not value.lower().endswith(extensions):
        return False
    return all(_SEGMENT.match(part) and part != ".." for part in value.split("/"))


def split_key(value: str) -> tuple[str, str]:
    """``(prefix, name)`` as the object storage service takes them."""
    prefix, _, name = value.rpartition("/")
    return prefix, name


def image_content_type(value: str) -> str | None:
    for extension, content_type in _IMAGE_TYPES.items():
        if value.lower().endswith(extension):
            return content_type
    return None
