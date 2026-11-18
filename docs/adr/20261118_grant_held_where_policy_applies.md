# Grant only what you hold: a policy is held where it applies

- **Status:** Accepted
- **Date:** 2026-11-18

## Context

IAM refuses a policy write that would give, at some scope, more than the writer
holds there ("Grant only what you hold", `IAMService._require_held`). A
container's policy was checked at its owner; a platform policy unscoped and
below the platform (`abi:*`), as if attached in every container; both also at
each scope they are attached or invited at.

After the upgrade from sets and toggles (`policy_tree_v1`), every workspace's
"<W> access" denies the agents the workspace had turned off
(`TurnedOffAgents`). On a deployment of 114 workspaces about 110 deny agents of
every module. Whoever holds "<W> access" or a policy below it holds those
Denies: the workspace's admins and owners, the platform admin among them. An
organization's access ("<O> access") is a platform policy, so widening it was
checked at `abi:*`, where any of those Denies overlaps: the platform admin
could grant no module's agents to a new organization (#1519).

## Decision

A policy is held where it applies: at its owner (a container, or the platform,
`abi:`, and unscoped for a platform policy), at each scope it is attached or
invited at, and each policy below it at its own. A platform policy is no
longer also checked at `abi:*`. The rule is the same for every writer: the
alternative, exempting the platform admin from workspaces' Denies when
granting, would have broken the rule for one caller.

## Consequences

- A Deny the writer holds in another organization's workspace no longer stops
  a grant to an organization. One in a workspace of that organization, where
  the policy is attached, still does. An org admin or a workspace owner still
  gives only what they hold at the owner and where the policy is attached.
- A policy attached nowhere grants nothing. Whoever attaches, invites or binds
  it later is checked at that scope, as before. A platform policy written by
  hand is no longer refused at creation for what its writer lacks in some
  container: the refusal comes when it is attached there.
- No access decision changes, only which writes are refused. Details:
  `libs/naas-abi-core/naas_abi_core/services/iam/AGENTS.md`, "Where a policy is
  held" and the Decisions.
