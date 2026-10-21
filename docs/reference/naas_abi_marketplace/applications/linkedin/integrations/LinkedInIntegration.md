# LinkedInIntegration

## What it is
- A Python integration client for LinkedIn’s private “voyager” API endpoints.
- Authenticates using LinkedIn cookies (`li_at`, `JSESSIONID`) and supports:
  - Organization info retrieval
  - Profile top card and profile sections (skills/experience/education)
  - Profile posts feed + post stats/reactions/comments/reposts
  - People search and “mutual connections” export (JSON + Excel), with optional upload via Naas integration
- Stores raw and derived artifacts (JSON, optional images, Excel) under a configured datastore path.
- Exposes a subset of operations as LangChain `StructuredTool`s via `as_tools()`.

## Public API

### `LinkedInIntegrationConfiguration` (dataclass)
Configuration for `LinkedInIntegration`.
- `li_at: str` — LinkedIn `li_at` cookie.
- `JSESSIONID: str` — LinkedIn `JSESSIONID` cookie; double-quotes are stripped in `LinkedInIntegration.__init__`.
- `linkedin_url: str` — a LinkedIn profile URL used at initialization.
- `naas_integration_config: NaasIntegrationConfiguration | None` — optional; enables Excel upload via Naas.
- `base_url: str = "https://www.linkedin.com/voyager/api"` — API base URL.
- `datastore_path: str` — storage root (defaults to `ABIModule.get_instance().configuration.datastore_path`).

### `LinkedInIntegration`
Main integration client.

#### Constructor
- `LinkedInIntegration(configuration: LinkedInIntegrationConfiguration)`
  - Initializes cookies/headers and storage.
  - Resolves and stores `self.profile_public_id` by calling `get_profile_public_id(configuration.linkedin_url)`.
  - Raises `RuntimeError` if the public id cannot be resolved.

#### Data retrieval / parsing
- `get_organization_id_from_url(url: str) -> dict[str, str]`
  - Extracts organization “public id” from `/company/`, `/school/`, or `/showcase/` URLs.
- `get_organization_id(url: str) -> dict[str, str]`
  - Calls `get_organization_info()` and extracts the numeric organization id from the `*elements` URN.
- `get_organization_info(url: str, return_cleaned_json: bool = False) -> dict`
  - Calls `/organization/companies?...` and persists JSON under `datastore_path/get_organization_info/<org_public_id>/`.
  - If `return_cleaned_json=True`, returns `clean_json(...)` output.

- `get_profile_id_from_url(url: str) -> dict[str, str]`
  - Extracts vanity profile id from `/in/<id>/` URLs.
- `get_profile_top_card(url: str, return_cleaned_json: bool = False) -> dict`
  - GraphQL call using `vanityName:<id>`.
  - Rejects vanity ids starting with `AcoAA` as invalid input.
- `get_profile_public_id(url: str) -> dict[str, str]`
  - Reads `publicIdentifier` from the top-card response (via `included` entity).
  - Fallback: tries to parse a “share profile URL” from overflow actions.
- `get_profile_id(url: str) -> dict[str, str]`
  - Extracts internal profile id (URN suffix) from top-card response.
- `get_profile_data(url: str, profile_type: str = "skills", locale: str = "en_US", return_cleaned_json: bool = False) -> dict`
  - GraphQL call for a profile section by `sectionType` (e.g. `skills`, `experience`, `education`).
- `get_profile_skills(url: str, return_cleaned_json: bool = False) -> dict`
- `get_profile_experience(url: str, return_cleaned_json: bool = False) -> dict`
- `get_profile_education(url: str, return_cleaned_json: bool = False) -> dict`

- `get_profile_posts_feed(url: str, start: int = 0, count: int = 1, pagination_token: str | None = None, return_cleaned_json: bool = False) -> dict`
  - GraphQL call for the profile posts feed.
  - Extracts `activity_id` and a `paginationToken`; derives a publish date using `get_date_from_token()`.
  - Persists JSON under `datastore_path/get_profile_posts_feed/<profile_public_id>/<date>_<activity_id>/`.

- `get_activity_id_from_url(url: str) -> dict`
  - Extracts activity id from URLs containing `-activity-` or `:activity:`.
