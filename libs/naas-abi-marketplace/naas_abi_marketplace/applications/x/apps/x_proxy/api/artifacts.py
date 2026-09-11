"""Publish small direct post/user documents and durable same-origin media."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import (
    DEFAULT_APP_PREFIX,
    content_digest,
    encode_compact,
)

ARTIFACT_FORMAT = 1
MEDIA_BACKFILL_DAYS = 30
MAX_MEDIA_BYTES = 25 * 1024 * 1024
MEDIA_HOSTS = {"pbs.twimg.com", "video.twimg.com"}
_HANDLE = re.compile(r"^[A-Za-z0-9_]{1,64}$")


def post_id_of(post: dict[str, Any]) -> str:
    explicit = str(post.get("tweet_id") or "").strip()
    if explicit:
        return explicit
    match = re.search(r"/status/(\d+)", str(post.get("url") or ""))
    return match.group(1) if match else ""


def user_artifact_key(username: str) -> tuple[str, str]:
    handle = username.strip().lstrip("@")
    if not _HANDLE.fullmatch(handle):
        raise ValueError(f"Unsafe X username {username!r}")
    return f"users/by-handle/{handle.lower()}", "user.json"


def post_artifact_key(tweet_id: str) -> tuple[str, str]:
    if not tweet_id.isdigit():
        raise ValueError(f"Unsafe X post id {tweet_id!r}")
    return f"posts/by-id/{tweet_id}", "post.json"


def _read_json(storage: ObjectStorageService, prefix: str, key: str) -> dict:
    try:
        value = json.loads(storage.get_object(prefix, key))
    except Exception:  # noqa: BLE001 - absent/corrupt artifacts are rebuilt
        return {}
    return value if isinstance(value, dict) else {}


def _extension(content_type: str, source_url: str) -> str:
    media_type = content_type.split(";", 1)[0].strip().lower()
    extension = mimetypes.guess_extension(media_type) or ""
    if extension == ".jpe":
        extension = ".jpg"
    if not extension:
        suffix = urlparse(source_url).path.rsplit("/", 1)[-1].rsplit(".", 1)
        extension = f".{suffix[-1].lower()}" if len(suffix) == 2 else ".bin"
    return extension if re.fullmatch(r"\.[a-z0-9]{1,5}", extension) else ".bin"


def _download_media(
    storage: ObjectStorageService,
    *,
    source_url: str,
    prefix: str,
) -> str | None:
    parsed = urlparse(source_url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in MEDIA_HOSTS:
        logger.warning(f"X artifact media: rejected URL {source_url!r}")
        return None
    try:
        request = Request(source_url, headers={"User-Agent": "AXI-X-Proxy/1.0"})
        with urlopen(request, timeout=15) as response:
            final = urlparse(response.geturl())
            if (
                final.scheme != "https"
                or (final.hostname or "").lower() not in MEDIA_HOSTS
            ):
                raise ValueError("redirect left approved X media hosts")
            content_type = str(response.headers.get("Content-Type") or "")
            if not content_type.startswith(("image/", "video/")):
                raise ValueError(f"unsupported content type {content_type!r}")
            body = bytearray()
            while chunk := response.read(64 * 1024):
                body.extend(chunk)
                if len(body) > MAX_MEDIA_BYTES:
                    raise ValueError("media exceeds size limit")
    except Exception as exc:  # noqa: BLE001 - one attachment must not fail publish
        logger.warning(f"X artifact media: download failed for {source_url!r} ({exc})")
        return None

    digest = hashlib.sha256(body).hexdigest()
    filename = f"{digest}{_extension(content_type, source_url)}"
    storage.put_object(prefix, filename, bytes(body))
    return filename


def _localize_post_media(
    storage: ObjectStorageService, post: dict[str, Any], tweet_id: str
) -> tuple[dict[str, Any], bool]:
    localized = dict(post)
    source_urls = str(post.get("media_url") or "").split()
    if not source_urls:
        return localized, True
    prefix = f"{DEFAULT_APP_PREFIX}/posts/by-id/{tweet_id}/media"
    local_urls: list[str] = []
    complete = True
    for source_url in source_urls:
        filename = _download_media(storage, source_url=source_url, prefix=prefix)
        if filename:
            local_urls.append(f"posts/by-id/{tweet_id}/media/{filename}")
        else:
            complete = False
    localized["source_media_urls"] = source_urls
    if local_urls:
        localized["media_url"] = " ".join(local_urls)
    else:
        localized.pop("media_url", None)
    return localized, complete


def publish_post(
    storage: ObjectStorageService,
    post: dict[str, Any],
    *,
    force: bool = False,
) -> dict[str, Any]:
    tweet_id = post_id_of(post)
    prefix_rel, key = post_artifact_key(tweet_id)
    prefix = f"{DEFAULT_APP_PREFIX}/{prefix_rel}"
    source_hash = content_digest(encode_compact(post))
    existing = _read_json(storage, prefix, key)
    if (
        not force
        and existing.get("format") == ARTIFACT_FORMAT
        and existing.get("source_hash") == source_hash
        and (
            existing.get("media_complete") is True
            or int(existing.get("media_attempts") or 0) >= 3
        )
    ):
        return {"post_id": tweet_id, "skipped": True, "media_complete": True}

    localized, complete = _localize_post_media(storage, post, tweet_id)
    document = {
        "format": ARTIFACT_FORMAT,
        "updated_at": datetime.now(UTC).isoformat(),
        "source_hash": source_hash,
        "media_complete": complete,
        "media_attempts": int(existing.get("media_attempts") or 0) + 1,
        "post": localized,
    }
    storage.put_object(prefix, key, encode_compact(document))
    return {"post_id": tweet_id, "skipped": False, "media_complete": complete}


def is_recent_post(post: dict[str, Any], *, now: datetime | None = None) -> bool:
    try:
        created = datetime.fromisoformat(str(post.get("created_at") or ""))
    except ValueError:
        return False
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return created >= (now or datetime.now(UTC)) - timedelta(days=MEDIA_BACKFILL_DAYS)


def publish_user(
    storage: ObjectStorageService,
    username: str,
    bundle: dict[str, Any],
    *,
    force_posts: bool = False,
) -> dict[str, Any]:
    """Publish one direct user document and recent/called-out post artifacts."""
    prefix_rel, key = user_artifact_key(username)
    prefix = f"{DEFAULT_APP_PREFIX}/{prefix_rel}"
    posts = list(bundle.get("posts") or [])
    source_hash = content_digest(encode_compact(bundle))
    existing = _read_json(storage, prefix, key)
    if (
        not force_posts
        and existing.get("format") == ARTIFACT_FORMAT
        and existing.get("source_hash") == source_hash
    ):
        return {"username": username, "skipped": True, "posts": len(posts)}
    post_results = []
    direct_posts: list[dict[str, Any]] = []
    for post in posts:
        if force_posts or is_recent_post(post):
            result = publish_post(storage, post, force=force_posts)
            post_results.append(result)
            post_prefix_rel, post_key = post_artifact_key(result["post_id"])
            post_doc = _read_json(
                storage, f"{DEFAULT_APP_PREFIX}/{post_prefix_rel}", post_key
            )
            direct_posts.append(dict(post_doc.get("post") or post))
        else:
            # The bounded rollout intentionally does not contact X CDNs for old
            # media. Do not make a supposedly static user page fetch it later.
            without_remote_media = dict(post)
            without_remote_media.pop("media_url", None)
            direct_posts.append(without_remote_media)

    profile = dict(bundle.get("profile") or {})
    for field, basename in (
        ("profile_image_url", "avatar"),
        ("profile_banner_url", "banner"),
    ):
        source_url = str(profile.get(field) or "")
        if not source_url:
            continue
        media_prefix = f"{prefix}/media"
        filename = _download_media(storage, source_url=source_url, prefix=media_prefix)
        profile[f"source_{field}"] = source_url
        if filename:
            profile[field] = f"{prefix_rel}/media/{basename}-{filename}"
            # Store a readable alias while retaining content identity in its name.
            raw = storage.get_object(media_prefix, filename)
            storage.put_object(media_prefix, f"{basename}-{filename}", raw)
        else:
            profile.pop(field, None)

    direct_bundle = {"profile": profile, "posts": direct_posts}
    storage.put_object(
        prefix,
        key,
        encode_compact(
            {
                "format": ARTIFACT_FORMAT,
                "updated_at": datetime.now(UTC).isoformat(),
                "source_hash": source_hash,
                "bundle": direct_bundle,
            }
        ),
    )
    return {
        "username": username,
        "skipped": False,
        "posts": len(posts),
        "post_artifacts": len(post_results),
    }
