"""Offline checks of the module: no broker, no engine."""

from __future__ import annotations

import json

import pytest
from naas_abi_apps.common.runtime import configuration_from
from naas_abi_apps.common.testing import fake_engine, no_core_import
from naas_abi_apps.x import MODULE_ID, ABIModule
from naas_abi_apps.x.__main__ import ENV_PREFIX
from naas_abi_apps.x.agents.XAgent import NAME
from naas_abi_apps.x.configuration import (
    XSearchRecentTweetsEventConfiguration,
    XTweetSearchWorkflowConfiguration,
)

# An in-engine config.yaml ``modules:`` entry of the X module, copied as it is
# (its ``module:`` line aside; its bearer token is now the engine secret
# applications.x/X_BEARER_TOKEN).
IN_ENGINE_ENTRY = """\
enabled: true
config:
  datastore_path: x
  search_recent_tweets_workflow:
    - name: ai_llms
      query: "(openai OR anthropic) lang:en -is:retweet"
      interval_seconds: 3600
      max_results: 100
      max_pages: 1
      sort_order: recency
      save_every_pages: 10
      save_every_tweets: 1000
      persist: true
      app_publish: false
      cost_per_tweet_usd: 0.005
      daily_max_usd: 20
      monthly_max_usd: 250
    - name: business_hours
      query: "(openai OR anthropic) lang:en -is:retweet"
      cron: "*/15 9-17 * * 1-5"
      count_recent_tweets: true
  search_recent_tweets_event:
    - name: search_envelopes
      enabled: true
      interval_seconds: 30
      prefix: x/search_recent_tweets
      events_per_tick: 100
      max_concurrent_runs: 1
  search_recent_tweets_files:
    - name: reprocess_envelopes
      enabled: true
      cron: "0,15,30,45 * * * *"
      prefix: x/search_recent_tweets
      skip_existing: true
      max_age_hours: 24
  count_recent_tweets_workflow:
    - name: example_feed
      query: "(openai OR anthropic) lang:en -is:retweet"
      label: "Example feed"
      enabled: true
  app:
    publish: true
    dataset:
      sync_enabled: true
      read_enabled: true
"""


def test_the_module_declares_its_agent_services_and_ontologies() -> None:
    assert ABIModule.module_id == MODULE_ID == "applications.x"
    assert [agent.name for agent in ABIModule.agents] == [NAME]
    assert set(ABIModule.dependencies.services) == {
        "model_registry",
        "document",
        "secret",
        "cache",
        "object_storage",
        "triple_store",
        "dataset",
    }
    assert {
        "module/applications.x/modules/XOntology.ttl",
        "module/applications.x/queries/XSparqlQueries.ttl",
    } <= {o.source(MODULE_ID) for o in ABIModule.get_ontologies()}


def test_the_class_declares_the_jobs_and_the_workflows_without_triggers() -> None:
    jobs = {job.name: job for job in ABIModule.jobs}
    assert set(jobs) == {
        "map_tweet_envelope",
        "count_recent_tweets",
        "build_app",
        "compact_dataset",
    }
    assert {n for n, j in jobs.items() if j.kind == "workflow"} == {
        "map_tweet_envelope",
        "count_recent_tweets",
    }
    assert jobs["build_app"].skip_if_running and jobs["compact_dataset"].skip_if_running


def test_on_load_declares_the_configured_workflows_with_their_handlers() -> None:
    configuration = ABIModule.Configuration(
        search_recent_tweets_workflow=[
            XTweetSearchWorkflowConfiguration(name="news", query="news")
        ]
    )
    module = ABIModule(fake_engine(), configuration)

    module.on_load()

    names = {job.name for job in module.jobs}
    assert {"search_recent_tweets", "reprocess_tweet_envelopes"} <= names
    assert module.missing_job_handlers() == set()
    # the class keeps its own: another instance declares from its configuration
    assert "search_recent_tweets" not in {job.name for job in ABIModule.jobs}


def test_an_in_engine_entry_loads_from_the_config_file(tmp_path) -> None:
    path = tmp_path / "x.yaml"
    path.write_text(IN_ENGINE_ENTRY)

    config = configuration_from(
        ABIModule.Configuration, ENV_PREFIX, {"X_CONFIG_FILE": str(path)}
    )

    filters = config.search_recent_tweets_workflow
    assert [f.name for f in filters] == ["ai_llms", "business_hours"]
    assert (filters[0].interval_seconds, filters[0].daily_max_usd) == (3600, 20)
    assert filters[1].cron == "*/15 9-17 * * 1-5" and filters[1].count_recent_tweets
    assert isinstance(
        config.search_recent_tweets_event[0], XSearchRecentTweetsEventConfiguration
    )
    assert config.search_recent_tweets_files[0].max_age_hours == 24
    assert config.count_recent_tweets_workflow[0].label == "Example feed"
    assert config.app.dataset.sync_enabled and config.app.dataset.read_enabled

    module = ABIModule(fake_engine(), config)
    module.on_load()
    jobs = {job.name: job for job in module.jobs}
    assert [t.spec for t in jobs["search_recent_tweets"].triggers] == [
        "3600s",
        "0 */15 9-17 * * 1-5",
    ]
    assert [t.spec for t in jobs["reprocess_tweet_envelopes"].triggers] == [
        "0 0,15,30,45 * * * *"
    ]


def test_a_bearer_token_in_the_config_file_is_refused(tmp_path) -> None:
    path = tmp_path / "x.yaml"
    path.write_text(
        IN_ENGINE_ENTRY.replace(
            "config:\n", 'config:\n  bearer_token: "{{ secret.X_BEARER_TOKEN }}"\n'
        )
    )
    with pytest.raises(ValueError, match="engine secret"):
        configuration_from(
            ABIModule.Configuration, ENV_PREFIX, {"X_CONFIG_FILE": str(path)}
        )


def test_the_variables_win_over_the_config_file(tmp_path) -> None:
    path = tmp_path / "x.yaml"
    path.write_text(IN_ENGINE_ENTRY)
    filters = [{"name": "env", "query": "q", "cron": "@hourly"}]

    config = configuration_from(
        ABIModule.Configuration,
        ENV_PREFIX,
        {
            "X_CONFIG_FILE": str(path),
            "X_GRAPH_NAME": "urn:graph",
            "X_SEARCH_RECENT_TWEETS_WORKFLOW": json.dumps(filters),
        },
    )

    assert config.graph_name == "urn:graph"
    assert [f.name for f in config.search_recent_tweets_workflow] == ["env"]
    assert config.search_recent_tweets_files[0].name == "reprocess_envelopes"


def test_the_defaults_need_no_configuration() -> None:
    config = configuration_from(ABIModule.Configuration, ENV_PREFIX, {})
    assert (config.datastore_path, config.bearer_token_secret) == (
        "x",
        "X_BEARER_TOKEN",
    )
    assert config.search_recent_tweets_workflow == []


def test_the_module_never_imports_abi_core() -> None:
    assert (
        no_core_import(
            "naas_abi_apps.x",
            "naas_abi_apps.x.__main__",
            "naas_abi_apps.x.flows.search",
            "naas_abi_apps.x.flows.mapping",
            "naas_abi_apps.x.flows.reprocess",
            "naas_abi_apps.x.flows.count",
            "naas_abi_apps.x.flows.maintenance",
        )
        is None
    )
