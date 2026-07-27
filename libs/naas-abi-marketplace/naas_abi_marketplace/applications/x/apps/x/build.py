"""Build / publish the X Recent Tweets app snapshots + dashboard.

Runs SPARQL against the count + tweet graphs (via ``config.local.yaml`` /
``config.remote.yaml`` as loaded by the Engine) and writes typed JSON snapshots
under ``x/apps/x/`` in object storage:

```
x/apps/x/
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--query",
        action="append",
        default=None,
        help="Followed query to publish (repeatable). Defaults to config entries.",
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

    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.x import ABIModule
    from naas_abi_marketplace.applications.x.apps.x.api.publish import publish_app

    # Engine(configuration=…) expects YAML *content*, not a filesystem path.
    config_yaml: str | None = None
    config_path = args.config
    if config_path is None:
        for candidate in ("config.local.yaml", ".abi/config.local.yaml"):
            if os.path.isfile(candidate):
                config_path = candidate
                break
    if config_path is not None:
        with open(config_path, encoding="utf-8") as fh:
            config_yaml = fh.read()
        print(f"Using config: {config_path}")

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

    result = publish_app(
        module.engine.services.object_storage,
        module.engine.services.triple_store,
        queries,
        namespace=module.configuration.ontology_namespace,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
