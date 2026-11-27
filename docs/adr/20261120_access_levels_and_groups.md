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
   - **An Org Admin holds no level** (decided 2026-11-24): "<O> admins" reaches every workspace of O, so a level would give them nothing there. They hold one only when they also work where it does not reach (a workspace of another organization, or of none). The access move gives none otherwise, and takes out one a move of before left (said among the redundant groups).
   - **A person's level is one choice.** It can be changed by org admins, platform admins and the admins of any of the person's workspaces. It applies in all their workspaces and is audited. This is the one place where IAM allows a writer to change access beyond what they hold, and only for the generic level policies.
   - **People with no workspace** are in "<O> people", a membership group of the organization. So are its admins and whoever holds a role at the organization itself. What it holds there is decision 12.

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
   - As built (#1584): a group carries `membership_of` (a registered container at or below its owner) and `level_group`; the scope is `names.MY_CONTAINERS_SCOPE`. A policy there applies only within the owners of the policy and of the group holding it, so an organisation's level group never reaches another organisation. Attaching there is the platform's (the attachment is named at the platform), and so is marking a level group. Joining or leaving a level group is allowed to whoever may change the group's members as it is named in one of the person's containers, without the held check of its `${my workspaces}` policies, and is audited (`IAMService.add_audit_listener`).
   - As built (#1585): what a membership group holds **at its own container** is that container's **bound**, not a grant: "<W> workspace" holds "<W> access" at W. When a customer policy attached at `${my workspaces}` is expanded at W, each of its Allows counts only where W's bound (with its chain, "<O> access") allows it too; its Denies, and the bound's, apply. Built-in roles expanded there are not bounded (they hold no module scope or feature). So the level supplies the what, generic (`${scope}/module:agent/*`, its features), and W's offer the where. "<W> admins" is a membership group of W too, holding `builtin.admin` and "Workspace admin access" at `${my workspaces}`: reaching W alone (its owner), bounded the same way. No stored field: the rule reads the group's `membership_of` and the attachment's scope. The first membership of someone who belongs to nothing yet is made by a first-party account acting for no user (Nexus, after its own check). A grant meant for every person of W (a shared graph) cannot be held by "<W> workspace" (a workspace's group receives attachments at it only, and is then a bound), so it stays an attachment Nexus keeps in step with the group.

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
   - Accepted widenings, flagged intended in the report:
     - a level's features apply in every workspace, within its offer (`level_features`): a Member gains there a feature the workspace's old "Features of member" did not give but its offer has;
     - org admins use the organization's offer in each of its workspaces (`org_admins`), and the workspace's lists show them its offer (decision 11).
   - The sets' move's per-workspace copies of an org-wide "Features of <role>" go with the others. What they gave was their holder's, so they add nothing to the workspace's offer.
   - The start that moves does not wait for the report. It tries the plan on a copy of IAM, the only check that stops the move, keeps IAM as it was (`access_model_v1_planned`), makes the move and records it, then serves. Who gains and loses what is compared afterwards, from the kept copy (`decisions` "pending", then "compared"). On a deployment of about 150 people in 115 workspaces, comparing takes most of an hour and the move itself a few minutes.

10. **Platform Files comes with the workspace** (#1590).
    - Workspace settings › General › Platform Files is Off, Read, or Read and write, for everyone in the workspace. Only the platform admin changes it.
    - Two platform policies, written once: "Platform Files · read" and "Platform Files · write", each naming both halves (the Nexus actions on `abi:nexus:platform_file/*` and the object storage's on `naas_abi/platform-drive`).
    - "<W> workspace" cannot hold them: what it holds at W is W's bound, and IAM refuses an unscoped attachment to a group a workspace owns. Option (b), a core rule, was rejected as a second exception to the bound rule.
    - As built (option (a)): a **platform group per workspace that has it**, "Platform Files · <W> (<workspace id>)", holds one of the two policies, unscoped. Nexus keeps its members equal to the people of W (the members of W's membership groups): at each membership change, where "Workspace admins" follows "<W> admins"; after a member is added or removed on the IAM admin pages; when the setting changes; and at each start, which also deletes the group of a deleted workspace. The setting is which policy the group holds, so IAM is its only store.
    - Why a group per workspace and not one per mode ("readers", "editors"): with one group per mode, leaving W would have to recompute the person's mode from all their other workspaces, and the setting would need a store of its own. With a group per workspace, a membership change is decided for W alone.
    - The legacy flags: `0073_drop_drive_flags.sql` copies the flagged workspaces into `workspace_drive_flags_legacy` (PostgreSQL only) before it drops the columns. `access_model_v1` converts `platform_drive_enabled` into Read and write and reports `system_drive_enabled` without converting it (System Files stays the platform admin's).

11. **A workspace's lists show its offer, for everyone.** An Org Admin holds "<O> access" below the organization, so IAM lets them use, in every workspace of O, what O offers: a client's agents in another client's workspace. They need it: widening a workspace's offer is checked against what the writer holds there ("Grant only what you hold"), and org admins are who widen offers.
    - Nexus narrows what it **shows**, not what IAM allows. What `Authz.filter_scopes` keeps (the agents, apps, workflows and pipelines a workspace lists, the chat's agents and their sub-agents, the models of the OpenAI gateway, the workspace's usage counts) is also within the workspace's offer. For Members and Workspace Admins this changes nothing, their level being bounded by the offer already. A single item asked by name (`require_scope`: opening an app, a turn of an agent) stays IAM's decision.
    - A workspace with no record, or whose access policy is not an allow-list yet, is not narrowed. The offer is read as `api` and remembered for 30 seconds in each process; a change of an offer made in that process forgets it at once.
    - Rejected: bounding org admins by the offer inside IAM ("<W> access" held by "<O> admins" at each W). Org admins could then no longer widen an offer, only the platform admins, unless Nexus wrote the offer for them, a second exception to "Grant only what you hold". It would add no protection either: an org admin may add any module of O to a workspace's offer and use it.

12. **The organization's people see it, and nothing it holds** (decided 2026-11-26).
    - Before: "<O> people" held `builtin.viewer` and "Viewer access" at `${my workspaces}`, which IAM fills with the organization itself. Its people listed the organization's secrets (masked) and read what it holds (Organization Files, its drive, its graphs, its datasets). A Member of the organization wrote its Organization Files through the built-in role of their level, which reached the organization the same way.
    - Now Nexus's `organization` type is marked `no_membership_roles` (catalog 21; core IAM: a built-in role attached at `${my workspaces}` gives nothing at a container of a type so marked). "<O> people" holds "Organization view" (`GetOrganization`, `ListOrganizations` on `${scope}`) at `${my workspaces}`, which grants it, and at the organization, its bound, which keeps the level policies to it there.
    - Org admins keep what `builtin.admin` attached at the organization and below it gives them ("<O> admins"). The people of a workspace are not "<O> people": unchanged.
    - Someone who should read Organization Files gets them from a workspace's offer (`GivenOrgFiles`), or from a policy attached at the organization to them or to a group of theirs. That policy is not at `${my workspaces}`, so no bound narrows it. Seeing them in a workspace still takes that workspace's `files` feature.
    - The move `org_people_view_v1` converts each organization once: "Organization view" attached first, then the two policies of before detached. The access move's report names the change `org_people_view` (intended).
    - Rejected: a Deny on "<O> people", which would refuse the org admins too (they are in it); removing `builtin.viewer` alone, which leaves the level's built-in role reaching the organization.

## Consequences

- **A person is a few group memberships and nothing attached to them directly.** On the audited deployment this means 491–651 memberships instead of 3,764 attachments, and 407 policies instead of 1,210. The higher figure counts a default admin assigned to the workspaces left empty.
- **Core IAM evaluates a new scope.** Its memberships are cached per principal, invalidated on join and leave, and followed by the kick of the principal's connections. "Grant only what you hold" checks an addition to a membership group against what the group's level policies give there.
- **A person has one level everywhere.** Administering a workspace is the only per-workspace exception. Being a Viewer in one workspace and a Member in another needs a capability group or a level change.
- **New modules reach no workspace until added to its allow-list,** where today they are offered everywhere unless denied.
- **The catalog changes.** `DeleteWorkspace` moves to the Org Admin and `DeleteOrganization` to the Platform Admin. The Owner role stays declared, for the policies that name it, but nothing assigns it.
- **People flows change in one place.** Since #1580, creating, adding and removing people goes through the people service's access gateway. Its grant changes from role and policies to level and groups, and the platform, organization and workspace user pages follow (S6).
- **Nexus keeps the Platform Files groups in step,** like a grant meant for every person of W: a platform group per workspace that has it. A membership changed straight in IAM, around Nexus, is followed at the next start. A SQLite deployment keeps no legacy drive flag: its platform admin sets each workspace's Platform Files again.
- **The move's report comes after its start.** For a while after the upgrade, its record says which groups people joined and what was detached and retired, but not yet who gained or lost what. A restart in between compares again from the kept copy, which the comparison then drops.
- **What a workspace shows is narrower than what IAM allows** for org and platform admins (decision 11). An org admin who calls the API for an item their workspace does not offer is still allowed: the separation of clients is what Nexus shows, and who may widen offers.
- **An organization's people hold its view only** (decision 12). Organization Files reach someone through a workspace's offer or a policy attached at the organization; core IAM has one more mark on a container type, `no_membership_roles`.
- **Deployment-specific choices are configuration,** not code: the member model set, a default admin for workspaces left empty, personal workspaces, and the features of the Viewer and Member levels (`feature_flags.level_features`: one deployment caps Viewers at apps and lets each workspace's offer decide its Members' features, another keeps the defaults).
