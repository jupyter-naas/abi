---
sidebar_position: 3
title: "Deploy with Dokploy"
---

# Deploy with Dokploy

[Dokploy](https://dokploy.com) deploys Docker Compose apps from a Git
repository, with Traefik as its edge and Let's Encrypt certificates. `abi
deploy dokploy` renders a compose file built for it, so a project is deployed,
redeployed and managed from the Dokploy UI. Each extra environment (staging,
production, a client's stack) is another Dokploy compose app, on the same
server or another one, with different Environment values.

The stack follows the project's config: a project with a `nats:` block (the default)
runs on the `nats` service, with remote modules as extra services; a project without
one gets the [classic stack](/user-guide/get-started/legacy-mode). For one machine
without a domain, see [Deploy with Docker](/user-guide/deploy/local-docker); for the
other options, [Production and remote deployments](/user-guide/deploy/production).

What changes from `abi deploy local`:

| `abi deploy local` | `abi deploy dokploy` |
|---|---|
| `docker-compose.yml` | `docker-compose.dokploy.yml` |
| Caddy binds 80/443 and gets the certificates | Dokploy's Traefik routes by host through labels on `dokploy-network`, with Let's Encrypt |
| Services publish host ports (5432, 3030, 6379, ...) | No host port; everything else stays on the stack's internal network |
| `abi` mounts the source tree for hot reload | Dokploy builds `abi` from the project `Dockerfile` on each deploy |
| `.env` | `.env.dokploy`, pasted into Dokploy's Environment tab |
| `config.local.yaml` | `config.dokploy.yaml`, derived from `config.local.yaml` (`ENV=dokploy`) |
| yasgui, redis-commander, service-portal, graph-explorer | Not deployed |
| `--headscale` | Not supported yet |

## 1. Render the stack

From the project root (a project created with `abi new project`):

```bash
abi deploy dokploy --domain example.com            # Nexus + API
abi deploy dokploy --domain example.com --coding   # + Coder, Forgejo, Actions CI
```

With `--coding`, `--wildcard-cert-resolver <name>` also gets a certificate for
the workspace apps once the server has a DNS-challenge resolver (see
[The `*.coder` wildcard certificate](#the-coder-wildcard-certificate)).

It writes:

- `docker-compose.dokploy.yml`: the stack. NATS or classic follows the
  project's config, like `abi deploy local`.
- `config.dokploy.yaml`: a copy of `config.local.yaml` with Dokploy's secret
  adapters added to `services.secret.secret_adapters` (see
  [Secrets](#secrets)). Nothing else changes: the project's adapters,
  comments, line endings and Jinja (`{% if %}`, `{% include %}`) are copied
  line for line. Jinja tags inside the `secret_adapters` list itself are
  refused: put the condition around the whole `services.secret` section.
- `.deploy/docker/`: the Postgres init scripts, `nats.conf`, `dagster.yaml`
  and, with `--coding`, the coding bootstrap script. The compose mounts them
  from the repository.
- `.env.dokploy`: every variable the stack needs, with generated passwords and
  keys. The secrets the config reads that have no value yet, such as
  `OPENROUTER_API_KEY`, are listed commented out at the end. It is added to
  `.gitignore`; `.env` and `.env.*` are added to `.dockerignore`, so the
  Environment tab never ends up in the image.

Rerun the command after upgrading the CLI or editing `config.local.yaml`: the
compose file, `config.dokploy.yaml` and `.deploy/docker` are rewritten, and the
values in `.env.dokploy` are kept. `--domain` moves the hosts and keeps the
secrets. `--regenerate` generates new secrets, keeps the hosts, the other settings and
your own keys, and backs the old file up under `.abi-backups/deploy-dokploy/`. Do not regenerate a stack that already holds
data: Postgres, MinIO and Fuseki keep the passwords they were created with.

The hosts are `nexus.<domain>` for Nexus and `api.<domain>` for the API. To
use other names, change `PUBLIC_WEB_HOST`, `PUBLIC_API_HOST` and
`NEXUS_API_URL` in the Environment tab.

Commit and push `docker-compose.dokploy.yml`, `config.dokploy.yaml` and
`.deploy/`. Never commit `.env.dokploy`.

## 2. DNS

Point these records at the Dokploy server's public IP (A, or AAAA for IPv6):

| Record | Serves |
|---|---|
| `nexus.<domain>` | Nexus web, and `/app-html/*` from the API |
| `api.<domain>` | ABI API |
| `coder.nexus.<domain>` | Coder (`--coding`) |
| `*.coder.nexus.<domain>` | Coder workspace apps (`--coding`) |
| `git.nexus.<domain>` | Forgejo (`--coding`) |

Let's Encrypt validates each host over HTTP, so the records must resolve
before the first deploy. Set the Let's Encrypt email in Dokploy's web server
settings if it is not set yet.

## 3. Create the compose app

1. In Dokploy, open or create a project, then **Create Service → Compose**.
2. **Provider**: your Git provider (GitHub, GitLab, Gitea, Bitbucket) or a
   plain Git URL with a deploy key. Pick the repository and branch.
   - If the project resolves ABI from the `.abi` submodule
     (`use_local_abi_sources`), enable submodules.
3. **Compose type**: Docker Compose. **Compose path**:
   `./docker-compose.dokploy.yml`.
4. **Environment**: paste the content of `.env.dokploy`, then uncomment and
   fill in the keys it lists commented out at the end, such as
   `OPENROUTER_API_KEY`. A key left commented out starts empty and can be set
   later from the Nexus admin console (see [Secrets](#secrets)). Dokploy
   writes the tab to `.env` next to the compose file on every deploy.
5. Leave the **Domains** tab empty: routing is in the compose labels. Leave
   **Isolated Deployment** and **Randomize Compose** off, since the stack joins
   `dokploy-network` itself and its router names come from `ABI_STACK_NAME`.
6. **Deploy**.

The first deploy builds the image and starts the engine, which loads every
module and runs the Nexus migrations: allow a few minutes. Follow it in the
app's **Logs** for the `abi` service. Then open `https://nexus.<domain>` and
sign in as `admin@example.com` with `NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD`
from the Environment tab.

## The Environment tab

The Environment tab is the source of truth for a deployed stack. Each variable
in it:

- is interpolated into the compose file, and
- reaches the `abi` engine as an environment variable (`env_file: .env`), and
  wins over every secrets file (see [Secrets](#secrets)). Every
  `{{ secret.X }}` in the config can be set here. Add the keys of the modules
  you enable to this tab.

Variables specific to this stack:

| Variable | Purpose |
|---|---|
| `ABI_STACK_NAME` | Prefix of the Traefik router names, of the stack's DNS aliases (`<name>-abi`, ...) and name of the internal network (`<name>-abi-network`). Unique per stack on a server. |
| `PUBLIC_WEB_HOST`, `PUBLIC_API_HOST`, `NEXUS_API_URL` | Public hosts and the API URL the browser calls. |
| `TRAEFIK_CERT_RESOLVER` | Traefik certificate resolver; Dokploy's is `letsencrypt`. |
| `CODER_WILDCARD_CERT_RESOLVER` | DNS-challenge resolver of the `*.coder` certificate. Written by `--wildcard-cert-resolver`, absent until then, and kept by later runs. |

Changing a value takes effect on the next deploy.

## Secrets

The container's files are replaced on every deploy, so `config.dokploy.yaml`
adds two dotenv adapters on named volumes to the project's own:

- **The engine's secrets file**: `/var/lib/abi-secrets/.env` on the
  `abi_secrets` volume. Every secret the engine writes lands there and
  survives redeploys: passwords it generates for users in `users:` that have
  none, keys saved from the Nexus admin console. It takes the place of the
  project's `.env` dotenv, which stays right behind it and reads an empty
  file (`.env` is kept out of the image). It never goes ahead of the
  project's first adapter: with a `naas` or `nats_rpc` adapter first, that
  one still answers first.
- **With `--coding`, the coding tokens**, last: a read-only adapter on the
  `coding_secrets` volume (see [Coding workspaces](#coding-workspaces)).
  Writes skip it, so deleting `CODER_ADMIN_TOKEN` or `FORGEJO_ADMIN_TOKEN` in
  Nexus reports success but the token is still served from that file. Delete
  the volume to replace them.

On every start, the container adds the secrets the config reads that
`.env.dokploy` leaves commented out to the secrets file, empty, unless the
file has them. A first deploy therefore starts with those values empty, and
one saved from Nexus is kept.

A dotenv adapter on any file other than `.env` is refused: the image
Dokploy builds from git does not have it. Move its values to the Environment
tab.

**The Environment tab wins.** For a key set there, the engine sees the tab's
value when it renders `config.dokploy.yaml`, when code reads the secret
service, and in the Nexus admin console. A key set in the tab cannot be
changed from Nexus: an edit there lasts until the next restart. To manage a
key from Nexus, leave it out of the tab. The secrets file serves the keys the
tab does not set. This is why `.env.dokploy` comments out every key it has no
value for: an empty variable would still win over the file.

## Another environment

An environment is another compose app with its own Environment tab:

- **On another server.** Add the server in Dokploy (remote servers), then
  create the compose app as above and pick that server. Use the same repository
  and compose path, maybe another branch.
- **On the same server.** Create another compose app. Change at least
  `ABI_STACK_NAME` and the hosts: two stacks on one server cannot share router
  or network names.

The services Traefik reaches (`abi`, `nexus-web`, and with `--coding`
`coder` and `forgejo`) join `dokploy-network` under their service names, and
so do those of every other stack on the server. From one of these containers a
bare name such as `abi` can resolve to another stack. The stack's own calls
use aliases that exist only on its internal network:
`${ABI_STACK_NAME}-<service>`, that is `<ABI_STACK_NAME>-abi`, `-nexus-web`,
`-coder` and `-forgejo`. Internal URLs between these services must use these
aliases. Follow the same rule in `config.local.yaml`: when `abi` calls Coder or
Forgejo, use their public URLs or these aliases, never `http://coder:7080` or
`http://forgejo:3000`. The other
services (`postgres`, `nats`, `redis`, ...) are only on the internal network;
keep services of other Dokploy apps with those names off `dokploy-network`.

Generate a separate set of values for each environment. For example, run
`abi deploy dokploy --domain staging.example.com --regenerate` in a scratch
checkout, or copy `.env.dokploy` and replace each password.

## Redeploys and webhooks

- **Manual**: **Deploy** in the app rebuilds `abi` from the current commit and
  recreates what changed. Named volumes (Postgres, Fuseki, MinIO, NATS,
  Qdrant, Coder and Forgejo data, `abi_secrets`, the coding tokens) are kept.
- **On push**: with a GitHub provider, turn on **Autodeploy**. With another
  provider, copy the webhook URL from the app's deployments view into a
  push webhook of the repository.
- After editing `config.local.yaml`, rerun `abi deploy dokploy`, commit the
  new `config.dokploy.yaml`, and push.
- `NEXUS_WEB_TAG` pins the Nexus web image. Its default is `latest`, which is
  pulled on every deploy.

## Coding workspaces

With `--coding`, the stack adds Coder, Forgejo, the Forgejo Actions runner and
`coding-init`, a one-shot bootstrap that runs on every deploy.

- `coding-init` creates the Coder and Forgejo admins from the passwords in the
  Environment tab, mints their API tokens, and writes them to
  `/run/abi-secrets/coding.env` on the `coding_secrets` volume. It keeps a
  token that is already there.
- If a token is still missing at the end, `coding-init` exits with an error
  and the deploy fails, rather than start `abi` without it. Its logs say which
  step failed; a redeploy runs it again.
- `abi` waits for `coding-init`, mounts the volume read-only, and reads the
  file through a read-only dotenv secret adapter in `config.dokploy.yaml`, so
  `{{ secret.CODER_ADMIN_TOKEN }}` and `{{ secret.FORGEJO_ADMIN_TOKEN }}`
  resolve after every redeploy with nothing to paste. Do not add these two
  variables to the Environment tab: an environment variable, even empty, wins
  over the file.
- The internal network has the fixed name `<ABI_STACK_NAME>-abi-network`.
  Coder attaches workspaces to it (`CODING_WORKSPACE_DOCKER_NETWORK`), and the
  runner starts CI job containers on it. Only this stack's containers are on
  it, so they reach `forgejo:3000` by its service name.
- Coder's access URL is `https://coder.<web host>`: workspaces connect back
  through Traefik.

Coder, the runner and `coding-init` mount the Docker socket of the Dokploy
server: anyone with a Coder workspace can start containers on it. Use a
dedicated server for stacks with coding workspaces.

To mint new tokens, for example when one was revoked, delete the
`coding_secrets` volume (`<compose project>_coding_secrets`, in the server's
Docker volumes) and redeploy. `coding-init` logs in with the admin passwords
from the Environment tab and mints tokens under new names
(`nexus-admin-<time>` in Coder, `nexus-<time>` in Forgejo). The previous
tokens stay valid until they expire: revoke them in Coder and Forgejo.

### The `*.coder` wildcard certificate

Coder serves workspace apps on subdomains of `coder.<web host>`, such as
`8080--main--ws--admin.coder.nexus.example.com`. One certificate covers them
all only as a wildcard, `*.coder.nexus.example.com`, and Let's Encrypt issues
wildcards only through a DNS challenge. Dokploy's default `letsencrypt`
resolver uses an HTTP challenge, so `coder.` and `git.` get their certificates.
Without `--wildcard-cert-resolver`, the stack asks for no wildcard
certificate, which Let's Encrypt would refuse and count against the rate
limit, and workspace apps get Traefik's default certificate. To serve them
with a valid one:

1. In Dokploy's Traefik settings, edit the main Traefik configuration
   (`traefik.yml`) and add a resolver with your DNS provider. With Cloudflare:

   ```yaml
   certificatesResolvers:
     letsencrypt:
       # ... keep Dokploy's resolver as is
     letsencrypt-dns:
       acme:
         email: you@example.com
         storage: /etc/dokploy/traefik/dynamic/acme-dns.json
         dnsChallenge:
           provider: cloudflare
           resolvers:
             - "1.1.1.1:53"
   ```

   The provider names and their variables are listed in
   [Traefik's DNS providers](https://doc.traefik.io/traefik/https/acme/#providers).

2. Give the Traefik container the provider's credentials, for Cloudflare
   `CF_DNS_API_TOKEN` (a token with `Zone:DNS:Edit` on the zone), in
   Dokploy's Traefik environment settings, then reload Traefik.
3. Rerun the command with the resolver's name, commit and push the new
   compose file:

   ```bash
   abi deploy dokploy --coding --wildcard-cert-resolver letsencrypt-dns
   ```

4. Add `CODER_WILDCARD_CERT_RESOLVER=letsencrypt-dns`, now in
   `.env.dokploy`, to the app's Environment tab and redeploy.

The `coder-apps` router then asks that resolver for one certificate for
`coder.<web host>` and `*.coder.<web host>`. Later runs keep the resolver.

## Troubleshooting

- **The deploy fails with `ABI_STACK_NAME` or `NATS_..._PASSWORD` missing**:
  the Environment tab is empty or incomplete. Paste `.env.dokploy` again.
- **`network dokploy-network not found`**: the compose app is not running on a
  Dokploy server, or Dokploy's Traefik was removed.
- **404 from Traefik**: the DNS record does not point to this server, or two
  stacks share `ABI_STACK_NAME`.
- **Certificate errors on a fresh host**: the DNS record did not resolve when
  the router started. Fix the record and redeploy.
- **"Incorrect email or password"**: use
  `NEXUS_USER_ADMIN_EXAMPLE_COM_PASSWORD` from the Environment tab. If it was
  changed after the first boot, the account keeps the first value.
- **The engine stops with `Secret '...' not found`**: a key the config reads
  is missing from the Environment tab. Add it and redeploy.
- **The deploy fails on `coding-init`** (`--coding`): a Coder or Forgejo
  token could not be minted. Its logs name the step; the usual causes are
  Coder or Forgejo still starting (redeploy), or admin passwords changed in
  the Environment tab after the first deploy (set them back).
