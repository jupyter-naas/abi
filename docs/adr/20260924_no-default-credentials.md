# No default credentials

Status: Accepted

Date: 2026-09-24

## Context

`abi deploy local` wrote `NEXUS_USER_ADMIN_PASSWORD=Admin1234!` into every project's `.env`, and `abi dev up` wrote `admin` for the same account and `abi` as `ABI_API_KEY`. The scaffolded configs make `admin@example.com` a superadmin with password login enabled. Because these values are published in the repository and docs, anyone who could reach a deployment could sign in as platform superadmin.

## Decision

ABI ships no default passwords or API keys.

- `abi new project`, `abi dev up` and `abi deploy local` generate the seeded admin password (`NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD`) and, for `abi dev up`, `ABI_API_KEY` per project into `.env`. A value an older CLI wrote is replaced in place; a custom value is kept.
- The seeded account stays `admin@example.com` and is the only account the config creates. Other users register or are invited.
- Nexus keeps a list of published defaults (`services/auth/default_passwords.py`). Login refuses them for every account even when the hash matches, and register, change and reset reject them.
- On boot the seeder ignores a default found in the secret store for a new account and replaces the password of an existing config account whose hash matches a shipped default, storing the generated one in the secret store.

## Consequences

Upgraded installs can no longer sign in with `admin` or `Admin1234!`; the admin reads the new password from `.env` (`NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD`) after the first boot. Tooling that assumed `ABI_API_KEY=abi` must read the generated key from `.env`. The CLI keeps its own copy of the default list because it does not depend on the Nexus app; the two lists must stay in sync.
