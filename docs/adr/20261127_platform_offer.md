# What the platform offers its organizations: "Platform access"

- **Status:** Accepted
- **Date:** 2026-11-27

## Context

The deployment's `enabled_features` (`nexus_config.feature_flags`) was the feature catalog itself: a feature
outside it existed nowhere, not even for the platform admin, and turning one on (Sheets, Tasks) meant editing
the deployment's configuration and restarting. Organizations and workspaces already narrow what they offer
("<O> access", then "<W> access", a sub-policy of it), but nothing above the organizations could be changed
from Settings.

## Decision

1. **Every known feature exists** (`KNOWN_FEATURE_KEYS`): Platform settings › Access › Features lists them all,
   the platform picked first in its Organization picker.
2. **"Platform access"**, a policy the platform owns (attached to nobody, the parent of nothing), records the
   features the platform offers its organizations, in the offer's form (its Features section,
   `workspace_offer`). It is made once, at the first start that finds none (`container_defaults.migrate`,
   `ensure_platform_offer`), from `enabled_features`: nothing changes on deploy. The platform admin then
   offers or takes back a feature there (`GET|PUT /api/platform/feature-access`, written as the caller:
   IAM's `iam:UpdatePolicy` decides).
3. **Nexus applies it where it applied `enabled_features`** (`feature_flags.deployment_catalog`: authz's
   `feature_exists`, the listers, a new workspace's offer, the access model, the workspace flags): a feature
   the platform does not offer is usable by nobody, the platform admin included, and an organization's
   Features page does not list it. Until "Platform access" exists (or when IAM cannot be read),
   `enabled_features` decide, as before. Settings stays pinned.
4. **Read from IAM's store**, as the engine reads its own configuration (no authorization asked), kept by
   the process for 10 s; a change made through Nexus is seen at once (`platform_offer.forget`).
5. **Not an IAM chain.** "Platform access" is not made the parent of every "<O> access": as a parent it would
   have to allow everything else an organization offers (agents, modules, datasets, files...) and every
   existing "<O> access" would need reparenting. It records the platform's choice; Nexus applies it, as for
   the dataset closures (ADR `20261125_offer_gives_outside_resources`).

## Consequences

- Sheets, Tasks or Code are offered from Platform settings, without a configuration change or a restart;
  `enabled_features` becomes the default of a new deployment.
- An organization inherits what the platform offers: its "<O> access" offers its workspaces only those
  features; one taken back from the platform disappears from every organization and workspace at once
  (their offers keep naming it, harmlessly, until it is offered again).
- Two sources until the first start makes "Platform access": the configuration, then the policy. Changing
  `enabled_features` afterwards changes nothing (the policy is kept); a deployment that wants the
  configuration back deletes "Platform access", which the next start makes again from it.