- `get_post_stats(url: str, return_cleaned_json: bool = False) -> dict`
  - Calls `/feed/updates/urn:li:activity:{id}`.
- `get_post_reactions(url: str, start: int = 0, count: int = 100, limit: int = -1, return_cleaned_json: bool = False) -> dict`
  - Intended pagination loop for reactions (aggregates results then persists JSON).
- `get_post_comments(url: str, start: int = 0, count: int = 100, limit: int = -1, return_cleaned_json: bool = False) -> dict`
  - Intended pagination loop for comments (aggregates results then persists JSON).
- `get_post_reposts(url: str, start: int = 0, count: int = 100, limit: int = -1, return_cleaned_json: bool = False) -> dict`
  - Intended pagination loop for reposts (aggregates results then persists JSON).

#### Export / search
- `get_mutual_connexions(profile_url: str, connection_distance: str = "F", organization_url: str | None = None, start: int = 0, count: int = 50, limit: int = 1000, query_id: str = "...") -> dict`
  - GraphQL pagination loop to fetch PEOPLE results “connected to” `profile_url`, optionally filtered by organization.
  - Produces:
    - `total_connections`
    - `connections_returned`
    - `connections` (simplified list of people)
    - `excel_url` (local path or Naas asset URL)
- `search_people(connection_distance: str = "F", organization_url: str | None = None, location: str | None = None, start: int = 0, count: int = 50, limit: int = 1000, query_id: str = "...") -> dict`
  - GraphQL pagination loop for generic PEOPLE search.
  - Optional `location` filter uses a hardcoded mapping: `"France" -> "105015875"`.

#### Cleaning
- `clean_json(prefix: str, filename: str, data: dict) -> dict[str, Any]`
  - Returns existing `*_cleaned.json` from storage if present; otherwise:
    - Recursively removes keys starting with `*` or containing `"urn"` (case-insensitive).
    - Re-groups `included` entities by `$type`, optionally replacing image-like fields with highest-quality URL.
    - Flattens nested dict keys using `_`.
    - Saves the cleaned file under `datastore_path/<prefix>/`.

### `as_tools(configuration: LinkedInIntegrationConfiguration) -> list`
Returns LangChain `StructuredTool` wrappers around:
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

Tools validate inputs via Pydantic schemas (URL patterns, `connection_distance` pattern `^[FSO]$`, etc.).

## Configuration/Dependencies
- Runtime dependencies:
  - `requests`, `pydash`
  - `naas_abi_core` (integration base classes, logger, caching, `StorageUtils`)
  - `naas_abi_marketplace` (`ABIModule`)
- Optional dependencies:
  - `pandas` (required for Excel export in `get_mutual_connexions` / `search_people`)
  - `langchain_core`, `pydantic` (required for `as_tools`)
- Authentication:
  - Requires valid LinkedIn cookies: `li_at` and `JSESSIONID`.
- Storage:
  - Uses `StorageUtils` with `ABIModule.get_instance().engine.services.object_storage`.
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
    JSESSIONID='"YOUR_JSESSIONID"',  # quotes are stripped
    linkedin_url="https://demo.example/profiles/demo",
)

li = LinkedInIntegration(cfg)

org = li.get_organization_info(
    "https://www.linkedin.com/company/demo/",
    return_cleaned_json=True,
)
top = li.get_profile_top_card("https://demo.example/profiles/demo", return_cleaned_json=True)
print(org.keys())
print(top.keys())
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
    linkedin_url="https://demo.example/profiles/demo",
)

tools = as_tools(cfg)
```

## Caveats
- Uses private LinkedIn endpoints and hard-coded GraphQL `queryId`s; these may change and break requests.
- `LinkedInIntegration.__init__` performs a live call and raises `RuntimeError` if it cannot resolve a profile public id.
- `_make_request` is cached for 1 day; responses can be stale within the TTL.
- `get_profile_posts_feed` uses `assert` statements on the API response structure and may raise `AssertionError` if the response differs.
- `get_post_reactions`, `get_post_comments`, and `get_post_reposts` call `_make_request` with unsupported keyword arguments (`prefix`, `filename`) in this file; as written, those paths will raise `TypeError` if executed.
- `clean_json` removes any key containing `"urn"` in its name; this can drop fields you may need.
- `search_people` location mapping only supports `"France"`; other values are ignored (with a `print`).
