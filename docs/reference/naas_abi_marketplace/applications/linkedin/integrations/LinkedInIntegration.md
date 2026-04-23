# LinkedInIntegration

## What it is
- A Python integration client for LinkedIn’s private “voyager” API endpoints.
- Authenticates using LinkedIn cookies (`li_at`, `JSESSIONID`) and fetches:
  - Organization info
  - Profile “top card”, skills, experience, education
  - Profile posts feed and post engagement (stats, reactions, comments, reposts)
  - People search and mutual connections exports (JSON + Excel)
- Persists raw and derived artifacts (JSON, optional images, Excel) under a configured datastore path.
- Provides `as_tools()` to expose selected actions as LangChain `StructuredTool`s.

## Public API

### `LinkedInIntegrationConfiguration` (dataclass)
Configuration for `LinkedInIntegration`.
- `li_at: str` — LinkedIn `li_at` cookie.
- `JSESSIONID: str` — LinkedIn `JSESSIONID` cookie (quotes are stripped in `__init__`).
- `linkedin_url: str` — a LinkedIn profile URL used to initialize the integration and derive `profile_public_id`.
- `naas_integration_config: NaasIntegrationConfiguration | None` — optional; if provided, enables uploading exported Excel as a Naas asset.
- `base_url: str = "https://www.linkedin.com/voyager/api"` — API base.
- `datastore_path: str` — storage root (defaults from `ABIModule` configuration).

### `LinkedInIntegration`
Main integration client.

#### Constructor
- `LinkedInIntegration(configuration: LinkedInIntegrationConfiguration)`
  - Validates access by calling `get_profile_public_id(configuration.linkedin_url)`.
  - Raises `Exception` if the public ID cannot be resolved.

#### Data retrieval methods
- `get_organization_id_from_url(url: str) -> Dict[str, str]`
  - Parses organization “public id” from `/company/`, `/school/`, or `/showcase/` URLs.
- `get_organization_id(url: str) -> Dict[str, str]`
  - Fetches organization info then extracts the numeric org id from `*elements`.
- `get_organization_info(url: str, return_cleaned_json: bool = False) -> Dict`
  - Calls `/organization/companies?...` and saves response; optionally returns cleaned/flattened JSON.

- `get_profile_id_from_url(url: str) -> Dict[str, str]`
  - Extracts vanity id from `/in/<id>/` profile URLs.
- `get_profile_public_id(url: str) -> Dict[str, str]`
  - Reads `publicIdentifier` from top-card response; falls back to parsing a “share URL” from overflow actions.
- `get_profile_id(url: str) -> Dict[str, str]`
  - Extracts internal profile id (URN suffix) from top-card response.
- `get_profile_top_card(url: str, return_cleaned_json: bool = False) -> Dict`
  - GraphQL request for top-card; rejects vanity ids starting with `AcoAA` (treated as invalid URL input).

- `get_profile_data(url: str, profile_type: str = "skills", locale: str = "en_US", return_cleaned_json: bool = False) -> Dict`
  - GraphQL request for a profile section (`skills`, `experience`, `education`, etc.).
- `get_profile_skills(url: str, return_cleaned_json: bool = False) -> Dict`
- `get_profile_experience(url: str, return_cleaned_json: bool = False) -> Dict`
- `get_profile_education(url: str, return_cleaned_json: bool = False) -> Dict`

- `get_profile_posts_feed(url: str, start: int = 0, count: int = 1, pagination_token: str | None = None, return_cleaned_json: bool = False) -> Dict`
  - GraphQL request for profile posts feed.
  - Extracts `activity_id` and `paginationToken`; derives a publish date from token.
  - Saves response under a date/activity-based prefix.

- `get_activity_id_from_url(url: str) -> Dict`
  - Extracts activity id from URLs containing `-activity-` or `:activity:`.
- `get_post_stats(url: str, return_cleaned_json: bool = False) -> Dict`
  - Calls `/feed/updates/urn:li:activity:{id}`.
- `get_post_reactions(url: str, start: int = 0, count: int = 100, limit: int = -1, return_cleaned_json: bool = False) -> Dict`
  - GraphQL pagination loop; merges `included` and `data.*elements`; saves aggregated JSON.
- `get_post_comments(url: str, start: int = 0, count: int = 100, limit: int = -1, return_cleaned_json: bool = False) -> Dict`
  - GraphQL pagination loop; merges comment elements; saves aggregated JSON.
- `get_post_reposts(url: str, start: int = 0, count: int = 100, limit: int = -1, return_cleaned_json: bool = False) -> Dict`
  - GraphQL pagination loop; merges reshare elements; saves aggregated JSON.

