import hashlib
import json as json_module
import os
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests
from naas_abi_core import logger
from naas_abi_core.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_marketplace.applications.x import ABIModule

cache = CacheFactory.CacheFS_find_storage(subpath="x")


def slugify_query(query: str) -> str:
    ascii_query = (
        unicodedata.normalize("NFKD", query)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    slug = ascii_query.replace(" ", "_").replace("'", "").replace('"', "").lower()
    return slug


# X requires search/recent end_time to be a minimum of 10 seconds prior to the
# request time. Use a slightly larger safety margin to absorb clock skew and
# request latency.
_END_TIME_SAFETY_SECONDS = 15


def _clamp_end_time(end_time: str) -> str:
    """Clamp an X v2 ``end_time`` so it is safely before the request time.

    X's ``/2/tweets/search/recent`` rejects an ``end_time`` that is not at least
    10 seconds prior to the request time with a 400 "Invalid 'end_time'" error.
    This caps ``end_time`` at ``now - 15s`` (UTC) when it is too recent (or in the
    future), and returns it unchanged otherwise.

    Args:
        end_time (str): UTC timestamp in ISO-8601 form (e.g. "2026-06-15T09:00:00Z").

    Returns:
        str: A safe ``end_time`` formatted as ``YYYY-MM-DDTHH:mm:ssZ``. The input
        is returned unchanged if it cannot be parsed.
    """
    try:
        parsed = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Could not parse X end_time %r; leaving it unchanged", end_time)
        return end_time
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    latest_allowed = datetime.now(timezone.utc) - timedelta(
        seconds=_END_TIME_SAFETY_SECONDS
    )
    if parsed > latest_allowed:
        clamped = latest_allowed.strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info(
            "Clamped X end_time %r to %r to satisfy the 10s rule", end_time, clamped
        )
        return clamped
    return end_time


@dataclass
class XIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for the X (Twitter) integration.

    Attributes:
        bearer_token (str): OAuth 2.0 App-Only bearer token for the X v2 API.
        base_url (str): Base URL for the X v2 API. Defaults to "https://api.twitter.com/2".
        datastore_path (str): Object-storage prefix for persisted responses.
    """

    bearer_token: str
    base_url: str = "https://api.twitter.com/2"
    datastore_path: str = field(
        default_factory=lambda: ABIModule.get_instance().configuration.datastore_path
    )


class XIntegration(Integration):
    """X (Twitter) v2 API integration — read-only with bearer-token auth."""

    __configuration: XIntegrationConfiguration
    __storage_utils: StorageUtils

    def __init__(self, configuration: XIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__storage_utils = StorageUtils(
            ABIModule.get_instance().engine.services.object_storage
        )

        self.headers = {
            "Authorization": f"Bearer {self.__configuration.bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @cache(
        lambda self, endpoint, method, params, json: (
            f"{method}_{endpoint}_{hashlib.md5(str(params).encode()).hexdigest()[:8]}_{hashlib.md5(str(json).encode()).hexdigest()[:8]}"
        ),
        cache_type=DataType.JSON,
        ttl=timedelta(minutes=1),
    )
    def _make_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
    ) -> Dict:
        """Make an HTTP request to the X v2 API.

        Args:
            endpoint (str): API endpoint path (without leading slash).
            method (str): HTTP verb. Defaults to "GET".
            params (Dict, optional): Query-string parameters.
            json (Dict, optional): JSON body for non-GET requests.

        Returns:
            Dict: Parsed JSON response.

        Raises:
            IntegrationConnectionError: If the request fails.
        """
        url = f"{self.__configuration.base_url}/{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params or {},
                json=json,
            )
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"X API request failed: {str(e)}")

        if not response.ok:
            try:
                body = response.json()
                detail = json_module.dumps(body, ensure_ascii=False)
            except ValueError:
                detail = response.text
            raise IntegrationConnectionError(
                f"X API {response.status_code} {response.reason} for {url} — {detail}"
            )

        return response.json()

    def _get_all_items(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        max_pages: Optional[int] = None,
    ) -> Dict:
        """Iterate an X v2 paginated endpoint until exhausted and merge all response keys.

        X v2 pagination uses `pagination_token` in the request and
        `meta.next_token` in the response.

        Args:
            endpoint (str): API endpoint path.
            params (Dict, optional): Query-string parameters. `max_results`
                defaults to 100 (the v2 cap for most endpoints).
            max_pages (int, optional): Stop after this many pages.

        Returns:
            Dict: Merged response with keys:
                - ``data``: concatenated items from every page.
                - ``includes``: merged sub-lists (media, users, tweets, …), deduplicated by id.
                - ``errors``: concatenated error objects.
                - ``meta``: newest_id from first page, oldest_id from last page, summed result_count.
        """
        params = dict(params or {})
        params.setdefault("max_results", 100)

        items: List[Dict] = []
        includes: Dict[str, List[Dict]] = {}
        errors: List[Dict] = []
        merged_meta: Dict = {}
        sources = []
        page = 0

        while True:
            logger.info(f"Fetching page {page} of {endpoint} with params {params}")
            response = self._make_request(endpoint, params=params)
            dirname = os.path.join(self.__configuration.datastore_path, "get_all_items")
            filename = f"{endpoint.replace('/', '_')}_{hashlib.md5(str(params).encode()).hexdigest()[:8]}.json"
            self.__storage_utils.save_json(
                response,
                dirname,
                filename,
            )
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
                break

            next_token = page_meta.get("next_token")
            if not next_token:
                break
            params["pagination_token"] = next_token

        result: Dict = {"data": items}
        if includes:
            result["includes"] = includes
        if errors:
            result["errors"] = errors
        if merged_meta:
            result["meta"] = merged_meta
        result["sources"] = sources
        return result

    # ------------------------------------------------------------------ users

    @cache(
        lambda self, user_id: "get_user_by_id_" + user_id,
        cache_type=DataType.JSON,
        ttl=timedelta(days=1),
    )
    def get_user_by_id(self, user_id: str) -> Dict:
        """Get a user by numeric ID.

        Endpoint: GET /2/users/{id}
        """
        user = self._make_request(f"users/{user_id}")
        self.__storage_utils.save_json(
            user,
            os.path.join(self.__configuration.datastore_path, "get_user_by_id"),
            f"{user_id}.json",
        )
        return user

    @cache(
        lambda self, username: "get_user_by_username_" + username,
        cache_type=DataType.JSON,
        ttl=timedelta(days=1),
    )
    def get_user_by_username(self, username: str) -> Dict:
        """Get a user by handle.

        Endpoint: GET /2/users/by/username/{username}
        """
        user = self._make_request(f"users/by/username/{username}")
        self.__storage_utils.save_json(
            user,
            os.path.join(self.__configuration.datastore_path, "get_user_by_username"),
            f"{username}.json",
        )
        return user

    @cache(
        lambda self, ids: (
            "get_users_by_ids_"
            + hashlib.md5(",".join(sorted(ids)).encode()).hexdigest()[:8]
        ),
        cache_type=DataType.JSON,
        ttl=timedelta(days=1),
    )
    def get_users_by_ids(self, ids: List[str]) -> Dict:
        """Get up to 100 users by numeric IDs.

        Endpoint: GET /2/users?ids=...
        """
        params = {"ids": ",".join(ids)}
        users = self._make_request("users", params=params)
        ids_hash = hashlib.md5(",".join(sorted(ids)).encode()).hexdigest()[:8]
        self.__storage_utils.save_json(
            users,
            os.path.join(self.__configuration.datastore_path, "get_users_by_ids"),
            f"{ids_hash}.json",
        )
        return users

    @cache(
        lambda self, usernames: (
            "get_users_by_usernames_"
            + hashlib.md5(",".join(sorted(usernames)).encode()).hexdigest()[:8]
        ),
        cache_type=DataType.JSON,
        ttl=timedelta(days=1),
    )
    def get_users_by_usernames(self, usernames: List[str]) -> Dict:
        """Get up to 100 users by handles.

        Endpoint: GET /2/users/by?usernames=...
        """
        params = {"usernames": ",".join(usernames)}
        users = self._make_request("users/by", params=params)
        names_hash = hashlib.md5(",".join(sorted(usernames)).encode()).hexdigest()[:8]
        self.__storage_utils.save_json(
            users,
            os.path.join(self.__configuration.datastore_path, "get_users_by_usernames"),
            f"{names_hash}.json",
        )
        return users

    # -------------------------------------------------------------- timelines

    @cache(
        lambda self, user_id, max_results=100, max_pages=1: (
            f"get_user_tweets_{user_id}_{max_results}_{max_pages}"
        ),
        cache_type=DataType.JSON,
        ttl=timedelta(days=1),
    )
    def get_user_tweets(
        self,
        user_id: str,
        max_results: int = 100,
        max_pages: Optional[int] = 1,
    ) -> Dict:
        """Get tweets posted by a user.

        Endpoint: GET /2/users/{id}/tweets
        """
        tweets = self._get_all_items(
            f"users/{user_id}/tweets",
            params={"max_results": max_results},
            max_pages=max_pages,
        )
        self.__storage_utils.save_json(
            tweets,
            os.path.join(self.__configuration.datastore_path, "get_user_tweets"),
            f"{user_id}.json",
        )
        return tweets

    @cache(
        lambda self, user_id, max_results=100, max_pages=1: (
            f"get_user_mentions_{user_id}_{max_results}_{max_pages}"
        ),
        cache_type=DataType.JSON,
        ttl=timedelta(days=1),
    )
    def get_user_mentions(
        self,
        user_id: str,
        max_results: int = 100,
        max_pages: Optional[int] = 1,
    ) -> Dict:
        """Get tweets mentioning a user.

        Endpoint: GET /2/users/{id}/mentions
        """
        mentions = self._get_all_items(
            f"users/{user_id}/mentions",
            params={"max_results": max_results},
            max_pages=max_pages,
        )
        self.__storage_utils.save_json(
            mentions,
            os.path.join(self.__configuration.datastore_path, "get_user_mentions"),
            f"{user_id}.json",
        )
        return mentions

    @cache(
        lambda self, user_id, max_results=100, max_pages=1: (
            f"get_user_liked_tweets_{user_id}_{max_results}_{max_pages}"
        ),
        cache_type=DataType.JSON,
        ttl=timedelta(days=1),
    )
    def get_user_liked_tweets(
        self,
        user_id: str,
        max_results: int = 100,
        max_pages: Optional[int] = 1,
    ) -> Dict:
        """Get tweets liked by a user.

        Endpoint: GET /2/users/{id}/liked_tweets
        """
        liked = self._get_all_items(
            f"users/{user_id}/liked_tweets",
            params={"max_results": max_results},
            max_pages=max_pages,
        )
        self.__storage_utils.save_json(
            liked,
            os.path.join(self.__configuration.datastore_path, "get_user_liked_tweets"),
            f"{user_id}.json",
        )
        return liked

    # ----------------------------------------------------------------- follow

    @cache(
        lambda self, user_id, max_results=100, max_pages=1: (
            f"get_user_followers_{user_id}_{max_results}_{max_pages}"
        ),
        cache_type=DataType.JSON,
        ttl=timedelta(days=1),
    )
    def get_user_followers(
        self,
        user_id: str,
        max_results: int = 100,
        max_pages: Optional[int] = 1,
    ) -> Dict:
        """Get followers of a user.

        Endpoint: GET /2/users/{id}/followers (max 1000/page).
        """
        followers = self._get_all_items(
            f"users/{user_id}/followers",
            params={"max_results": max_results},
            max_pages=max_pages,
        )
        self.__storage_utils.save_json(
            followers,
            os.path.join(self.__configuration.datastore_path, "get_user_followers"),
            f"{user_id}.json",
        )
        return followers

    @cache(
        lambda self, user_id, max_results=100, max_pages=1: (
            f"get_user_following_{user_id}_{max_results}_{max_pages}"
        ),
        cache_type=DataType.JSON,
        ttl=timedelta(days=1),
    )
    def get_user_following(
        self,
        user_id: str,
        max_results: int = 100,
        max_pages: Optional[int] = 1,
    ) -> Dict:
        """Get accounts followed by a user.

        Endpoint: GET /2/users/{id}/following (max 1000/page).
        """
        following = self._get_all_items(
            f"users/{user_id}/following",
            params={"max_results": max_results},
            max_pages=max_pages,
        )
        self.__storage_utils.save_json(
            following,
            os.path.join(self.__configuration.datastore_path, "get_user_following"),
            f"{user_id}.json",
        )
        return following

    # ----------------------------------------------------------------- tweets

    @cache(
        lambda self, tweet_id: "get_tweet_by_id_" + tweet_id,
        cache_type=DataType.JSON,
        ttl=timedelta(days=1),
    )
    def get_tweet_by_id(self, tweet_id: str) -> Dict:
        """Get a single tweet by ID.

        Endpoint: GET /2/tweets/{id}
        """
        tweet = self._make_request(f"tweets/{tweet_id}")
        self.__storage_utils.save_json(
            tweet,
            os.path.join(self.__configuration.datastore_path, "get_tweet_by_id"),
            f"{tweet_id}.json",
        )
        return tweet

    @cache(
        lambda self, ids: (
            "get_tweets_by_ids_"
            + hashlib.md5(",".join(sorted(ids)).encode()).hexdigest()[:8]
        ),
        cache_type=DataType.JSON,
        ttl=timedelta(days=1),
    )
    def get_tweets_by_ids(self, ids: List[str]) -> Dict:
        """Get up to 100 tweets by ID.

        Endpoint: GET /2/tweets?ids=...
        """
        params = {"ids": ",".join(ids)}
        tweets = self._make_request("tweets", params=params)
        ids_hash = hashlib.md5(",".join(sorted(ids)).encode()).hexdigest()[:8]
        self.__storage_utils.save_json(
            tweets,
            os.path.join(self.__configuration.datastore_path, "get_tweets_by_ids"),
            f"{ids_hash}.json",
        )
        return tweets

    # ----------------------------------------------------------------- search

    @cache(
        lambda self, query, start_time=None, end_time=None, since_id=None, until_id=None, max_results=100, sort_order=None, tweet_fields=None, expansions=None, media_fields=None, poll_fields=None, user_fields=None, place_fields=None, max_pages=1: (
            "search_recent_tweets_"
            + hashlib.md5(
                json_module.dumps(
                    {
                        "query": query,
                        "start_time": start_time,
                        "end_time": end_time,
                        "since_id": since_id,
                        "until_id": until_id,
                        "max_results": max_results,
                        "sort_order": sort_order,
                        "tweet_fields": sorted(tweet_fields) if tweet_fields else None,
                        "expansions": sorted(expansions) if expansions else None,
                        "media_fields": sorted(media_fields) if media_fields else None,
                        "poll_fields": sorted(poll_fields) if poll_fields else None,
                        "user_fields": sorted(user_fields) if user_fields else None,
                        "place_fields": sorted(place_fields) if place_fields else None,
                        "max_pages": max_pages,
                    },
                    sort_keys=True,
                    default=str,
                ).encode()
            ).hexdigest()[:8]
        ),
        cache_type=DataType.JSON,
        ttl=timedelta(minutes=1),
    )
    def search_recent_tweets(
        self,
        query: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        since_id: Optional[str] = None,
        until_id: Optional[str] = None,
        max_results: int = 100,
        sort_order: Optional[str] = "recency",
        tweet_fields: Optional[List[str]] = None,
        expansions: Optional[List[str]] = None,
        media_fields: Optional[List[str]] = None,
        poll_fields: Optional[List[str]] = None,
        user_fields: Optional[List[str]] = None,
        place_fields: Optional[List[str]] = None,
        max_pages: Optional[int] = 1,
    ) -> Dict:
        """Search tweets from the last 7 days.

        Endpoint: GET /2/tweets/search/recent

        Args:
            query (str): X v2 search query (1-4096 chars), e.g. "(from:TwitterDev
                OR from:TwitterAPI) has:media -is:retweet".
            start_time (str, optional): Oldest UTC timestamp (YYYY-MM-DDTHH:mm:ssZ),
                inclusive.
            end_time (str, optional): Newest UTC timestamp (YYYY-MM-DDTHH:mm:ssZ),
                exclusive.
            since_id (str, optional): Only return tweets with an ID greater than this.
            until_id (str, optional): Only return tweets with an ID less than this.
            max_results (int): Results per page, 10-100. Defaults to 100.
            sort_order (str, optional): "recency" or "relevancy".
            tweet_fields (list[str], optional): Fields to include on each Tweet object
                (sent as `tweet.fields`).
            expansions (list[str], optional): Object expansions (e.g. "author_id",
                "referenced_tweets.id").
            media_fields (list[str], optional): Fields on expanded Media objects
                (sent as `media.fields`).
            poll_fields (list[str], optional): Fields on expanded Poll objects
                (sent as `poll.fields`).
            user_fields (list[str], optional): Fields on expanded User objects
                (sent as `user.fields`).
            place_fields (list[str], optional): Fields on expanded Place objects
                (sent as `place.fields`).
            max_pages (int, optional): Pages of results to fetch (None to exhaust).
                Defaults to 1.

        Returns:
            Dict: The persisted search envelope with keys ``query``, ``options``,
            ``results`` (the merged X v2 response — ``data``, ``includes``,
            ``errors``, ``meta``), ``started_at``, ``ended_at`` and ``file_path``
            (object-storage path of the saved envelope JSON).
        """
        params: Dict = {"query": query, "max_results": max_results}
        if start_time is not None:
            params["start_time"] = start_time
        if end_time is not None:
            # X requires end_time to be at least 10 seconds before the request
            # time; clamp it to a safe buffer (15s) before "now" to avoid the
            # "Invalid 'end_time'" 400 error on near-real-time queries.
            end_time = _clamp_end_time(end_time)
            params["end_time"] = end_time
        if since_id is not None:
            params["since_id"] = since_id
        if until_id is not None:
            params["until_id"] = until_id
        if sort_order is not None:
            params["sort_order"] = sort_order
        if not tweet_fields:
            tweet_fields = [
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
                # "non_public_metrics",
                "note_request_suggestions",
                "note_tweet",
                # organic_metrics — EXCLUDED on search/recent: Field Authorization Error
                # (not-authorized-for-field). Sub-fields impression_count, like_count,
                # reply_count, retweet_count, url_link_clicks, user_profile_clicks
                # require tweet-owner OAuth; use public_metrics instead.
                # "organic_metrics",
                "paid_partnership",
                "possibly_sensitive",
                # promoted_metrics — EXCLUDED on search/recent: Field Authorization Error
                # (not-authorized-for-field). Same owner-only sub-fields as organic_metrics.
                # "promoted_metrics",
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
        params["tweet.fields"] = ",".join(tweet_fields)
        if not expansions:
            expansions = [
                "article.cover_media",
                "article.media_entities",
                "attachments.media_keys",
                # "attachments.media_source_tweet",
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
        params["expansions"] = ",".join(expansions)
        if not media_fields:
            media_fields = [
                "duration_ms",
                "height",
                "media_key",
                "preview_image_url",
                "type",
                "url",
                "width",
            ]
        params["media.fields"] = ",".join(media_fields)
        if not poll_fields:
            poll_fields = [
                "duration_minutes",
                "end_datetime",
                "id",
                "options",
                "voting_status",
            ]
        params["poll.fields"] = ",".join(poll_fields)
        if not user_fields:
            user_fields = [
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
        params["user.fields"] = ",".join(user_fields)
        if not place_fields:
            place_fields = [
                "contained_within",
                "country",
                "country_code",
                "full_name",
                "id",
                "name",
                "place_type",
            ]
        params["place.fields"] = ",".join(place_fields)

        started_at = datetime.now(timezone.utc).isoformat()
        tweets = self._get_all_items(
            "tweets/search/recent",
            params=params,
            max_pages=max_pages,
        )
        ended_at = datetime.now(timezone.utc).isoformat()
        # params_hash = hashlib.md5(
        #     json_module.dumps(params, sort_keys=True, default=str).encode()
        # ).hexdigest()[:8]
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
        envelope_dir = os.path.join(
            self.__configuration.datastore_path,
            "search_recent_tweets",
            slugify_query(query),
        )
        envelope_filename = (
            f"{datetime.now(timezone.utc).isoformat()}_{slugify_query(query)}.json"
        )

        # Return the exact object we persist — the {query, options, results,
        # started_at, ended_at, file_path} envelope — rather than just the raw
        # ``results``. Callers (e.g. XSearchRecentTweetsWorkflow) can then hand
        # ``file_path`` straight to XSearchRecentTweetsPipeline without having to
        # rediscover the timestamped filename, and the pipeline's direct-query
        # branch reads query/options/results/started_at/ended_at from it.
        envelope = {
            "query": query,
            "options": options,
            "results": tweets,
            "started_at": started_at,
            "ended_at": ended_at,
            "file_path": os.path.join(envelope_dir, envelope_filename),
        }
        self.__storage_utils.save_json(
            envelope,
            envelope_dir,
            envelope_filename,
            copy=False,
        )
        return envelope


def as_tools(configuration: XIntegrationConfiguration):
    """Expose the X integration as LangChain tools for agent use."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = XIntegration(configuration)

    class GetUserByIdSchema(BaseModel):
        user_id: str = Field(..., description="Numeric X user ID")

    class GetUserByUsernameSchema(BaseModel):
        username: str = Field(..., description="X handle without the @ prefix")

    class GetUsersByIdsSchema(BaseModel):
        ids: List[str] = Field(..., description="List of up to 100 numeric X user IDs")

    class GetUsersByUsernamesSchema(BaseModel):
        usernames: List[str] = Field(
            ..., description="List of up to 100 X handles (without @)"
        )

    class UserTimelineSchema(BaseModel):
        user_id: str = Field(..., description="Numeric X user ID")
        max_results: int = Field(
            100, description="Results per page (X v2 cap is 100 for most endpoints)"
        )
        max_pages: Optional[int] = Field(
            1, description="Maximum number of pages to fetch (None to exhaust)"
        )

    class GetTweetByIdSchema(BaseModel):
        tweet_id: str = Field(..., description="Numeric tweet ID")

    class GetTweetsByIdsSchema(BaseModel):
        ids: List[str] = Field(..., description="List of up to 100 tweet IDs")

    class SearchRecentTweetsSchema(BaseModel):
        query: str = Field(
            ...,
            description="X v2 search query (1-4096 chars), e.g. 'python lang:en -is:retweet'",
        )
        start_time: Optional[str] = Field(
            None,
            description="Oldest UTC timestamp YYYY-MM-DDTHH:mm:ssZ (inclusive)",
        )
        end_time: Optional[str] = Field(
            None,
            description="Newest UTC timestamp YYYY-MM-DDTHH:mm:ssZ (exclusive)",
        )
        since_id: Optional[str] = Field(
            None, description="Only return tweets with an ID greater than this"
        )
        until_id: Optional[str] = Field(
            None, description="Only return tweets with an ID less than this"
        )
        max_results: int = Field(100, description="Results per page, 10-100")
        sort_order: Optional[str] = Field(None, description="'recency' or 'relevancy'")
        tweet_fields: Optional[List[str]] = Field(
            None,
            description="Tweet object fields (e.g. ['created_at', 'public_metrics', 'lang'])",
        )
        expansions: Optional[List[str]] = Field(
            None,
            description="Object expansions (e.g. ['author_id', 'referenced_tweets.id'])",
        )
        media_fields: Optional[List[str]] = Field(
            None, description="Media object fields when media is expanded"
        )
        poll_fields: Optional[List[str]] = Field(
            None, description="Poll object fields when polls are expanded"
        )
        user_fields: Optional[List[str]] = Field(
            None, description="User object fields when author is expanded"
        )
        place_fields: Optional[List[str]] = Field(
            None, description="Place object fields when geo is expanded"
        )
        max_pages: Optional[int] = Field(
            1, description="Maximum number of pages to fetch (None to exhaust)"
        )

    return [
        StructuredTool(
            name="x_get_user_by_id",
            description="Get an X (Twitter) user profile by numeric user ID.",
            func=lambda user_id: integration.get_user_by_id(user_id),
            args_schema=GetUserByIdSchema,
        ),
        StructuredTool(
            name="x_get_user_by_username",
            description="Get an X (Twitter) user profile by handle (without @).",
            func=lambda username: integration.get_user_by_username(username),
            args_schema=GetUserByUsernameSchema,
        ),
        StructuredTool(
            name="x_get_users_by_ids",
            description="Get multiple X user profiles in one call by their numeric IDs (up to 100).",
            func=lambda ids: integration.get_users_by_ids(ids),
            args_schema=GetUsersByIdsSchema,
        ),
        StructuredTool(
            name="x_get_users_by_usernames",
            description="Get multiple X user profiles in one call by their handles (up to 100).",
            func=lambda usernames: integration.get_users_by_usernames(usernames),
            args_schema=GetUsersByUsernamesSchema,
        ),
        StructuredTool(
            name="x_get_user_tweets",
            description="Get tweets posted by an X user (their timeline).",
            func=lambda user_id, max_results=100, max_pages=1: (
                integration.get_user_tweets(
                    user_id, max_results=max_results, max_pages=max_pages
                )
            ),
            args_schema=UserTimelineSchema,
        ),
        StructuredTool(
            name="x_get_user_mentions",
            description="Get tweets that mention an X user.",
            func=lambda user_id, max_results=100, max_pages=1: (
                integration.get_user_mentions(
                    user_id, max_results=max_results, max_pages=max_pages
                )
            ),
            args_schema=UserTimelineSchema,
        ),
        StructuredTool(
            name="x_get_user_liked_tweets",
            description="Get tweets that an X user has liked.",
            func=lambda user_id, max_results=100, max_pages=1: (
                integration.get_user_liked_tweets(
                    user_id, max_results=max_results, max_pages=max_pages
                )
            ),
            args_schema=UserTimelineSchema,
        ),
        StructuredTool(
            name="x_get_user_followers",
            description="Get the followers of an X user.",
            func=lambda user_id, max_results=100, max_pages=1: (
                integration.get_user_followers(
                    user_id, max_results=max_results, max_pages=max_pages
                )
            ),
            args_schema=UserTimelineSchema,
        ),
        StructuredTool(
            name="x_get_user_following",
            description="Get the accounts an X user is following.",
            func=lambda user_id, max_results=100, max_pages=1: (
                integration.get_user_following(
                    user_id, max_results=max_results, max_pages=max_pages
                )
            ),
            args_schema=UserTimelineSchema,
        ),
        StructuredTool(
            name="x_get_tweet_by_id",
            description="Get a single tweet by its numeric ID.",
            func=lambda tweet_id: integration.get_tweet_by_id(tweet_id),
            args_schema=GetTweetByIdSchema,
        ),
        StructuredTool(
            name="x_get_tweets_by_ids",
            description="Get multiple tweets in one call by their numeric IDs (up to 100).",
            func=lambda ids: integration.get_tweets_by_ids(ids),
            args_schema=GetTweetsByIdsSchema,
        ),
        StructuredTool(
            name="x_search_recent_tweets",
            description="Search tweets posted in the last 7 days using X v2 search syntax.",
            func=lambda query, start_time=None, end_time=None, since_id=None, until_id=None, max_results=100, sort_order=None, tweet_fields=None, expansions=None, media_fields=None, poll_fields=None, user_fields=None, place_fields=None, max_pages=1: (
                integration.search_recent_tweets(
                    query,
                    start_time=start_time,
                    end_time=end_time,
                    since_id=since_id,
                    until_id=until_id,
                    max_results=max_results,
                    sort_order=sort_order,
                    tweet_fields=tweet_fields,
                    expansions=expansions,
                    media_fields=media_fields,
                    poll_fields=poll_fields,
                    user_fields=user_fields,
                    place_fields=place_fields,
                    max_pages=max_pages,
                )
            ),
            args_schema=SearchRecentTweetsSchema,
        ),
    ]
