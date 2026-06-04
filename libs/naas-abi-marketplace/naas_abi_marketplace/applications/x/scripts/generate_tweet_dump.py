"""CLI: generate a tweet-dump file from the X v2 search endpoint.

The same loop the X agent runs when it calls ``x_generate_tweet_dump_file``,
exposed as a command-line entry point so operators can produce dumps
without going through the chat UI:

    uv run python -m naas_abi_marketplace.applications.x.scripts.generate_tweet_dump \\
        --query "(openai OR anthropic) lang:en -is:retweet" \\
        --max-pages 5 \\
        --max-results 100

Lives under the X application module (not at repo root) so it ships
with the module wherever the marketplace package is installed.

The script:
  1. Boots the ABI engine (so module config + secrets are wired).
  2. Looks up the X application module and its configured bearer token.
  3. Instantiates :class:`XGenerateTweetDumpPipeline` and runs it.
  4. Prints the resulting object-storage prefix + key as JSON to stdout.

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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    # Boot the engine using the project's config.yaml — same pattern as
    # the other scripts in this directory. We can't pin to a single
    # module here because the engine's default_chat_model /
    # default_embedding_model live in config.yaml and validate against
    # whatever modules registered them, so leaving the module list
    # implicit lets the engine load everything the project's config
    # declares.
    engine = Engine()
    engine.load()

    # Defer imports until after engine.load() so module-level singletons
    # (configuration, services) are populated before the pipeline picks
    # them up.
    from naas_abi_marketplace.applications.x import ABIModule
    from naas_abi_marketplace.applications.x.integrations.XIntegration import (
        XIntegration,
        XIntegrationConfiguration,
    )
    from naas_abi_marketplace.applications.x.pipelines.XGenerateTweetDumpPipeline import (
        XGenerateTweetDumpPipeline,
        XGenerateTweetDumpPipelineConfiguration,
        XGenerateTweetDumpPipelineParameters,
    )

    module = ABIModule.get_instance()
    x_integration = XIntegration(
        XIntegrationConfiguration(bearer_token=module.configuration.bearer_token)
    )

    config_kwargs: dict = {
        "x_integration": x_integration,
        "object_storage": engine.services.object_storage,
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
