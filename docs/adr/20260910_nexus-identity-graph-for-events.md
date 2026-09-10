# Nexus identity graph for event logs

## Status

Proposed (implemented on `feat/ontology-events`, awaiting review)

## Date

2026-09-10

## Context

Event logs (EventService, `naas_abi_core/services/*/ontologies`) say little about *who* and *where*:

- Only the seven agent event classes carry identity, as plain strings (`agent:userId`, `agent:workspaceId`, `agent:chatId`). They are filled only when a Nexus chat request sets the ContextVars (`chat__primary_adapter__streaming.py`). In the live log, 110 of 3,512 agent events have a workspace. The rest come from git tooling (`Git_Agent`, `Pull_Request_Description_Agent`, `GitHub`), which runs outside Nexus.
- Every other event type (`ObjectPut`, `TriplesInserted`, `BusMessagePublished`, …, ~99% of rows) records neither a user nor a workspace, even when a Nexus request caused it.
- Users, organizations, workspaces and memberships live in Nexus Postgres. Feature flags, role baselines, workspace overrides, tenant branding, seeds and module settings live in the naas_abi module configuration. The event log, and core services generally, cannot and should not reach either.

`NexusPlatformOntology.ttl` already modelled part of this: `nexus:User` is a GDC (the user account) carried by `abi:Person` (`nexus:hasUserAccount` ⊑ `abi:isCarrierOf`), `nexus:Workspace` is a GDC, and `nexus:CreateUser`, `nexus:CreateWorkspace`, `nexus:AddUserToWorkspace` and `nexus:Login` are processes. Nothing instantiated them.

Constraints found while reviewing it:

1. `NexusPlatformPipeline` clears `http://ontology.naas.ai/graph/nexus` whenever its agent signature changes. `apply_nexus_platform_pipeline` drops that graph when the pipeline is disabled. Anything else stored there is lost.
2. Four processes made the user account a participant: `nexus:Login` and `nexus:Logout` (`createdBy some nexus:User`), `nexus:VisitSession` (`startedBy`) and `nexus:PageView` (`viewedBy`); `nexus:startedBy` and `nexus:viewedBy` also had `rdfs:range nexus:User`. These are sub-properties of `abi:hasParticipant`, which `abi:Process` restricts to `MaterialEntity ∪ Quality`. A GDC participant is inconsistent: BFO makes GDCs disjoint from both. `nexus:hasUser` (organization → user account) had the same problem through `abi:hasMemberPart`.
3. `nexus:WorkspaceRole` inheres in `nexus:Workspace`, a GDC. BFO roles inhere only in independent continuants, and `abi:Role` requires `inheresIn some MaterialEntity`.
4. Coding-environment events already use `workspace_id` for a Coder workspace id, so a generic `workspace_id` on every event would be ambiguous.

## Decision

1. **Events reference accounts by id, never persons.** Payloads hold Nexus ids and IRIs derived from them, never names or emails. The person is reached through the graph: `nexus:User` → `nexus:isUserAccountOf` → `abi:Person`.

2. **Every event says who and where.** `abi:LogProcess` gains `abi:actorUserId`, `abi:actorWorkspaceId` and `abi:triggeredVia` (`api`, `configuration`, `system`), fields `actor_user_id`, `actor_workspace_id`, `triggered_via`. They are distinct from `workspace_id` because of constraint 4. `EventService.publish()` fills them from request-scoped ContextVars in `services/event/context.py`, unless the caller set them. The agent's `agent_user_id` / `agent_workspace_id` are the same ContextVars. `EventCodec` merges `_property_uris` along the MRO so inherited fields keep their IRIs. Nexus sets the ContextVars for every request in `RequestIdentityMiddleware` (pure ASGI): the user from the bearer token, the workspace from `/workspaces/{id}` or `?workspace_id=`. The boot seed runs with `triggered_via=configuration`.

3. **Identity and access in the 7 buckets.** A new section of `NexusPlatformOntology.ttl` places every element in its bucket:

   | Bucket | Classes |
   |---|---|
   | WHO (material entity) | `abi:Person`; `nexus:Organization`, whose members (`nexus:hasUser`) are persons |
   | WHERE (site) | `nexus:DeploymentSite`, the host every setup process occurs in |
   | HOW WE KNOW (GDC) | `nexus:User` (profile: avatar, company, job title, bio, credential storage), `nexus:Workspace` (branding, drives, coding repo, default/seeded agents, apps, ontologies), `nexus:OrganizationProfile` (name, slug, login branding), `nexus:WorkspaceMembership`, `nexus:OrganizationMembership`, `nexus:WorkspaceAppConfiguration`, `nexus:WorkspaceAgentConfiguration`, `nexus:PlatformConfiguration` with `nexus:ConfigurationSetting`, `nexus:TenantBranding`, `nexus:Feature`, `nexus:FeatureAccessPolicy` (role baseline and organization overlays), `nexus:WorkspaceFeatureOverride` |
   | WHY (role) | `nexus:PlatformSuperadminRole` (concretizes the platform configuration); `nexus:WorkspaceAccessRole` {Owner, Admin, Member, Viewer} and `nexus:OrganizationAccessRole` {Owner, Admin, Member}, which inhere in the person and concretize the membership that grants them |
   | WHAT (process) | `nexus:IdentityAndAccessProcess` and 19 subclasses: apply platform configuration; create / update / delete user, organization, workspace; add user to / change member role in / remove user from an organization or a workspace; configure workspace app, workspace agent, organization role features |
   | WHEN (temporal region) | `nexus:createdAt` → `abi:TemporalInstant` |

   A workspace-scoped process reaches its workspace through the role it realizes: process → `abi:realizes` → access role → `abi:concretizes` → membership → `nexus:isMembershipOfWorkspace` → workspace. This settles constraint 3; `nexus:WorkspaceRole` itself becomes an artifact category (a GDC), see Consequences. Relations between information entities use `nexus:isAbout` and `nexus:hasPart` / `nexus:isPartOf` (⊑ BFO continuant part). Constraint 2 is fixed: those restrictions and ranges point at `abi:Person`. `NexusPlatformOntology_test.py` checks the buckets, the roles and the participant rules.

