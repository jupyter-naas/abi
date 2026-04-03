# Troubleshooting

## `Configuration file not found`

Cause: no `config.yaml` and no `config.<ENV>.yaml`.

Fix: create `config.yaml` in project root, or set `ENV` and provide `config.<ENV>.yaml`.

## Dotenv secret adapter fails at startup

Cause: configured dotenv path does not exist.

Fix: create the file (for example `.env`) or update `services.secret.secret_adapters[].config.path`.

## Missing secret during startup in CI/non-interactive runtime

Cause: templated secret was unresolved and no TTY prompt is available.

Fix: provide secret through environment variable or your configured secret backend.

## Triple store events not working

Cause: triple store requires bus service wiring to publish/consume events.

Fix: ensure modules requiring triple store also trigger bus loading (handled automatically for triple store dependency, but verify service config is valid).

## API auth always returns 401

Cause: bearer token does not match `ABI_API_KEY`.

Fix: export `ABI_API_KEY` and pass the same value in `Authorization` header or `?token=` query param.

## PostgreSQL checkpointer fails with hostname errors

Cause: wrong `POSTGRES_URL` host, often Docker hostname used outside Docker network.

Fix: use `localhost` for local runtime (for example `postgresql://...@localhost:5432/...`).

## `qdrant-client` / `redis` / `pika` import errors

Cause: optional dependencies not installed.

Fix: install package extras:

- `naas-abi-core[qdrant]`
- `naas-abi-core[redis]`
- `naas-abi-core[rabbitmq]`
