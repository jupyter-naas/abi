"""Durable flows of the X module: SDK workflows and jobs.

``search``, ``mapping``, ``reprocess``, ``count`` and ``maintenance`` hold the
async bodies of the workflows and jobs ``ABIModule`` declares; each runs its
synchronous pieces (``common``, ``envelopes``, the domain classes, ``x_proxy``)
in worker threads, on ``module.sync``. See the module's AGENTS.md.

``declare_configured_workflows`` declares the two workflows whose triggers come
from the configuration; ``ABIModule.on_load`` calls it.
"""

from __future__ import annotations

from typing import Any

from naas_abi_apps.x.flows.models import (
    ReprocessTweetEnvelopesInput,
    ReprocessTweetEnvelopesOutput,
    SearchRecentTweetsInput,
    SearchRecentTweetsOutput,
)
from naas_abi_apps.x.flows.triggers import reprocess_triggers, search_triggers, shards

SEARCH_WORKFLOW = "search_recent_tweets"
REPROCESS_WORKFLOW = "reprocess_tweet_envelopes"


def _shard_name(name: str, index: int) -> str:
    return name if index == 1 else f"{name}_{index}"


def declare_configured_workflows(module: Any) -> None:
    """Declare, on *module* (the SDK ``ABIModule``, in ``on_load``):

    - ``search_recent_tweets``: one trigger per ``search_recent_tweets_workflow``
      entry, each tick carrying ``{"filter": <name>}``. Not declared without entries.
    - ``reprocess_tweet_envelopes``: manual, plus one trigger per
      ``search_recent_tweets_files`` entry (none by default).

    Both are ``skip_if_running``: a tick whose previous run with the same input
    (the same filter, the same sweep) is still running ends SKIPPED instead of
    queueing. A descriptor holds 16 triggers at most, so more entries declare
    ``<name>_2`` and so on.
    """

    async def search_recent_tweets(ctx: Any, inp: SearchRecentTweetsInput) -> Any:
        from naas_abi_apps.x.flows.search import run_search_recent_tweets

        return await run_search_recent_tweets(module, ctx, inp)

    async def reprocess_tweet_envelopes(
        ctx: Any, inp: ReprocessTweetEnvelopesInput
    ) -> Any:
        from naas_abi_apps.x.flows.reprocess import run_reprocess_tweet_envelopes

        return await run_reprocess_tweet_envelopes(module, ctx, inp)

    configuration = module.configuration
    searches = shards(search_triggers(configuration.search_recent_tweets_workflow))
    for index, group in enumerate(searches, start=1):
        module.declare_workflow(
            _shard_name(SEARCH_WORKFLOW, index),
            search_recent_tweets,
            input_type=SearchRecentTweetsInput,
            output_type=SearchRecentTweetsOutput,
            description=(
                "One tick of an X search filter: spend guard, fetch and save the "
                "envelopes, map them, follow the counts, sync the dataset, publish the app."
            ),
            triggers=group,
            # Different filters run side by side, and a tick of a filter that is
            # still running is SKIPPED, not queued: it needs a slot of its own to
            # start and skip, so two per filter.
            max_concurrency=min(64, 2 * len(group)),
            max_attempts=3,
            skip_if_running=True,
        )
    sweeps = shards(reprocess_triggers(configuration.search_recent_tweets_files))
    for index, group in enumerate(sweeps or [()], start=1):
        module.declare_workflow(
            _shard_name(REPROCESS_WORKFLOW, index),
            reprocess_tweet_envelopes,
            input_type=ReprocessTweetEnvelopesInput,
            output_type=ReprocessTweetEnvelopesOutput,
            description=(
                "Re-map every search envelope under a prefix that is not yet in the "
                "graph and the dataset, then sync the dataset and publish the app."
            ),
            triggers=group,
            max_concurrency=2,  # a running sweep, and the next tick, which skips
            max_attempts=2,
            skip_if_running=True,
        )
