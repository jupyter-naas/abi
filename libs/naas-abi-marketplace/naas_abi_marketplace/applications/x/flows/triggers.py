"""Triggers of the X workflows, built from the module configuration."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta

from naas_abi_core import logger
from naas_abi_core.module.jobs import Cron, Every
from naas_abi_marketplace.applications.x import (
    DEFAULT_FILES_INTERVAL_SECONDS,
    DEFAULT_SEARCH_INTERVAL_SECONDS,
)

# A job descriptor holds at most this many triggers (naas_abi_sdk.jobs.MAX_TRIGGERS).
MAX_TRIGGERS_PER_WORKFLOW = 16


def nats_cron(expression: str) -> str:
    """A configured cron expression in the form NATS schedules take.

    The configuration keeps the Dagster dialect: 5 fields (``min hour dom mon
    dow``), or 6 with the seconds **last** (croniter), or an ``@`` macro. NATS
    takes 6 fields with the seconds **first**.
    """
    expression = expression.strip()
    if expression.startswith("@"):
        return expression
    fields = expression.split()
    if len(fields) == 5:
        return " ".join(["0", *fields])
    if len(fields) == 6:
        return " ".join([fields[5], *fields[:5]])
    raise ValueError(f"cron needs 5 or 6 fields, got {expression!r}")


def schedule_trigger(
    config, payload: dict, default_interval_seconds: int
) -> Cron | Every:
    """The trigger of one configured entry: its cron, else its interval, else
    *default_interval_seconds*; each tick carries *payload* as its input."""
    if config.cron:
        return Cron(nats_cron(config.cron), time_zone="UTC", input=payload)
    return Every(
        timedelta(seconds=config.interval_seconds or default_interval_seconds),
        input=payload,
    )


def search_trigger(config) -> Cron | Every:
    """The trigger of one ``search_recent_tweets_workflow`` entry (every 60 s by
    default); each tick carries ``{"filter": <name>}``."""
    return schedule_trigger(
        config, {"filter": config.name}, DEFAULT_SEARCH_INTERVAL_SECONDS
    )


def reprocess_trigger(config) -> Cron | Every:
    """The trigger of one ``search_recent_tweets_files`` entry (every 1 h 30 by
    default); each tick carries the ``reprocess_tweet_envelopes`` input the entry
    stands for. ``skip_existing: false`` is ``force``."""
    payload: dict = {
        "prefix": config.prefix,
        "persist": config.persist,
        "force": not config.skip_existing,
        "app_publish": config.app_publish,
    }
    if config.max_age_hours is not None:
        payload["max_age_hours"] = config.max_age_hours
    return schedule_trigger(config, payload, DEFAULT_FILES_INTERVAL_SECONDS)


def _triggers(configs: Iterable, make, what: str) -> dict[str, Cron | Every]:
    """One trigger per entry, by entry name. A duplicate name or an entry NATS
    cannot schedule is logged and left out (as the Dagster definitions skip a duplicate)."""
    triggers: dict[str, Cron | Every] = {}
    for config in configs:
        if config.name in triggers:
            logger.warning(
                f"X: duplicate {what} name {config.name!r}; skipping the duplicate"
            )
            continue
        try:
            triggers[config.name] = make(config)
        except ValueError as error:
            logger.error(
                f"X: {what} {config.name!r} has no valid schedule ({error}); "
                "it will not run"
            )
    return triggers


def search_triggers(configs: Iterable) -> dict[str, Cron | Every]:
    return _triggers(configs, search_trigger, "search_recent_tweets_workflow")


def reprocess_triggers(configs: Iterable) -> dict[str, Cron | Every]:
    return _triggers(configs, reprocess_trigger, "search_recent_tweets_files")


def shards(triggers: dict[str, Cron | Every]) -> list[tuple[Cron | Every, ...]]:
    """The triggers split into groups of at most ``MAX_TRIGGERS_PER_WORKFLOW``: each
    group is one declared workflow (``search_recent_tweets``, then
    ``search_recent_tweets_2``...)."""
    items = list(triggers.values())
    return [
        tuple(items[i : i + MAX_TRIGGERS_PER_WORKFLOW])
        for i in range(0, len(items), MAX_TRIGGERS_PER_WORKFLOW)
    ]
