# The NATS broker admits only clients with a password

Status: Accepted

Date: 2026-10-08

## Context

The broker that `abi deploy local` generates accepted any client. A client
that reaches port 4222 can subscribe to `>` and read every request and reply,
including the service tokens in their headers. It can also publish replies,
trigger jobs, and read or rewrite JetStream streams and KV buckets directly.
Service tokens only check who is calling a service; they do not stop a client
from listening or from reaching JetStream.

The broker was reachable from:

- every container on the Compose network, including coding workspaces (Coder
  attaches them to it) and CI jobs;
- every interface of the host, because the port was published as `4222:4222`.
  On a laptop, that means the local network.

## Decision

- `nats.conf` declares two users with passwords: `abi`, for the engine's
  process (kernel services, API, Nexus, jobs), and `module`, for SDK modules.
  A client without a valid user and password is refused.
- `abi deploy local` generates `NATS_ABI_PASSWORD` and `NATS_MODULE_PASSWORD`
  in `.env` (`admin_credentials.ensure_nats_passwords`). It replaces a value
  that is empty or shorter than 16 characters.
- A generated password starts with a letter and contains only URL-safe
  characters. nats-server reads `$VAR` in `nats.conf` as a config value, so a
  value that starts with a digit or `-` fails to parse. Clients pass the
  password in the URL, so it must need no escaping.
- The Compose service refuses to start when either password is empty.
  nats-server takes an empty `$VAR` as an empty password, which lets anyone in
  as that user. The check runs in the container rather than as `${VAR:?}`,
  because Compose checks `:?` for every command, even when the `nats` profile
  is off.
- Clients pass their credentials in the URL: `nats.nats_url` is
  `nats://abi:{{ secret.NATS_ABI_PASSWORD }}@nats:4222`, and modules use
  `ABI_NATS_URL=nats://module:...@nats:4222`. nats-py reads `user:password@`
  from the URL, so no connect site changed. Nothing in ABI logs or displays
  that URL.
- The client and monitoring ports are published on 127.0.0.1 only. Containers
  still reach the broker as `nats:4222`.
- `abi dev up --with-nats` is unchanged. Its broker listens on 127.0.0.1 and
  has no users.

## Alternatives

- **One shared token.** Simpler, but it gives modules the engine's credential
  and cannot grow into per-user rights.
- **NKeys, or NATS accounts with operator JWTs.** Stronger (no shared secret on
  the wire, revocation), but they need `nsc`, key distribution and a resolver.
  That is too much before modules run outside the engine's host.
- **Auth callout.** The broker asks a service to check each new connection,
  for example against ABI's own module tokens, and gets the connection's
  rights back. This is the way to give each module only the subjects it
  declared. It is the next step, not this one.

## Consequences

- Something that reaches the broker without a password is refused: a coding
  workspace, a CI job, or a machine on the same network.
- Both users have every right. A module can still read and publish on any
  subject.
- Modules that receive `NATS_JWT_SECRET` can still sign a token for any
  identity, `api` and `engine` included. Per-module rights only help once
  modules receive tokens the engine issues instead of the secret.
- Traffic is not encrypted. That is acceptable on one host or over a VPN
  (WireGuard encrypts it). A module connecting across an untrusted network
  needs TLS on the broker first.
- An existing `.env` without the passwords stops the `nats` service. Running
  `abi deploy local --regenerate` adds them, and the engine's `nats_url` must
  name the `abi` user.
