# GitHub product: App install + Agent (spec)

Status: Layer B implemented (install + setup callback + installation tokens)  
Date: 2026-08-07  
Owner: ABI Marketplace (consumers include Zen and other ABI deployments)

## Problem

Users expect: Install → grant access (account, org, repos) → **GitHub Agent** appears in chat and can do the same work as `gh` (issues, PRs, comments, reviews).

## Decision

Ship in two layers.

### Layer A: MVP (device OAuth / PAT)

Still available under **Other options** in the Connect panel.

1. Module enabled in config
2. Connect with GitHub (device flow) or paste PAT
3. Restart OS
4. Open GitHub agent (`?agent=GitHub`)

### Layer B: GitHub App (primary CX)

| Capability | MVP (device/PAT) | GitHub App |
|------------|-----------------|------------|
| Account picker | GitHub login page | App install UI |
| Org / repo selection | No | Yes |
| Token type | User PAT / OAuth token | Installation access token |
| Storage | `GITHUB_ACCESS_TOKEN` | `GITHUB_APP_INSTALLATION_ID` + refreshed access token |
| Agent | Same tools | Same tools; token resolved via App when installation id is set |

#### User journey

1. Marketplace → GitHub → **Install GitHub App**
2. Redirect to GitHub → choose account/org → select repositories → Approve
3. GitHub redirects to `{PUBLIC_API_HOST}/api/integrations/github/app/setup?installation_id=…&state=…`
4. ABI validates `state`, stores `GITHUB_APP_INSTALLATION_ID`, mints installation token into `GITHUB_ACCESS_TOKEN`
5. Browser returns to Marketplace with `?github_app=installed`
6. **Restart OS**, then open GitHub agent

#### Env vars (every ABI deployment)

```bash
GITHUB_APP_ID=
GITHUB_APP_SLUG=naasai-abi
GITHUB_APP_PUBLIC_LINK=https://github.com/apps/naasai-abi
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----"
# optional metadata
GITHUB_APP_CLIENT_ID=
GITHUB_APP_CLIENT_SECRET=
GITHUB_APP_ORG=
# set automatically after install:
# GITHUB_APP_INSTALLATION_ID=
PUBLIC_WEB_HOST=https://zen.naas.ai
PUBLIC_API_HOST=https://api.zen.naas.ai
```

#### GitHub App settings (NaasAI ABI)

| Field | Value |
|--------|--------|
| Name | NaasAI ABI |
| Setup URL | `{PUBLIC_API_HOST}/api/integrations/github/app/setup` |
| Redirect on update | On |
| Permissions | Metadata R, Contents R/W, Issues R/W, Pull requests R/W |
| Install target | Any account |

For Zen today: Setup URL = `https://api.zen.naas.ai/api/integrations/github/app/setup`.  
Self-hosted ABI: same path on that deployment’s API host (or register a dedicated App).  
Later: optional central Naas setup router that redirects via signed `state.return_to`.

#### API

- `POST /api/integrations/github/app/install` (superadmin): `{ install_url, state }`
- `GET /api/integrations/github/app/setup` (no session; validates `state`): redirects to web
- `GET /api/integrations/github/status`: includes `app_available`, `installation_id`, `auth_mode`

## Consequences

- Primary CX is App install with org/repo picker
- Device/PAT remain as fallback
- Installation tokens expire (~1h); agent boot re-mints from `GITHUB_APP_INSTALLATION_ID` when App credentials are present
- GCP: never rely on Marketplace writing `config.gcp.yaml` (RO mount)

## Out of scope (for now)

- Chat-native "connect GitHub" slash command
- Per-workspace installation ids (current: instance `.env`)
- Central multi-tenant setup router
- Webhooks for live PR/issue events
