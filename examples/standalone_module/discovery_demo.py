"""SDK-only provider/consumer processes: readiness, crash expiry and recovery."""

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path

from naas_abi_sdk import BaseModule, ModuleDependencies, run_module
from naas_abi_sdk.discovery import AgentDescriptor, DiscoveryConfiguration
from naas_abi_sdk.listers import Listed, ListerQuery, lister
from naas_abi_sdk.permissions import default_manifest
from naas_abi_sdk.services.errors import NotFound, PermissionDenied
from naas_abi_sdk.transport import RPCError

ROOT = Path(os.environ["DISCOVERY_REPORT_DIR"])


class ResearchAgent:
    def __init__(self):
        self.calls = 0

    async def invoke(self, prompt, context):
        self.calls += 1
        if prompt == "slow":
            await asyncio.sleep(30)
        return f"remote:{prompt}:{self.calls}"

    async def stream_invoke(self, prompt, context):
        self.calls += 1
        yield {"event": "message", "data": "hello from the provider"}
        yield {"event": "done", "data": "[DONE]"}


# The actions the provider declares: its own catalog, ``demo_research``, sent
# with its manifest and registered when the manifest is approved.
BRIEFS = {
    "resource_types": [
        {"name": "brief", "id": "path", "description": "A research brief."}
    ],
    "actions": [
        {"name": "ExportBrief", "level": "read", "resource_types": ["brief"]},
        {"name": "DeleteBrief", "level": "write", "resource_types": ["brief"]},
    ],
}
CONSUMER_DEPENDENCIES = ModuleDependencies(modules=("demo.research",))


class Provider(BaseModule):
    module_id = "demo.research"
    iam_catalog = BRIEFS
    agents = (
        AgentDescriptor(
            "Researcher",
            "Research capability descriptor",
            capabilities=("agent.invoke.v1",),
        ),
    )
    dependencies = ModuleDependencies(services=("document",))

    async def on_initialized(self):
        self.expose_agent("Researcher", ResearchAgent())

    @lister("brief")
    async def briefs(self, query: ListerQuery):
        """Its briefs, for the policy builder: IAM asks over NATS and keeps
        what the caller may list."""
        return [
            Listed(f"abi:demo_research:brief/{name}", name, label=f"Brief {name}")
            for name in ("q1", "q2", "q3")
        ]

    async def run(self):
        # Its own actions, for itself: the approval let it act on its catalog.
        await self.require_action("ExportBrief", "brief", "q3")
        (ROOT / "provider-ready").write_text(str(os.getpid()))
        await asyncio.Event().wait()


