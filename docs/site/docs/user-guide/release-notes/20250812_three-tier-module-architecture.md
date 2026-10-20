---
sidebar_position: 15
title: "Three-Tier Module Architecture (Core / Custom / Marketplace)"
---

# Three-Tier Module Architecture (Core / Custom / Marketplace)

- **Document Type:** ADR
- **Status:** Accepted
- **Date:** 2025-08-12

## Context

ABI's module system had grown organically with no enforced separation between system-level modules, private user extensions, and community-contributed integrations. All modules lived in a flat directory, making it hard to:

- Distinguish what is essential system functionality vs. optional add-ons.
- Safely enable/disable third-party marketplace modules without affecting core behavior.
- Package and distribute community modules independently from the core system.

## Decision

Consolidate into a **three-tier module architecture** with explicit separation of concerns:

| Tier | Path | Purpose |
|------|------|---------|
| **Core** | `src/core/modules/` | Essential system functionality; always loaded |
| **Custom** | `src/custom/modules/` | Private, project-specific extensions; not distributed |
| **Marketplace** | `src/marketplace/modules/` | Community integrations; opt-in, disabled by default |

All three paths are registered in `MODULE_PATH` for auto-discovery. Marketplace modules ship with a `.disabled` suffix and must be explicitly enabled. The `assistants/` directory is renamed to `agents/` across all tiers for naming consistency.

## Consequences

### Positive
- Clear ownership boundaries: core is owned by the platform, custom by the project, marketplace by the community.
- Marketplace modules are safe-by-default; a broken community module cannot affect core startup.
- Enables selective activation and per-module dependency management.

### Tradeoffs
- Three `MODULE_PATH` entries increase discovery scan time proportionally.
- The `.disabled` suffix convention is non-standard; developers must remember to rename files to activate modules.
- Boundary enforcement is by convention, not by code - nothing prevents core code from importing marketplace code directly.
