# A workspace's graphs are IAM placements; what it shares is an Allow statement

Status: Accepted

Date: 2026-10-19

Specification: [`docs/specs/rfcs/20261013_identity-and-authorization.md`](../specs/rfcs/20261013_identity-and-authorization.md), §4.4, §6.4 and §13.

## Context

Nexus decided who may read or write which knowledge graph itself: `GraphAccessScope`
resolved a workspace's `graphWorkspaceId` triples and its saved `workspace_resource_policies`
(`WorkspaceGraphPolicyConfig`) against the caller's role, and a scoped store rewrote every query.
The triple store now authorizes every call for the signed-in user, by where IAM placed each
graph. Two authorities would disagree, and the data is reachable without Nexus.

## Decision

- **Owned graphs are placements.** The kernel's create rule places a graph created through a route
  in the workspace the call names. A startup source (`graph_placements`) places the graphs that
  already carry a `graphWorkspaceId` triple. The workspace's roles then reach exactly its graphs
  (viewers: list, read; members: insert, remove, create; admins: clear, drop). New graphs write no
  ownership triple.
- **Sharing is a statement for the receiving workspace.** A policy attached at a scope may only
  allow `${scope}:` resources, so a grant onto another workspace's graph cannot be a scoped
  attachment. For each workspace Nexus keeps two policies, `workspace.<ws>.graphs.read` (list and
  read actions of what it reads or writes, plus the Denies of `allow_create` and `include_owned`)
  and `workspace.<ws>.graphs.write` (`Insert`, `Remove` of what it writes). They name graphs
  wherever placed (`abi:*:*:triple_store:graph/<iri>`) and are attached, without scope, to the
  members who hold a role in the workspace (read: all roles; write: member and above).
  `ClearGraph` and `DropGraph` are never shared.
- **The saved assignments stay the editable document.** `workspace_resource_policies` is what
  administrators edit; saving it, and startup, project it into IAM (`graph_grants`). A graph's
  assignment needs a right over the graph: an administrator may add only graphs they can drop (their
  workspace's own) or that the workspace already holds; a platform administrator any.
- **What remains in Nexus** is the workspace's view (`GraphAccessScope`): which graphs the
  workspace offers, already narrowed to what the kernel lets the caller read and write. Nexus's
  application graph (labels, roles, view filters) is platform data, read and written as `api`.

## Consequences

- Membership changes must call `GRANTS.sync_members(workspace_id)` (`graph_grants`), or a removed
  member keeps the shared graphs and a new one lacks them. A core "scope grant" attached in step
  with role attachments, as feature policies are, would remove that step.
- `api` needs `iam:CreatePolicy`, `UpdatePolicy`, `DeletePolicy`, `GetPolicy`, `ListPolicies`.
- `read_all` shares the graphs that exist when it is applied (a later graph joins at the next sync), but only
  those of the workspace's own organization and the platform's: never another organization's, nor another
  personal workspace's (the shared `_none` organization). Turning it on is for platform administrators.
- Saving an assignment checks more than the catalog: a graph moved from read to write needs the right to drop it
  (the writers of the workspace may change it), as sharing it for writing did.
- Dropping or clearing a graph shared for writing is the owning workspace's alone (a tightening).
