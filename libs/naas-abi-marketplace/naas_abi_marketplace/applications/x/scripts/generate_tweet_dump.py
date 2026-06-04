"""CLI: generate a tweet-dump file from the X v2 search endpoint.

The same loop the X agent runs when it calls ``x_generate_tweet_dump_file``,
exposed as a command-line entry point so operators can produce dumps
without going through the chat UI.

Lives under the X application module (not at repo root) so it ships
with the module wherever the marketplace package is installed.

Three invocation styles, pick whichever fits:

  # 1) The bash wrapper (shortest — same dir as this file). It just
  #    forwards your args to `abi run script` so the engine is
  #    preloaded for the Python entry point:
  libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/scripts/generate_tweet_dump.sh \\
      --query "(openai OR anthropic) lang:en -is:retweet" \\
      --max-pages 5

  # 2) Direct `abi run script` invocation, if you don't want the wrapper:
  abi run script \\
      libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/scripts/generate_tweet_dump.py \\
      -- --query "(openai OR anthropic) lang:en -is:retweet" \\
      --max-pages 5

  # 3) Standalone — the script detects no engine has been loaded and
  #    boots one itself. Useful when you don't have the abi CLI at hand:
  uv run python -m naas_abi_marketplace.applications.x.scripts.generate_tweet_dump \\
      --query "(openai OR anthropic) lang:en -is:retweet" \\
      --max-pages 5

Internally the script:
  1. Looks up the X application module via ``ABIModule.get_instance()``.
     If that raises ``ValueError`` (module not initialised — i.e. we
     weren't invoked through ``abi run script``), it falls back to
     booting the engine itself with ``Engine().load()``.
  2. Instantiates :class:`XGenerateTweetDumpPipeline` and runs it.
  3. Prints the resulting prefix + key as JSON on stdout.

Because the pipeline goes through ``ObjectStorageService.put_object``,
an ``ObjectPut`` event is published as a side effect — so if Dagster's
auto-discovery sensor is running, the produced file gets streamed into
the graph automatically a few seconds after this command returns.

Prereqs:
  - The dev stack must be running (``abi dev up``) so the engine can
    reach oxigraph at the configured ``OXIGRAPH_URL`` during ``load()``.
    This script doesn't itself touch the triple store, but the X module
    declares ``TripleStoreService`` as a dependency and the engine
    refuses to load if its services aren't reachable.
  - ``X_BEARER_TOKEN`` must be set in the shell env (``set -a; .
    .env; set +a`` works, or export it explicitly) so the X module
    config substitution at engine load picks it up.
"""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv
from naas_abi_core import logger
from naas_abi_core.engine.Engine import Engine

load_dotenv()


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="x_generate_tweet_dump",
        description=__doc__.split("\n\n", 1)[0],  # the one-liner
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--query",
        required=True,
        help=(
            "X v2 search query (1-4096 chars), e.g. "
            "'(openai OR anthropic) lang:en -is:retweet'. Same syntax as "
            "XIntegration.search_recent_tweets."
        ),
    )
    p.add_argument(
        "--max-results",
        type=int,
        default=100,
        help="Page size forwarded to X v2 (10-100). Default: 100.",
    )
    p.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help=(
            "Number of pages to fetch before stopping. Total tweets "
            "<= max_results * max_pages. Default: 1."
        ),
    )
    p.add_argument(
        "--file-name",
        default=None,
        help=(
            "Override the auto-generated filename (must end in .ndjson). "
            "Default: <slug(query)>-<utc-iso>.ndjson"
        ),
    )
    p.add_argument(
        "--output-prefix",
        default=None,
        help=(
            "Object-storage prefix the file lands under. Default: the "
            "pipeline's default of 'x/dumps'."
        ),
    )
    return p


def _ensure_engine_loaded():
    """Return the module instance, booting the engine first if needed.

    When this script is invoked via ``abi run script``, the CLI wrapper
    has already called ``Engine().load()`` for us — so ``get_instance()``
    succeeds and we just return. When invoked standalone (``python -m
    naas_abi_marketplace.applications.x.scripts.generate_tweet_dump``),
    no engine has been loaded yet, ``get_instance()`` raises
    ``ValueError("Module … not initialized")``, and we boot the engine
    ourselves before retrying. Either way the rest of ``main()`` sees a
    fully-wired module.
    """
    from naas_abi_marketplace.applications.x import ABIModule

    try:
        return ABIModule.get_instance()
    except ValueError:
        Engine().load()
        return ABIModule.get_instance()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    module = _ensure_engine_loaded()

    # Defer the rest of the imports until after the engine is up — module
    # globals (configuration, services) are populated during load(), so
    # importing earlier could pick up half-initialised state on first run.
    from naas_abi_marketplace.applications.x.integrations.XIntegration import (
        XIntegration,
        XIntegrationConfiguration,
    )
    from naas_abi_marketplace.applications.x.pipelines.XGenerateTweetDumpPipeline import (
        XGenerateTweetDumpPipeline,
        XGenerateTweetDumpPipelineConfiguration,
        XGenerateTweetDumpPipelineParameters,
    )

    x_integration = XIntegration(
        XIntegrationConfiguration(bearer_token=module.configuration.bearer_token)
    )

    config_kwargs: dict = {
        "x_integration": x_integration,
        "object_storage": module.engine.services.object_storage,
    }
    if args.output_prefix is not None:
        config_kwargs["output_prefix"] = args.output_prefix
    pipeline = XGenerateTweetDumpPipeline(
        XGenerateTweetDumpPipelineConfiguration(**config_kwargs)
    )

    logger.info(
        f"x_generate_tweet_dump: running on query={args.query!r}, "
        f"max_results={args.max_results}, max_pages={args.max_pages}"
    )
    result = pipeline.run(
        XGenerateTweetDumpPipelineParameters(
            query=args.query,
            max_results=args.max_results,
            max_pages=args.max_pages,
            file_name=args.file_name,
        )
    )

    # Print as JSON on stdout so the output is machine-consumable (handy
    # for chaining: `... | jq -r .key | xargs ...`).
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
