from __future__ import annotations

import asyncio
import stat
import threading
from pathlib import Path

import pytest
from naas_abi import ABIModule
from naas_abi.agents.CodingAgent import CodingAgent
from naas_abi_core.module.ModuleAgentLoader import ModuleAgentLoader
from naas_abi_core.services.agent.context import coding_harness_base
from naas_abi_core.services.agent.OpencodeAgent import OpencodeStartupError


def test_the_coding_agent_keeps_off_the_module_unless_configured() -> None:
    assert CodingAgent not in ModuleAgentLoader.load_agents(ABIModule)
    off = ABIModule.Configuration.model_construct()
    assert CodingAgent not in ModuleAgentLoader.load_agents(ABIModule, off)
    on = ABIModule.Configuration.model_construct(opencode_coding_agent=True)
    assert CodingAgent in ModuleAgentLoader.load_agents(ABIModule, on)


def test_the_coding_agent_keeps_off_the_api_host(tmp_path: Path) -> None:
    """Without a coding sandbox bound to the conversation, nothing starts:
    no OpenCode process on the host, in the package or anywhere else."""
    record = tmp_path / "ran"
    fake = tmp_path / "opencode"
    fake.write_text(f"#!/bin/sh\npwd > {record}\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    agent = CodingAgent.New()
    agent.conf.opencode_bin = str(fake)
    package_root = Path(__file__).resolve().parents[1]
    assert Path(agent.conf.workdir or ".").resolve() != package_root
    token = coding_harness_base.set(None)
    try:
        with pytest.raises(OpencodeStartupError):
            agent.start()
    finally:
        coding_harness_base.reset(token)
    assert not record.exists()
    assert agent._proc is None


def test_the_coding_agent_talks_to_the_bound_sandbox() -> None:
    agent = CodingAgent.New()
    token = coding_harness_base.set("http://sandbox.internal:4096/")
    try:
        assert agent._base_url == "http://sandbox.internal:4096"
    finally:
        coding_harness_base.reset(token)


def test_the_coding_agent_keeps_its_health_check_off_the_event_loop(monkeypatch) -> None:
    seen: list[tuple[int, str | None]] = []

    def start(self) -> None:
        seen.append((threading.get_ident(), coding_harness_base.get()))

    monkeypatch.setattr(CodingAgent, "start", start)
    agent = CodingAgent.New()

    async def run() -> int:
        await agent._astart()
        return threading.get_ident()

    token = coding_harness_base.set("http://sandbox.internal:4096")
    try:
        loop_thread = asyncio.run(run())
    finally:
        coding_harness_base.reset(token)
    assert seen and seen[0][0] != loop_thread
    assert seen[0][1] == "http://sandbox.internal:4096"
