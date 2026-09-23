"""SDK-only provider/consumer processes: readiness, crash expiry and recovery."""

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path

from naas_abi_sdk import BaseModule, ModuleDependencies, run_module
from naas_abi_sdk.discovery import AgentDescriptor, DiscoveryConfiguration
from naas_abi_sdk.transport import RPCError

ROOT = Path(os.environ["DISCOVERY_REPORT_DIR"])


class Provider(BaseModule):
    module_id = "demo.research"
    agents = (AgentDescriptor("Researcher", "Research capability descriptor"),)

    async def run(self):
        (ROOT / "provider-ready").write_text(str(os.getpid()))
        await asyncio.Event().wait()


class Consumer(BaseModule):
    module_id = "demo.consumer"
    dependencies = ModuleDependencies(modules=("demo.research",))

    async def run(self):
        provider = self.engine.modules["demo.research"]
        initial = (await provider.ready_instances())[0].instance_id
        assert (await provider.list_agents())[0].name == "Researcher"
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
        await run_module(
            Provider if sys.argv[1] == "provider" else Consumer,
            url=os.environ["ABI_NATS_URL"],
            token=os.environ["ABI_SERVICE_TOKEN"],
            timeout=1,
            discovery=DiscoveryConfiguration(startup_timeout=15, refresh_seconds=0.05),
        )


if __name__ == "__main__":
    asyncio.run(main())
