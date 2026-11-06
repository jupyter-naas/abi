# Remote agents carry their display name, avatar and suggestions

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

An in-process agent is presented in Nexus from its class:

- `name` is the display name;
- `logo_url` is the avatar, a module asset under `/modules/`;
- `suggestions` are the starter prompts.

An agent published by a remote module (NATS discovery, `agent.invoke.v1`)
reached Nexus as `AgentDescriptor(name, description)` only. Its name is also
its key (`<module_id>/<name>`), so it must be NATS-safe.

Moving an agent from the engine to a remote module therefore changed what
users saw, which was a visible regression:

- `ACME_Account_Director` instead of "ACME Account Director";
- no avatar;
- no suggestion chips.

Descriptors travel in every registration and listing, and they are stored in
the registry snapshot. That snapshot holds every module and is bounded to
512 KiB. Remote apps already follow this rule: their descriptor stays small,
and their files are served by the app host.

## Decision

- **Proto.** `AgentDescriptor` gains three fields:
  - `display_name` (5);
  - `avatar_url` (6);
  - `repeated AgentSuggestion suggestions` (7), where `AgentSuggestion` is
    `label`, `value` and `description`.

  All are optional and presentation only. The `name` stays the key.
- **Avatar is a reference, never image bytes.** It is one of:
  - an `https://` URL;
  - a `/modules/<path>` asset served by an engine module, which Nexus prefixes
    with its public API host. This is the same place an in-process agent's
    `logo_url` resolves to.

  Image bytes inline would let a handful of modules exhaust the shared
  registry snapshot.
- **Bounds.** The SDK checks them when the descriptor is declared; the engine's
  discovery refuses a registration that breaks them, with `INVALID_ARGUMENT`.

  | Field | Bound |
  |---|---|
  | `display_name` | ≤ 128 characters, not blank |
  | `avatar_url` | ≤ 1024 characters, `https://` or `/modules/` (no `..`) |
  | `suggestions` | ≤ 8 |
  | suggestion `label` | 1–128 characters |
  | suggestion `value` | 1–1024 characters |
  | suggestion `description` | ≤ 256 characters |

  Eight suggestions at the bound cost about 11 KiB per agent. In practice they
  cost a few hundred bytes.
- **Nexus.**
  - A new remote agent row is named with its `display_name`.
  - A listing presents remote rows from the last discovery read: display name,
    avatar and suggestions. That read is refreshed by every reconcile, and on a
    listing with remote rows once it is older than 30 s.
  - When discovery cannot be read, a remote row keeps its stored name, with no
    avatar or suggestions. Its model fields are unchanged: its module picks the
    model.

## Consequences

- A module moved out of the engine can present its agent as it did in the
  engine. It sets `display_name`, `suggestions` and `avatar_url`, pointing the
  avatar at an asset an engine module serves, or at an https URL.
- Older modules and older engines interoperate:
  - unknown proto fields are ignored;
  - absent fields mean "no presentation", which is the previous behaviour.
- **Not covered here:**
  - **Intents:** the `IntentAgent` quick answers stay inside the remote
    process, which handles them on invocation.
  - **Avatars served by the remote module itself:** this would need an asset
    endpoint on the agent host. It is left for when a module has no engine
    module or https host to put its avatar on.
