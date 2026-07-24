"""Build the X "Post Count Following" dashboard via object storage.

Runs the count SPARQL queries against the ``x_recent_posts_count`` graph and
publishes the dashboard + JSON snapshots to ``x/apps/x/``. The list of followed
queries defaults to the module's ``count_recent_tweets_workflow`` config; pass
``--query`` one or more times to override.

The Nexus catalog loads ``/app-html/x/apps/x/index.html``, which the module
middleware (``routes.py``) serves from ``x/apps/x/index.html`` in object storage.
"""

from __future__ import annotations

import argparse
import json

from naas_abi_marketplace.applications.x.apps.x.hub import XCountAppHubBuilder


def _followed_queries_from_config(module) -> list[dict]:
    entries = getattr(module.configuration, "count_recent_tweets_workflow", []) or []
    return [
        {"name": e.name, "query": e.query, "label": e.label or e.name} for e in entries
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--query",
        action="append",
        default=None,
        help="Followed query to publish (repeatable). Defaults to config entries.",
    )
    args = parser.parse_args()

    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.x import ABIModule

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.x"])
    module = ABIModule.get_instance()

    if args.query:
        queries = [{"name": q, "query": q, "label": q} for q in args.query]
    else:
        queries = _followed_queries_from_config(module)

    builder = XCountAppHubBuilder(
        module.engine.services.object_storage,
        module.engine.services.triple_store,
        namespace=module.configuration.ontology_namespace,
    )
    result = builder.publish(queries)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
