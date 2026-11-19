"""Publish the X Recent Tweets app: JSON snapshots + the Next.js web export.

The remote module publishes through its ``build_app`` job (hourly, or run it
from System -> Jobs), which calls ``flows/common.publish_x_app``: the snapshots
are read from the module's dataset tables and written under ``x/apps/x_proxy/``
in object storage, with the web export when this process can see one::

    x/apps/x_proxy/
    ├── index.html, <page>/index.html (+ index.txt), _next/...   (web export)
    ├── globals/{scenarios,queries,timezone,graph}.json
    ├── count_recent_tweets/{kpis,barcharts,linecharts}.json
    └── search_recents_tweets/{kpis,barcharts,linecharts,tables,facets}.json

The in-engine CLI bootstrapped an ``Engine`` from ``config.local.yaml``; a
remote module has no engine of its own, so the functions below take the
module's ``SyncModule`` (blocking services) and run in a worker thread.
``python -m naas_abi_apps.x.x_proxy.build`` only says where the web export is
looked for (``build.sh --web`` builds it).
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from naas_abi_apps.x.x_proxy.api.common import DEFAULT_APP_PREFIX
from naas_abi_apps.x.x_proxy.web.publish_assets import (
    export_candidates,
    resolve_export_dir,
    upload_web_export,
)


def publish_web_export(module: Any, *, required: bool = True) -> dict[str, Any]:
    """Upload the web export only (no snapshot rebuild), with ``module`` a
    ``SyncModule``. ``required`` false skips a missing export."""
    return upload_web_export(
        module.engine.services.object_storage, DEFAULT_APP_PREFIX, required=required
    )


def publish_snapshots(
    module: Any,
    queries: list[dict[str, Any]],
    *,
    require_web: bool = False,
) -> dict[str, Any]:
    """Every snapshot of ``queries`` (``{"name", "query", "label"}`` each) and
    the web export, from the dataset; ``module`` is a ``SyncModule``."""
    from naas_abi_apps.x.x_proxy.api.publish import publish_app

    services = module.engine.services
    return publish_app(
        services.object_storage,
        services.triple_store,
        queries,
        dataset=services.dataset,
        namespace=module.configuration.ontology_namespace,
        require_web=require_web,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.parse_args(argv)
    found = resolve_export_dir()
    print(
        json.dumps(
            {
                "web_export": str(found) if found else None,
                "looked_in": [str(path) for path in export_candidates()],
                "publish": "the X module's build_app job (System -> Jobs)",
            },
            indent=2,
        )
    )
    return 0 if found else 1


if __name__ == "__main__":
    raise SystemExit(main())
