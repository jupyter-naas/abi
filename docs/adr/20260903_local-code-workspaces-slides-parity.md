# Local code workspaces (Slides parity)

## Status

Accepted

## Date

2026-09-03

## Context

The Nexus Code feature today depends on **Coder** (per-user Docker workspaces + embedded code-server) and **Forgejo** (git forge, PRs, Actions). That stack is heavy for local development (`abi dev`) and couples the product to infrastructure most solo developers do not need on a laptop.

Slides already demonstrates the desired control loop: the user stays in Nexus, a hidden runtime (sidecar) holds the live working tree, Abi agents edit via domain tools, and git provides history. Code should follow the same pattern locally before adding managed harnesses (OpenCode, Claude Code, Codex, …).

## Decision

1. Add **`local_git`** source-control adapter — repos on disk under `storage/git`, branches/commits/files via the `git` CLI.
2. Add **`local_directory`** coding-environment adapter — git checkout + **`abi_sidecar`** subprocess on localhost (no Coder).
3. Follow **Slides-parity UX**: Nexus UI + Abi chat orchestrate edits; no external IDE as the primary loop in v1.
4. Defer in-app PR/Actions locally (`NotImplementedError` on unsupported port methods).
5. Managed harness adapters come in a later phase; v1 is Abi + sidecar + git only.

## Consequences

- `abi dev` can enable Code with `local_git` + `local_directory` in config — no Forgejo/Coder containers.
- Production Docker deploy keeps existing `forgejo` + `coder` adapters unchanged.
- Nexus provision flow stores `sidecar_base` / `sidecar_secret` on `coding_environments` (same as Slides).
- Chat binds `context.coding` → sidecar ContextVars → `coding_tools`.
