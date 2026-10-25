"""Fakes for the flow tests: a context that journals steps the way ``FlowContext``
does, so a test can run a handler twice and see what a retry does not repeat."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import GlobalConfig
from naas_abi_marketplace.applications.x import (
    ABIModule,
    XTweetSearchWorkflowConfiguration,
)


class FakeDocuments:
    """Run records, with the one ``find`` the overlap guard makes."""

    def __init__(self, records: list[dict[str, Any]] | None = None):
        self.records = records or []
        self.finds: list[dict[str, Any]] = []

    async def find(self, collection, *, where=(), limit=100, **_):
        self.finds.append({"collection": collection, "where": list(where)})
        wanted = {field: value for field, op, value in where}
        items = [
            SimpleNamespace(id=r["run_id"], data=r)
            for r in self.records
            if r["job"] == wanted["job"] and r["status"] in wanted["status"]
        ]
        return SimpleNamespace(items=items[:limit], next_cursor=None)


class FakeFlowContext:
    """``SyncFlowContext``: ``step`` journals (by key, in ``journal``, which outlives
    one attempt), ``map_call`` and ``call`` ask ``children(workflow, input)``."""

    def __init__(
        self,
        *,
        job: str = "search_recent_tweets",
        run_id: str = "search_recent_tweets:10",
        module_id: str = "naas_abi_marketplace.applications.x",
        journal: dict[str, Any] | None = None,
        children: Callable[[str, dict[str, Any]], Any] | None = None,
        payload: dict[str, Any] | None = None,
    ):
        self.payload = payload or {}
        self.job, self.run_id = job, run_id
        self.journal = journal if journal is not None else {}
        self.children = children or (lambda workflow, payload: {"ok": True})
        self.runtime = SimpleNamespace(module_id=module_id, project="default")
        self.skipped: str | None = None
        self.logs: list[str] = []
        self.ran: list[str] = []  # steps that really ran, in order
        self.fanned: list[tuple[str, str, list[dict[str, Any]]]] = []
        self.called: list[tuple[str, str, dict[str, Any]]] = []

    @property
    def stages(self) -> list[str]:
        """The steps that really ran, a fan-out's ``key[i]`` collapsed to ``key``."""
        return list(dict.fromkeys(k.split("[")[0] for k in self.ran))

    def attach(self, module) -> FakeFlowContext:
        """What the host does before the handler starts: its run is a RUNNING
        record of the job, which the overlap check must find."""
        host = module._job_host()[0]
        if not any(r["run_id"] == self.run_id for r in host.documents.records):
            host.documents.records.append(
                {
                    "run_id": self.run_id,
                    "job": self.job,
                    "status": "RUNNING",
                    "sequence": int(self.run_id.rsplit(":", 1)[1]),
                    "payload": self.payload,
                }
            )
        return self

    def step(self, key, fn, *args, retries=0, backoff=1.0, **kwargs):
        if key in self.journal:
            return self.journal[key]
        value = (
            asyncio.run(fn(*args, **kwargs))
            if inspect.iscoroutinefunction(fn)
            else fn(*args, **kwargs)
        )
        value = json.loads(json.dumps(value))
        self.ran.append(key)
        self.journal[key] = value
        return value

    def map_call(self, key, module_id, workflow, inputs, *, concurrency=8):
        inputs = list(inputs)
        if key not in self.journal:
            self.ran.append(key)
            self.fanned.append((module_id, workflow, inputs))
            self.journal[key] = [self.children(workflow, i) for i in inputs]
        return self.journal[key]

    def call(self, module_id, workflow, input=None, key=None):
        key = key or f"call:{workflow}"  # (the real one numbers its auto keys)
        if key not in self.journal:
            self.ran.append(key)
            self.called.append((module_id, workflow, input))
            self.journal[key] = self.children(workflow, input)
        return self.journal[key]

    def skip(self, reason=""):
        self.skipped = reason

    def log(self, message):
        self.logs.append(message)


@pytest.fixture
def make_ctx():
    return FakeFlowContext


def search_filter(
    name: str = "news", **overrides: Any
) -> XTweetSearchWorkflowConfiguration:
    return XTweetSearchWorkflowConfiguration(
        name=name, query=f"{name} lang:en", **overrides
    )


def x_module(
    *filters: XTweetSearchWorkflowConfiguration,
    records: list[dict[str, Any]] | None = None,
    **services: Any,
) -> Any:
    """A module with the configuration the flows read and the services they reach.
    ``records`` are the run records its job host holds."""
    host = SimpleNamespace(documents=FakeDocuments(records), collection="runs_default")
    return SimpleNamespace(
        _job_host=lambda: (host, None),
        configuration=SimpleNamespace(
            search_recent_tweets_workflow=list(filters),
            graph_name="http://ontology.naas.ai/graph/x",
            ontology_namespace="http://ontology.naas.ai/x/",
        ),
        engine=SimpleNamespace(services=SimpleNamespace(**services)),
    )


def real_x_module(
    *filters: XTweetSearchWorkflowConfiguration,
    files: list[Any] | None = None,
    **services: Any,
) -> ABIModule:
    """The real ``ABIModule`` (its workflows and jobs, declared as ``on_load`` does),
    on a fake engine. ``files`` are ``search_recent_tweets_files`` entries."""
    configuration = ABIModule.Configuration(
        global_config=GlobalConfig(ai_mode="local"),
        search_recent_tweets_workflow=list(filters),
        search_recent_tweets_files=files or [],
    )
    engine = SimpleNamespace(services=SimpleNamespace(**services))
    module = ABIModule(engine=engine, configuration=configuration)  # type: ignore[arg-type]
    module._declare_workflows()  # what on_load does
    return module
