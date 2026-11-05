"""LinkedIn (Voyager API, with the session cookies of a member), async, on
``naas_abi_sdk`` only.

Port of ``naas_abi_marketplace.applications.linkedin.integrations``: same
endpoints, query ids and tool names. Every raw response is archived as JSON in
object storage under ``datastore_path`` (as ``StorageUtils.save_json`` did), and
each request is cached for a day in the engine's cache service, as core's file
cache did (LinkedIn limits accounts that send too many requests).

Fixed in the port (in-engine bugs):
- an error result no longer carries the request headers and cookies (the
  session token went to the model and the conversation);
- comments, reactions and reposts passed arguments ``_make_request`` does not
  take (every call failed), and paginated on a URL computed once;
- ``search_people`` without an organization read an unset variable;
- the posts feed raised ``AssertionError`` on an empty feed;
- picture URLs no longer download each picture.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import logging
import urllib.parse
from collections.abc import MutableMapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pydash as _
from naas_abi_apps.common.http import HttpConfiguration, request
from naas_abi_apps.common.storage import ObjectStorage, archive_json
from naas_abi_sdk.integration import Integration, IntegrationConnectionError

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://www.linkedin.com/voyager/api"
CACHE_TTL = timedelta(days=1)
# Pause between two pages of a people search, as in-engine.
PAGE_DELAY_SECONDS = 1.0
MUTUAL_CONNECTIONS_QUERY_ID = (
    "voyagerSearchDashClusters.ef3d0937fb65bd7812e32e5a85028e79"
)
SEARCH_PEOPLE_QUERY_ID = "voyagerSearchDashClusters.c0f8645a22a6347486d76d5b9d985fd7"
LOCATION_IDS = {"France": "105015875"}


@dataclass(kw_only=True)
class LinkedInIntegrationConfiguration(HttpConfiguration):
    """li_at, JSESSIONID: the member's session cookies. linkedin_url: the
    member's own profile URL. storage: where responses are archived. cache: the
    engine's cache service (``None``: no cache)."""

    li_at: str
    JSESSIONID: str
    linkedin_url: str = ""
    base_url: str = DEFAULT_BASE_URL
    datastore_path: str = "linkedin"
    storage: ObjectStorage | None = None
    cache: Any = field(default=None, repr=False)
    page_delay: float = PAGE_DELAY_SECONDS


def _join(*parts: str) -> str:
    return "/".join(p.strip("/") for p in parts if p)


def _flatten_dict(data: Any, parent_key: str = "", sep: str = "_") -> Any:
    if not isinstance(data, dict):
        return data
    items: list = []
    for k, v in data.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _clean_dict(data: Any) -> Any:
    """Drop keys starting with ``*`` or containing ``urn``, recursively."""
    if isinstance(data, list):
        return [v for v in (_clean_dict(x) for x in data) if v is not None]
    if isinstance(data, dict):
        return {
            k: v
            for k, v in ((k, _clean_dict(v)) for k, v in data.items())
            if v is not None and not k.startswith("*") and "urn" not in k.lower()
        }
    return data


