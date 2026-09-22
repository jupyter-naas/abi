"""Build / publish the X Recent Tweets app snapshots + dashboard.

Reads Dataset Service tables (via ``config.local.yaml`` / ``config.remote.yaml`` as
loaded by the Engine) and writes typed JSON snapshots
under ``x/apps/x_proxy/`` in object storage:

```
x/apps/x_proxy/
├── index.html
├── globals/{scenarios,queries,timezone}.json
├── count_recent_tweets/{kpis,barcharts,linecharts}.json
└── search_recents_tweets/{kpis,barcharts,linecharts,tables}.json
```

Followed queries default to the module's ``count_recent_tweets_workflow`` +
search filters with ``count_recent_tweets: true``; pass ``--query`` to override.
"""

from __future__ import annotations

import argparse
import json
import os


def _followed_queries_from_config(module) -> list[dict]:
    from naas_abi_marketplace.applications.x.orchestrations.utils import (
        followed_count_entries,
    )

    return followed_count_entries(module)


def _read_config(args) -> tuple[str | None, str | None]:
    """Return ``(yaml content, path printed to stdout)``."""
    config_path = args.config
    if config_path is None:
        for candidate in ("config.local.yaml", ".abi/config.local.yaml"):
            if os.path.isfile(candidate):
                config_path = candidate
                break
    if config_path is None:
        return None, None
    with open(config_path, encoding="utf-8") as fh:
        return fh.read(), config_path


def _upload_web_only(config_yaml: str | None) -> None:
    """Upload ``web/out/`` using only object storage - no graph, no Fuseki."""
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        EngineConfiguration,
    )
    from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import (
        DEFAULT_APP_PREFIX,
    )
    from naas_abi_marketplace.applications.x.apps.x_proxy.web.publish_assets import (
        upload_web_export,
    )

    configuration = EngineConfiguration.load_configuration(config_yaml)
    object_storage = configuration.services.object_storage.load()
    result = upload_web_export(object_storage, DEFAULT_APP_PREFIX)
    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--query",
        action="append",
        default=None,
        help="Followed query to publish (repeatable). Defaults to config entries.",
    )
    parser.add_argument(
        "--web-only",
        action="store_true",
        help=(
            "Upload web/out/ and nothing else - no SPARQL, no snapshot rebuild. "
            "For iterating on the UI against snapshots already published."
        ),
    )
    parser.add_argument(
        "--config",
        default=None,
        help=(
            "Path to an ABI config YAML (default: ABI_CONFIG / config.yaml lookup). "
            "Use config.local.yaml to hit the local stack."
        ),
    )
    args = parser.parse_args()

    config_yaml, config_path = _read_config(args)
    if config_path is not None:
        print(f"Using config: {config_path}")

    if args.web_only:
        _upload_web_only(config_yaml)
        return

    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.x import ABIModule
    from naas_abi_marketplace.applications.x.apps.x_proxy.api.publish import publish_app

    engine = Engine(configuration=config_yaml)
    engine.load(module_names=["naas_abi_marketplace.applications.x"])
    module = ABIModule.get_instance()

    if args.query:
        queries = [{"name": q, "query": q, "label": q} for q in args.query]
    else:
        queries = _followed_queries_from_config(module)
        if not queries:
            # Fall back to raw search workflow entries so a local run still works
            # when count_recent_tweets is set but followed_count_entries is empty.
            for flt in module.configuration.search_recent_tweets_workflow or []:
                queries.append(
                    {"name": flt.name, "query": flt.query, "label": flt.name}
                )

    dataset = getattr(module.engine.services, "dataset", None)
    if dataset is None:
        raise SystemExit(
            "Dataset Service is not wired in this config (required for publish)."
        )

    result = publish_app(
        module.engine.services.object_storage,
        module.engine.services.triple_store,
        queries,
        dataset=dataset,
        namespace=module.configuration.ontology_namespace,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
