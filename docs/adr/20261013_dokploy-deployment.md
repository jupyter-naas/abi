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
- The container's files are replaced on every deploy, so what the engine
  writes to its `.env` at runtime (generated user passwords, keys saved from
  Nexus) would be lost.
- Every stack on a Dokploy server shares `dokploy-network`, and Compose adds
  each service's name on every network it joins. A container on both networks
  can resolve `abi` to another stack's container.

## Decision

- `abi deploy dokploy [--domain D] [--coding] [--regenerate]
  [--wildcard-cert-resolver R]` renders
  `docker-compose.dokploy.yml` from its own template, with the same `NATS` and
  `INCLUDE_CODING` switches as the local one. The `.deploy/docker` files it
  mounts come from the local and coding templates.
- **Traefik labels instead of Caddy.** The stack has no edge service and no
  host port. Services that are served publicly join the external
  `dokploy-network` and carry Traefik labels: the web host to nexus-web,
  `/app-html/` on the web host to abi at a higher priority, the API host to
  abi, and with `--coding` `coder.`, `*.coder.` and `git.` to Coder and
  Forgejo. Certificates come from Dokploy's `letsencrypt` resolver.
- **The `*.coder` wildcard certificate is opt-in.** Let's Encrypt issues a
  wildcard only through a DNS challenge, which the server must set up. The
  compose asks for one only when rendered with `--wildcard-cert-resolver`;
  otherwise the workspace-app router serves Traefik's default certificate
  rather than make a request Let's Encrypt refuses and counts toward its rate
  limit. The choice is kept in `.env.dokploy` across reruns.
- **Stack-unique aliases for internal calls.** The services Traefik reaches
  join `dokploy-network`; their names there are shared by every stack. Each of
  them also gets the alias `${ABI_STACK_NAME}-<service>` on the stack's own
  network, and every call between them (nexus-web to abi, the runner to
  Forgejo, mcp-server to abi) uses the alias. Services that are not routed
  stay off `dokploy-network`, so their bare names resolve only inside the
  stack.
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
  the file from `config.local.yaml` on every run, so the two do not drift. It
  only inserts lines: a dotenv adapter at the head of
  `services.secret.secret_adapters` (found by indentation, not by the first
  key of that name) and, with coding, one at its end. The project's adapter
  lines, comments, quoting and Jinja are copied unchanged. The list is read
  with the engine's own renderer (`render_without_secrets`, which resolves
  `{% if %}` and `{% include %}`) before and after, and the command refuses a
  result that does not read back as the project's list plus the two adapters.
- **The abi_secrets volume.** The added head adapter reads
  `/var/lib/abi-secrets/.env` on the `abi_secrets` named volume, so secrets
  the engine writes at runtime survive redeploys. The project's own `.env`
  dotenv stays behind it and reads an empty file. A dotenv on `.env.*`
  (excluded from the image) or on a file missing from the project is refused,
  since the engine would stop at boot on it.
- **The Environment tab wins over every secrets file.** Config rendering
  already reads the environment first. The dotenv adapter takes
  `environment_first: true`, set on the head adapter, so runtime reads agree:
  environment, then the secrets file, then the project's adapters.
  `.env.dokploy` comments out the keys it has no value for, since an empty
  variable would hide a value in the file. A key saved from Nexus that is also
  in the Environment tab is replaced by the tab's value on the next deploy.
- **The coding-secrets volume.** `coding-init` writes the tokens to
  `CODING_SECRETS_FILE`, a dotenv file on the `coding_secrets` named volume.
  `abi` waits for it, mounts the volume read-only, and `config.dokploy.yaml`
  appends the file as a dotenv secret adapter. Tokens survive every
  redeploy, and nothing is pasted by hand. The tokens are left out of
  `.env.dokploy`: an empty environment variable would shadow the file.
- **Read-only dotenv adapters.** The secret service writes to every adapter
  and fails on the first error, so a dotenv on a read-only mount broke every
  secret write. The dotenv adapter takes `read_only: true`: it serves reads,
  and `set` / `remove` skip it, logging a warning when the key is in the
  file. The coding adapter uses it.
- **`coding-init` on Dokploy fails loudly.** The bootstrap mints tokens under
  names that carry the time, so a mint after the volume was lost does not
  collide with an existing token. With `CODING_INIT_STRICT=1`, set by the
  Dokploy compose, it exits 1 when a token is still missing, which fails the
  deploy instead of starting `abi` without it.
- **Aliases rather than Dokploy's isolated deployments.** Isolated
  deployments connect Traefik to each app's own network and would remove the
  shared names altogether, but the compose would then depend on a Dokploy
  setting the repository does not carry, and on how Dokploy rewrites the
  compose's networks, while Coder workspaces and CI jobs join a network by a
  name the stack sets. The aliases keep the stack self-contained; the guide
  states that internal URLs must use them.
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
  local stack works as before. It shares the time-stamped token names and
  stays non-strict: a missing token is a warning there.

## Consequences

- A project is deployed, redeployed and given more environments from the
  Dokploy UI. An environment differs from another only in its Environment
  values.
- Each deploy rebuilds the image on the server. There is no registry image
  and no image pipeline; build time and server resources grow with the
  project.
- Workspace apps on `*.coder` need a DNS-challenge resolver on the Dokploy
  server and a rerun with `--wildcard-cert-resolver`; until then they get
  Traefik's default certificate.
- A key is managed either in the Environment tab or from Nexus, not both:
  the tab's value replaces a Nexus save on the next deploy.
- Deleting a coding token in Nexus does not remove it: it is still served
  from the read-only file until the `coding_secrets` volume is deleted.
- A secret the config reads that is in neither the Environment tab nor the
  secrets file stops the engine at boot, where an empty value used to let it
  start.
- A project config that calls Coder or Forgejo from `abi` must use their
  public URLs or the stack aliases, not the bare service names. Another
  Dokploy app that puts a service named like an internal one (`postgres`,
  `redis`, ...) on `dokploy-network` could still shadow it for `abi`.
- A Coder or Forgejo failure during `coding-init` keeps the whole Dokploy
  stack from deploying until a redeploy succeeds.
- The Dokploy stack has no hot reload and no admin UIs on host ports.
  Internal services are reached through the Dokploy terminal or a tunnel.
- `config.dokploy.yaml` is generated: edits go to `config.local.yaml`,
  followed by a rerun of the command.
- Coder, the runner and `coding-init` mount the server's Docker socket, as in
  the local stack. Stacks with coding workspaces want a dedicated server.
