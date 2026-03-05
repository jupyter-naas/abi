# organizations.py (Organizations API endpoints)

## What it is
FastAPI endpoints for managing **Organizations**:
- Public, unauthenticated endpoint to fetch **branding by slug** (used by login pages).
- Authenticated CRUD-style operations for organizations, members, workspaces listing, domain management, and placeholders for billing.

Two routers are defined:
- `public_router`: public endpoints (no auth)
- `router`: authenticated endpoints (requires `get_current_user_required`)

## Public API

### Routers
- `public_router`: exposes public branding lookup.
- `router`: exposes authenticated organization operations.

### Pydantic schemas
- `OrganizationBranding`: public branding view (no auth).
- `Organization`: full organization view (auth).
- `OrganizationCreate`: create org payload (validates `slug` pattern).
- `OrganizationUpdate`: partial update payload for org branding/settings.
- `OrganizationMember`: org member view (includes user `email`/`name` when returned by endpoints).
- `OrganizationMemberInvite`: invite payload (`email`, `role` in `owner|admin|member`).
- `OrganizationMemberUpdate`: role update payload (`owner|admin|member`).
- `OrganizationDomain`: domain view (token hidden when verified).
- `OrganizationDomainCreate`: add domain payload (validates domain pattern).
- `BillingInfo`, `BillingUpgrade`: billing placeholder schemas.

### Helpers (internal)
- `_to_schema(row: OrganizationModel) -> Organization`: maps DB model to authenticated schema.
- `_to_branding(row: OrganizationModel) -> OrganizationBranding`: maps DB model to public branding schema.
- `get_org_role(user_id, org_id, db) -> str | None`: returns member role or `None`.
- `require_org_access(user_id, org_id, db) -> str`: returns role or raises `403`.

### Endpoints

#### Public (no auth)
- `GET /slug/{slug}/branding` → `OrganizationBranding`  
  Returns branding for an organization by slug; `404` if not found.

#### Authenticated (requires current user)
- `GET /` → `list[Organization]`  
  Lists orgs where the user is owner or member.
- `GET /{org_id}` → `Organization`  
  Requires membership; `404` if org not found.
- `POST /` → `Organization`  
  Creates org; current user becomes owner and an `"owner"` membership row is created.  
  `400` if slug already exists.
- `PATCH /{org_id}` → `Organization`  
  Updates org fields provided; requires role `"owner"` or `"admin"`.
- `POST /{org_id}/upload-logo-square` → `{"logo_url": str}`  
  Upload square logo; requires `"owner"` or `"admin"`. Validates content-type and max size (5MB).
- `POST /{org_id}/upload-logo-rectangle` → `{"logo_rectangle_url": str}`  
  Upload wide logo; requires `"owner"` or `"admin"`. Validates content-type and max size (5MB).
- `GET /{org_id}/workspaces` → `list[dict]`  
  Lists accessible workspaces in org and includes both workspace branding and inherited org logos for UI fallback.
- `GET /{org_id}/members` → `list[OrganizationMember]`  
  Lists org members; includes user email/name; requires membership.
- `POST /{org_id}/members/invite` → `OrganizationMember`  
  Adds an existing user (looked up by email) as org member; requires `"owner"` or `"admin"`.  
  `404` if user not found; `400` if already a member.
- `PATCH /{org_id}/members/{user_id}` → `OrganizationMember`  
  Updates member role; requires `"owner"` or `"admin"`.  
  `400` if attempting to change your own role; `404` if member not found.
- `DELETE /{org_id}/members/{user_id}` → `{"message": str}`  
  Removes member; requires `"owner"` or `"admin"`.  
  Cannot remove self (`400`) or remove owner (`400`).

#### Organization domains
- `GET /{org_id}/domains` → `list[OrganizationDomain]`  
  Requires membership. Returns `verification_token` only for unverified domains.
- `POST /{org_id}/domains` → `OrganizationDomain`  
  Adds domain; requires `"owner"` or `"admin"`.  
  `400` if domain already registered (globally).
- `POST /{org_id}/domains/{domain_id}/verify` → `OrganizationDomain`  
  Marks domain verified (DNS verification is **TODO**); requires `"owner"` or `"admin"`.  
  `400` if already verified.
- `DELETE /{org_id}/domains/{domain_id}` → `{"message": str}`  
  Deletes domain; requires `"owner"` or `"admin"`.

#### Billing (placeholders; not implemented)
- `GET /{org_id}/billing` → raises `501 Not Implemented`
- `POST /{org_id}/billing/upgrade` → raises `501 Not Implemented`
- `POST /{org_id}/billing/payment-method` → raises `501 Not Implemented`

## Configuration/Dependencies
- FastAPI dependencies:
  - `get_current_user_required` provides `current_user: User` for authenticated endpoints.
  - `get_db` provides `db: AsyncSession`.
- Database models used (SQLAlchemy):
  - `OrganizationModel`, `OrganizationMemberModel`, `WorkspaceModel`, `WorkspaceMemberModel`, `OrganizationDomainModel` (+ `UserModel` imported inside member endpoints).
- File upload/storage:
  - Upload dir: `uploads/org-logos` (created at import time).
  - Allowed MIME types: `image/png`, `image/jpeg`, `image/jpg`, `image/gif`, `image/webp`, `image/svg+xml`
  - Max upload size: `5MB`
- Time handling:
  - Uses `datetime.now(UTC).replace(tzinfo=None)` for DB timestamps.

## Usage

### Mounting routers
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints import organizations

app = FastAPI()

# Example prefixes; adjust to your app's routing conventions
app.include_router(organizations.public_router, prefix="/organizations/public", tags=["organizations-public"])
app.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
```

### Calling the public branding endpoint
```python
import requests

slug = "acme"
resp = requests.get(f"http://localhost:8000/organizations/public/slug/{slug}/branding")
print(resp.status_code, resp.json())
```

## Caveats
- Logo uploads are written to local disk under `uploads/org-logos` and return relative URLs (e.g. `/uploads/org-logos/...`). Serving these files requires separate static file configuration elsewhere.
- Domain verification endpoint does **not** perform DNS checks; it currently just marks the domain as verified.
- Billing endpoints always raise `501 Not Implemented`.
- Some role constraints:
  - Only `"owner"`/`"admin"` can update org branding, manage members (invite/update/remove), and manage domains.
  - You cannot change your own member role or remove yourself.
  - You cannot remove the organization owner membership.
