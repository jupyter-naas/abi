"""Bring up TEN Agent for one voice call against an ABI voice gateway.

    uv run python -m naas_abi_marketplace.applications.ten_agent.scripts.run_ten_agent \\
        --dotenv .env --call-id call-1

Secrets come from the ABI secret service (dotenv adapter, environment first):
``OPENAI_API_KEY`` for TEN's ASR and TTS, and ``TEN_AGENT_GATEWAY_TOKEN`` (a
Nexus bearer token) for TEN to call ``/api/v1/voice``. Without that token the
graph runs, but every LLM turn is rejected by the gateway.

The first run installs TEN under ``--runtime-dir`` (about 115 MB: tman, the
pinned packages, a Python 3.10 venv); later runs reuse it. ``--prepare-only``
stops after the install.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from naas_abi_core.engine.engine_configuration.EngineConfiguration import GlobalConfig
from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
    DotenvSecretSecondaryAdaptor,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_marketplace.applications.ten_agent import (
    ABIModule,
    integration_configuration,
)
from naas_abi_marketplace.applications.ten_agent.domain.ports import VoiceSessionRequest
from naas_abi_marketplace.applications.ten_agent.integrations.TENAgentIntegration import (
    TENAgentIntegration,
    TENAgentRuntime,
)

GATEWAY_TOKEN_SECRET = "TEN_AGENT_GATEWAY_TOKEN"


def main(argv: list[str] | None = None) -> int:
    defaults = ABIModule.Configuration.model_fields
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dotenv", default=".env")
    parser.add_argument("--call-id", default=f"call-{uuid.uuid4().hex[:12]}")
    parser.add_argument("--agent", default=defaults["agent"].default)
    parser.add_argument(
        "--gateway-base-url", default=defaults["gateway_base_url"].default
    )
    parser.add_argument("--runtime-dir", default=defaults["runtime_dir"].default)
    parser.add_argument("--port", type=int, default=defaults["websocket_port"].default)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args(argv)

    secret = Secret(
        [
            DotenvSecretSecondaryAdaptor(
                path=args.dotenv, read_only=True, environment_first=True
            )
        ]
    )
    openai_api_key = secret.get("OPENAI_API_KEY")
    if not openai_api_key:
        print("Missing secret OPENAI_API_KEY", file=sys.stderr)
        return 2

    config = ABIModule.Configuration(
        global_config=GlobalConfig(ai_mode="cloud"),
        openai_api_key=openai_api_key,
        agent=args.agent,
        gateway_base_url=args.gateway_base_url,
        runtime_dir=args.runtime_dir,
        websocket_port=args.port,
    )
    integration_config = integration_configuration(config)
    runtime = TENAgentRuntime(integration_config)
    runtime.prepare()
    if args.prepare_only:
        print(f"TEN runtime ready in {runtime.root}")
        return 0

    gateway_token = secret.get(GATEWAY_TOKEN_SECRET) or ""
    if not gateway_token:
        print(
            f"Warning: {GATEWAY_TOKEN_SECRET} is not set; the gateway will reject LLM turns",
            file=sys.stderr,
        )
    session = TENAgentIntegration(integration_config).open_session(
        VoiceSessionRequest(
            call_id=args.call_id,
            agent=config.agent,
            gateway_base_url=config.gateway_base_url,
        ),
        gateway_token,
    )
    log_path = Path(runtime.root) / "app.log"
    proc = runtime.launch(session, log_path)
    print(f"TEN Agent call {session.call_id}: {session.url} (logs: {log_path})")
    try:
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        return proc.wait()


if __name__ == "__main__":
    raise SystemExit(main())
