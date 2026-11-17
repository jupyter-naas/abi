"""X (Twitter) v2 API, read-only with an app-only bearer token, async, on
``naas_abi_sdk`` only.

Port of the in-engine ``applications.x`` ``XIntegration``: same
endpoints, parameters, retries, envelopes and tool names, over ``httpx``.
Responses are archived in object storage (``storage``, the SDK's async
``object_storage``) at the paths and with the contents the in-engine version
wrote with ``StorageUtils.save_json``:

- each page of a paginated call: ``<datastore>/get_all_items/<ts>_<endpoint>_<md5>.json``;
- each lookup: ``<datastore>/<method>/<id or md5>.json``, plus the timestamped copy
  ``StorageUtils`` makes;
- each search / count envelope: ``<datastore>/search_recent_tweets/<slug>/<iso>_<slug>.json``
  and ``<datastore>/count_recent_tweets/<slug>/<iso>_<slug>.json``.

Cache. In-engine, core's file cache held every request for an hour, the lookups
(users, timelines, follows, tweets by id) for a day, a search for a minute and a
count for ever. Here only the lookups are cached, for a day, in the engine's
``cache`` service when the module declares it (``cache=None``: no cache). They are
billed per resource and an agent asks for the same profile again within a
conversation. Searches and counts are never cached: a search spends credits that
the spend ledger (``workflows.XSearchRecentTweetsWorkflow``) counts and caps, and a
cached search would hand back tweets the ledger never saw while the ``since_id``
walk needs the live pages; a count of the hour in progress must be fresh.
"""

from __future__ import annotations

import asyncio
import hashlib
import json as json_module
import os
import re
import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from naas_abi_apps.common.http import HttpConfiguration, request
from naas_abi_apps.common.storage import ObjectStorage
from naas_abi_apps.x.services import SyncModule, logger
from naas_abi_sdk.integration import Integration, IntegrationConnectionError


