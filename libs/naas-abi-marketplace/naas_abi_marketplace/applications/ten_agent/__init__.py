"""TEN Agent: real-time voice calls over ABI agents.

    caller audio -> voice engine (TEN Agent) -> /api/v1/voice -> ABI agent
                 <- speech                   <- speakable sentences

The module owns the voice gateway route, the TEN graph (``tenapp/``) and its
bring-up (``scripts/run_ten_agent.py``). The engine sits behind
``domain.ports.VoiceEnginePort`` so OpenAI Realtime can be a second adapter.
Enabling the module is the feature flag: nothing is mounted until it is.

See ``README.md`` for measurements and the recommendation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_marketplace.applications.ten_agent.domain.speech import DEFAULT_FILLER

if TYPE_CHECKING:
    from naas_abi_marketplace.applications.ten_agent.integrations.TENAgentIntegration import (
        TENAgentIntegrationConfiguration,
    )


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration example:

        module: naas_abi_marketplace.applications.ten_agent
        enabled: false
        config:
            openai_api_key: "{{ secret.OPENAI_API_KEY }}"
            gateway_base_url: "http://127.0.0.1:9879/api/v1/voice"
            agent: "AbiAgent"
        """

        # OpenAI streaming ASR and TTS inside the TEN graph.
        openai_api_key: str
        # Where the engine reaches this API's voice route.
        gateway_base_url: str = "http://127.0.0.1:9879/api/v1/voice"
        agent: str = "AbiAgent"
        filler: str | None = DEFAULT_FILLER
        # Throwaway TEN runtime (tman, packages, venv); rebuilt by the bring-up script.
        runtime_dir: str = "~/.cache/abi/ten_agent"
        ten_version: str = "0.11.74"
        websocket_host: str = "127.0.0.1"
        websocket_port: int = 8765
        language: str = "en"
        asr_model: str = "gpt-4o-transcribe"
        vad_silence_ms: int = 500
        tts_model: str = "gpt-4o-mini-tts"
        tts_voice: str = "coral"

    def api(self, app: FastAPI) -> None:
        from naas_abi_marketplace.applications.ten_agent.adapters.primary.ten_agent__primary_adapter__FastAPI import (
            build_router,
        )
        from naas_abi_marketplace.applications.ten_agent.adapters.secondary.ten_agent__secondary_adapter__AbiInProcess import (
            AbiInProcessAgentStream,
        )

        app.include_router(
            build_router(AbiInProcessAgentStream(), filler=self.configuration.filler),
            prefix="/api/v1/voice",
        )


def integration_configuration(
    config: ABIModule.Configuration,
) -> TENAgentIntegrationConfiguration:
    from naas_abi_marketplace.applications.ten_agent.integrations.TENAgentIntegration import (
        TENAgentIntegrationConfiguration,
    )

    return TENAgentIntegrationConfiguration(
        openai_api_key=config.openai_api_key,
        runtime_dir=Path(config.runtime_dir).expanduser(),
        ten_version=config.ten_version,
        websocket_host=config.websocket_host,
        websocket_port=config.websocket_port,
        language=config.language,
        asr_model=config.asr_model,
        vad_silence_ms=config.vad_silence_ms,
        tts_model=config.tts_model,
        tts_voice=config.tts_voice,
    )
