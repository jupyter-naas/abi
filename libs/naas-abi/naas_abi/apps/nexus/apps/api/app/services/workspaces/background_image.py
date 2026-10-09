"""Home desk wallpaper stored in the workspace drive.

An admin stages an image (uploaded, or downloaded from a URL) into
``.home/tmp/``, previews it, then commits it: the draft moves to
``.home/background-img/``, every other wallpaper and draft is removed, and the
workspace's ``background_image_url`` points at it. ``.home`` is a system folder
— the files API refuses writes there — so this module, going through
FilesService directly, is the only writer.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.services.files.drive_roots import workspace_drive_root
from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
    NotFoundError,
    RawFileData,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService

MAX_BACKGROUND_IMAGE_BYTES = 10 * 1024 * 1024
URL_FETCH_TIMEOUT_SECONDS = 15.0
MAX_URL_REDIRECTS = 3
MIN_ZOOM = 1.0
MAX_ZOOM = 4.0

# Raster formats only: SVG can carry script and is served from the API origin.
_EXTENSIONS = frozenset({".png", ".jpg", ".gif", ".webp", ".avif"})
_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
}


class BackgroundImageError(ValueError):
    """The image, its name or its source URL was refused."""


def detect_image_extension(content: bytes) -> str | None:
    """Extension from the file's magic bytes; None when it is not a supported image.

    The bytes decide, not the name or the Content-Type a client or remote
    server claims.
    """
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    if len(content) >= 12 and content[4:8] == b"ftyp" and content[8:12] in (b"avif", b"avis"):
        return ".avif"
    return None


def background_image_url(
    workspace_id: str,
    name: str,
    *,
    x: float = 50.0,
    y: float = 50.0,
    zoom: float = 1.0,
) -> str:
    """The value stored in ``workspaces.background_image_url``.

    ``v`` is the committed file name, new on every commit, so browsers never
    show a cached previous wallpaper. ``x``/``y`` (focal point, % of the image)
    and ``z`` (zoom) carry the framing chosen in the preview; defaults
    (centred, no zoom) are left out.
    """
    url = f"/api/workspaces/{workspace_id}/background-image?v={name}"
    if (x, y, zoom) != (50.0, 50.0, 1.0):
        url += f"&x={_fmt(x)}&y={_fmt(y)}&z={_fmt(zoom)}"
    return url


def _fmt(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def ensure_public_http_url(url: str) -> None:
    """Refuse anything but http(s) to a host that resolves only to public addresses.

    The server fetches this URL on the user's behalf, so it must not reach the
    internal network (MinIO, metadata endpoints, localhost services).
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise BackgroundImageError("Only http(s) image URLs are supported")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError) as exc:
        raise BackgroundImageError("Could not resolve the image URL's host") from exc
    if not infos:
        raise BackgroundImageError("Could not resolve the image URL's host")
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global or address.is_multicast:
            raise BackgroundImageError("Image URL points to a private or local address")


async def fetch_image_url(url: str, max_bytes: int = MAX_BACKGROUND_IMAGE_BYTES) -> bytes:
    """Download an image, re-checking every redirect hop against the SSRF guard."""
    import httpx

    current = url.strip()
    async with httpx.AsyncClient(
        timeout=URL_FETCH_TIMEOUT_SECONDS, follow_redirects=False
    ) as client:
        for _ in range(MAX_URL_REDIRECTS + 1):
            ensure_public_http_url(current)
            async with client.stream("GET", current) as response:
                if response.is_redirect and "location" in response.headers:
                    current = str(response.url.join(response.headers["location"]))
                    continue
                if response.status_code != 200:
                    raise BackgroundImageError(
                        f"Could not download the image (HTTP {response.status_code})"
                    )
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise BackgroundImageError(_too_large(max_bytes))
                    chunks.append(chunk)
                return b"".join(chunks)
    raise BackgroundImageError("Too many redirects")


def _too_large(max_bytes: int) -> str:
    return f"Image is too large (max {max_bytes // (1024 * 1024)} MB)"


class WorkspaceBackgroundImage:
    """Stage / preview / commit / discard one workspace's wallpaper."""

    def __init__(
        self,
        files: FilesService,
        workspace_id: str,
        max_bytes: int = MAX_BACKGROUND_IMAGE_BYTES,
    ) -> None:
        self._files = files
        home = f"{workspace_drive_root(workspace_id)}/.home"
        self._tmp = f"{home}/tmp"  # nosec B108 - workspace drive folder, not the system temp dir
        self._current = f"{home}/background-img"
        self._max_bytes = max_bytes

    def stage(self, content: bytes) -> str:
        """Write a draft to ``.home/tmp`` (replacing any earlier one); return its name."""
        if len(content) > self._max_bytes:
            raise BackgroundImageError(_too_large(self._max_bytes))
        ext = detect_image_extension(content)
        if ext is None:
            raise BackgroundImageError(
                "File is not a supported image (PNG, JPEG, GIF, WEBP or AVIF)"
            )
        self._clear(self._tmp)
        name = f"{uuid4().hex}{ext}"
        self._files.upload_file(
            filename=name, path=self._tmp, content=content, content_type=_MEDIA_TYPES[ext]
        )
        return name

    def read_draft(self, name: str) -> RawFileData:
        return self._read(self._tmp, name)

    def read_current(self, name: str) -> RawFileData:
        return self._read(self._current, name)

    def current_name(self) -> str | None:
        """File name of the wallpaper in ``.home/background-img``, if one is committed."""
        names: list[str] = []
        for entry in self._files.list_files(path=self._current).files:
            try:
                self._check_name(entry.name)
            except BackgroundImageError:
                continue
            names.append(entry.name)
        if not names:
            return None
        return sorted(names)[-1]

    def commit(self, name: str) -> str:
        """Move the draft into ``.home/background-img``; drop old wallpapers and drafts."""
        self._check_name(name)
        draft = f"{self._tmp}/{name}"
        target = f"{self._current}/{name}"
        try:
            self._files.rename(old_path=draft, new_path=target)
        except NotFoundError as exc:
            raise BackgroundImageError("Draft image not found; upload it again") from exc
        for entry in self._files.list_files(path=self._current).files:
            if entry.name != name:
                self._files.delete_path(path=entry.path)
        self._clear(self._tmp)
        return name

    def discard(self) -> None:
        self._clear(self._tmp)

    def _read(self, folder: str, name: str) -> RawFileData:
        self._check_name(name)
        try:
            return self._files.read_file_raw(path=f"{folder}/{name}")
        except NotFoundError as exc:
            raise BackgroundImageError("Image not found") from exc

    @staticmethod
    def _check_name(name: str) -> None:
        # Names are ours (uuid + ext): anything else is a crafted path.
        stem, dot, ext = name.rpartition(".")
        if not (dot and stem and stem.isalnum() and f".{ext}" in _EXTENSIONS):
            raise BackgroundImageError("Invalid image name")

    def _clear(self, folder: str) -> None:
        try:
            self._files.delete_path(path=folder)
        except NotFoundError:
            pass