def slugify_query(query: str) -> str:
    ascii_query = (
        unicodedata.normalize("NFKD", query)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    slug = ascii_query.replace(" ", "_").replace("'", "").replace('"', "").lower()
    return slug


DEFAULT_BASE_URL = "https://api.twitter.com/2"

# Example query of the schemas and docs (never a runtime fallback).
EXAMPLE_X_SEARCH_QUERY = "(openai OR anthropic) lang:en -is:retweet"

# Lookups (users, timelines, follows, tweets by id) are cached for a day, as in-engine.
LOOKUP_CACHE_TTL = timedelta(days=1)

# X requires search/recent end_time to be a minimum of 10 seconds prior to the
# request time. Use a slightly larger safety margin to absorb clock skew and
# request latency.
_END_TIME_SAFETY_SECONDS = 15

# HTTP status codes that warrant a transient retry. 503 (Service Unavailable) is
# the one X returns when overloaded; the other 5xx/429 codes are equally transient.
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# Backoff sleeps (seconds) between retries, following the Fibonacci sequence up
# to the 5th number: 1, 1, 2, 3, 5. This gives 5 retries (6 attempts total)
# before the request is allowed to fail.
_FIBONACCI_BACKOFF_SECONDS = (1, 1, 2, 3, 5)

DEFAULT_TWEET_FIELDS = [
    "article",
    "attachments",
    "author_id",
    "card_uri",
    "community_id",
    "context_annotations",
    "conversation_id",
    "created_at",
    "display_text_range",
    "edit_controls",
    "edit_history_tweet_ids",
    "entities",
    "geo",
    "id",
    "in_reply_to_user_id",
    "lang",
    "matched_media_notes",
    "media_metadata",
    # non_public_metrics — EXCLUDED on search/recent: Field Authorization Error
    # (not-authorized-for-field). Only the tweet owner may read sub-fields
    # engagements, impression_count, url_link_clicks, user_profile_clicks.
    "note_request_suggestions",
    "note_tweet",
    # organic_metrics — EXCLUDED on search/recent: Field Authorization Error
    # (not-authorized-for-field). Sub-fields impression_count, like_count,
    # reply_count, retweet_count, url_link_clicks, user_profile_clicks
    # require tweet-owner OAuth; use public_metrics instead.
    "paid_partnership",
    "possibly_sensitive",
    # promoted_metrics — EXCLUDED on search/recent: Field Authorization Error
    # (not-authorized-for-field). Same owner-only sub-fields as organic_metrics.
    "public_metrics",
    "referenced_tweets",
    "reply_settings",
    "scopes",
    "source",
    "suggested_source_links",
    "suggested_source_links_with_counts",
    "text",
    "withheld",
]
DEFAULT_EXPANSIONS = [
    "article.cover_media",
    "article.media_entities",
    "attachments.media_keys",
    "attachments.poll_ids",
    "author_id",
    "edit_history_tweet_ids",
    "entities.mentions.username",
    "geo.place_id",
    "in_reply_to_user_id",
    "entities.note.mentions.username",
    "referenced_tweets.id",
    "referenced_tweets.id.attachments.media_keys",
    "referenced_tweets.id.author_id",
]
DEFAULT_MEDIA_FIELDS = [
    "duration_ms",
    "height",
    "media_key",
    "preview_image_url",
    "type",
    "url",
    "variants",
    "width",
]
DEFAULT_POLL_FIELDS = [
    "duration_minutes",
    "end_datetime",
    "id",
    "options",
    "voting_status",
]
DEFAULT_USER_FIELDS = [
    "affiliation",
    "confirmed_email",
    "connection_status",
    "created_at",
    "description",
    "entities",
    "id",
    "is_identity_verified",
    "location",
    "most_recent_tweet_id",
    "name",
    "parody",
    "pinned_tweet_id",
    "profile_banner_url",
    "profile_image_url",
    "protected",
    "public_metrics",
    "receives_your_dm",
    "subscription",
    "subscription_type",
    "url",
    "username",
    "verified",
    "verified_followers_count",
    "verified_type",
    "withheld",
]
DEFAULT_PLACE_FIELDS = [
    "contained_within",
    "country",
    "country_code",
    "full_name",
    "id",
    "name",
    "place_type",
]


def _clamp_end_time(end_time: str) -> str:
    """Clamp an X v2 ``end_time`` so it is safely before the request time.

    X's ``/2/tweets/search/recent`` rejects an ``end_time`` that is not at least
    10 seconds prior to the request time with a 400 "Invalid 'end_time'" error.
    This caps ``end_time`` at ``now - 15s`` (UTC) when it is too recent (or in the
    future), and returns it unchanged otherwise (also when it cannot be parsed).
    """
    try:
        parsed = datetime.fromisoformat(end_time)
    except ValueError:
        logger.warning(f"Could not parse X end_time {end_time!r}; leaving it unchanged")
        return end_time
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    latest_allowed = datetime.now(UTC) - timedelta(seconds=_END_TIME_SAFETY_SECONDS)
    if parsed > latest_allowed:
        clamped = latest_allowed.strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info(
            f"Clamped X end_time {end_time!r} to {clamped!r} to satisfy the 10s rule"
        )
        return clamped
    return end_time


def _md5_8(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest()[:8]


# X ids are digits, handles letters, digits and "_": nothing else may reach a
# request path or an archive file name.
_PATH_SEGMENT = re.compile(r"[A-Za-z0-9_]{1,64}")


def checked_segment(value: str, what: str) -> str:
    """``value`` when it is a plain X id or handle; ``ValueError`` otherwise."""
    if not _PATH_SEGMENT.fullmatch(str(value)):
        raise ValueError(f"Invalid X {what}: {value!r}")
    return str(value)


@dataclass(kw_only=True)
class XIntegrationConfiguration(HttpConfiguration):
    """bearer_token: OAuth 2.0 app-only token for the X v2 API (the engine secret
    ``applications.x/X_BEARER_TOKEN``). datastore_path: object-storage prefix of
    the archived responses. storage: the SDK's async ``object_storage`` (``None``:
    nothing archived, and envelopes carry ``file_path: None``). cache: the SDK's
    ``cache`` service for the lookups (``None``: no cache). backoff: seconds
    between the retries of a transient failure. transport (``HttpConfiguration``):
    an httpx transport, for tests."""

    bearer_token: str
    base_url: str = DEFAULT_BASE_URL
    datastore_path: str = "x"
    storage: ObjectStorage | None = field(default=None, repr=False)
    cache: Any = field(default=None, repr=False)
    backoff: tuple[float, ...] = _FIBONACCI_BACKOFF_SECONDS


class XIntegration(Integration):
    """X (Twitter) v2 API integration — read-only with bearer-token auth."""

    def __init__(self, configuration: XIntegrationConfiguration):
        super().__init__(configuration)
        self.configuration = configuration
        self.headers = {
            "Authorization": f"Bearer {configuration.bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------- storage

    async def _save_json(
        self, data: Any, dir_path: str, file_name: str, copy: bool = True
    ) -> bool:
        """``StorageUtils.save_json``: indented JSON at ``dir_path/file_name``,
        plus a ``<YYYYmmddTHHMMSS>_<file_name>`` copy when ``copy``. ``False``
        when there is no storage."""
        storage = self.configuration.storage
        if storage is None:
            return False
        content = json_module.dumps(data, indent=4, ensure_ascii=False).encode("utf-8")
        await storage.put_object(dir_path, file_name, content)
        if copy:
            stamped = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_{file_name}"
            try:
                await storage.put_object(dir_path, stamped, content)
            except Exception as exc:  # noqa: BLE001 - a copy never fails the save
                logger.error(f"Error making copy in {dir_path}: {exc}")
        return True

    def _dir(self, *parts: str) -> str:
        return os.path.join(self.configuration.datastore_path, *parts)

    # --------------------------------------------------------------- cache

    async def _cached(self, key: str, fetch: Callable[[], Awaitable[dict]]) -> dict:
        """``fetch()`` through the cache (a day); a hit is not archived again."""
        cache = self.configuration.cache
        cache_key = f"x:{key}"
        if cache is not None:
            try:
                return await cache.get(cache_key, ttl=LOOKUP_CACHE_TTL)
            except Exception as exc:  # noqa: BLE001 - a miss, expired, or no cache tier
                logger.debug(f"X: cache miss for {key} ({exc})")
        data = await fetch()
        if cache is not None:
            try:
                await cache.set_json(cache_key, data)
            except Exception:  # noqa: BLE001
                logger.warning(f"X: could not cache {key}", exc_info=True)
        return data

    # ----------------------------------------------------------- transport

    async def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: dict | None = None,
        json: dict | None = None,
    ) -> dict:
        """One X v2 API request, retried on a transient failure.

        Raises:
            IntegrationConnectionError: the request failed (an error status, or
            every attempt failed).
        """
        if not self.configuration.bearer_token:
            raise IntegrationConnectionError(
                "X API: no bearer token (engine secret applications.x/X_BEARER_TOKEN)"
            )
        url = f"{self.configuration.base_url}/{endpoint}"
        backoff = tuple(self.configuration.backoff)

        # Retry transient failures (e.g. 503 Service Unavailable) with Fibonacci
        # backoff. One initial attempt plus one retry per backoff sleep.
        last_error: IntegrationConnectionError | None = None
        for attempt, sleep_seconds in enumerate((*backoff, None)):
            try:
                response = await request(
                    self.configuration,
                    method,
                    url,
                    service="X",
                    raise_for_status=False,
                    headers=self.headers,
                    params=params or {},
                    json=json,
                )
            except IntegrationConnectionError as exc:
                last_error = exc
            else:
                if response.is_success:
                    return response.json()
                try:
                    detail = json_module.dumps(response.json(), ensure_ascii=False)
                except ValueError:
                    detail = response.text
                last_error = IntegrationConnectionError(
                    f"X API {response.status_code} {response.reason_phrase} for "
                    f"{url} — {detail}"
                )
                # Only retry transient server-side errors; fail fast otherwise.
                if response.status_code not in _RETRYABLE_STATUS_CODES:
                    raise last_error

            if sleep_seconds is None:
                break
            logger.warning(
                f"X API request to {url} failed (attempt {attempt + 1}/"
                f"{len(backoff) + 1}); retrying in {sleep_seconds}s — {last_error}"
            )
            await asyncio.sleep(sleep_seconds)

        raise last_error  # type: ignore[misc]

    async def _get_all_items(
        self,
        endpoint: str,
        params: dict | None = None,
        max_pages: int | None = None,
    ) -> dict:
        """Iterate an X v2 paginated endpoint and merge every page.

        Returns ``data`` (every page's items), ``includes`` (merged, deduplicated
        by id), ``errors``, ``meta`` (``newest_id`` of the first page, ``oldest_id``
        of the last, summed ``result_count``; ``has_more`` when ``max_pages``
        stopped early) and ``sources`` (the archived page files).
        """
        params = dict(params or {})
        params.setdefault("max_results", 100)

        items: list[dict] = []
        includes: dict[str, list[dict]] = {}
        errors: list[dict] = []
        merged_meta: dict = {}
        sources = []
        page = 0

        while True:
            logger.info(f"Fetching page {page} of {endpoint} with params {params}")
            response = await self._make_request(endpoint, params=params)
            dirname = self._dir("get_all_items")
            filename = (
                f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_"
                f"{endpoint.replace('/', '_')}_{_md5_8(str(params))}.json"
            )
            if await self._save_json(response, dirname, filename, copy=False):
                filepath = os.path.join(dirname, filename)
                sources.append(filepath)
                logger.info(f"Saved response to {filepath}")

            items.extend(response.get("data") or [])

            for key, val in (response.get("includes") or {}).items():
                bucket = includes.setdefault(key, [])
                id_key = "media_key" if key == "media" else "id"
                seen = {item[id_key] for item in bucket if id_key in item}
                bucket.extend(item for item in val if item.get(id_key) not in seen)

            errors.extend(response.get("errors") or [])

            page_meta = response.get("meta") or {}
            if not merged_meta:
                merged_meta = dict(page_meta)
            else:
                if "oldest_id" in page_meta:
                    merged_meta["oldest_id"] = page_meta["oldest_id"]
                merged_meta["result_count"] = merged_meta.get(
                    "result_count", 0
                ) + page_meta.get("result_count", 0)

            page += 1
            if max_pages is not None and page >= max_pages:
                # Tell callers (the search workflow) that more pages exist
                # beyond this capped fetch, so they can continue with until_id.
                if page_meta.get("next_token"):
                    merged_meta["has_more"] = True
                break

            next_token = page_meta.get("next_token")
            if not next_token:
                break
            params["pagination_token"] = next_token

        result: dict = {"data": items}
        if includes:
            result["includes"] = includes
        if errors:
            result["errors"] = errors
        if merged_meta:
            result["meta"] = merged_meta
        result["sources"] = sources
        return result

    async def _lookup(
        self,
        cache_key: str,
        endpoint: str,
        archive_dir: str,
        archive_name: str,
        params: dict | None = None,
    ) -> dict:
        async def fetch() -> dict:
            data = await self._make_request(endpoint, params=params)
            await self._save_json(data, self._dir(archive_dir), archive_name)
            return data

        return await self._cached(cache_key, fetch)

    async def _timeline(
        self,
        method: str,
        user_id: str,
        path: str,
        max_results: int,
        max_pages: int | None,
    ) -> dict:
        checked_segment(user_id, "user id")

        async def fetch() -> dict:
            data = await self._get_all_items(
                f"users/{user_id}/{path}",
                params={"max_results": max_results},
                max_pages=max_pages,
            )
            await self._save_json(data, self._dir(method), f"{user_id}.json")
            return data

        return await self._cached(
            f"{method}_{user_id}_{max_results}_{max_pages}", fetch
        )

    # ------------------------------------------------------------------ users

    async def get_user_by_id(self, user_id: str) -> dict:
        """Get a user by numeric ID. Endpoint: GET /2/users/{id}"""
        checked_segment(user_id, "user id")
        return await self._lookup(
            "get_user_by_id_" + user_id,
            f"users/{user_id}",
            "get_user_by_id",
            f"{user_id}.json",
        )

    async def get_user_by_username(self, username: str) -> dict:
        """Get a user by handle. Endpoint: GET /2/users/by/username/{username}"""
        checked_segment(username, "username")
        return await self._lookup(
            "get_user_by_username_" + username,
            f"users/by/username/{username}",
            "get_user_by_username",
            f"{username}.json",
        )

    async def get_users_by_ids(self, ids: list[str]) -> dict:
        """Get up to 100 users by numeric IDs. Endpoint: GET /2/users?ids=..."""
        ids_hash = _md5_8(",".join(sorted(ids)))
        return await self._lookup(
            "get_users_by_ids_" + ids_hash,
            "users",
            "get_users_by_ids",
            f"{ids_hash}.json",
            params={"ids": ",".join(ids)},
        )

    async def get_users_by_usernames(self, usernames: list[str]) -> dict:
        """Get up to 100 users by handles. Endpoint: GET /2/users/by?usernames=..."""
        names_hash = _md5_8(",".join(sorted(usernames)))
        return await self._lookup(
            "get_users_by_usernames_" + names_hash,
            "users/by",
            "get_users_by_usernames",
            f"{names_hash}.json",
            params={"usernames": ",".join(usernames)},
        )

    # -------------------------------------------------------------- timelines

    async def get_user_tweets(
        self, user_id: str, max_results: int = 100, max_pages: int | None = 1
    ) -> dict:
        """Get tweets posted by a user. Endpoint: GET /2/users/{id}/tweets"""
        return await self._timeline(
            "get_user_tweets", user_id, "tweets", max_results, max_pages
        )

    async def get_user_mentions(
        self, user_id: str, max_results: int = 100, max_pages: int | None = 1
    ) -> dict:
        """Get tweets mentioning a user. Endpoint: GET /2/users/{id}/mentions"""
        return await self._timeline(
            "get_user_mentions", user_id, "mentions", max_results, max_pages
        )

    async def get_user_liked_tweets(
        self, user_id: str, max_results: int = 100, max_pages: int | None = 1
    ) -> dict:
        """Get tweets liked by a user. Endpoint: GET /2/users/{id}/liked_tweets"""
        return await self._timeline(
            "get_user_liked_tweets", user_id, "liked_tweets", max_results, max_pages
        )

    # ----------------------------------------------------------------- follow

    async def get_user_followers(
        self, user_id: str, max_results: int = 100, max_pages: int | None = 1
    ) -> dict:
        """Get followers of a user. Endpoint: GET /2/users/{id}/followers"""
        return await self._timeline(
            "get_user_followers", user_id, "followers", max_results, max_pages
        )

    async def get_user_following(
        self, user_id: str, max_results: int = 100, max_pages: int | None = 1
    ) -> dict:
        """Get accounts followed by a user. Endpoint: GET /2/users/{id}/following"""
        return await self._timeline(
            "get_user_following", user_id, "following", max_results, max_pages
        )

    # ----------------------------------------------------------------- tweets

    async def get_tweet_by_id(self, tweet_id: str) -> dict:
        """Get a single tweet by ID. Endpoint: GET /2/tweets/{id}"""
        checked_segment(tweet_id, "tweet id")
        return await self._lookup(
            "get_tweet_by_id_" + tweet_id,
            f"tweets/{tweet_id}",
            "get_tweet_by_id",
            f"{tweet_id}.json",
        )

    async def get_tweets_by_ids(self, ids: list[str]) -> dict:
        """Get up to 100 tweets by ID. Endpoint: GET /2/tweets?ids=..."""
        ids_hash = _md5_8(",".join(sorted(ids)))
        return await self._lookup(
            "get_tweets_by_ids_" + ids_hash,
            "tweets",
            "get_tweets_by_ids",
            f"{ids_hash}.json",
            params={"ids": ",".join(ids)},
        )

    # ----------------------------------------------------------------- search

    async def search_recent_tweets(
        self,
        query: str,
        start_time: str | None = None,
        end_time: str | None = None,
        since_id: str | None = None,
        until_id: str | None = None,
        max_results: int = 100,
        sort_order: str | None = "recency",
        tweet_fields: list[str] | None = None,
        expansions: list[str] | None = None,
        media_fields: list[str] | None = None,
        poll_fields: list[str] | None = None,
        user_fields: list[str] | None = None,
        place_fields: list[str] | None = None,
        max_pages: int | None = 1,
        persist_envelope: bool = True,
    ) -> dict:
        """Search tweets from the last 7 days. Endpoint: GET /2/tweets/search/recent

        Spends credits (one per tweet returned) and is never cached: callers that
        must respect the spend caps go through the ledger of
        ``XSearchRecentTweetsWorkflow`` (``search_with_budget``).

        ``persist_envelope=False`` when the caller (the search workflow) owns the
        envelopes. Returns the envelope ``{query, options, results, started_at,
        ended_at, file_path}``; ``results`` is the merged X v2 response
        (``meta.has_more`` when ``max_pages`` stopped pagination early).
        """
        params: dict = {"query": query, "max_results": max_results}
        if start_time is not None:
            params["start_time"] = start_time
        if end_time is not None:
            # X requires end_time to be at least 10 seconds before the request
            # time; clamp it to a safe buffer (15s) before "now".
            end_time = _clamp_end_time(end_time)
            params["end_time"] = end_time
        if since_id is not None:
            params["since_id"] = since_id
        if until_id is not None:
            params["until_id"] = until_id
        if sort_order is not None:
            params["sort_order"] = sort_order
        tweet_fields = tweet_fields or list(DEFAULT_TWEET_FIELDS)
        params["tweet.fields"] = ",".join(tweet_fields)
        expansions = expansions or list(DEFAULT_EXPANSIONS)
        params["expansions"] = ",".join(expansions)
        media_fields = media_fields or list(DEFAULT_MEDIA_FIELDS)
        params["media.fields"] = ",".join(media_fields)
        poll_fields = poll_fields or list(DEFAULT_POLL_FIELDS)
        params["poll.fields"] = ",".join(poll_fields)
        user_fields = user_fields or list(DEFAULT_USER_FIELDS)
        params["user.fields"] = ",".join(user_fields)
        place_fields = place_fields or list(DEFAULT_PLACE_FIELDS)
        params["place.fields"] = ",".join(place_fields)

        started_at = datetime.now(UTC).isoformat()
        tweets = await self._get_all_items(
            "tweets/search/recent", params=params, max_pages=max_pages
        )
        ended_at = datetime.now(UTC).isoformat()
        options = {
            k: v
            for k, v in {
                "start_time": start_time,
                "end_time": end_time,
                "since_id": since_id,
                "until_id": until_id,
                "max_results": max_results,
                "sort_order": sort_order,
                "tweet_fields": tweet_fields,
                "expansions": expansions,
                "media_fields": media_fields,
                "poll_fields": poll_fields,
                "user_fields": user_fields,
                "place_fields": place_fields,
                "max_pages": max_pages,
            }.items()
            if v is not None
        }
        envelope_dir = self._dir("search_recent_tweets", slugify_query(query))
        envelope_filename = (
            f"{datetime.now(UTC).isoformat()}_{slugify_query(query)}.json"
        )
        persist = persist_envelope and self.configuration.storage is not None
        # The envelope returned is the one persisted, so a caller can hand
        # ``file_path`` straight to XSearchRecentTweetsPipeline.
        envelope = {
            "query": query,
            "options": options,
            "results": tweets,
            "started_at": started_at,
            "ended_at": ended_at,
            "file_path": os.path.join(envelope_dir, envelope_filename)
            if persist
            else None,
        }
        if persist:
            await self._save_json(envelope, envelope_dir, envelope_filename, copy=False)
        return envelope

    # ------------------------------------------------------------ tweet counts

    async def count_recent_tweets(
        self,
        query: str,
        start_time: str | None = None,
        end_time: str | None = None,
        since_id: str | None = None,
        until_id: str | None = None,
        granularity: str = "hour",
        search_count_fields: list[str] | None = None,
        max_pages: int | None = None,
    ) -> dict:
        """Count tweets matching a query over the last 7 days, bucketed by time.
        Endpoint: GET /2/tweets/counts/recent

        Only counts (no tweet content): it does not spend the tweet budget. Never
        cached. Returns the persisted envelope ``{query, options, results,
        total_tweet_count, started_at, ended_at, file_path}``.
        """
        params: dict = {"query": query, "granularity": granularity}
        if start_time is not None:
            params["start_time"] = start_time
        if end_time is not None:
            # Same 10s rule as search/recent — clamp to a 15s safety buffer.
            end_time = _clamp_end_time(end_time)
            params["end_time"] = end_time
        if since_id is not None:
            params["since_id"] = since_id
        if until_id is not None:
            params["until_id"] = until_id
        if search_count_fields:
            params["search_count.fields"] = ",".join(search_count_fields)

        started_at = datetime.now(UTC).isoformat()

        # The counts endpoint paginates like the rest of v2 but carries the
        # running total in meta.total_tweet_count rather than a mergeable list.
        buckets: list[dict] = []
        errors: list[dict] = []
        total_tweet_count = 0
        merged_meta: dict = {}
        page = 0
        while True:
            response = await self._make_request("tweets/counts/recent", params=params)
            buckets.extend(response.get("data") or [])
            errors.extend(response.get("errors") or [])
            page_meta = response.get("meta") or {}
            total_tweet_count += page_meta.get("total_tweet_count", 0)
            merged_meta.update(page_meta)

            page += 1
            if max_pages is not None and page >= max_pages:
                break
            next_token = page_meta.get("next_token")
            if not next_token:
                break
            params["pagination_token"] = next_token

        merged_meta["total_tweet_count"] = total_tweet_count
        results: dict = {"data": buckets, "meta": merged_meta}
        if errors:
            results["errors"] = errors

        ended_at = datetime.now(UTC).isoformat()
        options = {
            k: v
            for k, v in {
                "start_time": start_time,
                "end_time": end_time,
                "since_id": since_id,
                "until_id": until_id,
                "granularity": granularity,
                "search_count_fields": search_count_fields,
                "max_pages": max_pages,
            }.items()
            if v is not None
        }
        envelope_dir = self._dir("count_recent_tweets", slugify_query(query))
        envelope_filename = (
            f"{datetime.now(UTC).isoformat()}_{slugify_query(query)}.json"
        )
        persist = self.configuration.storage is not None
        envelope = {
            "query": query,
            "options": options,
            "results": results,
            "total_tweet_count": total_tweet_count,
            "started_at": started_at,
            "ended_at": ended_at,
            "file_path": os.path.join(envelope_dir, envelope_filename)
            if persist
            else None,
        }
        if persist:
            await self._save_json(envelope, envelope_dir, envelope_filename, copy=False)
        return envelope


def _cache_service(services: Any) -> Any:
    """The engine's cache service when the module declared it, else ``None``."""
    available = getattr(services, "cache_available", None)
    if callable(available):
        return services.cache if available() else None
    return getattr(services, "cache", None)


def x_integration_for(module: Any, **overrides: Any) -> XIntegration:
    """The integration of the X module: its bearer token (``module.bearer_token``,
    ``""`` when the secret is not set: every call then fails), ``datastore_path``,
    the async object storage and, when declared, the cache.

    ``module``: the SDK ``ABIModule`` or its ``SyncModule`` (the integration is
    async either way: from a worker thread, await it with ``module.run``).
    ``overrides``: other ``XIntegrationConfiguration`` fields (``transport``...).
    """
    sdk_module = module.module if isinstance(module, SyncModule) else module
    services = sdk_module.engine.services
    values: dict[str, Any] = {
        "bearer_token": getattr(sdk_module, "bearer_token", None) or "",
        "datastore_path": sdk_module.configuration.datastore_path,
        "storage": services.object_storage,
        "cache": _cache_service(services),
    }
    values.update(overrides)
    return XIntegration(XIntegrationConfiguration(**values))


SearchRecentTweets = Callable[..., Awaitable[dict]]


def as_tools(
    configuration: XIntegrationConfiguration,
    *,
    search_recent_tweets: SearchRecentTweets | None = None,
) -> list[Any]:
    """The X integration as LangChain tools, under their in-engine names.

    ``search_recent_tweets``: the coroutine behind ``x_search_recent_tweets``
    (same arguments as ``XIntegration.search_recent_tweets``), so that the agent
    sends its searches through the spend ledger; default: the integration's.
    """
    from langchain_core.tools import StructuredTool
    from naas_abi_apps.common.agents import schema_tool
    from pydantic import BaseModel, Field

    integration = XIntegration(configuration)
    search = search_recent_tweets or integration.search_recent_tweets

    class GetUserByIdSchema(BaseModel):
        user_id: str = Field(..., description="Numeric X user ID")

    class GetUserByUsernameSchema(BaseModel):
        username: str = Field(..., description="X handle without the @ prefix")

    class GetUsersByIdsSchema(BaseModel):
        ids: list[str] = Field(..., description="List of up to 100 numeric X user IDs")

    class GetUsersByUsernamesSchema(BaseModel):
        usernames: list[str] = Field(
            ..., description="List of up to 100 X handles (without @)"
        )

    class UserTimelineSchema(BaseModel):
        user_id: str = Field(..., description="Numeric X user ID")
        max_results: int = Field(
            100, description="Results per page (X v2 cap is 100 for most endpoints)"
        )
        max_pages: int | None = Field(
            1, description="Maximum number of pages to fetch (None to exhaust)"
        )

    class GetTweetByIdSchema(BaseModel):
        tweet_id: str = Field(..., description="Numeric tweet ID")

    class GetTweetsByIdsSchema(BaseModel):
        ids: list[str] = Field(..., description="List of up to 100 tweet IDs")

    class SearchRecentTweetsSchema(BaseModel):
        query: str = Field(
            ...,
            description="X v2 search query (1-4096 chars), e.g. 'python lang:en -is:retweet'",
        )
        start_time: str | None = Field(
            None,
            description="Oldest UTC timestamp YYYY-MM-DDTHH:mm:ssZ (inclusive)",
        )
        end_time: str | None = Field(
            None,
            description="Newest UTC timestamp YYYY-MM-DDTHH:mm:ssZ (exclusive)",
        )
        since_id: str | None = Field(
            None, description="Only return tweets with an ID greater than this"
        )
        until_id: str | None = Field(
            None, description="Only return tweets with an ID less than this"
        )
        max_results: int = Field(100, description="Results per page, 10-100")
        sort_order: str | None = Field(None, description="'recency' or 'relevancy'")
        tweet_fields: list[str] | None = Field(
            None,
            description="Tweet object fields (e.g. ['created_at', 'public_metrics', 'lang'])",
        )
        expansions: list[str] | None = Field(
            None,
            description="Object expansions (e.g. ['author_id', 'referenced_tweets.id'])",
        )
        media_fields: list[str] | None = Field(
            None, description="Media object fields when media is expanded"
        )
        poll_fields: list[str] | None = Field(
            None, description="Poll object fields when polls are expanded"
        )
        user_fields: list[str] | None = Field(
            None, description="User object fields when author is expanded"
        )
        place_fields: list[str] | None = Field(
            None, description="Place object fields when geo is expanded"
        )
        max_pages: int | None = Field(
            1, description="Maximum number of pages to fetch (None to exhaust)"
        )

    class CountRecentTweetsSchema(BaseModel):
        query: str = Field(
            ...,
            description="X v2 search query (1-4096 chars), e.g. '(openai OR anthropic) lang:en -is:retweet'",
        )
        start_time: str | None = Field(
            None,
            description="Oldest UTC timestamp YYYY-MM-DDTHH:mm:ssZ (inclusive)",
        )
        end_time: str | None = Field(
            None,
            description="Newest UTC timestamp YYYY-MM-DDTHH:mm:ssZ (exclusive)",
        )
        since_id: str | None = Field(
            None, description="Only count tweets with an ID greater than this"
        )
        until_id: str | None = Field(
            None, description="Only count tweets with an ID less than this"
        )
        granularity: str = Field(
            "hour", description="Bucket size: 'minute', 'hour' or 'day'"
        )
        search_count_fields: list[str] | None = Field(
            None,
            description="Count bucket fields (subset of ['start', 'end', 'tweet_count'])",
        )
        max_pages: int | None = Field(
            None, description="Maximum number of pages to fetch (None to exhaust)"
        )

    def tool(name: str, description: str, fn: Any, schema: type) -> Any:
        return StructuredTool(
            name=name,
            description=description,
            coroutine=schema_tool(fn, schema),
            args_schema=schema,
        )

    return [
        tool(
            "x_get_user_by_id",
            "Get an X (Twitter) user profile by numeric user ID.",
            integration.get_user_by_id,
            GetUserByIdSchema,
        ),
        tool(
            "x_get_user_by_username",
            "Get an X (Twitter) user profile by handle (without @).",
            integration.get_user_by_username,
            GetUserByUsernameSchema,
        ),
        tool(
            "x_get_users_by_ids",
            "Get multiple X user profiles in one call by their numeric IDs (up to 100).",
            integration.get_users_by_ids,
            GetUsersByIdsSchema,
        ),
        tool(
            "x_get_users_by_usernames",
            "Get multiple X user profiles in one call by their handles (up to 100).",
            integration.get_users_by_usernames,
            GetUsersByUsernamesSchema,
        ),
        tool(
            "x_get_user_tweets",
            "Get tweets posted by an X user (their timeline).",
            integration.get_user_tweets,
            UserTimelineSchema,
        ),
        tool(
            "x_get_user_mentions",
            "Get tweets that mention an X user.",
            integration.get_user_mentions,
            UserTimelineSchema,
        ),
        tool(
            "x_get_user_liked_tweets",
            "Get tweets that an X user has liked.",
            integration.get_user_liked_tweets,
            UserTimelineSchema,
        ),
        tool(
            "x_get_user_followers",
            "Get the followers of an X user.",
            integration.get_user_followers,
            UserTimelineSchema,
        ),
        tool(
            "x_get_user_following",
            "Get the accounts an X user is following.",
            integration.get_user_following,
            UserTimelineSchema,
        ),
        tool(
            "x_get_tweet_by_id",
            "Get a single tweet by its numeric ID.",
            integration.get_tweet_by_id,
            GetTweetByIdSchema,
        ),
        tool(
            "x_get_tweets_by_ids",
            "Get multiple tweets in one call by their numeric IDs (up to 100).",
            integration.get_tweets_by_ids,
            GetTweetsByIdsSchema,
        ),
        tool(
            "x_search_recent_tweets",
            "Search tweets posted in the last 7 days using X v2 search syntax.",
            search,
            SearchRecentTweetsSchema,
        ),
        tool(
            "x_count_recent_tweets",
            "Count tweets posted in the last 7 days matching an X v2 query, bucketed by time — cheap way to size a query without retrieving tweet content.",
            integration.count_recent_tweets,
            CountRecentTweetsSchema,
        ),
    ]
