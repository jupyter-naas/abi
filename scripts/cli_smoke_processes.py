"""Calls a running remote module's workflows and pipelines over NATS, as a peer.

Run by scripts/cli_smoke.sh inside the generated project (`uv run python`), once
`abi dev up` has started the module: it needs `naas_abi_sdk`, which a standard
library script cannot stand in for. It checks what discovery lists for the
module, calls each process the way another module would (a token bound to the
instance), and starts the workflow as a job.

    python scripts/cli_smoke_processes.py --module-id my_project.research \
        --nats-url nats://module:<password>@127.0.0.1:4222 --project my_project \
        --key "$(abi module key my_project.research)" \
        --workflow digest_workflow --pipeline catalog_pipeline

The probe signs as the module itself (its own key): a module acts only as itself,
and discovery authorizes a call by the token's binding, not by who is asking.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from typing import Any

from naas_abi_sdk.discovery import DiscoveryClient, ModuleProxy
from naas_abi_sdk.service_token import ModuleToken
from naas_abi_sdk.transport import Transport


class NotYet(Exception):
    """The check does not pass yet; the message says what it saw."""


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
    deadline = time.monotonic() + args.timeout
    transport = Transport(args.nats_url, ModuleToken(args.module_id, args.key))
    client = DiscoveryClient(transport, args.project)
    module = ModuleProxy(client, args.module_id)

    async def listed() -> tuple[Any, ...]:
        ready = [i for i in await module.instances() if i.status == "READY"]
        if not ready:
            raise NotYet(f"{args.module_id} has no READY instance")
        processes = {(p.kind, p.name) for p in ready[0].processes}
        wanted = {("workflow", args.workflow), ("pipeline", args.pipeline)}
        if not wanted <= processes:
            raise NotYet(f"discovery lists {sorted(processes)}, wants {sorted(wanted)}")
        return ready[0].processes

    processes = await wait(
        "discovery lists the workflow and the pipeline", deadline, listed
    )
    for process in processes:
        if not process.description:
            sys.exit(f"FAIL  {process.kind} {process.name} has no description")

    async def workflow() -> str:
        proxy = await module.get_workflow(args.workflow)  # describes it: the schema
        result = await proxy.run({"message": "smoke"}, timeout=60)
        if result != {"message": "smoke"}:
            raise NotYet(f"the workflow answered {result!r}")
        return "ok"

    await wait("workflow called over NATS", deadline, workflow)

    async def pipeline() -> str:
        from rdflib import RDFS, Literal, URIRef

        graph = await module.get_pipeline(args.pipeline).run(
            {"iri": "urn:smoke:a", "label": "Smoke"}, timeout=60
        )
        if (URIRef("urn:smoke:a"), RDFS.label, Literal("Smoke")) not in graph:
            raise NotYet(
                f"the pipeline's graph has {len(graph)} triples, not the label"
            )
        return "ok"

    await wait("pipeline called over NATS", deadline, pipeline)

    async def refused() -> str:
        from naas_abi_sdk.transport import RPCError

        try:
            await module.get_workflow("no_such_workflow").run({}, timeout=30)
        except RPCError as exc:
            if exc.code != "PROCESS_NOT_FOUND":
                raise NotYet(f"an unknown workflow answered {exc.code}") from exc
            return exc.code
        raise NotYet("an unknown workflow was run")

    await wait("an undeclared process is refused", deadline, refused)

    if args.job:

        async def job() -> str:
            run = await module.get_workflow(args.workflow).trigger(
                {"message": "job"}, idempotency_key=f"smoke-{int(time.time())}"
            )
            record = await run.wait(timeout=60)
            if record.get("status") != "SUCCEEDED" or record.get("result") != {
                "message": "job"
            }:
                raise NotYet(f"the job run ended {record!r}")
            return record["status"]

        await wait("workflow run as a job", deadline, job)
    await transport.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--module-id", required=True)
    parser.add_argument("--nats-url", required=True)
    parser.add_argument("--project", required=True, help="the discovery project")
    parser.add_argument("--key", required=True, help="the module's key")
    parser.add_argument("--workflow", required=True, help="a workflow's name")
    parser.add_argument("--pipeline", required=True, help="a pipeline's name")
    parser.add_argument(
        "--job", action="store_true", help="the workflow declares job settings"
    )
    parser.add_argument("--timeout", type=float, default=300.0)
    asyncio.run(main(parser.parse_args()))