4. **Boot initializes the graph with processes.** `services/identity_graph` rebuilds `graph/nexus-identity` from Postgres and the running configuration on every boot, and again 2 s after a burst of identity events. It uses a separate graph because of constraint 1. IRIs come from Postgres ids (`services/identity_graph/iris.py`): memberships and roles are keyed by the (scope, user) pair. Setup processes (`CreateUser`, `CreateOrganization`, `AddUserToOrganization`, `CreateWorkspace`, `AddUserToWorkspace`, `ApplyPlatformConfiguration`) are placed at their Postgres timestamps. Secrets are dropped by key name and credentials are stripped from URLs before configuration reaches the graph.

5. **Runtime logs the same processes as events.** `services/identity_events` projects each `nexus:IdentityAndAccessProcess` subclass to a `LogProcess` event class with the same class IRI. Property IRIs are taken from the generated ontology class. One ORM listener catches every write path: endpoints, invites, signup, config seeds, admin tools. It reads each change at `after_flush`, publishes at `after_commit` and drops everything at `after_rollback`. Personal fields appear only by name in `changed_fields`; non-personal before/after values go in `changes_json`. The events carry the same IRIs as the graph (`created_for`, `creates`, `updates`, `deletes`, `occurs_in`).

6. **Names are resolved when events are read.** `/admin/events/recent` resolves each page's distinct ids with a few SPARQL queries (`IdentityResolver`) and attaches `_identity` (actor, subject, workspace, organization, workspace role, superadmin) to each event. The live Socket.IO relay does the same through a 60 s cache, off the publisher thread. The Events UI draws the person as a material entity, the workspace and membership records as GDCs, the access role as a realizable, and the deployment host as the only site.

## Consequences

- The static ontology check (`validate_bfo_ontology`) resolves imports by `owl:versionIRI` too, so the vendored `bfo-core.ttl` is used instead of an HTTP fetch that made the check flaky. The Makefile fixes generated code with the same ruff as `make check` (`RUFF ?= uvx ruff`), in the per-file `%.py: %.ttl` rule too.

- Events already in the log that carry ids (agent and analytics events) resolve to people and workspaces as soon as the graph exists. No migration is needed.
- Uploads, triple-store writes and other service events caused by a Nexus request now carry the actor and workspace without changes to those services.
- A first boot on a fresh database logs one event per seeded record. For the current Forvis Mazars configuration that is 576 events (87 users, 26 workspaces, 311 memberships, 64 app configurations). Later boots log only what the seed actually changes.
- Names and emails live in Postgres and in the identity graph, never in the event log. `AnalyticsEventRecorded` no longer writes `user_email` (column or payload); the analytics adapter restores it on read from its user directory (`ref-users.json`), which stays mutable, so an address can be changed or erased. Events written before 2026-09-10 keep theirs.
- Configuration values that come from `{{ secret.* }}` templates are resolved before the graph sees them. Secrets are filtered by key name (`password`, `secret`, `token`, `api_key`, `database_url`, …), not by origin. With the current configuration that keeps `email_from_name` and `frontend_url`, which are public-facing.
- Bulk SQL `update()` / `delete()` statements bypass the ORM listener. The only one (demoting the previous default agent) now updates ORM rows, locked `FOR UPDATE`; any new bulk statement on an identity table is reported as a warning (`do_orm_execute`).
- Events started from a terminal (`abi chat`, the git agents) carry `actor_user_id = email-sha256:<sha256 of the git user.email>` and `triggered_via=cli`. Accounts carry `nexus:user_email_sha256`, so the resolver maps a git author to their person when a Nexus account has the same email; otherwise the UI shows `git author <8 hex>`.
- The fifteen `*Role` classes attached to artifacts (agent, conversation, knowledge graph, workspace, …) were not roles: artifacts are GDCs and cannot bear roles, and one individual such as "Supervisor Agent" classifies many artifacts. They are now GDCs under `nexus:ArtifactCategory`. `is*RoleOf` ⊑ `nexus:isAbout`, and `has*Role` is no longer a `bearerOf`. Class and property IRIs are unchanged, so code, queries and stored triples keep working.
