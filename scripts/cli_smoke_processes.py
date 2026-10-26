"""Starts a running remote module's Workflow and Pipeline classes over NATS.

Run by scripts/cli_smoke.sh inside the generated project (`uv run python`), once
`abi dev up` has started the module: it needs `naas_abi_sdk`, which a standard
library script cannot stand in for. It checks that discovery lists each class as
a durable workflow (`workflow.<name>`, `pipeline.<name>`), runs both by name as
another module does, and reads a started run's record and step.

    ABI_NATS_URL=nats://module:<password>@127.0.0.1:4222 \
    ABI_MODULE_KEY="$(abi module key my_project.research)" \
    python scripts/cli_smoke_processes.py --module-id my_project.research \
        --project my_project --workflow digest_workflow --pipeline catalog_pipeline

The probe signs as the module itself (its own key): a module acts only as itself, so
this starts the module's own workflows, as any module of the project may. The
broker URL and the key come from ABI_NATS_URL and ABI_MODULE_KEY, like a module's.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from typing import Any

from naas_abi_sdk.discovery import DiscoveryClient, ModuleProxy
from naas_abi_sdk.service_token import ModuleToken
from naas_abi_sdk.transport import Transport


class NotYet(Exception):
    """The check does not pass yet; the message says what it saw.

    Same as scripts/cli_smoke_checks.py, which cannot be imported here: it is
    standard library only and this one runs in the project's environment."""


async def wait(name: str, deadline: float, check: Any) -> Any:
    started = time.monotonic()
    last = "never ran"
    while True:
        try:
            result = await check()
        except NotYet as exc:
            last = str(exc)
        except Exception as exc:  # noqa: BLE001 - the broker or discovery not up yet
            last = f"{type(exc).__name__}: {exc}"
        else:
            print(f"ok    {name} ({time.monotonic() - started:.0f}s)", flush=True)
            return result
        if time.monotonic() >= deadline:
            print(f"FAIL  {name}: {last}", flush=True)
            sys.exit(1)
        await asyncio.sleep(3)


async def main(args: argparse.Namespace) -> None:
    transport = Transport(
        os.environ["ABI_NATS_URL"],
        ModuleToken(args.module_id, os.environ["ABI_MODULE_KEY"]),
    )
    try:
        await probe(args, transport)
    finally:
        await transport.close()


async def probe(args: argparse.Namespace, transport: Transport) -> None:
    deadline = time.monotonic() + args.timeout
    client = DiscoveryClient(transport, args.project)
    module = ModuleProxy(client, args.module_id)
    workflow_name = f"workflow.{args.workflow}"
    pipeline_name = f"pipeline.{args.pipeline}"

    async def listed() -> tuple[Any, ...]:
        ready = [i for i in await module.instances() if i.status == "READY"]
        if not ready:
            raise NotYet(f"{args.module_id} has no READY instance")
        flows = {j.name: j for j in ready[0].jobs if j.is_workflow}
        wanted = {workflow_name, pipeline_name}
        if not wanted <= set(flows):
            raise NotYet(f"discovery lists {sorted(flows)}, wants {sorted(wanted)}")
        return tuple(flows[name] for name in sorted(wanted))

    flows = await wait(
        "discovery lists the workflow and the pipeline as workflows", deadline, listed
    )
    for flow in flows:
        if not flow.description or not flow.input_schema:
            sys.exit(f"FAIL  {flow.name} has no description or no input schema")

    async def workflow() -> str:
        proxy = await module.get_workflow(workflow_name)
        result = await proxy.run({"message": "smoke"}, timeout=60)
        if result != {"message": "smoke"}:
            raise NotYet(f"the workflow answered {result!r}")
        return "ok"

    await wait("workflow started over NATS", deadline, workflow)

    async def pipeline() -> str:
        from rdflib import RDFS, Graph, Literal, URIRef

        proxy = await module.get_workflow(pipeline_name)
        output = await proxy.run({"iri": "urn:smoke:a", "label": "Smoke"}, timeout=60)
        if output.get("format") != "text/turtle" or "data" not in output:
            raise NotYet(f"the pipeline answered {output!r}")
        graph = Graph().parse(data=output["data"], format="turtle")
        if (URIRef("urn:smoke:a"), RDFS.label, Literal("Smoke")) not in graph:
            raise NotYet(
                f"the pipeline's graph has {len(graph)} triples, not the label"
            )
        return "ok"

    await wait("pipeline started over NATS", deadline, pipeline)

    async def refused() -> str:
        from naas_abi_sdk.transport import RPCError

        try:
            await module.get_workflow("workflow.no_such_workflow")
        except RPCError as exc:
            if exc.code != "WORKFLOW_NOT_FOUND":
                raise NotYet(f"an unknown workflow answered {exc.code}") from exc
            return exc.code
        raise NotYet("an unknown workflow was found")

    await wait("an undeclared workflow is refused", deadline, refused)

    # Started once: a run that ends badly is a failure, not a reason to start another.
    async def start() -> Any:
        proxy = await module.get_workflow(workflow_name)
        return await proxy.start(
            {"message": "run"}, idempotency_key=f"smoke-{int(time.time())}"
        )

    run = await wait("workflow run started", deadline, start)

    async def finished() -> str:
        try:
            output = await run.result(
                timeout=min(60, max(1, deadline - time.monotonic()))
            )
        except TimeoutError as exc:
            raise NotYet(f"the run is still {(await run.status())!r}") from exc
        if output != {"message": "run"}:
            sys.exit(f"FAIL  workflow run: its output is {output!r}")
        steps = [step["key"] for step in await run.steps()]
        if steps != ["run"]:
            sys.exit(f"FAIL  workflow run: its steps are {steps!r}")
        return "ok"

    await wait("workflow run recorded with its step", deadline, finished)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--module-id", required=True)
    parser.add_argument("--project", required=True, help="the discovery project")
    parser.add_argument("--workflow", required=True, help="a workflow's name")
    parser.add_argument("--pipeline", required=True, help="a pipeline's name")
    parser.add_argument("--timeout", type=float, default=300.0)
    asyncio.run(main(parser.parse_args()))
