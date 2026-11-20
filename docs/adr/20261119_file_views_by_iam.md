# Every view of the file system is opened by IAM alone; the workspace drive flags go

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

Nexus calls five things "drives" (My, Workspace, Organization, Platform and System
Drive), but there is one drive, the object storage, and each is a view of it: a
folder someone may open, shown as a starting point (epic #1528). Three of the views
were decided by IAM alone. The other two had a second source of truth:

- **Platform Drive** (`naas_abi/platform-drive`): the workspace's roles by level
  (`ListFiles`… on `<workspace>/nexus:file/platform/...`) **and** the workspace flag
  `platform_drive_enabled`. The kernel let every role holder read the folder and
  members write it (core's `roles.py` platform row for `object_storage`).
- **System Drive** (the whole object storage): the workspace's admins
  (`*SystemFile`, admin level on `<workspace>/nexus:file/system/...`) **and** the
  workspace flag `system_drive_enabled`.

The flags were columns of `workspaces`, flipped by a platform admin in Workspace
settings › Drives. A workspace role reaching a tree shared by the whole platform,
gated by a per-workspace switch beside IAM, made two places to ask "who may open
this" (#1529).

## Decision

1. **Platform Files** is its own platform-level type, `platform_file` (path id,
   `policy_only`), with `ListPlatformFiles`, `GetPlatformFile` (`list`/`read`) and
   `PutPlatformFile`, `DeletePlatformFile` (`write`), on
   `abi:nexus:platform_file/platform/<path>`. No role holds it, owners included: a
   policy at the platform grants it, the platform admin holds it. It is decided at
   the platform, with no workspace feature, whatever workspace the request names.
2. **The kernel follows.** Core's `roles.py` platform row for `object_storage` no
   longer names `object/naas_abi/platform-drive` (a naas-abi-core change), so the
   object storage refuses its objects to every role too. A Platform Files grant
   names both halves: the Nexus actions on `abi:nexus:platform_file/*` (or a folder)
   and `object_storage:ListObjects`, `ListObjectsRecursive`, `GetObject`,
   `GetObjectMetadata`, `GetObjectStream` (plus `PutObject`, `PutObjectStream`,
   `DeleteObject` to write) on `abi:object_storage:object/naas_abi/platform-drive`
   and `.../platform-drive/*`. Documented (IAM `AGENTS.md`), not templated: Nexus
   has no policy templates yet.
3. **System Files** moves to `system_file` (platform-level, `policy_only`), with
   `ListObjectStoreFiles`, `GetObjectStoreFile`, `PutObjectStoreFile`,
   `DeleteObjectStoreFile` on `abi:nexus:system_file/system/<path>`: the platform
   admin's (`*` on `*`), workspace owners and admins lose it.
4. **The old actions stay declared.** IAM refuses a catalog version dropping an
   action a policy names, so `ListSystemFiles`, `GetSystemFile`, `PutSystemFile`
   and `DeleteSystemFile` stay, deprecated: no route asks for them, they authorize
   nothing (as `GetRoleFeatures` did). The catalog is version 12.
5. **The flags go**: the files API checks, the workspace API fields and their
   platform-admin-only guard, `WorkspaceRecord` / `WorkspaceUpdateInput`, the
   identity graph's workspace settings, the ontology's two properties and the web
   store's `platformDriveEnabled` / `systemDriveEnabled`. Migration
   `0073_drop_drive_flags.sql` drops the columns (`DROP COLUMN IF EXISTS`, rewritten
   for SQLite by the runner); `0026` and `0027`, which made them, have no statement
   any more. A PATCH still sending a flag is ignored.
6. **The views are listed for the UI**: `GET /api/files/views?workspace_id=`
   answers the views the caller may open from that workspace, in order (`my_files`,
   `workspace_files`, `organization_files`, `platform_files`, `system_files`), each
   with its `label`, `drive` (`file_system`), `scope` (the files routes' `scope`) and
   `root` (its storage folder, `""` for the whole store), each IAM's `List*` on the
   view's root, decided as the files routes decide it. It replaces
   `organization_drive` on `/api/workspaces` (#1511); that field stays until the
   Files page and sidebar move to the views (#1530).

## Consequences

- **Access is reset, no upgrade keeps it.** Whoever reached the platform drive
  through a workspace flag loses it until a platform admin grants Platform Files
  (both halves above); workspace admins who used the system drive lose it. The
  release notes say so.
- One question, one place: who opens a view is a policy, listed and edited with
  the other policies; nothing in the workspace settings decides it.
- Platform Files can be granted per folder (`abi:nexus:platform_file/platform/shared/*`)
  and per person or group, where the flag was all of a workspace or nothing.
- A Platform Files grant that names only the Nexus actions lists the folder in the
  API but the object storage refuses it: an administrator grants both halves until
  a policy template carries them together.
- `GET /api/files/views` shadows a file named exactly `views` at the root of a
  view for the JSON read route (`GET /api/files/{path}`); `/api/files/raw/views`
  still reads it.
- Workspace settings › Drives loses its toggles; Platform settings › Drives lists
  the drives instead (#1531).
