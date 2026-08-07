# GitHub product: App install + Agent (spec)

Status: proposed  
Date: 2026-08-07  
Owner: Zen / ABI Marketplace

## Problem

Users expect: Install → grant access (account, org, repos) → **GitHub Agent** appears in chat and can do the same work as `gh` (issues, PRs, comments, reviews).

Today (OAuth device flow + PAT):

- No org/repo picker (device OAuth is user-scoped, not App installation)
- Marketplace Install cannot write read-only GCP config
- "Connected" can be a placeholder `.env` value
- Agent exists (`GitHubAgent`) but onboarding does not land you on it

## Decision

Ship in two layers.

### Layer A: MVP (this PR track)

Linear Marketplace card flow:

1. Module enabled in config (or Install where config is writable)
2. **Connect with GitHub** (device flow) or paste PAT
3. **Restart OS**
4. **Open GitHub agent** deep link to chat (`?agent=GitHub`)

Also: Reconnect (clear token), reject placeholder secrets, no duplicate Installed CTAs.

Scope: `repo` + `read:user` user token. No per-repo grant UI.

### Layer B: GitHub App (real product)

Replace user-token connect with a **GitHub App** installation.

| Capability | MVP (device/PAT) | GitHub App |
|------------|-----------------|------------|
| Account picker | GitHub login page | App install UI |
| Org / repo selection | No (all repos the user can access) | Yes (install on selected repos) |
| Fine-grained permissions | OAuth scopes | App permissions + optional checks |
| Workspace isolation | Shared instance `.env` token | Per-workspace installation + secrets |
| Agent surfacing | Chat deep link | Same + Agents list badge "GitHub connected" |
| `gh`-parity tools | Existing REST/GraphQL tools | Expand tools; map to App token |

#### User journey (Layer B)

1. Marketplace → GitHub → **Install GitHub App**
2. Redirect to GitHub → choose account/org → select repositories → Approve
3. Callback stores `installation_id` + short-lived tokens (or refresh) in **workspace secrets**
4. Restart not required if token bridge is hot-reloadable; otherwise Restart OS once
5. Agents list shows **GitHub**; chat opens with that agent selected
6. Gatekeeper still gates destructive tools (create issue, merge, etc.)

#### Agent capabilities (target parity with Cursor `gh` usage)

Must-have:

- List/create/update issues; comment
- List/create/review PRs; comment; request reviewers
- List repos, branches, commits for the installed set
- Search code/issues within installed repos

Later:

- Actions / workflow dispatch
- Project (v2) items
- Release drafts
- Codespaces (optional)

#### Platform requirements

- GitHub App registered under NaasAI (or customer-owned App for enterprise)
- Callback URL on `api.zen.naas.ai` (and local)
- Secrets: `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, webhook secret
- Do **not** store long-lived PATs in git; prefer installation tokens
- GCP: never rely on Marketplace writing `config.gcp.yaml` (RO mount)

## Consequences

- Layer A unblocks testing on zen.naas.ai without lying about repo pickers
- Layer B is the only honest path for "grant rights to these repos from the UI"
- Until Layer B, docs and UI must say: user-level access via OAuth/PAT, not per-repo install

## Out of scope (for now)

- Chat-native "connect GitHub" slash command
- Bridging Nexus workspace Secrets → engine dotenv automatically
- Non-superadmin self-serve connect (follow-up after App + workspace secrets)
