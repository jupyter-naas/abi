import asyncio
from typing import ClassVar

from naas_abi_core.services.agent.Agent import AgentSharedState
from naas_abi_core.services.agent.context import coding_harness_base
from naas_abi_core.services.agent.OpencodeAgent import (
    OpencodeAgent,
    OpencodeAgentConfiguration,
    OpencodeStartupError,
)
from naas_abi_core.services.coding_environment.adapters.secondary.OpencodeHarnessClient import (
    is_healthy,
)

NO_SANDBOX = (
    "No coding sandbox is bound to this conversation. Open a repository in Code "
    "and wait for its OpenCode runtime to become ready."
)


class CodingAgent(OpencodeAgent):
    """OpenCode in the caller's own coding sandbox.

    A module agent only when the ``naas_abi`` configuration sets
    ``opencode_coding_agent``. It never starts OpenCode on the API host: it
    talks to the OpenCode server of the coding sandbox bound to the
    conversation (``coding_harness_base``), and refuses without one.
    """

    enabled_by: ClassVar[str] = "opencode_coding_agent"

    name: str = "OpenCode Coding"
    description: str = "Coding agent backed by the OpenCode server of your coding sandbox."
    system_prompt: str = """
You are the coding agent of the user's coding sandbox.
You must work only in the sandbox's working directory.
Always read existing files before changing code.
Keep changes minimal and focused.
""".strip()
    logo_url: str = "naas_abi/assets/public/opencode-logo-light.png"
    model = "gpt-5.3-codex"
    provider = "opencode"

    @classmethod
    def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: dict | None = None,
    ) -> "CodingAgent":
        del agent_configuration

        return cls(
            configuration=OpencodeAgentConfiguration(
                # The sandbox's own checkout: nothing runs here.
                workdir="",
                port=None,
                name=cls.name,
                description=cls.description,
                model=cls.model,
                system_prompt=cls.system_prompt,
            ),
            agent_shared_state=agent_shared_state,
        )

    @property
    def _base_url(self) -> str:
        base = coding_harness_base.get()
        if not base:
            raise OpencodeStartupError(NO_SANDBOX)
        return base.rstrip("/")

    def start(self) -> None:
        """Nothing is started: the sandbox runs OpenCode. It must be bound and
        ready."""
        if not is_healthy(self._base_url, timeout_s=2.0):
            raise OpencodeStartupError(
                "The coding sandbox's OpenCode runtime is not ready yet."
            )

    async def _astart(self) -> None:
        # The health check is a blocking request: off the event loop, with the
        # conversation's context (its bound sandbox).
        await asyncio.to_thread(self.start)
