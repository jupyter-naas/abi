# Standalone package

Keep this package independent of naas-abi-core, naas-abi, and marketplace.
Transport DTOs are protobuf messages. Do not introduce engine domain objects.
Generated artifacts are checked in; regenerate with `make generate` in the proto package.
Use UV. `make deps`, `make test`, `make lint`, and `make build` are the local gates.
Tests live under tests/. Update the standalone module demonstration when adding endpoints.

## Identity on the wire

The engine's authorization model (principals, policies, evaluation, tokens) is core's
`services/iam/AGENTS.md`; the SDK's side of credentials is `libs/naas-abi-sdk/AGENTS.md`,
"Identity, credentials and permissions". This is what the protos carry.

- **Who calls is never a message field.** The caller is read from the `Nats-Auth-Token`
  header (an engine-signed JWT, verified against the JWKS) into the engine's
  `CallContext` variable. The user a caller acts for is the `sub` of an
  `abi:delegated:agent` token whose `act` is the caller; the `Abi-On-Behalf-Of`
  header is gone and a request carrying it is refused (`on-behalf-of refused`).
- **`common.v1.CallContext`** is request data: `trace_id`, `timeout_ms` and
  `container` (6: the container the call is made in, a container's name `abi:...`;
  an input IAM checks against its registry). `principal_id` (3) and `tenant_id` (5)
  are reserved and deprecated: servers ignore them and clients leave them empty. Do
  not reuse them for anything. `workspace_id` (4) is what SDK 0.2 sends: kept so an
  engine can refuse a call that sets it (`INVALID_ARGUMENT`); clients leave it empty.
- **Other fields that look like identity are not.** `HttpRequest.user_id` and
  `principal_*` (app) are replaced by the app host from verified credentials;
  `user_id` in `source_control` and `coding_environment` requests is ignored, and so
  is any `X-User-*` header: the service derives the user from the call's context.
  `discovery.v1` reserves `caller_on_behalf_of` for the same reason.
- **`agent.v1.SubmitRequest.delegated_token`** hands a run its delegation (an
  `abi:delegated:agent` token naming the module and the user); the host keeps it only
  if it names the run's owner, uses it for the run's kernel calls and never stores it.
- **Subjects.** Data and runtime services: `abi.svc.<service>.v1.<operation>`, plus a
  `transfer.*` family for streamed operations. IAM: `abi.iam.v1.*`, identity:
  `abi.identity.v1.*` (the generator rewrites their prefix), discovery:
  `abi.discovery.<project>.v1.*`. A catalog action in IAM maps to the operations
  (subjects) that perform it, which is also what the broker grants a module.
- **IAM messages** (`iam.v1`): `TokenRequest` exchanges a service key for an `abi:nats`
  token or an `abi:host:<sa>` token (`audience`, at most 600 seconds);
  `ExchangeTokenRequest` is the token exchange of RFC 8693 (delegated audiences, keys, links);
  `SubmitManifestRequest` / `Manifest` carry a module's permission manifest
  (`status`: pending, approved, rejected, superseded); `Key` carries `kind`, `audience`,
  `resource` and `scope_json` for personal keys and link grants. Resource names,
  scopes and owners are container paths (core `services/iam/AGENTS.md`, "Resource
  names"): `Placement.container`, `Container` (a registered container:
  `RegisterContainerRequest`, `DeleteContainerRequest`, `GetContainerRequest`),
  `AuthorizeDeclaredRequest.container`; the `org`/`workspace` fields of the earlier
  grammar are reserved, and `Scope`, `PutScope*` and `DeleteScope*` are gone.
  `ResourceType.id_prefix` (4) is the field once named `container`;
  `ResourceType.container` (9) marks a container type, `platform_companions` (10)
  and `ActionSpec.deletes` (8) go with it.
- **Errors.** `CallError.code` is the stable code a client matches on, and a denial is
  `PERMISSION_DENIED` (or the service's own not-found where a resource must not be
  revealed). Never put a backend's exception text in `message`.
- **Compatibility.** Never change a field number or name; reserve what is removed.
  Comment changes do not alter the descriptor, so the generated `*_pb2` files stay as
  they are.
