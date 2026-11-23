# A drive per organization, decided at the organization; the workspace list grouped by organization

- **Status:** Accepted
- **Date:** 2026-11-18

## Context

Nexus had a drive per user (My Drive), per workspace, one platform drive shared by
the whole deployment, and the admins' system drive. An organization had none, so a
file that belongs to the organization as a whole (policies, contracts, brand
assets) lived either in one workspace, hidden from the others, or in the platform
drive, seen by every organization of the deployment (#1511; #907 had asked for
organization drives and shipped the platform drive instead).

A person may also belong to several organizations. The Workspaces list grouped
only by workspace group, a free-text field, so two organizations' "Operations"
groups merged, and nothing in the list named the organization.

## Decision

1. **One drive per organization**, `naas_abi/organization-drive/<org_id>`, with a
   manifest and the nine staff folders. An ORM listener on organizations makes it
   (`OrganizationDriveWriter`, so seeds and the API alike), a start-up backfill
   gives it to the organizations that predate it.
2. **Decided by IAM at the organization, not by a flag.** Its files are named
   `<org container>/nexus:file/organization/<path>` with their own actions:
   `ListOrgFiles` and `GetOrgFile` at `list`/`read` (the organization's viewers
   and up), `PutOrgFile` and `DeleteOrgFile` at `admin` (its admins and owners).
   Anything finer (members writing `operations/`, a folder hidden from viewers)
   is a policy attached at the organization. Its object storage is placed in the
   organization's container (`Placement.organization`), so the kernel holds
   everyone to the organization's roles too.
3. **Reached through a workspace.** The files API takes
   `scope=organization_drive` with the workspace the request comes from; the
   organization is the one IAM registered the workspace in. A workspace reaches
   its own organization's drive alone; one in no organization has none (404).
   The workspace's `files` feature applies.
4. **Shown to who may open it.** `/api/workspaces` answers `organization_drive`
   (IAM's `ListOrgFiles` on the drive's root, in one `filter`) and the
   organization's `organization_name` and `organization_slug`. The Files sidebar
   and Workspace settings › Drives show the drive under the organization's name.
5. **The Workspaces list groups by organization, then by workspace group**, with
   the organization's name and logo; personal workspaces go under "Personal". The
   organization headings appear only when the person's workspaces span more than
   one organization. The current organization comes first, then the others
   alphabetically, then Personal. Search matches organization names.

## Consequences

- A role held only in one of an organization's workspaces reaches nothing of its
  drive: someone must hold a role at the organization (or a policy there).
- Changing who writes a folder is an IAM policy, not a release. A policy that lets
  a viewer write must also grant `object_storage:PutObject` at the organization,
  since the kernel checks the role's object storage level.
- The `nexus` catalog is version 11.
- The staff folders' READMEs no longer say "workspace": the same text fits the
  workspace, organization and platform drives. READMEs already written stay.
- Not done here: the organization's logos still live on the API's disk
  (`uploads/org-logos`), and the organization headings of the Workspaces list are
  not collapsible.
