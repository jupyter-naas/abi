import hashlib
import os
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Dict, List, Optional

import requests
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
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"X API request failed: {str(e)}")

    def _get_all_items(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        max_pages: Optional[int] = None,
    ) -> List[Dict]:
        """Iterate an X v2 paginated endpoint until exhausted.

        X v2 pagination uses `pagination_token` in the request and
        `meta.next_token` in the response.

        Args:
            endpoint (str): API endpoint path.
            params (Dict, optional): Query-string parameters. `max_results`
                defaults to 100 (the v2 cap for most endpoints).
            max_pages (int, optional): Stop after this many pages.

        Returns:
            List[Dict]: Concatenated `data` items from every page.
        """
        params = dict(params or {})
        params.setdefault("max_results", 100)

        items: List[Dict] = []
        page = 0
        while True:
            response = self._make_request(endpoint, params=params)
            data = response.get("data", [])
            if data:
                items.extend(data)

            page += 1
            if max_pages is not None and page >= max_pages:
                break

            next_token = response.get("meta", {}).get("next_token")
            if not next_token:
                break
            params["pagination_token"] = next_token

        return items

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
    ) -> List[Dict]:
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
    ) -> List[Dict]:
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
    ) -> List[Dict]:
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
    ) -> List[Dict]:
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
    ) -> List[Dict]:
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
        lambda self, query, max_results=100, max_pages=1: (
            "search_recent_tweets_"
            + hashlib.md5(query.encode()).hexdigest()[:8]
            + f"_{max_results}_{max_pages}"
        ),
        cache_type=DataType.JSON,
        ttl=timedelta(days=1),
    )
    def search_recent_tweets(
        self,
        query: str,
        max_results: int = 100,
        max_pages: Optional[int] = 1,
    ) -> List[Dict]:
        """Search tweets from the last 7 days.

        Endpoint: GET /2/tweets/search/recent
        """
        tweets = self._get_all_items(
            "tweets/search/recent",
            params={"query": query, "max_results": max_results},
            max_pages=max_pages,
        )
        query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
        self.__storage_utils.save_json(
            tweets,
            os.path.join(self.__configuration.datastore_path, "search_recent_tweets"),
            f"{query_hash}.json",
        )
        return tweets


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
            description="X v2 search query (e.g. 'python lang:en -is:retweet')",
        )
        max_results: int = Field(100, description="Results per page (cap 100)")
        max_pages: Optional[int] = Field(
            1, description="Maximum number of pages to fetch"
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
            func=lambda query, max_results=100, max_pages=1: (
                integration.search_recent_tweets(
                    query, max_results=max_results, max_pages=max_pages
                )
            ),
            args_schema=SearchRecentTweetsSchema,
        ),
    ]
