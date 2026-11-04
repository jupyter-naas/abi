from __future__ import annotations

import json
from pathlib import Path

import pytest
from naas_abi_marketplace.applications.ten_agent.domain.ports import VoiceSessionRequest
from naas_abi_marketplace.applications.ten_agent.integrations.TENAgentIntegration import (
    SOURCE_EXTENSIONS,
    TENAPP_TEMPLATE_DIR,
    TENAgentIntegration,
    TENAgentIntegrationConfiguration,
    launch_env,
    redact,
    tman_asset,
)

OPENAI_KEY = "sk-test-openai-0000"
GATEWAY_TOKEN = "nexus-token-1111"


def _session(**overrides):
    cfg = TENAgentIntegrationConfiguration(openai_api_key=OPENAI_KEY, **overrides)
    return TENAgentIntegration(cfg).open_session(
        VoiceSessionRequest(
            call_id="call-7",
            agent="AbiAgent",
            gateway_base_url="http://127.0.0.1:9879/api/v1/voice",
        ),
        GATEWAY_TOKEN,
    )


def _nodes(prop: dict) -> dict:
    return {n["name"]: n for n in prop["ten"]["predefined_graphs"][0]["graph"]["nodes"]}


def test_template_wires_the_llm_node_to_the_voice_gateway_through_env() -> None:
    llm = _nodes(json.loads((TENAPP_TEMPLATE_DIR / "property.json").read_text()))["llm"]
    assert llm["addon"] == "openai_llm2_python"
    assert llm["property"]["base_url"] == "${env:TEN_LLM_BASE_URL}"
    assert llm["property"]["api_key"] == "${env:TEN_LLM_API_KEY}"
    assert llm["property"]["custom_headers"] == {
        "X-Voice-Session": "${env:TEN_VOICE_SESSION|}"
    }


def test_manifest_pins_registry_packages_not_repo_paths() -> None:
    deps = json.loads((TENAPP_TEMPLATE_DIR / "manifest.json").read_text())[
        "dependencies"
    ]
    assert all("path" not in d for d in deps)
    names = {d["name"] for d in deps}
    assert names >= {"openai_asr_python", "openai_llm2_python", "openai_tts2_python"}
    # Copied from the pinned TEN tag instead; see SOURCE_EXTENSIONS.
    assert not names & set(SOURCE_EXTENSIONS)
    assert set(SOURCE_EXTENSIONS) == {"websocket_server", "main_python"}


def test_rendered_graph_never_contains_a_credential() -> None:
    session = _session()
    rendered = json.dumps(session.engine_config)
    assert OPENAI_KEY not in rendered
    assert GATEWAY_TOKEN not in rendered
    assert OPENAI_KEY not in repr(session) and GATEWAY_TOKEN not in repr(session)
    assert session.env["OPENAI_API_KEY"] == OPENAI_KEY
    assert session.env["TEN_LLM_API_KEY"] == GATEWAY_TOKEN
    assert session.env["TEN_VOICE_SESSION"] == "call-7"
    assert session.env["TEN_LLM_MODEL"] == "AbiAgent"


def test_deployment_settings_are_applied_to_the_graph() -> None:
    session = _session(
        websocket_port=9100,
        asr_model="whisper-1",
        language="fr",
        vad_silence_ms=300,
        tts_voice="marin",
    )
    nodes = _nodes(session.engine_config)
    assert session.url == "ws://127.0.0.1:9100"
    assert session.transport == "websocket" and session.engine == "ten"
    assert nodes["websocket_server"]["property"]["port"] == 9100
    stt = nodes["stt"]["property"]["params"]
    assert stt["input_audio_transcription"]["model"] == "whisper-1"
    assert stt["input_audio_transcription"]["language"] == "fr"
    assert stt["turn_detection"]["silence_duration_ms"] == 300
    assert nodes["tts"]["property"]["params"]["voice"] == "marin"


def test_redact_hides_the_token_ten_logs_at_info_level() -> None:
    line = f"OpenAIChatGPT initialized with config: {GATEWAY_TOKEN}\n"
    assert (
        redact(line, [GATEWAY_TOKEN, ""])
        == "OpenAIChatGPT initialized with config: ***\n"
    )


def test_tman_asset_matches_ten_release_names() -> None:
    assert tman_asset("Darwin", "arm64") == "tman-mac-release-arm64.zip"
    assert tman_asset("Linux", "x86_64") == "tman-linux-release-x64.zip"
    with pytest.raises(RuntimeError):
        tman_asset("Windows", "arm64")


def test_launch_env_points_the_runtime_at_its_packages_and_drops_ambient_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    app = Path("/rt/tenapp")
    env = launch_env(
        app,
        Path("/py/lib/libpython3.10.dylib"),
        Path("/venv/site"),
        {"OPENAI_API_KEY": OPENAI_KEY},
    )
    assert "OPENAI_BASE_URL" not in env
    assert env["OPENAI_API_KEY"] == OPENAI_KEY
    assert env["TEN_PYTHON_LIB_PATH"] == "/py/lib/libpython3.10.dylib"
    assert (
        env["PYTHONPATH"].split(":")[0]
        == "/rt/tenapp/ten_packages/system/ten_runtime_python/lib"
    )
    assert env["PYTHONPATH"].endswith("/venv/site")
