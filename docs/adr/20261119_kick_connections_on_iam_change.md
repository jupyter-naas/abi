# Module connections end when IAM changes, not every two minutes

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

NATS fixes a connection's permissions when it logs in. The engine's auth
callout (`nats_auth_callout.py`) checks a module's service key, derives the
subjects its approved policy allows and answers with a user JWT. A connection
keeps those subjects until it logs in again.

So that a revoked key, a suspended account or a narrowed policy took effect,
the callout gave each connection five minutes (ten at most, "never longer than
an access token"), and the SDK reconnected every module every two minutes
(`force_reconnect()`, `RENEW_CONNECTION_SECONDS`).

Each of those reconnects drops the module's subscriptions until it is logged in
again, which takes up to the broker's 2 s callout timeout when the engine is
busy. A request sent to the module then finds no responder: Nexus answers 503
("The module instance stopped"). With a hundred modules, something is
reconnecting most of the time, and a sign-in through the built-in IdP module
failed about one time in three (#1538). The module's own sends in the window
fail too (`OutboundBufferLimitError`).

## Decision

A connection keeps its permissions until something changes, and the engine ends
the connections a change affects.

1. The callout records each admitted connection: broker server, client id,
   service account, key and the permissions it granted.
2. When the IAM store changes (a change made in this process, or the store's
   revision moving), the engine checks each recorded connection: is its key
   still usable, its account active, and its permissions what they were? A
   connection that fails the check is kicked (`$SYS.REQ.SERVER.<id>.KICK`):
   nats-py reconnects, and the callout grants the new subjects or refuses.
3. At start and every few minutes the engine lists the broker's connections
   (`CONNZ`). One it did not admit (admitted by a previous engine) is kicked so
   that it logs in again here; a recorded one that is gone is forgotten. A
   change missed while the engine was down is applied this way.
4. A module's user JWT lives until its key expires; without an expiry, until a
   kick. The SDK no longer reconnects on a timer: `RENEW_CONNECTION_SECONDS`
   and the transport's `renew_seconds` are removed, and so is
   `auth_callout.user_ttl_seconds` (ignored, with a warning, when a
   configuration still sets it). A timed renewal was the cause of the 503s, so
   no option keeps it.
5. The engine logs in to the broker's system account as a dedicated `sys` user
   (`nats.conf`: `accounts { SYS: { users: [sys] } }`, `system_account: SYS`,
   `sys` exempt from the callout), for KICK and CONNZ only.
   `NATS_SYSTEM_PASSWORD` is generated with the other broker passwords
   (`ensure_nats_passwords`). `auth_callout.system_url` is required.

## Consequences

- No module is unreachable on a timer: remote apps, the IdP among them, no
  longer answer 503 between renewals, and the broker sees no login storm.
- A revocation or a narrowed policy takes effect within the revision check and
  the kick (seconds), instead of within the next renewal (up to two minutes).
- "Never longer than an access token" no longer bounds a connection: the bound
  is the engine's check on every change and on every sweep. If the engine is
  down, a connection keeps its permissions until the engine's next sweep.
- An engine restart kicks every module connection once, at a bounded rate, so
  that it is known to the new engine.
- Every deployment's `nats.conf` gains the `SYS` account and the `sys` user,
  and every engine configuration `auth_callout.system_url`.
