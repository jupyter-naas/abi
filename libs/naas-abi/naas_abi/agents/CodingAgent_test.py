from pathlib import Path

from naas_abi.agents.CodingAgent import CodingAgent


def test_coding_agent_workdir_is_naas_abi_module_dir():
    agent = CodingAgent.New()
    expected = str(Path(__file__).resolve().parents[1])

    assert agent.conf.workdir == expected