#### Search/export methods
- `get_mutual_connexions(profile_url: str, connection_distance: str = "F", organization_url: str | None = None, start: int = 0, count: int = 50, limit: int = 1000, query_id: str = "...") -> Dict`
  - GraphQL pagination loop to fetch people results connected to `profile_url` (optionally filtered by organization).
  - Builds a simplified list of people (id, public_id, name, headline, location, profile_url, etc.).
  - Saves final JSON and exports Excel; if Naas is configured, uploads and returns an `excel_url`.

- `search_people(connection_distance: str = "F", organization_url: str | None = None, location: str | None = None, start: int = 0, count: int = 50, limit: int = 1000, query_id: str = "...") -> Dict`
  - GraphQL pagination loop for generic PEOPLE search.
  - Optional `location` mapping currently contains only `"France" -> "105015875"`.
  - Saves final JSON and exports Excel (same upload behavior as above).

#### Cleaning utilities
- `clean_json(prefix: str, filename: str, data: dict) -> Dict[str, Any]`
  - If a cleaned file exists, returns it.
  - Otherwise:
    - Removes keys starting with `*` or containing `urn` (case-insensitive) recursively.
    - Parses `included` entities into a `$type`-keyed structure, optionally replacing image-like fields with highest-quality URL.
    - Flattens nested dict keys with `_`.
    - Saves `*_cleaned.json` under `datastore_path/prefix/`.

### `as_tools(configuration: LinkedInIntegrationConfiguration) -> list`
- Returns a list of LangChain `StructuredTool` wrappers around:
  - `linkedin_get_organization_info`
  - `linkedin_get_profile_top_card`
  - `linkedin_get_profile_skills`
  - `linkedin_get_profile_experience`
  - `linkedin_get_profile_education`
  - `linkedin_get_profile_posts_feed`
  - `linkedin_get_post_comments`
  - `linkedin_get_post_reactions`
  - `linkedin_get_post_reposts`
  - `linkedin_get_mutual_connexions`
  - `linkedin_search_people`
- Each tool validates inputs via Pydantic schemas (URL patterns, connection distance pattern `^[FSO]$`, etc.).

## Configuration/Dependencies
- Required runtime dependencies:
  - `requests`, `pydash`, `naas_abi_core` (Integration base, cache, storage utils), `naas_abi_marketplace` (`ABIModule`)
- Optional dependencies (only used by specific paths):
  - `pandas` (Excel export)
  - `langchain_core`, `pydantic` (for `as_tools`)
- Authentication:
  - Must provide valid LinkedIn cookies: `li_at` and `JSESSIONID`.
- Storage:
  - Uses `StorageUtils` bound to `ABIModule.get_instance().engine.services.object_storage`.
  - Writes under `LinkedInIntegrationConfiguration.datastore_path`.

## Usage

### Minimal client usage
```python
from naas_abi_marketplace.applications.linkedin.integrations.LinkedInIntegration import (
    LinkedInIntegration,
    LinkedInIntegrationConfiguration,
)

cfg = LinkedInIntegrationConfiguration(
    li_at="YOUR_LI_AT",
    JSESSIONID='"YOUR_JSESSIONID"',  # quotes are stripped automatically
    linkedin_url="https://www.linkedin.com/in/someone/",
)

li = LinkedInIntegration(cfg)

org = li.get_organization_info("https://www.linkedin.com/company/naas-ai/", return_cleaned_json=True)
profile = li.get_profile_top_card("https://www.linkedin.com/in/someone/", return_cleaned_json=True)
print(org.keys(), profile.keys())
```

### LangChain tools
```python
from naas_abi_marketplace.applications.linkedin.integrations.LinkedInIntegration import (
    LinkedInIntegrationConfiguration,
    as_tools,
)

cfg = LinkedInIntegrationConfiguration(
    li_at="YOUR_LI_AT",
    JSESSIONID="YOUR_JSESSIONID",
    linkedin_url="https://www.linkedin.com/in/someone/",
)

tools = as_tools(cfg)
# tools is a list[StructuredTool]
```

## Caveats
- Uses LinkedIn private endpoints (`voyager` + hard-coded GraphQL `queryId`s); these may break if LinkedIn changes/rotates query IDs.
- `LinkedInIntegration.__init__` performs a live call to resolve `profile_public_id` and will raise if it fails.
- `_make_request` is cached for 1 day keyed by method + cookies + endpoint (+ params); responses may be stale within TTL.
- `get_profile_posts_feed` contains `assert` statements expecting specific response structure; it can raise `AssertionError` on unexpected API responses.
- `get_post_reactions`, `get_post_comments`, and `get_post_reposts` call `_make_request` with unsupported keyword arguments (`prefix`, `filename`) in this file; as written, this will raise `TypeError` at runtime if those code paths are executed.
- `clean_json` removes keys containing `"urn"` anywhere in the key name; this may drop fields you care about.
- Location filtering in `search_people` only maps `"France"`; other locations are ignored (with a `print`).