def _find_keys(d: Any, target_keys: list[str]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    if isinstance(d, dict):
        for k, v in d.items():
            if k in target_keys:
                results[k] = v
            if isinstance(v, (dict, list)):
                results.update(_find_keys(v, target_keys))
    elif isinstance(d, list):
        for item in d:
            results.update(_find_keys(item, target_keys))
    return results


def picture_urls(data: dict, key: str) -> list[str]:
    """The picture URLs under ``data[key]``, smallest to largest."""
    found = _find_keys(data.get(key, {}), ["rootUrl", "artifacts"])
    root_url = found.get("rootUrl")
    if not root_url:
        return []
    return [
        f"{root_url}{a.get('fileIdentifyingUrlPathSegment')}"
        for a in found.get("artifacts", [])
    ]


def _pop_noise(d: Any) -> None:
    if isinstance(d, dict):
        for key in ("trackingId", "$recipeTypes", "paging"):
            d.pop(key, None)
        for v in d.values():
            _pop_noise(v)
    elif isinstance(d, list):
        for item in d:
            _pop_noise(item)


def parse_clean(data: dict, include_images: bool = True) -> dict:
    """The ``included`` entities grouped by ``$type``, without view/group/action
    entries and tracking noise; pictures replaced by their largest URL."""
    results: dict[str, list] = {}
    for include in _.get(data, "included", []) or []:
        _type = include.get("$type")
        if _type is None or _type.endswith(("View", "Group", "Action")):
            continue
        entities = results.setdefault(_type, [])
        if include_images:
            for key in list(include):
                if any(img in key.lower() for img in ("logo", "picture", "image")):
                    urls = picture_urls(include, key)
                    if urls:
                        include[key] = urls[-1]
        _pop_noise(include)
        if include:
            entities.append(include)
    return results


def clean(data: dict) -> dict:
    """What the tools return to the model: the raw response, cleaned, parsed
    and flattened (the in-engine ``clean_json``)."""
    cleaned = _clean_dict(data)
    parsed = parse_clean(cleaned) if isinstance(cleaned, dict) else {}
    return _flatten_dict(parsed)


def date_from_pagination_token(token: str) -> str:
    epoch_str = str(base64.b64decode(token)).split("-")[-1][:-1]
    return datetime.fromtimestamp(
        int(epoch_str) / 1000.0, ZoneInfo("Europe/Paris")
    ).strftime("%Y-%m-%dT%H:%M:%S%z")


def organization_public_id(url: str) -> dict[str, str]:
    """``.../company/<id>/``, ``/school/`` or ``/showcase/`` -> ``<id>``."""
    for marker in ("/company/", "/school/", "/showcase/"):
        if marker in url:
            return {"result": url.rsplit(marker)[-1].split("/")[0]}
    return {
        "error": f"LinkedIn organization URL '{url}' not recognized. Must contain "
        "/company/, /school/ or /showcase/ in the URL"
    }


def profile_vanity_name(url: str) -> dict[str, str]:
    """``.../in/<vanity>/`` -> ``<vanity>``."""
    if "/in/" in url:
        return {"result": url.rsplit("/in/")[-1].split("/")[0]}
    return {
        "error": f"LinkedIn profile URL '{url}' not recognized. Must contain /in/ in the URL"
    }


def activity_id(url: str) -> dict[str, str]:
    """The activity id of a post URL (``-activity-<id>-`` or ``:activity:<id>``)."""
    if "-activity-" in url:
        return {"result": url.split("-activity-")[-1].split("-")[0]}
    if ":activity:" in url:
        return {"result": url.split(":activity:")[-1].split("/")[0]}
    return {"error": f"LinkedIn activity ID not found for URL '{url}'"}


def people_results(cleaned: dict) -> list[dict[str, Any]]:
    """The people of one cleaned search page."""
    people = []
    for entity in cleaned.get(
        "com.linkedin.voyager.dash.search.EntityResultViewModel", []
    ):
        navigation_url = _.get(entity, "navigationUrl") or ""
        profile_url = navigation_url.split("?")[0]
        people.append(
            {
                "id": navigation_url.split("miniProfile%3")[-1]
                if "miniProfile%3" in navigation_url
                else None,
                "public_id": profile_url.rstrip("/").split("/")[-1],
                "name": _.get(entity, "title.text"),
                "headline": _.get(entity, "primarySubtitle.text"),
                "location": _.get(entity, "secondarySubtitle.text"),
                "profile_url": profile_url,
                "profile_picture": _.get(
                    entity,
                    "image.attributes[0].detailData.nonEntityProfilePicture.vectorImage.artifacts[0].fileIdentifyingUrlPathSegment",
                ),
                "connection_degree": _.get(
                    entity, "entityCustomTrackingInfo.memberDistance"
                ),
            }
        )
    return people


class LinkedInIntegration(Integration):
    """LinkedIn organizations, profiles, posts and people searches."""

    def __init__(self, configuration: LinkedInIntegrationConfiguration):
        super().__init__(configuration)
        self.configuration = configuration
        jsessionid = configuration.JSESSIONID.replace('"', "")
        self.cookies = {"li_at": configuration.li_at, "JSESSIONID": jsessionid}
        self.headers = {
            "x-li-lan": "en_US",
            "accept": "application/vnd.linkedin.normalized+json+2.1",
            "csrf-token": jsessionid,
            "x-restli-protocol-version": "2.0.0",
            "cookie": "; ".join(f"{k}={v}" for k, v in self.cookies.items()),
        }
        self._own_public_id: str | None = None

    # -- transport ---------------------------------------------------------

    def _cache_key(self, endpoint: str) -> str:
        # The cookies scope the cache to the member, hashed: never in a key.
        digest = hashlib.sha256(
            f"{self.cookies['li_at']}\n{self.cookies['JSESSIONID']}\n{endpoint}".encode()
        ).hexdigest()
        return f"linkedin:{digest}"

    async def _make_request(self, endpoint: str) -> dict[str, Any]:
        """GET ``base_url + endpoint``, through the cache. A failure is an
        ``{"error": ...}`` result (status and body, never the credentials)."""
        cache = self.configuration.cache
        key = self._cache_key(endpoint)
        if cache is not None:
            try:
                return await cache.get(key, ttl=CACHE_TTL)
            except Exception as exc:  # noqa: BLE001 - a miss, expired, or no cache tier
                logger.debug("LinkedIn: cache miss for %s (%s)", endpoint, exc)
        url = f"{self.configuration.base_url}{endpoint}"
        try:
            response = await request(
                self.configuration,
                "GET",
                url,
                service="LinkedIn",
                raise_for_status=False,
                headers=self.headers,
            )
        except IntegrationConnectionError as exc:
            return {"error": str(exc), "url": url}
        if response.status_code >= 400:
            return {
                "error": f"LinkedIn API request failed: HTTP {response.status_code}",
                "url": url,
                "response": response.text[:2000],
            }
        data = response.json()
        if cache is not None:
            try:
                await cache.set_json(key, data)
            except Exception:
                logger.warning("LinkedIn: could not cache %s", endpoint, exc_info=True)
        return data

    async def _archive(self, prefix: str, filename: str, data: Any) -> None:
        await archive_json(
            self.configuration.storage,
            _join(self.configuration.datastore_path, prefix),
            filename if filename.endswith(".json") else f"{filename}.json",
            data,
        )

    async def _result(
        self, prefix: str, filename: str, data: dict, cleaned: bool
    ) -> dict:
        await self._archive(prefix, filename, data)
        if "error" in data or not cleaned:
            return data
        result = clean(data)
        await self._archive(prefix, f"{filename.removesuffix('.json')}_cleaned", result)
        return result

    # -- organizations -----------------------------------------------------

    async def get_organization_info(
        self, url: str, return_cleaned_json: bool = False
    ) -> dict:
        """An organization (company, school or showcase page)."""
        org = organization_public_id(url)
        if "error" in org:
            return org
        org_id = org["result"]
        params = {
            "decorationId": "com.linkedin.voyager.deco.organization.web.WebFullCompanyMain-33",
            "q": "universalName",
            "universalName": org_id,
        }
        data = await self._make_request(
            f"/organization/companies?{urllib.parse.urlencode(params)}"
        )
        return await self._result(
            _join("get_organization_info", org_id), org_id, data, return_cleaned_json
        )

    async def get_organization_id(self, url: str) -> dict[str, str]:
        """The numeric id of an organization (what the people searches filter on)."""
        data = await self.get_organization_info(url)
        if "error" in data:
            return data
        elements = (data.get("data") or {}).get("*elements", [])
        if not elements:
            return {"error": f"LinkedIn organization ID not found for URL '{url}'"}
        return {"result": elements[0].replace("urn:li:fs_normalized_company:", "")}

    # -- profiles ----------------------------------------------------------

    async def get_profile_top_card(
        self, url: str, return_cleaned_json: bool = False
    ) -> dict:
        """The top card of a profile: the quick overview."""
        vanity = profile_vanity_name(url)
        if "error" in vanity:
            return vanity
        profile_id = vanity["result"]
        if profile_id.startswith("AcoAA"):
            return {
                "error": f"LinkedIn profile ID '{profile_id}' starts with AcoAA. "
                f"LinkedIn profile URL is not valid: {url}"
            }
        data = await self._make_request(
            f"/graphql?variables=(vanityName:{profile_id})"
            "&queryId=voyagerIdentityDashProfiles.0bc93b66ba223b9d30d1cb5c05ff031a"
        )
        return await self._result(
            _join("get_profile_top_card", profile_id),
            profile_id,
            data,
            return_cleaned_json,
        )

    @staticmethod
    def _profile_entity(data: dict) -> tuple[str | None, dict | None]:
        elements = _.get(
            data, "data.data.identityDashProfilesByMemberIdentity.*elements", []
        )
        if not elements:
            return None, None
        urn = elements[0]
        entity = _.find(data.get("included", []), lambda x: x.get("entityUrn") == urn)
        return urn, entity

    async def get_profile_id(self, url: str) -> dict[str, str]:
        """The member id of a profile (``ACoAA...``)."""
        data = await self.get_profile_top_card(url)
        if "error" in data:
            return data
        urn, _entity = self._profile_entity(data)
        if not urn:
            return {"error": f"LinkedIn profile ID not found for URL '{url}'"}
        return {"result": urn.replace("urn:li:fsd_profile:", "")}

    async def get_profile_public_id(self, url: str) -> dict[str, str]:
        """The public identifier of a profile (the vanity name it resolves to)."""
        data = await self.get_profile_top_card(url)
        if "error" in data:
            return data
        urn, entity = self._profile_entity(data)
        if not urn:
            return {"error": f"LinkedIn profile public ID not found for URL '{url}'"}
        if entity and entity.get("publicIdentifier"):
            return {"result": entity["publicIdentifier"]}
        actions = _.get(
            entity or {},
            "profileStatefulProfileActions.overflowActionsResolutionResults",
            [],
        )
        for key in ("shareProfileUrlViaMessage", "shareProfileUrl"):
            for action in actions or []:
                if action.get(key):
                    return profile_vanity_name(action[key])
        return {"error": f"LinkedIn profile public ID not found for URL '{url}'"}

    async def own_public_id(self) -> str:
        """The public id of the member whose cookies these are (from
        ``linkedin_url``), fetched once."""
        if self._own_public_id is None:
            if not self.configuration.linkedin_url:
                raise RuntimeError(
                    "LinkedIn profile URL is not configured: set the "
                    "LINKEDIN_PROFILE_URL secret to use this feature."
                )
            result = await self.get_profile_public_id(self.configuration.linkedin_url)
            if not result.get("result"):
                raise RuntimeError(
                    "Failed to fetch the LinkedIn profile public ID for "
                    f"'{self.configuration.linkedin_url}': {result.get('error')}"
                )
            self._own_public_id = result["result"]
        return self._own_public_id

    async def _ids(self, url: str) -> dict[str, str]:
        """``{"id", "public_id"}`` of a profile, or an error."""
        profile_id = await self.get_profile_id(url)
        if "error" in profile_id:
            return profile_id
        public_id = await self.get_profile_public_id(url)
        if "error" in public_id:
            return public_id
        return {"id": profile_id["result"], "public_id": public_id["result"]}

    async def get_profile_data(
        self,
        url: str,
        profile_type: str = "skills",
        locale: str = "en_US",
        return_cleaned_json: bool = False,
    ) -> dict:
        """One section of a profile: ``skills``, ``experience``, ``education``."""
        ids = await self._ids(url)
        if "error" in ids:
            return ids
        data = await self._make_request(
            "/graphql?variables=(profileUrn:urn%3Ali%3Afsd_profile%3A"
            f"{ids['id']},sectionType:{profile_type},locale:{locale})"
            "&queryId=voyagerIdentityDashProfileComponents.c5d4db426a0f8247b8ab7bc1d660775a"
        )
        return await self._result(
            _join("get_profile_data", ids["public_id"], profile_type),
            ids["id"],
            data,
            return_cleaned_json,
        )

    async def get_profile_skills(self, url: str, return_cleaned_json: bool = False):
        return await self.get_profile_data(
            url, "skills", return_cleaned_json=return_cleaned_json
        )

    async def get_profile_experience(self, url: str, return_cleaned_json: bool = False):
        return await self.get_profile_data(
            url, "experience", return_cleaned_json=return_cleaned_json
        )

    async def get_profile_education(self, url: str, return_cleaned_json: bool = False):
        return await self.get_profile_data(
            url, "education", return_cleaned_json=return_cleaned_json
        )

    async def get_profile_posts_feed(
        self,
        url: str,
        start: int = 0,
        count: int = 1,
        return_cleaned_json: bool = False,
    ) -> dict:
        """The latest posts of a profile."""
        ids = await self._ids(url)
        if "error" in ids:
            return ids
        data = await self._make_request(
            "/graphql?includeWebMetadata=true&variables="
            f"(start:{start},count:{count},profileUrn:urn%3Ali%3Afsd_profile%3A{ids['id']})"
            "&queryId=voyagerFeedDashProfileUpdates.80d5abb3cd25edff72c093a5db696079"
        )
        if "error" in data:
            return data
        feed = _.get(data, "data.data.feedDashProfileUpdatesByMemberShareFeed") or {}
        elements = feed.get("*elements") or []
        token = _.get(feed, "metadata.paginationToken")
        if not elements:
            return {"error": f"No post found for LinkedIn profile '{url}'"}
        post_id = elements[0].split("urn:li:activity:")[-1].split(",")[0]
        published = date_from_pagination_token(token) if token else "unknown-date"
        return await self._result(
            _join("get_profile_posts_feed", ids["public_id"], f"{published}_{post_id}"),
            f"profile_{ids['id']}_post_{post_id}",
            data,
            return_cleaned_json,
        )

    # -- posts -------------------------------------------------------------

    async def get_post_stats(self, url: str, return_cleaned_json: bool = False) -> dict:
        """One post and its counts."""
        activity = activity_id(url)
        if "error" in activity:
            return activity
        post = activity["result"]
        data = await self._make_request(f"/feed/updates/urn:li:activity:{post}")
        return await self._result(
            _join("get_post_stats", post), post, data, return_cleaned_json
        )

    async def _paginate(
        self,
        name: str,
        query_id: str,
        variables: dict[str, Any],
        path: str,
        start: int,
        count: int,
        limit: int,
        return_cleaned_json: bool,
        include_web_metadata: bool = False,
    ) -> dict:
        """Fetch pages of ``count`` until ``total`` (at ``path + .paging``) or
        ``limit`` (-1: none) is reached; the pages merged into the first."""
        all_data: dict | None = None
        post = variables["_post"]
        while True:
            if limit != -1 and limit < count:
                count = limit
            page_variables = {k: v for k, v in variables.items() if k != "_post"} | {
                "start": start,
                "count": count,
            }
            endpoint = (
                "/graphql?"
                + ("includeWebMetadata=true&" if include_web_metadata else "")
                + f"variables={urllib.parse.quote(str(page_variables))}&queryId={query_id}"
            )
            data = await self._make_request(endpoint)
            if "error" in data:
                if all_data is None:
                    return data
                break
            if all_data is None:
                all_data = data
            else:
                all_data.setdefault("included", []).extend(data.get("included", []))
                merged = _.get(all_data, f"{path}.*elements")
                if isinstance(merged, list):
                    merged.extend(_.get(data, f"{path}.*elements") or [])
            total = _.get(data, f"{path}.paging.total") or 0
            fetched = start + len(_.get(data, f"{path}.*elements") or [])
            if fetched >= total:
                break
            if limit != -1:
                limit -= count
                if limit <= 0:
                    break
            start += count
        return await self._result(
            _join(name, post), post, all_data or {}, return_cleaned_json
        )

    async def get_post_reactions(
        self,
        url: str,
        start: int = 0,
        count: int = 100,
        limit: int = -1,
        return_cleaned_json: bool = False,
    ) -> dict:
        """The reactions to a post."""
        activity = activity_id(url)
        if "error" in activity:
            return activity
        post = activity["result"]
        return await self._paginate(
            "get_post_reactions",
            "voyagerSocialDashReactions.41ebf31a9f4c4a84e35a49d5abc9010b",
            {"_post": post, "threadUrn": f"urn:li:activity:{post}"},
            "data.data.socialDashReactionsByReactionType",
            start,
            count,
            limit,
            return_cleaned_json,
        )

    async def get_post_comments(
        self,
        url: str,
        start: int = 0,
        count: int = 100,
        limit: int = -1,
        return_cleaned_json: bool = False,
    ) -> dict:
        """The comments on a post, newest first."""
        activity = activity_id(url)
        if "error" in activity:
            return activity
        post = activity["result"]
        return await self._paginate(
            "get_post_comments",
            "voyagerSocialDashComments.afec6d88d7810d45548797a8dac4fb87",
            {
                "_post": post,
                "socialDetailUrn": f"urn:li:fsd_socialDetail:(urn:li:activity:{post},"
                f"urn:li:activity:{post},urn:li:highlightedReply:-)",
                "sortOrder": "REVERSE_CHRONOLOGICAL",
            },
            "data.data.socialDashCommentsBySocialDetail",
            start,
            count,
            limit,
            return_cleaned_json,
        )

    async def get_post_reposts(
        self,
        url: str,
        start: int = 0,
        count: int = 100,
        limit: int = -1,
        return_cleaned_json: bool = False,
    ) -> dict:
        """The reposts of a post."""
        activity = activity_id(url)
        if "error" in activity:
            return activity
        post = activity["result"]
        return await self._paginate(
            "get_post_reposts",
            "voyagerFeedDashReshareFeed.47df8432a2f218e699221ed615e04842",
            {"_post": post, "targetUrn": f"urn:li:share:{post}"},
            "data.data.feedDashReshareFeedByReshareFeed",
            start,
            count,
            limit,
            return_cleaned_json,
            include_web_metadata=True,
        )

    # -- people searches ---------------------------------------------------

    async def _export_excel(
        self, people: list[dict[str, Any]], prefix: str, filename: str, **columns: str
    ) -> str:
        """The people as an Excel sheet in object storage; its path, or "" when
        there is no one or no storage."""
        storage = self.configuration.storage
        if not people or storage is None:
            return ""
        import pandas as pd

        df = pd.DataFrame(people)
        df["init_profile_id"] = await self.own_public_id()
        for column, value in columns.items():
            if value:
                df[column] = value
        buffer = io.BytesIO()
        await asyncio.to_thread(
            df.to_excel, buffer, sheet_name="EXPORT_LINKEDIN", index=False
        )
        path = _join(self.configuration.datastore_path, prefix)
        await storage.put_object(path, filename, buffer.getvalue())
        return _join(path, filename)

    async def _organization_filter(
        self, organization_url: str | None
    ) -> dict[str, str]:
        """``{"id", "public_id"}`` of an organization filter ("" for none)."""
        if organization_url is None:
            return {"id": "", "public_id": ""}
        org_id = await self.get_organization_id(organization_url)
        if "error" in org_id:
            return org_id
        public = organization_public_id(organization_url)
        if "error" in public:
            return public
        return {"id": org_id["result"], "public_id": public["result"]}

    async def _search(
        self,
        prefix: str,
        filename: str,
        query_id: str,
        parameters: str,
        start: int,
        count: int,
        limit: int,
    ) -> dict[str, Any]:
        people: list[dict[str, Any]] = []
        total = 0
        while True:
            endpoint = (
                f"/graphql?queryId={query_id}&variables=(start:{start},count:{count},"
                "origin:FACETED_SEARCH,query:(flagshipSearchIntent:SEARCH_SRP,"
                f"queryParameters:List({parameters},(key:resultType,value:List(PEOPLE))),"
                "includeFiltersInResponse:false))"
            )
            data = await self._make_request(endpoint)
            if "error" in data:
                if not people:
                    return data
                break
            page = f"{filename}_{start}_{count}"
            await self._archive(_join(prefix, "pages"), page, data)
            people.extend(people_results(clean(data)))
            total = (
                _.get(
                    data, "data.data.searchDashClustersByAll.metadata.totalResultCount"
                )
                or 0
            )
            logger.info("LinkedIn search %s: %d of %d", filename, len(people), total)
            if start + count >= total or len(people) >= limit:
                break
            await asyncio.sleep(self.configuration.page_delay)
            start += count
        return {
            "total_connections": total,
            "connections_returned": len(people),
            "connections": people,
        }

    async def get_mutual_connexions(
        self,
        profile_url: str,
        connection_distance: str = "F",
        organization_url: str | None = None,
        start: int = 0,
        count: int = 50,
        limit: int = 1000,
        query_id: str = MUTUAL_CONNECTIONS_QUERY_ID,
    ) -> dict:
        """The members connected to a profile, at a distance (F first, S second,
        O others), optionally working at an organization."""
        ids = await self._ids(profile_url)
        if "error" in ids:
            return ids
        org = await self._organization_filter(organization_url)
        if "error" in org:
            return org
        own = await self.own_public_id()
        prefix = _join(
            "get_mutual_connexions",
            own,
            ids["public_id"],
            connection_distance,
            org["public_id"] or "_all",
        )
        filename = f"get_mutual_connexions_{ids['public_id']}_{connection_distance}"
        if org["public_id"]:
            filename += f"_{org['public_id']}"
        result = await self._search(
            prefix,
            filename,
            query_id,
            f"(key:connectionOf,value:List({ids['id']})),"
            f"(key:currentCompany,value:List({org['id']})),"
            f"(key:network,value:List({connection_distance}))",
            start,
            count,
            limit,
        )
        if "error" in result:
            return result
        await self._archive(prefix, filename, result)
        result["excel_url"] = await self._export_excel(
            result["connections"],
            prefix,
            f"{own}_{filename}.xlsx",
            linkedin_profile_id_parameter=ids["public_id"],
            connections_distance_parameter=connection_distance,
            linkedin_organization_id_parameter=org["public_id"],
        )
        return result

    async def search_people(
        self,
        connection_distance: str = "F",
        organization_url: str | None = None,
        location: str | None = None,
        start: int = 0,
        count: int = 50,
        limit: int = 1000,
        query_id: str = SEARCH_PEOPLE_QUERY_ID,
    ) -> dict:
        """Members at a connection distance, optionally at an organization and in
        a location (only ``France`` is mapped)."""
        org = await self._organization_filter(organization_url)
        if "error" in org:
            return org
        own = await self.own_public_id()
        prefix = _join(
            "search_people", own, connection_distance, org["public_id"] or "_all"
        )
        filename = f"search_people_{connection_distance}"
        if org["public_id"]:
            filename += f"_{org['public_id']}"
        location_id = LOCATION_IDS.get(location or "", "")
        if location and not location_id:
            logger.warning(
                "LinkedIn: location %r is not mapped; not filtered", location
            )
        if location_id:
            prefix = _join(prefix, location_id)
            filename += f"_{location_id}"
        result = await self._search(
            prefix,
            filename,
            query_id,
            f"(key:network,value:List({connection_distance})),"
            f"(key:currentCompany,value:List({org['id']})),"
            f"(key:geoUrn,value:List({location_id}))",
            start,
            count,
            limit,
        )
        if "error" in result:
            return result
        await self._archive(prefix, filename, result)
        result["excel_url"] = await self._export_excel(
            result["connections"],
            prefix,
            f"{own}_{filename}.xlsx",
            connections_distance_parameter=connection_distance,
            linkedin_organization_id_parameter=org["public_id"],
        )
        return result


def as_tools(configuration: LinkedInIntegrationConfiguration) -> list[Any]:
    """LangChain tools over the integration, under their in-engine names."""
    from typing import Annotated

    from langchain_core.tools import StructuredTool
    from naas_abi_apps.common.agents import schema_tool
    from pydantic import BaseModel, Field

    integration = LinkedInIntegration(configuration)
    organization_pattern = r"https://.+\.linkedin\.com/(company|school|showcase)/[^?]+"
    profile_pattern = r"https://.+\.linkedin\.[^/]+/in/[^?]+"

    class GetOrganizationInfoSchema(BaseModel):
        url: str = Field(
            ..., description="LinkedIn organization URL", pattern=organization_pattern
        )

    class GetProfileSchema(BaseModel):
        url: str = Field(
            ..., description="LinkedIn profile URL", pattern=profile_pattern
        )

    class GetProfilePostsFeedSchema(BaseModel):
        url: str = Field(
            ..., description="LinkedIn profile URL", pattern=profile_pattern
        )
        count: int = Field(1, ge=1, le=50, description="Number of posts to fetch")

    class GetActivitySchema(BaseModel):
        url: str = Field(
            ...,
            description="LinkedIn post URL (with -activity-<id>- or urn:li:activity:<id>)",
        )

    distance = Annotated[
        str,
        Field(
            description="Connection distance. F for First Degree, S for Second Degree, O for Others.",
            pattern=r"^[FSO]$",
        ),
    ]

    class GetMutualConnectionsSchema(BaseModel):
        profile_url: str = Field(
            ...,
            description="LinkedIn profile URL of the person you want to get mutual connections.",
            pattern=profile_pattern,
        )
        connection_distance: distance = "F"
        organization_url: str | None = Field(
            None,
            description="LinkedIn organization URL to filter the mutual connections.",
            pattern=organization_pattern,
        )

    class SearchPeopleSchema(BaseModel):
        connection_distance: distance = "F"
        organization_url: str | None = Field(
            None,
            description="LinkedIn organization URL to filter the people.",
            pattern=organization_pattern,
        )
        location: str | None = Field(None, description="Location to filter the people.")
        limit: int = Field(
            1000, ge=1, description="Maximum number of people to return."
        )

    def cleaned(method: Any) -> Any:
        async def call(**kwargs: Any) -> Any:
            return await method(return_cleaned_json=True, **kwargs)

        return call

    def tool(name: str, description: str, fn: Any, schema: type) -> Any:
        return StructuredTool(
            name=name,
            description=description,
            coroutine=schema_tool(fn, schema),
            args_schema=schema,
        )

    return [
        tool(
            "linkedin_get_organization_info",
            "Get organization information for a LinkedIn organization.",
            cleaned(integration.get_organization_info),
            GetOrganizationInfoSchema,
        ),
        tool(
            "linkedin_get_profile_top_card",
            "Get profile top card for a LinkedIn profile, meaning the quick overview information of the profile.",
            cleaned(integration.get_profile_top_card),
            GetProfileSchema,
        ),
        tool(
            "linkedin_get_profile_skills",
            "Get profile skills for a LinkedIn profile.",
            cleaned(integration.get_profile_skills),
            GetProfileSchema,
        ),
        tool(
            "linkedin_get_profile_experience",
            "Get profile experience for a LinkedIn profile.",
            cleaned(integration.get_profile_experience),
            GetProfileSchema,
        ),
        tool(
            "linkedin_get_profile_education",
            "Get profile education for a LinkedIn profile.",
            cleaned(integration.get_profile_education),
            GetProfileSchema,
        ),
        tool(
            "linkedin_get_profile_posts_feed",
            "Get posts feed for a LinkedIn profile.",
            cleaned(integration.get_profile_posts_feed),
            GetProfilePostsFeedSchema,
        ),
        tool(
            "linkedin_get_post_stats",
            "Get a LinkedIn post and its statistics.",
            cleaned(integration.get_post_stats),
            GetActivitySchema,
        ),
        tool(
            "linkedin_get_post_comments",
            "Get comments for a LinkedIn activity.",
            cleaned(integration.get_post_comments),
            GetActivitySchema,
        ),
        tool(
            "linkedin_get_post_reactions",
            "Get reactions for a LinkedIn activity.",
            cleaned(integration.get_post_reactions),
            GetActivitySchema,
        ),
        tool(
            "linkedin_get_post_reposts",
            "Get reposts for a LinkedIn activity.",
            cleaned(integration.get_post_reposts),
            GetActivitySchema,
        ),
        tool(
            "linkedin_get_mutual_connexions",
            "Get mutual connections for a LinkedIn profile.",
            integration.get_mutual_connexions,
            GetMutualConnectionsSchema,
        ),
        tool(
            "linkedin_search_people",
            "Search for people on LinkedIn.",
            integration.search_people,
            SearchPeopleSchema,
        ),
    ]
