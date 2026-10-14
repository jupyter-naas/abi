# Skill package ownership

Status: Accepted
Date: 2026-10-05

## Context

The skills settings page writes a database record and package files. Loading files
as independent workspace skills bypasses private-record visibility, lets equal
slugs share files, and resurrects deleted records.

## Decision

Database records are authoritative for user skill identity, ownership, visibility,
and lifecycle. Package writes require a record ID and its update permissions.
Files live under `records/<sha256(record-id)>/package`, independent of slug changes.
Only files attached to an authorized record are listed or read. Deleting a record
removes its attached package.

Module skills follow ABI component discovery instead: `BaseModule.on_load` discovers
`skills/<slug>/SKILL.md`, the module registry identifies them as `module:slug`, and
workspace `skills:` configuration selects the visible catalog. Missing configuration
enables none. This config is authoritative on each request; unlike editable ontology
assignment snapshots, there is no database override for module skills. Read-only
module records carry explicit source and catalog reference metadata, and their IDs
include the authorized workspace. They are never inserted as private database rows.
Catalog listing does not disclose their procedure bodies; invocation and detail
reads resolve them after rechecking the current allowlist.

## Consequences

Existing workspace/slug directories are not automatically exposed or migrated:
they contain no trustworthy ownership metadata, and multiple private records can
share a slug. Their contents must be explicitly reattached to an authorized record.
Files left by a failed cleanup cannot reappear in the catalog without a record.
