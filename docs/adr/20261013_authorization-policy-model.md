# Authorization uses AWS-style policies, denied by default

Status: Accepted

Date: 2026-10-13

Discussion: [#1314](https://github.com/jupyter-naas/abi/issues/1314).
Specification: [`docs/specs/rfcs/20261013_identity-and-authorization.md`](../specs/rfcs/20261013_identity-and-authorization.md), §3 to §7.

## Context

**Authorization in ABI is thin.**

- Nexus's `services/iam` matches scopes, and every caller passes `scopes={"*"}`. When no service is bound it
  fails open.
- About 45 endpoints check `role in ("owner", "admin")` inline.
- Viewers are read-only in graph, sheets and ontology icons only.
- Feature flags hide UI but guard almost no API.

**The engine's kernel services have no notion of a caller.**

- Over NATS, any holder of the shared service credential can read any graph, object, secret or document
  namespace.
- `PlatformServicesAgent` reaches the same services with no user check.

**What we need:**

- "Viewer on workspace W" for people.
- "This IdP group reads graph A and writes graph B" for teams.
- "This module may read these graphs and write its own namespace" for modules.

A fixed role matrix answers the first only.

**What earlier work already decided.** The NATS RFC (`20260910_distributed-modules-nats-jetstream.md`)
decided three things:

- authorization is checked inside the domain service;
- identity travels in a `contextvars.ContextVar`;
- resource names are ARN-style.

It defined no format.

## Decision

- **Model: identity-based policies.**
  - A policy document has a `version` and statements. Each statement has an optional `sid`, an `effect`
    (`Allow` or `Deny`), `actions` and `resources`.
  - `conditions` is reserved for a later version.
  - Policies attach to users, groups (ABI groups, or IdP groups mapped through a claim) and service accounts,
    optionally at a scope.
  - There are no resource-based policies.
- **Zero trust.**
  - Every call is denied unless a matching Allow exists.
  - An explicit Deny always wins.
  - No principal has implicit access, `api` and `engine` included. Platform admin is itself an attached
    policy.
- **Acting for a user.** When an actor acts for a user, both must be allowed (intersection). Narrowed tokens
  can only remove permissions.
- **Not found or denied.**
  - A caller with no access at all to a resource gets the service's normal not-found error.
  - A caller who can see the resource but may not perform this action gets `PERMISSION_DENIED`.
- **Lists** return only the items an Allow covers and no Deny excludes. Paging applies after filtering.
- **Names.**
  - Actions are `<service>:<Action>`, with one action per operation. List, stream and export operations are
    distinct actions. Each action has an access level: list, read, write or admin.
  - Resources are `abi:<org>:<workspace>:<service>:<type>/<id>`, with `-` for "none" and percent-encoded ids.
  - Patterns use `*` (across segments) and `?`, never regular expressions.
- **Placement.** The org and workspace of a kernel resource come from a placement registry in IAM.
  - A placement is recorded when a resource is created in a workspace that no existing placement covers.
    A container's placement, platform included, also covers its children.
  - Every existing container is placed, module namespaces on the platform, so a workspace cannot claim a
    name inside one.
  - A create can never override an existing placement.
  - The org and workspace never come from a request field, which any caller could set.
- **Catalogs.** Every service registers its action catalog at load time. Policies are validated against the
  catalogs.
- **Roles are managed policies attached at a scope:** owner, admin, member, viewer and platform admin, plus
  `self` for every user.
  - Policy variables resolve against the principal being evaluated, so a user's `self` policy names the user
    even when Nexus calls on their behalf.
  - The roles are cumulative (viewer ⊆ member ⊆ admin ⊆ owner).
  - Nexus features and platform-level resources (models, agents, apps, views, templates) come from
    companion managed policies that IAM attaches with workspace roles. Org-level roles bring neither, and
    no role reaches a feature the deployment has not enabled.
  - They are generated from the catalogs by access level.
  - Only owners can grant, demote or remove owners.
- **Sealed resources.** A few resources are sealed in code to a single principal (the built-in IdP's data, the
  engine's signing keys). No policy can open them.
- **The authorizer port is shaped like OpenFGA's:** `check(principal, action, resource)`, a list `filter`, and
  `explain`. A relationship-based adapter can be added later without touching callers.
- **Fresh installs enforce policies.** `authorizer: allow_all` exists only as an explicit opt-out, and logs a
  warning at boot.

## Consequences

- **One check for every caller.** The check runs in the domain service, so Nexus REST, SDK modules over NATS
  and in-process callers are authorized identically.
  - The event, vector_store and cache NATS adapters must go through their services.
  - `document_admin`, the hard-coded `api`/`engine` admin identities and the unlocked proxy go away.
- **Every service publishes a catalog,** and every operation names its resource. New operations need a
  catalog entry before they ship.
- **Graph access needs the query dataset restricted.** A SPARQL query must not read a graph its caller may
  not read, so triple-store adapters restrict the query dataset (SPARQL Protocol `default-graph-uri` and
  `named-graph-uri`, or the embedded store's equivalents). SPARQL Update is mapped to per-graph write actions.
- **Ids are encoded.** IRIs and keys in resource names are percent-encoded, which is hard to read by hand.
  IAM provides helpers and a CLI command to build names, and the admin UI shows decoded ids.
- **The bugs close.** Viewers become read-only on every router, feature flags are enforced at the API, and
  owner protection (bug c) and workspace creation in an org (bug d) become policy rules.
- **Some sharing is out of reach.** Per-object sharing beyond personal resources (one conversation with one
  colleague) is not expressible without naming the object in a statement. That remains the open OpenFGA
  question of #1314.
