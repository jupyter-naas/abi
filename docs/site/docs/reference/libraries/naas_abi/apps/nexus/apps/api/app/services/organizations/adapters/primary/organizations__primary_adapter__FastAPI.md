# organizations__primary_adapter__FastAPI

## What it is
FastAPI “primary adapter” (HTTP layer) exposing organization-related endpoints: organizations CRUD (limited), branding/logo uploads, workspace listing, member management, and domain management. It wires requests to `OrganizationService` backed by a Postgres secondary adapter.

## Public API

### Routers
- `router: APIRouter`
  - Authenticated endpoints (require `get_current_user_required`).
- `public_router: APIRouter`
  - Public endpoints (no auth).

### Dependency providers / helpers
- `get_organization_service(db: AsyncSession = Depends(get_db)) -> OrganizationService`
  - Builds `OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))`.
- `get_org_role(user_id: str, org_id: str, service: OrganizationService) -> str | None`
  - Returns the user role in an org via the service.
- `require_org_access(user_id: str, org_id: str, service: OrganizationService) -> str`
  - Enforces org access via the service; maps `OrganizationPermissionError` to HTTP 403.
- `_to_schema(row: OrganizationRecord) -> Organization`
  - Converts service record to `Organization` response schema.
- `_to_branding(row: OrganizationRecord) -> OrganizationBranding`
  - Converts service record to `OrganizationBranding` response schema (sets default `primary_color` if missing).

### Pydantic models (request/response)
- `OrganizationBranding`
  - Public branding view (logo/theme/login UI fields).
- `Organization`
  - Organization details including timestamps.
- `OrganizationCreate`
  - Create payload; validates `name`, `slug` (pattern: `^[a-z0-9][a-z0-9\-]*[a-z0-9]$`).
- `OrganizationUpdate`
  - Patch payload for organization branding fields.
- `OrganizationMember`
  - Member representation.
- `OrganizationMemberInvite`
  - Invite payload: `email`, `role` in `owner|admin|member` (default `member`).
- `OrganizationMemberUpdate`
  - Update member role payload.
- `OrganizationDomain`
  - Domain representation; token is only returned when not verified.
- `OrganizationDomainCreate`
  - Add domain payload; validates domain pattern `^[a-z0-9][a-z0-9\-\.]*[a-z0-9]$`.
- `BillingInfo`, `BillingUpgrade`
  - Billing schemas (billing endpoints are not implemented; always return 501).

### HTTP endpoints

#### Public
- `GET /slug/{slug}/branding` → `OrganizationBranding`
  - Fetch branding by org slug; 404 if not found.

#### Authenticated (via `router`)
- `GET /` → `list[Organization]`
  - List organizations for the current user.
- `GET /{org_id}` → `Organization`
  - Get org by id; requires org access; 404 if not found.
- `POST /` → `Organization`
  - Create org; slug uniqueness handled:
    - 400 if `OrganizationSlugAlreadyExistsError`.
- `PATCH /{org_id}` → `Organization`
  - Update org branding fields; requires role `owner` or `admin`, else 403.

##### Logo upload (writes to disk)
- `POST /{org_id}/upload-logo-square` → `{"logo_url": ...}`
  - Requires role `owner|admin`.
  - Accepts multipart file; validates:
    - `content_type` in `ALLOWED_IMAGE_TYPES`
    - size ≤ `MAX_IMAGE_SIZE` (5MB)
  - Writes file to `uploads/org-logos/org-{org_id}-square{ext}`
  - If existing `logo_url` starts with `/uploads/org-logos/`, deletes the old file.
  - Updates org `logo_url` to `/uploads/org-logos/{filename}`.
- `POST /{org_id}/upload-logo-rectangle` → `{"logo_rectangle_url": ...}`
  - Same as square, but filename `org-{org_id}-rectangle{ext}` and updates `logo_rectangle_url`.

##### Workspaces
- `GET /{org_id}/workspaces` → `list[dict]`
  - Requires org access.
  - Returns workspace fields plus `organization_logo_url` and `organization_logo_rectangle_url`.

##### Members
- `GET /{org_id}/members` → `list[OrganizationMember]`
  - Requires org access.
- `POST /{org_id}/members/invite` → `OrganizationMember`
  - Requires role `owner|admin`.
  - 400 if already a member (`OrganizationMemberAlreadyExistsError`).
  - 404 if user not found by email.
- `PATCH /{org_id}/members/{user_id}` → `OrganizationMember`
  - Requires role `owner|admin`.
  - 400 if attempting to change own role.
  - 404 if member not found.
- `DELETE /{org_id}/members/{user_id}` → `{"message": ...}`
  - Requires role `owner|admin`.
  - 400 if attempting to remove self.
  - 400 if target user is `owner`.
  - 404 if member not found.

##### Domains
- `GET /{org_id}/domains` → `list[OrganizationDomain]`
  - Requires org access.
  - Only returns `verification_token` when domain is not verified.
- `POST /{org_id}/domains` → `OrganizationDomain`
  - Requires role `owner|admin`.
  - Generates `verification_token=secrets.token_urlsafe(32)`.
  - 400 if domain already registered (`OrganizationDomainAlreadyExistsError`).
- `POST /{org_id}/domains/{domain_id}/verify` → `OrganizationDomain`
  - Requires role `owner|admin`.
  - 404 if domain not found.
  - 400 if already verified.
  - On success, returns with `verification_token=None`.
- `DELETE /{org_id}/domains/{domain_id}` → `{"message": ...}`
  - Requires role `owner|admin`.
  - 404 if domain not found.

##### Billing (not implemented)
- `GET /{org_id}/billing` → always 501
- `POST /{org_id}/billing/upgrade` → always 501 (requires role `owner|admin`)
- `POST /{org_id}/billing/payment-method` → always 501 (requires role `owner|admin`)

## Configuration/Dependencies
- FastAPI dependencies:
  - `get_current_user_required` for authenticated endpoints.
  - `get_db` providing `sqlalchemy.ext.asyncio.AsyncSession`.
- Service layer:
  - `OrganizationService` using `OrganizationSecondaryAdapterPostgres`.
- File storage:
  - Upload directory: `ORG_LOGO_UPLOAD_DIR = Path("uploads") / "org-logos"` (created at import time).
  - Allowed MIME types in `ALLOWED_IMAGE_TYPES`:
    - `image/png`, `image/jpeg`, `image/jpg`, `image/gif`, `image/webp`, `image/svg+xml`
  - Max file size: `MAX_IMAGE_SIZE = 5 * 1024 * 1024` bytes.

## Usage

### Mount routers in a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary.organizations__primary_adapter__FastAPI import (
    router as org_router,
    public_router as org_public_router,
)

app = FastAPI()
app.include_router(org_public_router, prefix="/organizations", tags=["organizations-public"])
app.include_router(org_router, prefix="/organizations", tags=["organizations"])
```

### Example request (public branding)
```bash
curl http://localhost:8000/organizations/slug/acme/branding
```

## Caveats
- Logo uploads write to local disk under `uploads/org-logos` and only delete previous files when the stored URL starts with `/uploads/org-logos/`.
- Billing endpoints exist but always return HTTP 501 (not implemented).
- Role enforcement is explicit:
  - Many mutations require role `owner` or `admin`; non-admin members receive HTTP 403.
