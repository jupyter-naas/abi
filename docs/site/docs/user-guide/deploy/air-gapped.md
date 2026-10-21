---
sidebar_position: 8
---

# Air-Gapped Deployment

Run ABI on a network with no internet access, with local models and no call to an external service. This page lists what a default project reaches out for, and how to bring it all in beforehand.

:::info Professional Services Implementation
Air-gapped installations are customized to each environment and implemented with dedicated support. Contact our enterprise team at [support@naas.ai](mailto:support@naas.ai) to discuss your needs and implementation timeline.
:::

ABI has no component that must call home. The engine, the Nexus web app, the knowledge graph and the NATS broker all run on your hosts. What needs the internet in a default project is the *installation* (images, Python packages) and the *model provider* (OpenRouter). Both are replaced by what you carry in.

## What reaches the network by default

| What | When | Offline replacement |
|---|---|---|
| Model calls to OpenRouter | At every chat | Local models with Ollama (below). |
| Docker images | `docker compose up`, build | Load them from archives; do not pull. Most services of the generated file carry `pull_policy: always`. |
| The `abi` image build | `docker compose build` | Build it on a connected machine. Its `Dockerfile` runs `apt-get`, `pip install uv`, and downloads the AWS CLI and the OpenCode CLI. |
| Python packages | First start of the `abi` container | A package mirror, or a virtual environment you populated beforehand (below). |
| ABI framework source | `abi new project` clones `jupyter-naas/abi` into `.abi/`; a NATS project resolves `naas-abi-proto` and `naas-abi-sdk` from it | `--abi-source` with a local checkout. |
| Document models | First use of the document pipeline (Docling), cached in the `huggingface_cache` volume | Populate the volume beforehand. |
| Let's Encrypt | Caddy, for a public domain | Your own certificates (below). |
| `docker build` of the snapshot helper | First `abi stack snapshot create` | Build or load the image `abi-snapshot-helper:zstd1` beforehand (below). |

## Plan the environment

