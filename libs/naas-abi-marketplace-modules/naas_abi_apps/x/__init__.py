"""X: a remote ABI module (recent tweets: search, graph, dataset, Recent Tweets app).

Runs in its own process (``python -m naas_abi_apps.x``) and reaches the engine
only through NATS. Replaces the in-engine ``naas_abi_marketplace.applications.x``
(#1423, #1425-#1428):

- the ``X`` agent and its tools over ``XIntegration`` (async, httpx), with the
  per-filter spend caps of ``XSearchRecentTweetsWorkflow``;
- the durable flows as SDK workflows and jobs (``flows/``): ``search_recent_tweets``
  (one trigger per ``search_recent_tweets_workflow`` entry),
  ``reprocess_tweet_envelopes``, ``map_tweet_envelope``, ``count_recent_tweets``,
  ``build_app``, ``compact_dataset``. Overlapping ticks are skipped by the SDK's
  ``skip_if_running``;
- the Recent Tweets app (``apps/x_proxy``, app id ``remote/applications.x:x_proxy``)
  served with ``expose_app`` from object storage and the dataset service; the
  web export the image carries is uploaded at start, in the background;
- the X ontologies, sent to the schema graph.

The synchronous bodies (mapping, dataset, snapshots) run on the module's own
threads and reach the engine through ``self.sync`` (``services.SyncModule``). The bearer token
is the engine secret ``applications.x/X_BEARER_TOKEN``. See ``AGENTS.md``.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from naas_abi_apps.common.agents import read_secrets
from naas_abi_apps.common.runtime import serve_until_stopped
from naas_abi_apps.x.agents.XAgent import (
    DESCRIPTION,
    LOGO_URL,
    NAME,
    SUGGESTIONS,
    create_agent,
)
from naas_abi_apps.x.configuration import XConfiguration
from naas_abi_apps.x.flows.models import (
    CountRecentTweetsInput,
    CountRecentTweetsOutput,
    MapTweetEnvelopeInput,
    MapTweetEnvelopeOutput,
)
from naas_abi_apps.x.services import SyncModule
from naas_abi_sdk import (
    AgentDescriptor,
    BaseModule,
    ModuleDependencies,
)
from naas_abi_sdk.jobs import Cron, JobContext, job
from naas_abi_sdk.workflows import FlowContext, workflow

MODULE_ID = "applications.x"
AGENT_INVOKE = ("agent.invoke.v1",)
APP_NAME = "x_proxy"


class ABIModule(BaseModule[XConfiguration]):
    Configuration = XConfiguration
    module_id = MODULE_ID
    package_version = "0.1.0"
    dependencies = ModuleDependencies(
        services=(
            "model_registry",
            "document",
            "secret",
            # Lookups of the X API (users, timelines, tweets by id): a day.
            "cache",
            "object_storage",
            "triple_store",
            "dataset",
        )
    )
    agents = (
        AgentDescriptor(
            NAME,
            DESCRIPTION,
            capabilities=AGENT_INVOKE,
            avatar_url=LOGO_URL,
            suggestions=SUGGESTIONS,
        ),
    )

    bearer_token: str | None = None
    sync: SyncModule
    # The start-up upload of the web export (``on_initialized``).
    _web_export: asyncio.Task[Any]

    def on_load(self) -> None:
        # The workflows whose triggers come from the configuration are declared
        # before the module's jobs go to its job host.
        from naas_abi_apps.x.flows import declare_configured_workflows

        declare_configured_workflows(self)

    async def on_initialized(self) -> None:
        self.sync = SyncModule(self, asyncio.get_running_loop())
        secrets = await read_secrets(
            self.engine,
            {"bearer_token": self.configuration.bearer_token_secret},
            module_id=MODULE_ID,
        )
        self.bearer_token = secrets.get("bearer_token") or None
        agent = await create_agent(self)
        self.expose_agent(NAME, agent.as_handler())

        from naas_abi_apps.x.x_proxy.app import create_app

        self.expose_app(APP_NAME, create_app(self))

        # The web export this image carries replaces the one in object storage
        # (an earlier version's), whatever app.dataset.read_enabled says. In the
        # background: READY does not wait for it, a failure is only logged.
        from naas_abi_apps.x.flows.maintenance import publish_web_export_at_start

        self._web_export = asyncio.create_task(
            publish_web_export_at_start(self), name="x-web-export"
        )

    async def run(self) -> None:
        await serve_until_stopped(self)

    async def on_unloaded(self) -> None:
        # The start-up upload first: it runs on the pool closed below.
        task = self.__dict__.get("_web_export")
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        sync = self.__dict__.get("sync")
        if sync is not None:
            sync.close()

    # ----- durable workflows and jobs: bodies in flows/ ---------------------------

    @workflow(
        description="Map one saved X search envelope into the graph (idempotent).",
        max_concurrency=4,  # flows.search.MAP_CONCURRENCY
        max_attempts=3,
    )
    async def map_tweet_envelope(
        self, ctx: FlowContext, inp: MapTweetEnvelopeInput
    ) -> MapTweetEnvelopeOutput:
        from naas_abi_apps.x.flows.mapping import run_map_tweet_envelope

        return await run_map_tweet_envelope(self, ctx, inp)

    @workflow(
        description="Follow the hourly recent-post count of an X query: fetch, then map.",
        max_attempts=3,
    )
    async def count_recent_tweets(
        self, ctx: FlowContext, inp: CountRecentTweetsInput
    ) -> CountRecentTweetsOutput:
        from naas_abi_apps.x.flows.count import run_count_recent_tweets

        return await run_count_recent_tweets(self, ctx, inp)

    @job(
        description="Rebuild the Recent Tweets app from the dataset, then one media batch.",
        triggers=(Cron("0 0 * * * *", time_zone="UTC"),),
        max_concurrency=2,  # a running rebuild, and the next tick, which skips
        skip_if_running=True,
    )
    async def build_app(self, ctx: JobContext) -> dict[str, Any]:
        from naas_abi_apps.x.flows.maintenance import run_build_app

        return await run_build_app(self, ctx)

    @job(
        description="Compact the X dataset tables (every six hours, at :30).",
        # Half past, so it never overlaps the :00 rebuild.
        triggers=(Cron("0 30 */6 * * *", time_zone="UTC"),),
        timeout=timedelta(hours=5),
        max_concurrency=2,  # a running compaction, and the next tick, which skips
        skip_if_running=True,
    )
    async def compact_dataset(self, ctx: JobContext) -> dict[str, Any]:
        from naas_abi_apps.x.flows.maintenance import run_compact_dataset

        return await run_compact_dataset(self, ctx)