class Consumer(BaseModule):
    module_id = "demo.consumer"
    dependencies = CONSUMER_DEPENDENCIES
    # Granted the provider's ExportBrief, not its DeleteBrief.
    permissions = {
        **default_manifest(CONSUMER_DEPENDENCIES),
        "statements": [
            *default_manifest(CONSUMER_DEPENDENCIES)["statements"],
            {
                "sid": "ExportResearchBriefs",
                "effect": "Allow",
                "actions": ["demo_research:ExportBrief"],
                # Its briefs at the platform and in any container.
                "resources": [
                    "abi:demo_research:brief/*",
                    "abi:*/demo_research:brief/*",
                ],
            },
        ],
    }

    async def declared_actions(self) -> dict[str, str]:
        """IAM decides on the provider's declared actions for this module."""
        iam = self.engine.services.iam
        found = {}
        for action in ("ExportBrief", "DeleteBrief"):
            try:
                await iam.require_declared(f"demo_research:{action}", "brief", ["q3"])
                found[action] = "allowed"
            except (PermissionDenied, NotFound):
                found[action] = "refused"
        return found

    async def run(self):
        provider = self.engine.modules["demo.research"]
        initial = (await provider.ready_instances())[0].instance_id
        assert (await provider.list_agents())[0].name == "Researcher"
        agent = await provider.get_agent("Researcher")
        answer = await agent.invoke("hello", invocation_id="demo-invoke", timeout=10)
        assert answer == "remote:hello:1"
        assert (
            await agent.invoke("hello", invocation_id="demo-invoke", timeout=10)
            == answer
        )
        events = [event async for event in agent.stream_invoke("stream", timeout=10)]
        assert events == [
            {"event": "message", "data": "hello from the provider"},
            {"event": "done", "data": "[DONE]"},
        ]
        handle = await agent.submit("slow")
        await handle.cancel()
        while (await handle.status()).status == "CANCELLING":
            await asyncio.sleep(0.05)
        assert (await handle.status()).status == "CANCELLED"
        declared = await self.declared_actions()
        assert declared == {"ExportBrief": "allowed", "DeleteBrief": "refused"}
        # The provider's lister, asked by IAM over NATS: the briefs this module
        # may act on (ExportBrief on every brief; the type has no list action).
        listed = await self.engine.services.iam.list_resources(
            "demo_research", "brief", text="q"
        )
        assert listed["listed"], listed
        assert [i["id"] for i in listed["items"]] == ["q1", "q2", "q3"], listed
        assert listed["items"][0]["label"] == "Brief q1"
        (ROOT / "agent-proxy.json").write_text(
            json.dumps(
                {
                    "answer": answer,
                    "stream_events": events,
                    "deduplicated": True,
                    "cancelled": True,
                    "declared_actions": declared,
                    "listed_briefs": [i["id"] for i in listed["items"]],
                }
            )
        )
        (ROOT / "consumer-ready").write_text(str(os.getpid()))
        lost = False
        while True:
            try:
                instances = await provider.ready_instances()
            except RPCError as exc:
                if exc.code not in ("MODULE_NOT_FOUND", "MODULE_UNAVAILABLE"):
                    raise
                lost = True
                (ROOT / "provider-lost").touch()
            else:
                if lost and instances[0].instance_id != initial:
                    (ROOT / "recovered.json").write_text(
                        json.dumps(
                            {
                                "initial_instance": initial,
                                "replacement_instance": instances[0].instance_id,
                                "agents": [
                                    a.name for a in await provider.list_agents()
                                ],
                            }
                        )
                    )
                    # Completed invocations can be read through a replacement process.
                    assert (
                        await agent.invocation("demo-invoke").status()
                    ).result == answer
                    return
            await asyncio.sleep(0.05)


async def orchestrate():
    processes = []

    async def start(role):
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-I", __file__, role
        )
        processes.append(process)
        return process

    async def wait_file(name):
        while not (ROOT / name).exists():
            if any(p.returncode not in (None, -9) for p in processes):
                raise RuntimeError("Discovery demo child exited early")
            await asyncio.sleep(0.05)

    async def scenario():
        consumer = await start("consumer")
        await asyncio.sleep(0.3)
        assert not (ROOT / "consumer-ready").exists()
        provider = await start("provider")
        await wait_file("consumer-ready")
        provider.kill()
        await provider.wait()
        await wait_file("provider-lost")
        replacement = await start("provider")
        await wait_file("recovered.json")
        assert await consumer.wait() == 0
        report = json.loads((ROOT / "recovered.json").read_text())
        report["agent_proxy"] = json.loads((ROOT / "agent-proxy.json").read_text())
        report.update(
            status="passed",
            consumer_pid=consumer.pid,
            provider_pid=provider.pid,
            replacement_pid=replacement.pid,
            core_installed=False,
        )
        (ROOT / "discovery.json").write_text(json.dumps(report))
        print(json.dumps({"discovery": report}), flush=True)

    try:
        await asyncio.wait_for(scenario(), 45)
    finally:
        for process in processes:
            if process.returncode is None:
                process.terminate()
        for process in processes:
            await process.wait()


async def main():
    assert importlib.util.find_spec("naas_abi_core") is None
    if len(sys.argv) == 1:
        await orchestrate()
    else:
        module = Provider if sys.argv[1] == "provider" else Consumer
        keys = json.loads(Path(os.environ["DEMO_KEYS"]).read_text())
        await run_module(
            module,
            url=os.environ["ABI_NATS_URL"],
            token=keys[module.module_id],
            timeout=1,
            discovery=DiscoveryConfiguration(startup_timeout=15, refresh_seconds=0.05),
        )


if __name__ == "__main__":
    asyncio.run(main())