- **No internet at all, in or out.** Nothing in ABI needs it once the pieces above are in place.
- **Internal DNS** for the hosts you publish (`PUBLIC_WEB_HOST`, `PUBLIC_API_HOST`; the project's `--domain`).
- **Certificates** from an internal CA, for those hosts.
- **Time synchronization** between every host that runs an ABI process. Calls on the NATS broker carry short-lived signed tokens, so hosts whose clocks drift apart can have their calls refused. Use a local NTP server.
- **Container runtime**: Docker with Compose v2. ABI ships a Compose stack; it does not ship Kubernetes manifests. If you run on Kubernetes, translate the stack's services yourself; [Production and remote deployments](/user-guide/deploy/production) lists what to run and what to size.
- **Compute** for the models. A GPU is optional: the default local pair (`qwen2.5:3b` and `nomic-embed-text`) is small.

## Local models

`global_config.ai_mode` takes `cloud`, `local` or `airgap`. It is a value that modules read, not a switch that blocks the network: what keeps your data on the machine is which model modules are enabled, and which models the registry defaults point at.

1. **Install [Ollama](https://ollama.com) on a connected machine** and pull the models you need:

   ```bash
   ollama pull qwen2.5:3b
   ollama pull nomic-embed-text
   ```

   The default local pair is the one `make ollama-models` pulls. `naas_abi_marketplace.ai.gemma` (`gemma3:4b`), `ai.qwen` (`qwen3:8b`) and `ai.deepseek` (DeepSeek R1 8B) are Ollama models too: pull the ones you enable.

2. **Move the models.** Copy Ollama's model directory (set by `OLLAMA_MODELS`; check with the Ollama docs for your platform) to the isolated host, next to the same Ollama version. Models are large: plan the transfer media.

3. **Install the extra and enable the module**, in the project's config (see [AI mode](/user-guide/get-started/quickstart#ai-mode-cloud-vs-local)):

   ```bash
   uv add "naas-abi-marketplace[ai-ollama]"
   ```

   ```yaml
   global_config:
     ai_mode: "airgap"        # or "local"

   modules:
     - module: naas_abi_marketplace.ai.ollama
       enabled: true
       config:
         base_url: "http://host.docker.internal:11434"   # where the engine reaches Ollama

   services:
     model_registry:
       default_chat_model: "qwen-2.5-3b"
       default_embedding_model: "nomic-embed-text"
   ```

4. **Turn off every cloud provider module**: in a generated project, set `enabled: false` (or remove) `naas_abi_marketplace.ai.openrouter`, and any other provider you enabled. The registry defaults are checked after the modules load, so the engine stops at start if a default names a model nothing serves.

The module's `base_url` can also come from `ABI_OLLAMA_BASE_URL` or `OLLAMA_HOST`, and `probe_on_load: false` skips the check at start. In the Docker stack the engine reaches Ollama on the host as `host.docker.internal`; on Linux, Ollama listens on `127.0.0.1` unless you change `OLLAMA_HOST` (see the comments in the generated `docker-compose.yml` for the trade-off). You can also point `base_url` at a dedicated Ollama server on your network.

## Prepare the offline bundle

On a connected machine.

### 1. The project and the framework

Create or update the project, with the framework in `.abi/`:

```bash
abi new project my_project
```

For an isolated environment, bring a checkout of the ABI repository for the version you run, and create the project from it with `abi new project my_project --abi-source /path/to/abi`. Then archive the whole project folder, `.abi/` included, with `git bundle` or `tar`.

### 2. The images

```bash
cd my_project
docker compose build                              # the abi and mcp-server images
docker compose pull                               # every other image
docker compose config --images                    # the list, as Compose resolves it
docker compose config --images | sort -u | xargs docker save -o abi-images.tar
docker save -o abi-helpers.tar alpine:3.20 abi-snapshot-helper:zstd1   # optional, see Backups
```

Run `docker compose config --images` with the same profiles you will run. The list includes the Nexus web image (`NEXUS_WEB_IMAGE`, `NEXUS_WEB_TAG` in `.env`), NATS, PostgreSQL, Fuseki, Qdrant, Redis, MinIO and Caddy. If a remote module has its own service, build its image too.

### 3. The Python environment

The `abi` container runs `uv run --no-dev python -m naas_abi_core.apps.api.api`, which creates the project's virtual environment in the `venv_cache` volume at its first start from `pyproject.toml` and `uv.lock`. Two ways to make that offline:

- **A mirror.** Run an internal package index (a PyPI mirror, or a folder served as a find-links index) and point `uv` at it: set `UV_DEFAULT_INDEX` in the `abi` service's `environment:` in `docker-compose.override.yml`. Fill the mirror from the `uv.lock` of your project.
- **A populated volume.** Start the stack once on the connected machine, so `venv_cache` holds the environment, and carry the volume (and `huggingface_cache`) to the isolated host with your usual Docker volume tooling.

### 4. Checksums and transfer

```bash
sha256sum abi-images.tar abi-helpers.tar my_project.tar > checksums.txt
tar czf abi-offline.tar.gz abi-images.tar abi-helpers.tar my_project.tar checksums.txt ollama-models/
gpg --symmetric --cipher-algo AES256 abi-offline.tar.gz
```

Move the archive on your approved media, then verify the checksums on the other side:

```bash
gpg --decrypt abi-offline.tar.gz.gpg | tar xz
sha256sum -c checksums.txt
```

## Install on the isolated network

```bash
docker load -i abi-images.tar
docker load -i abi-helpers.tar
tar xf my_project.tar && cd my_project
```

Then:

1. **Stop Compose from pulling.** Most services of the generated `docker-compose.yml` have `pull_policy: always`, which fails with no registry. Set `never` for each one in `docker-compose.override.yml` (the CLI never rewrites that file; `docker compose config --services` lists the names):

   ```yaml
   services:
     nexus-web:
       pull_policy: never
     nats:
       pull_policy: never
     # ... one entry per service of the stack
   ```

2. **Point the `abi` service at your package index**, if you use a mirror (see above).
3. **Set the model configuration** as described above.
4. **Certificates.** The generated `.deploy/docker/Caddyfile` serves `PUBLIC_WEB_HOST` and `PUBLIC_API_HOST`. For a public-looking domain Caddy tries to obtain a certificate from Let's Encrypt, which fails offline: give Caddy your own certificate and key with a `tls <cert> <key>` line in each site block (mount the files into the `caddy` service), or use Caddy's internal CA and distribute its root to your clients. Edits to files under `.deploy/` are overwritten by `abi deploy local --regenerate`; make them again, or keep a patched copy.
5. **Start**:

   ```bash
   abi stack start
   ```

   `abi stack start` generates the broker's passwords and signing secret into `.env` on first run. See [Deploy with Docker](/user-guide/deploy/local-docker).

6. **Check it**: `abi stack status`, then Nexus at your `PUBLIC_WEB_HOST`, then a chat against the local model. The broker's monitoring endpoint answers `http://127.0.0.1:8222/healthz`.

Without Docker, `abi dev up` runs the engine natively (with `nats-server` 2.14 or later on `PATH` and a Python environment you prepared with `uv sync`); it is for development, not for an operated installation.

## Network and data isolation

- **The broker stays private.** The generated stack publishes NATS (4222) and its monitoring port (8222) on `127.0.0.1` only. Remote modules on other hosts need a private route to the broker, and the broker does not encrypt traffic: see [Security model](/developer-guide/architecture/security).
- **Expose Caddy only**, on ports 80 and 443, and keep PostgreSQL, Fuseki, Qdrant, Redis and MinIO on the internal Docker network, behind your firewall. The generated file publishes some of them on host ports for development: remove or restrict those ports on a server.
- **Encrypt data at rest at the volume or disk level** (LUKS, or your storage platform): ABI does not encrypt the stores itself. Object storage can be S3 with server-side encryption if you replace MinIO.
- **Keep the NATS passwords, `NATS_AUTH_CALLOUT_SEED` and `ABI_API_KEY` out of images and repositories.** See [Add secrets to production](/user-guide/deploy/add_secrets_to_production).

## Monitoring

Everything ABI needs to be observed is inside the deployment:

- the Nexus **System** app (super admins): services, modules, jobs, agents, the broker, live traffic and traces ([Observability](/developer-guide/architecture/observability));
- `docker compose logs -f abi`, and the logs of each service;
- OpenTelemetry traces to a Jaeger you run on the isolated network, with the `telemetry:` block described in [Observability](/developer-guide/architecture/observability#with-docker-compose). Its image is one more image to bring in;
- the broker's `/healthz`, `/connz` and `/jsz`.

Ship the container logs to the log platform you already run in the isolated network.

## Updates

1. On the connected side, update the project (`git submodule update --remote .abi` for the framework, `uv lock` for packages), rebuild the `abi` image, and produce a new bundle with new checksums.
2. Carry it across, verify the checksums and load the images.
3. Read the [release notes](/user-guide/release-notes) and, for a major version, the [upgrade guide](/user-guide/upgrade/migrate-to-3).
4. Take a snapshot (below), then redeploy. To avoid downtime on shared backends, set `ABI_ROLLOUT_ID` per deploy: see [one serving engine](/developer-guide/architecture/nats#one-serving-engine).

## Backups

`abi stack snapshot` archives the stack's data while it is briefly stopped: the PostgreSQL, MinIO, Fuseki, Qdrant, Redis and NATS volumes, and the project's `storage/` folder.

```bash
abi stack snapshot create --note "before update"
abi stack snapshot list
abi stack snapshot export <id> /secure-media/snapshot.tar
abi stack snapshot restore <id>
```

Snapshots live in `.snapshots/` of the project. `export` makes one archive you can move to another host, and `import` reads it there. Archives are compressed inside a helper container: `abi-snapshot-helper:zstd1`, built from `alpine:3.20` with `apk add zstd` the first time. Build or load it before you go offline, as in the bundle above, or the first snapshot fails.

Snapshots are cold copies. A restore is destructive, and it takes a safety snapshot of the current state first. For the knowledge graph alone, the project also has `.deploy/docker/fuseki/backup.sh`, which dumps the Fuseki dataset (and can compact it) through Fuseki's admin API. Encrypt the archives before they leave the host (`gpg --symmetric`), and test a restore on a spare host.

## Troubleshooting

**The `abi` container hangs or exits at first start.** It is resolving Python packages with no reachable index. Check its logs; configure the mirror or the populated volume.

**`pull access denied` or `connection refused` on `up`.** A service still has `pull_policy: always`, or an image is missing: `docker image ls`, then `docker load` it.

**No model responds.** Check Ollama on its host (`ollama list`, `curl http://<host>:11434/api/tags`), the module's `base_url`, and that the registry defaults name models that module serves.

**Nexus loads but chat fails with the broker down.** Kernel calls need the broker; see [NATS and the kernel services](/developer-guide/architecture/nats). `docker compose logs nats`, and `curl http://127.0.0.1:8222/healthz`.

**Calls fail between hosts with token errors.** Check that the clocks agree.
