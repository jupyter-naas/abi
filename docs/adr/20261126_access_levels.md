# Access levels of Nexus features and core services in a workspace

- **Status:** Accepted
- **Date:** 2026-11-26

## Context

The workspace offer ("<W> access", ADR `20261125_offer_gives_outside_resources`) says *whether* a workspace offers a feature, a module or a resource. It does not say *how far* its people go with it: read only, or also write and administer. The policy builder can say it action by action, but no settings page could, and two different layers were mixed up:

- **Nexus features**: the UI, gated by `nexus:UseFeature`, and the `nexus:` actions the catalog ties to each feature (`feature=` in `catalog/`, e.g. Graph's `CreateView`).
- **Core services**: the engine's resources, each service with its own IAM catalog (the triple store's graphs, object storage, vector store, datasets, documents, secrets, key-value, cache, events).

A bound's Allows do not reach the built-in roles; its Denies apply to everyone in the workspace.

## Decision

1. **One access level per group.** A group is either a Nexus feature (`feature:<key>`: its `nexus:` actions on types placed in a workspace, not policy-only) or a core service (`service:<service>`: its actions on types placed in a workspace, named `${scope}/<service>:*`). Its level is `none`, `read` (list and read), `write` or `admin`, among those its actions have (`iam/access_levels.py`).
2. **In "<W> access", a cap.** Section `AccessLevelCap` (Deny): the group's actions above the level, for everyone in the workspace, admins included. No statement means no cap. Each person's level still applies below it.
3. **In another policy of the workspace, a grant.** Section `AccessLevelGrant` (Allow): the group's actions up to the level, for whoever holds the policy, within the offer. As any grant, it holds only what the caller holds.
4. **Apart from the offer's sections.** `workspace_offer.with_offer` keeps these sections as they are; `access_levels.with_levels` keeps every other statement.
5. **A feature's gate is part of it.** A feature's group holds its `nexus:UseFeature` on `${scope}/nexus:feature/<key>` at the read level: `none` denies the feature itself, so a feature with no action of its own (documents, slides…) can be denied too. Each action is matched to its group with the resource it names.
6. **The organization's pages.** Organization › Access › Features, Services and Modules edit "<O> access" (`/api/organizations/{id}/feature-access`, `/offer`, `/access-levels`): its Denies are in the chain of every workspace's bound, so a cap or a `none` there reaches every workspace of the organization, and nobody below reopens it ("<O> access" is the platform's; its admins only narrow). A workspace's Features page hides a feature its ceiling does not offer (or denies), unless its policy still allows it.
7. **Two pages, kept apart.** Access › Features adds an Access column to the Nexus features. A new page, Access › Services (`/settings/core-services`), sets the core services. Both pick the policy edited from the same dropdown as Features and Modules. API: `GET|PUT /api/workspaces/{id}/access-levels?kind=feature|service&policy=<id>`.

## Consequences

- A workspace can be made read-only for a feature or a service (e.g. the graphs of the triple store), for everyone in it, without touching roles. A group of Viewers can be granted writing through a policy.
- Only workspace-placed types are covered: platform types (identity, discovery…) cannot be capped by a workspace and are not listed.
- Graphs given from outside the workspace (Settings › Graphs, by absolute name) are not under `${scope}` and so are not capped by these sections.
- Caps are Denies: removing one widens the workspace and is a write of "<W> access" as the caller, decided by IAM like any change of the offer.
