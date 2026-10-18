---
sidebar_position: 9
---

# Add secrets to production

ABI reads its secrets through the **secret service**. A config file refers to one as `{{ secret.NAME }}`, and the service looks it up in its adapters, in order: by default the project's `.env` file (the `dotenv` adapter), and optionally the Naas secret store. Where `NAME` comes from in production depends on how you deploy.

| Deployment | Where a new secret goes |
|---|---|
| Docker Compose (`abi deploy local`) | `.env`, next to `docker-compose.yml`. |
| Dokploy (`abi deploy dokploy`) | The Environment tab of the Dokploy application, filled from `.env.dokploy` (generated and gitignored). |
| Naas space, from this repository's GitHub Actions | A repository secret, passed to the space by `deploy_api.yml`. |
| Naas space, from the CLI (`abi deploy naas`) | The `deploy.env` block of the config. |

Never commit a secret. `.env` is gitignored in a generated project.

## A secret used in the config

1. Put the value where your deployment reads it (the table above).
2. Refer to it in the config file:

   ```yaml
   modules:
     - module: naas_abi_marketplace.ai.openrouter
       enabled: true
       config:
         openrouter_api_key: "{{ secret.OPENROUTER_API_KEY }}"
   ```

3. Restart the engine. The config is rendered through Jinja at start, and a `{{ secret.X }}` that nothing defines stops the engine: with a terminal it prompts for the value, without one (a container, CI) it fails.

A full-line YAML comment is not rendered, so an example reference in a comment is safe.

## On a Docker Compose deployment

Add `NAME=value` to `.env`, then recreate the services that use it:

```bash
docker compose up -d --force-recreate
```

`abi deploy local --regenerate` re-renders the deployment files and keeps `.env`. The broker's passwords and signing secret (`NATS_ABI_PASSWORD`, `NATS_MODULE_PASSWORD`, `NATS_JWT_SECRET`) are generated into `.env` for you; do not copy them from another environment. See [Deploy with Docker](/user-guide/deploy/local-docker).

## On Dokploy

On Dokploy, the **Environment** tab is the source of truth: add the variable there and deploy again. A value in the tab wins over the engine's secrets file. `.env.dokploy` holds the starting values you paste into the tab; `abi deploy dokploy` keeps the ones already in it on later runs, and `--regenerate` generates new secrets and backs up the previous file, so use that flag only when you mean to rotate them. See [Deploy with Dokploy](/user-guide/deploy/dokploy#secrets).

## On a Naas space, with `abi deploy naas`

`abi deploy naas` builds the project's image, pushes it to a Naas registry and creates or updates the space named in the `deploy` block of the config. The space gets the variables listed under `deploy.env`:

```yaml
deploy:
  workspace_id: "<your workspace id>"
  space_name: "my-space"
  naas_api_key: "{{ secret.NAAS_API_KEY }}"
  env:
    NAAS_API_KEY: "{{ secret.NAAS_API_KEY }}"
    OPENROUTER_API_KEY: "{{ secret.OPENROUTER_API_KEY }}"
    ABI_API_KEY: "{{ secret.ABI_API_KEY }}"
```

To add a secret: put it in `.env`, add a line to `deploy.env`, and run `abi deploy naas` again. Only the variables listed in `deploy.env` reach the space.

The secrets can also live in the Naas secret store, which the secret service reads through its `naas` adapter:

```bash
abi secrets naas push-env-as-base64 --naas-api-key "$NAAS_API_KEY" --naas-secret-name abi_secrets --env-file .env.prod
abi secrets naas list --naas-api-key "$NAAS_API_KEY"
```

`push-env-as-base64` uploads a whole env file as one base64-encoded secret. `abi secrets naas get-base64-env` reads it back.

## From the repository's GitHub Actions

The ABI repository deploys its own API to a Naas space with `.github/workflows/deploy_api.yml`, after a release (see [Releasing](/developer-guide/releasing/release-process#containers-and-the-api-deploy)). It reads the secrets stored in the repository settings. To add a new one:

1. In the repository, open **Settings > Secrets and variables > Actions** and add the secret.
2. Open `.github/workflows/deploy_api.yml`.
3. In the step **Push latest abi container**, add the secret to the step's `env:` section, as the existing ones are.
4. In the same step, add it to `ENV_CONFIG`, the JSON the space is created or updated with.
5. Commit and push.

If the engine must also see it when the API is tested before the deployment, add it to the `docker run` of the step **Test API with production secrets before deployment**.
