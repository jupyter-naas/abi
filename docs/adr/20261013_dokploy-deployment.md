# Deploy a project with Dokploy

Status: Accepted

Date: 2026-10-13

## Context

A project is deployed today with `abi deploy local`: a Docker Compose stack
with Caddy as its edge, run by hand on a server. Every redeploy, every new
environment and every change of value is a shell session on that server.

Dokploy deploys Compose apps from a Git repository and manages their
environment, redeploys and webhooks from a UI. The local stack does not run
on it:

- Dokploy runs Traefik on 80/443 and issues the certificates. Caddy cannot
  bind those ports.
- The local stack publishes many host ports, which collide between stacks on
  one server and expose internal services.
- `abi` mounts the source tree for hot reload; Dokploy deploys a checkout, and
  the local Dockerfile carries no code.
- Dokploy rewrites the compose `.env` from its Environment tab on every
  deploy. `coding-init` writes the minted Coder and Forgejo admin tokens to
  the host `.env`, where `abi` reads them: on Dokploy they would be lost.
- Dokploy names the compose project after the app, so the derived network
  name `<dir>_abi-network`, which Coder workspaces and CI jobs join, does not
  match.

## Decision

- `abi deploy dokploy [--domain D] [--coding] [--regenerate]` renders
  `docker-compose.dokploy.yml` from its own template, with the same `NATS` and
  `INCLUDE_CODING` switches as the local one. The `.deploy/docker` files it
  mounts come from the local and coding templates.
- **Traefik labels instead of Caddy.** The stack has no edge service and no
  host port. Services that are served publicly join the external
  `dokploy-network` and carry Traefik labels: the web host to nexus-web,
  `/app-html/` on the web host to abi at a higher priority, the API host to
  abi, and with `--coding` `coder.`, `*.coder.` and `git.` to Coder and
  Forgejo. Certificates come from Dokploy's `letsencrypt` resolver. The
  `*.coder` wildcard has its own resolver variable, since a wildcard needs a
  DNS challenge that a server must set up.
- **Dokploy builds the image.** `abi` (and mcp-server and Dagster) build from
  the project `Dockerfile` on each deploy, with no source mount and no venv
  volume. `.env` and `.env.*` go to `.dockerignore`, so the Environment tab is
  not baked into the image.
- **The Environment tab is the source of truth.** It is interpolated into the
  compose file and passed to `abi` whole through `env_file`. Environment
  variables already win over dotenv files when the config resolves
  `{{ secret.X }}`. The command writes a starting set to the gitignored
  `.env.dokploy`, with the same generators as `abi deploy local`; reruns keep
  its values and `--regenerate` replaces them.
- **`config.dokploy.yaml`.** The stack sets `ENV=dokploy`. The command derives
  the file from `config.local.yaml` on every run, so the two do not drift.
- **The coding-secrets volume.** `coding-init` writes the tokens to
  `CODING_SECRETS_FILE`, a dotenv file on the `coding_secrets` named volume.
  `abi` waits for it, mounts the volume read-only, and `config.dokploy.yaml`
  adds the file as a second dotenv secret adapter. Tokens survive every
  redeploy, and nothing is pasted by hand. The tokens are left out of
  `.env.dokploy`: an empty environment variable would shadow the file.
- **A fixed network name.** The internal network is named
  `${ABI_STACK_NAME}-abi-network`. Coder workspaces, the act-runner config
  (inlined as a Compose `configs:` entry, so it reads the same variable) and
  `coding-init`'s container lookup use it. `ABI_STACK_NAME` also prefixes the
  Traefik router names, which are global on a Dokploy server.
- **Not deployed:** yasgui, redis-commander, service-portal and graph-explorer.
- **Headscale is deferred.** `--headscale` is refused: Headscale needs its own
  ports and DERP setup, which Traefik's HTTP routing does not cover.
- **`abi deploy local` keeps writing the tokens to the host `.env`.** Moving
  it to the volume also means adding the second adapter to every existing
  `config.local.yaml`, which is not a trivial change. The bootstrap script
  defaults to `/host/.env` when `CODING_SECRETS_FILE` is not set, so the
  local stack works as before.

## Consequences

- A project is deployed, redeployed and given more environments from the
  Dokploy UI. An environment differs from another only in its Environment
  values.
- Each deploy rebuilds the image on the server. There is no registry image
  and no image pipeline; build time and server resources grow with the
  project.
- Workspace apps on `*.coder` need a DNS-challenge resolver on the Dokploy
  server; until then they get Traefik's default certificate.
- The Dokploy stack has no hot reload and no admin UIs on host ports.
  Internal services are reached through the Dokploy terminal or a tunnel.
- `config.dokploy.yaml` is generated: edits go to `config.local.yaml`,
  followed by a rerun of the command.
- Coder, the runner and `coding-init` mount the server's Docker socket, as in
  the local stack. Stacks with coding workspaces want a dedicated server.
