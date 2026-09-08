# Nexus automatic session renewal

Status: Accepted

Date: 2026-09-08

## Context

Nexus persists access and refresh tokens in browser storage. Access tokens expire
in 30 minutes by default. The API rotates refresh tokens and grants each new
refresh token another 30 days. Previously, renewal only followed a failed API
request. Concurrent requests could rotate the same credential, temporary server
failures caused logout, and the middleware auth flag expired without renewal.

## Decision

Mount a session lifecycle manager at the web application root. Check every 30
seconds and on focus, visibility, pageshow, and network recovery. Renew within
60 seconds of access-token expiry; authenticated fetches also check before use.
Refresh requests time out after 15 seconds and may retry on the next lifecycle
check. These are frontend reliability defaults, independent of DDS policies.

Share pending refreshes within each store and use the browser Web Locks API to
serialize rotation across tabs. Read persisted credentials after obtaining the
lock, adopt other tabs' rotations/logout, and discard responses superseded by a
login or logout. Renew the middleware routing flag as sessions remain active.
Only definitive credential rejection clears a session; network, rate-limit,
and server failures preserve credentials for recovery.

## Consequences

Sessions can renew indefinitely while Nexus is running. Returning within the
existing 30-day refresh window restores the session without login. A browser
closed longer than that window, cleared storage, or a revoked credential still
requires login. Browsers without Web Locks only deduplicate within one tab.

This changes security-sensitive session behavior but does not extend backend
credential lifetimes or change token storage. The routing cookie is only a UI
hint; API token validation remains authoritative. No migration is required.
