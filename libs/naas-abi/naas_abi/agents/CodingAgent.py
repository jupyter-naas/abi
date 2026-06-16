import os
from pathlib import Path
from typing import Optional

from naas_abi_core.services.agent.Agent import AgentSharedState
from naas_abi_core.services.agent.OpencodeAgent import (
    OpencodeAgent,
    OpencodeAgentConfiguration,
)


class CodingAgent(OpencodeAgent):
    name: str = "OpenCode Coding"
    description: str = (
        "Coding agent backed by an opencode server for the naas_abi module."
    )
    system_prompt: str = """
You are the coding agent for the naas_abi module.
You must work only in the provided working directory.
Always read existing files before changing code.
Keep changes minimal and focused.
""".strip()
    logo_url: str = "naas_abi/assets/public/opencode-logo-light.png"
    model = "gpt-5.3-codex"
    provider = "opencode"

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[dict] = None,
    ) -> "CodingAgent":
        del agent_configuration

        module_root = Path(__file__).resolve().parents[1]
        raw_port = os.getenv("NAAS_ABI_CODING_AGENT_PORT", "").strip()
        port = int(raw_port) if raw_port else None

        return cls(
            configuration=OpencodeAgentConfiguration(
                workdir=str(module_root),
                port=port,
                name=cls.name,
                description=cls.description,
                model=cls.model,
                system_prompt=cls.system_prompt,
            ),
            agent_shared_state=agent_shared_state,
        )
