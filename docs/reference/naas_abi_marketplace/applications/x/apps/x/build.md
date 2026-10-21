# build.py (X Recent Tweets app build/publish)

## What it is
A CLI entrypoint that builds and publishes the **X Recent Tweets** app artifacts:
- Runs SPARQL against configured graphs via the ABI Engine configuration.
- Writes typed JSON “snapshot” files and uploads the web dashboard assets to object storage under `x/apps/x/`.

## Public API
- `main() -> None`
  - CLI for publishing snapshots + dashboard (or only web assets).
- `_followed_queries_from_config(module) -> list[dict]`
  - Internal helper to derive “followed queries” from module configuration.

## Configuration/Dependencies
- **Configuration**
  - Loads ABI Engine YAML configuration content (not a path) from:
    - `--config <path>` if provided, else first existing:
      - `config.local.yaml`
      - `.abi/config.local.yaml`
    - If none found, Engine falls back to its internal defaults (`ABI_CONFIG / config.yaml lookup` per help text).
- **Dependencies (runtime imports)**
  - `naas_abi_core.engine.Engine.Engine`
  - `naas_abi_marketplace.applications.x.ABIModule`
  - Publishing:
    - `naas_abi_marketplace.applications.x.apps.x.api.publish.publish_app`
  - Web-only publishing:
    - `naas_abi_marketplace.applications.x.apps.x.api.common.DEFAULT_APP_PREFIX`
    - `naas_abi_marketplace.applications.x.apps.x.web.publish_assets.upload_web_export`
  - Followed query extraction:
    - `naas_abi_marketplace.applications.x.orchestrations.utils.followed_count_entries`

## Usage
Run from a Python environment where the ABI packages are installed.

### Publish snapshots + web app (default behavior)
```bash
python -m naas_abi_marketplace.applications.x.apps.x.build --config config.local.yaml
```

### Publish only the web assets (no SPARQL / no snapshot rebuild)
```bash
python -m naas_abi_marketplace.applications.x.apps.x.build --web-only --config config.local.yaml
```

### Override followed queries (repeatable)
```bash
python -m naas_abi_marketplace.applications.x.apps.x.build --query "my_query_1" --query "my_query_2"
```

## Caveats
- `Engine(configuration=...)` expects **YAML content**, so this script reads the file and passes its contents (not the file path).
- If no `--query` is provided and no followed queries are returned from config, it falls back to `module.configuration.search_recent_tweets_workflow` entries (if present) to keep local runs functional.
