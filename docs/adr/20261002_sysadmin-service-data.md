# Super admins manage kernel service data from the System app

## Status

Accepted

## Date

2026-10-02

## Context

The Nexus System app shows kernel services, modules and the NATS network, read-only. Operators also need to look at and fix what the services hold: an object left by a failed upload, a secret to rotate, a stuck cache entry, a stale module instance. Until now that meant a shell on the host or a database client, with no record of who changed what.

Several services could not enumerate or administer what they hold through their public API:

- key-value and cache had no key listing;
- the document service was scoped to one module's namespace;
- vector stores could not page through documents;
- events could only be filtered with a Python class;
- the activity log had no paging;
- email kept nothing;
- discovery could not evict an instance;
- source control could not delete a repository;
- coding environments could only be listed per user.

## Decision

- **One generic port.** `ServiceResources` represents a service's data as a tree of entries: containers hold entries, items hold a value. It offers list (paged), stat, read (bounded preview), download, write and delete. Each adapter declares its capabilities (including the expected write format) and what each entry allows. It passes either `ServiceResourcesContract` (writable data) or `ReadOnlyResourcesContract` (logs and registries) on a real backend. The web renders exactly the actions an entry carries. A container that cannot list says so (`listable: false`), and its entries open by id.
- **Every kernel service gets an adapter**: activity_log, bus (JetStream), cache, coding_environment, dataset, discovery, document, email, event, keyvalue, model_registry, object_storage, secret, source_control, triple_store and vector_store.
  - Logs and registries are read-only. That covers the event log (append-only), the activity log (an audit trail) and the model registry (per process).
  - `KV_` JetStream streams cannot be edited message by message.
- **Core is extended where a service fell short.** The extensions are additive: new port methods implemented by every adapter, the NATS client and the NATS primary, and new protobuf request/response pairs.
  - keyvalue: `list_keys`, `get_ttl`.
  - cache: `list_keys`, `get_entry`, which never deserializes.
  - document: `namespaces`, a public `for_namespace`, and `ServicesProxy.document_admin` for the unlocked platform proxy only.
  - vector_store: `list_vectors`, `get_collection_info`.
  - event: `list_event_types`, `query_stored`, `get_stored`.
  - activity_log: sequence paging.
  - email: kept sent mail (`list_sent`, `get_sent`, `delete_sent`).
  - source_control: `delete_repo`.
  - coding_environment: `list_all_environments`.
  - discovery: `evict`.
- **Platform operations are authorized explicitly.** Only the unlocked proxy (the `naas_abi` platform module) can open other modules' document namespaces. Over NATS, document namespace listing and discovery eviction accept only the `api` and `engine` identities. Like the rest of Stage 1 NATS auth, this separates first-party processes; it does not protect against a holder of the shared secret.
- **Audit before change, fail closed.** Create, replace, delete and reveal write an `audit_logs` row (`sysadmin.<operation>`, phase `requested`) before the call, and nothing changes if that row cannot be written (503). A `succeeded` or `failed` row follows, recording only the exception type.
- **Typed confirmation.** Replacing or deleting needs the resource id typed back, enforced by both the API (409) and the UI.
- **Secrets stay masked.** Listing and reading never return a secret's value or size. Revealing one is a separate, audited `POST` with `Cache-Control: no-store`.
- **No values in the HTTP activity log.** Its body capture skips `/api/admin/system/resources/`.

## Consequences

- Platform super admins can inspect and change the data of every kernel service with an audit trail. They can read any stored value and reveal any secret. That is deliberate for this role, and every reveal is on record.
- Custom adapters of the extended ports must implement the new methods. The engine checks ports at boot, so a third-party document adapter without `namespaces` fails to load until updated. Adapters that cannot support an operation raise `NotImplementedError`, which the System app shows as unsupported.
- Writing a secret updates every configured secret adapter, including `.env` and the API process environment. Writing a source-control file makes a commit. Sending email from the Data tab really sends it.
- Size limits apply: 25 MB uploads, 100 MB downloads and 64 KB previews.
- Listing keys in cache and Redis key-value scans the prefix on each page, which is acceptable for an admin view but not for hot paths.
- The SDK's generated clients gain the new operations (`make generate`). A namespace-bound SDK document client refuses platform-wide requests.
