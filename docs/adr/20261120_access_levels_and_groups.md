# Access levels and groups: where comes from a workspace group, what from a level

- **Status:** Accepted
- **Date:** 2026-11-20
- **Epic:** #1583 (S1 #1584, S2 #1585, S3 #1586, S4 #1587, S5 #1588, S6 #1589). Builds on the people directory, #1580 (#1566).

## Context

After the IAM upgrade, Nexus decides every access through IAM policies, but its starting state was built for equivalence rather than for being read. An audit of a live deployment (about 150 users, 115 workspaces, one organization) found the following.

- **1,210 policies.**
  - Each workspace owns 8: its access policy, "<W> modules (its people)", and "Features of viewer/member/admin/owner" (admin and owner twice).
  - 807 of these are copies of only 4 distinct documents.
  - 304 are attached to nobody.
- **3,764 attachments made to people one by one.**
  - A member holds 3 per workspace plus 2.
  - A platform admin holds up to 633, all of them covered by `builtin.platform_admin`.
  - Org owners and admins hold 2,350 per-workspace copies of what their org-wide role already gives them.
- **232 groups that grant nothing.** "<X> members" and "<X> admins" copy the roles, but no policy is attached to a group. The access policies ("<X> access") are attached to nobody.
- **Ceilings deny instead of allowing.** Each workspace's access policy allows every agent and then denies about 100 agents of other workspaces' modules.
- **Confusing names.**
  - "Member" (a role held at a place) and "Platform member" (the shared half that IAM attaches automatically) share a name.
  - Owner differs from Admin by two actions.
  - The UI says "Superadmin" where IAM says "Platform admin".

Administrators reason about people in two axes: **where** someone works (a workspace, which offers certain agents, apps, workflows and maps) and **what** they may do there (view, work, administer). IAM evaluates the **union** of what is attached, so two groups, one per axis, could not express "Member, but only in W".

## Decision

1. **Levels.** Platform Admin, Org Admin, Workspace Admin, Member and Viewer.

   | Level | Group | Holds |
   |---|---|---|
   | Platform Admin | "Platform admins" | `builtin.platform_admin`; creates and deletes organizations |
   | Org Admin | "<O> admins" | "<O> access" below the organization and admin at it; deletes workspaces |
   | Workspace Admin | "<W> admins" | "Workspace admin access" at W |
   | Member | "Members" | "Member access" at `${my workspaces}` |
   | Viewer | "Viewers" | "Viewer access" at `${my workspaces}` |

   - **Owner is no longer assigned.** The last Org Admin of an organization cannot be removed.
   - **A workspace is created with a workspace admin,** who defaults to the creator.
   - **A Workspace Admin is a Member** with "<W> admins" for each workspace they administer.
   - **A person's level is one choice.** It can be changed by org admins, platform admins and the admins of any of the person's workspaces. It applies in all their workspaces and is audited. This is the one place where IAM allows a writer to change access beyond what they hold, and only for the generic level policies.
   - **People with no workspace** are in "<O> people", a membership group of the organization that holds Viewer access at its own level.

2. **Generic level policies, written once.**

   | Policy | Actions | Features | Instances and models |
   |---|---|---|---|
   | "Viewer access" | read | apps, datasets | no model |
   | "Member access" | write | apps, chat, files, datasets, graph, maps, ontology, search | the workspace's agents and apps; the deployment's member model set |
   | "Workspace admin access" | admin, at W | all | adds workflows, pipelines and maps; all models |

   No copy of these policies exists per workspace.

3. **The workspace group is the "where".** "<W> workspace" is a **membership group** of W, and holds "<W> access".
   - That access policy is an **allow-list** of W's instances, shared modules included.
   - It is also W's ceiling.
   - Modules come with the workspace. A group of people is made only for a per-person exception, such as a seat licence or a pilot.

4. **Intersection inside IAM.**
   - Core IAM gains membership groups and the attachment scope `${my workspaces}`. At decision time, that scope resolves to the containers whose membership group holds the principal.
   - A level policy attached once to its level group therefore applies only where the person is a member.
   - `explain` names both groups.
   - Rejected alternative: Nexus keeping hidden per-person role attachments in step with the groups. That means two sources of truth, which drift when a group is changed outside Nexus, and a second migration to reach this model later.

5. **Capability groups** add one thing to a level. Examples: "Workflow runners" for a Member, and "Models · all" for every model.

6. **Models.**
   - `builtin.platform.member` no longer grants every model.
   - Model sets are policies on `abi:model_registry:model/<canonical id>`.
   - An agent's own model is always allowed.
   - Every Member and Viewer may use the embedding models.

7. **Built-ins.**
   - "Platform member" and "Platform viewer" stay automatic and are shown only as "Platform access (automatic)".
   - Service-account policies are shown only under Platform › Service accounts.
   - `builtin.self` no longer creates organizations, and creates a personal workspace only if `nexus.personal_workspaces` allows it.

8. **The org Member role.**
   - A workspace add never grants it (#1580).
   - People with no workspace move to "<O> people".
   - The migration removes it from people who reached the organization only through a workspace.

9. **Migration** (`access_model_v1`).
   - It builds the target from what IAM holds now, then removes the per-person attachments and the retired policies.
   - It reports every access change by person, the workspaces whose membership group is empty, and the people who are only org members.
   - Nothing changes silently. The intended narrowings are listed:
     - members lose workflows and pipelines unless they are in "Workflow runners";
     - model sets apply;
     - owners lose delete;
     - leftover org Member roles go.
   - Members gain the datasets feature.

## Consequences

- **A person is a few group memberships and nothing attached to them directly.** On the audited deployment this means 491–651 memberships instead of 3,764 attachments, and 407 policies instead of 1,210. The higher figure counts a default admin assigned to the workspaces left empty.
- **Core IAM evaluates a new scope.** Its memberships are cached per principal, invalidated on join and leave, and followed by the kick of the principal's connections. "Grant only what you hold" checks an addition to a membership group against what the group's level policies give there.
- **A person has one level everywhere.** Administering a workspace is the only per-workspace exception. Being a Viewer in one workspace and a Member in another needs a capability group or a level change.
- **New modules reach no workspace until added to its allow-list,** where today they are offered everywhere unless denied.
- **The catalog changes.** `DeleteWorkspace` moves to the Org Admin and `DeleteOrganization` to the Platform Admin. The Owner role stays declared, for the policies that name it, but nothing assigns it.
- **People flows change in one place.** Since #1580, creating, adding and removing people goes through the people service's access gateway. Its grant changes from role and policies to level and groups, and the platform, organization and workspace user pages follow (S6).
- **Deployment-specific choices are configuration,** not code: the member model set, a default admin for workspaces left empty, and personal workspaces.
