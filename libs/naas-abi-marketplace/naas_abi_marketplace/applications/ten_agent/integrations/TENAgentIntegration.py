"""TEN Agent as a ``VoiceEnginePort``: one TEN app process per call.

The graph is ``tenapp/property.json``: TEN's ``websocket_server`` transport,
OpenAI streaming ASR, ``openai_llm2_python`` pointed at the ABI voice gateway,
and OpenAI TTS. Every credential and every per-call value in it is an
``${env:...}`` placeholder, so the rendered graph can be written to disk and
read by anyone; the values travel only in ``VoiceSession.env``.

``TENAgentRuntime`` does the I/O: fetch ``tman``, install the pinned packages,
build a Python 3.10 environment, and launch the app with its logs redacted.
"""

from __future__ import annotations

import io
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

from naas_abi_core.integration.integration import Integration, IntegrationConfiguration
from naas_abi_marketplace.applications.ten_agent.domain.ports import (
    VoiceEnginePort,
    VoiceSession,
    VoiceSessionRequest,
)

TENAPP_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "tenapp"
TEN_REPO = "https://github.com/TEN-framework/ten-framework"
# Copied from the pinned TEN tag instead of the registry: the turn controller
# ships only inside TEN's websocket example, and the published websocket_server
# 0.0.2 omits its Python sources (its manifest's package.include lists no *.py).
SOURCE_EXTENSIONS = {
    "main_python": "ai_agents/agents/examples/websocket-example/tenapp/ten_packages/extension/main_python",
    "websocket_server": "ai_agents/agents/ten_packages/extension/websocket_server",
}
# On top of the extensions' own requirements: ``samplerate`` 0.1.0 loads a
# system libsamplerate (an Intel build on mixed Homebrew Macs) and the TTS
# extension opens an HTTP/2 client.
EXTRA_REQUIREMENTS = ("samplerate>=0.2.1", "httpx[http2]")


@dataclass
class TENAgentIntegrationConfiguration(IntegrationConfiguration):
    openai_api_key: str
    runtime_dir: Path = field(
        default_factory=lambda: Path.home() / ".cache" / "abi" / "ten_agent"
    )
    ten_version: str = "0.11.74"
    websocket_host: str = "127.0.0.1"
    websocket_port: int = 8765
    language: str = "en"
    asr_model: str = "gpt-4o-transcribe"
    vad_silence_ms: int = 500
    tts_model: str = "gpt-4o-mini-tts"
    tts_voice: str = "coral"


class TENAgentIntegration(Integration, VoiceEnginePort):
    name = "ten"

    def __init__(self, configuration: TENAgentIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def render_property(self) -> dict[str, Any]:
        """The graph template with this deployment's non-secret settings applied."""
        cfg = self.__configuration
        prop = json.loads((TENAPP_TEMPLATE_DIR / "property.json").read_text())
        nodes = {
            n["name"]: n for n in prop["ten"]["predefined_graphs"][0]["graph"]["nodes"]
        }
        nodes["websocket_server"]["property"].update(
            {"host": cfg.websocket_host, "port": cfg.websocket_port}
        )
        stt = nodes["stt"]["property"]["params"]
        stt["input_audio_transcription"].update(
            {"model": cfg.asr_model, "language": cfg.language}
        )
        stt["turn_detection"]["silence_duration_ms"] = cfg.vad_silence_ms
        nodes["tts"]["property"]["params"].update(
            {"model": cfg.tts_model, "voice": cfg.tts_voice}
        )
        return prop

    def open_session(
        self, request: VoiceSessionRequest, gateway_token: str
    ) -> VoiceSession:
        cfg = self.__configuration
        return VoiceSession(
            engine=self.name,
            transport="websocket",
            url=f"ws://{cfg.websocket_host}:{cfg.websocket_port}",
            call_id=request.call_id,
            engine_config=self.render_property(),
            env={
                "OPENAI_API_KEY": cfg.openai_api_key,
                "TEN_LLM_API_KEY": gateway_token,
                "TEN_LLM_BASE_URL": request.gateway_base_url,
                "TEN_LLM_MODEL": request.agent,
                "TEN_VOICE_SESSION": request.call_id,
            },
        )


def redact(line: str, secrets: list[str]) -> str:
    """TEN's ``openai_llm2_python`` logs its ``api_key`` (the caller's ABI token)."""
    for secret in secrets:
        if secret:
            line = line.replace(secret, "***")
    return line


def tman_asset(system: str | None = None, machine: str | None = None) -> str:
    system = (system or platform.system()).lower()
    machine = (machine or platform.machine()).lower()
    os_name = {"darwin": "mac", "linux": "linux"}.get(system)
    arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "amd64": "x64"}.get(
        machine
    )
    if not os_name or not arch:
        raise RuntimeError(f"TEN ships no tman build for {system}/{machine}")
    return f"tman-{os_name}-release-{arch}.zip"


def launch_env(
    app_dir: Path, python_lib: Path, site_packages: Path, session_env: dict[str, str]
) -> dict[str, str]:
    """Environment for ``python main.py`` inside a TEN Python app."""
    system = app_dir / "ten_packages" / "system"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("OPENAI_", "TEN_"))}
    env.update(session_env)
    env["TEN_PYTHON_LIB_PATH"] = str(python_lib)
    env["PYTHONPATH"] = os.pathsep.join(
        str(p)
        for p in (
            system / "ten_runtime_python" / "lib",
            system / "ten_runtime_python" / "interface",
            system / "ten_ai_base" / "interface",
            system,
            site_packages,
        )
    )
    lib_var = "DYLD_LIBRARY_PATH" if sys.platform == "darwin" else "LD_LIBRARY_PATH"
    env[lib_var] = str(system / "ten_runtime" / "lib")
    return env


class TENAgentRuntime:
    """Installs and runs the TEN app under ``runtime_dir`` (throwaway, rebuildable)."""

    def __init__(self, configuration: TENAgentIntegrationConfiguration):
        self.cfg = configuration
        self.root = Path(configuration.runtime_dir).expanduser()
        self.app_dir = self.root / "tenapp"
        self.venv = self.root / "venv"
        self.tman = self.root / "ten_manager" / "bin" / "tman"

    def prepare(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._ensure_tman()
        self._ensure_app()
        self._ensure_venv()

    def _ensure_tman(self) -> None:
        if self.tman.exists():
            return
        url = f"{TEN_REPO}/releases/download/{self.cfg.ten_version}/{tman_asset()}"
        with urllib.request.urlopen(url) as resp:
            zipfile.ZipFile(io.BytesIO(resp.read())).extractall(self.root)
        self.tman.chmod(0o755)

    def _ensure_app(self) -> None:
        if not (self.app_dir / "main.py").exists():
            subprocess.run(
                [
                    str(self.tman),
                    "create",
                    "app",
                    "tenapp",
                    "--template",
                    "default_app_python",
                ],
                cwd=self.root,
                check=True,
            )
        shutil.copy(
            TENAPP_TEMPLATE_DIR / "manifest.json", self.app_dir / "manifest.json"
        )
        for name, path in SOURCE_EXTENSIONS.items():
            dest = self.app_dir / "ten_packages" / "extension" / name
            if not (dest / "addon.py").exists():
                shutil.rmtree(dest, ignore_errors=True)
                self._fetch_source_extension(path, dest)
        subprocess.run([str(self.tman), "install"], cwd=self.app_dir, check=True)

    def _fetch_source_extension(self, path: str, dest: Path) -> None:
        src = self.root / "ten-framework"
        if not src.exists():
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--filter=blob:none",
                    "--sparse",
                    "--branch",
                    self.cfg.ten_version,
                    f"{TEN_REPO}.git",
                    str(src),
                ],
                check=True,
            )
        subprocess.run(
            ["git", "sparse-checkout", "set", *SOURCE_EXTENSIONS.values()],
            cwd=src,
            check=True,
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            src / path, dest, ignore=shutil.ignore_patterns("tests", "__pycache__")
        )

    def _ensure_venv(self) -> None:
        if not (self.venv / "bin" / "python").exists():
            subprocess.run(
                ["uv", "venv", "-q", "-p", "3.10", str(self.venv)], check=True
            )
        reqs = sorted((self.app_dir / "ten_packages").glob("*/*/requirements.txt"))
        pip = [
            "uv",
            "pip",
            "install",
            "-q",
            "--python",
            str(self.venv / "bin" / "python"),
        ]
        subprocess.run([*pip, *[a for r in reqs for a in ("-r", str(r))]], check=True)
        # A second resolve: openai_asr_python pins samplerate==0.1.0.
        subprocess.run([*pip, *EXTRA_REQUIREMENTS], check=True)

    def _python_paths(self) -> tuple[Path, Path]:
        out = subprocess.run(
            [
                str(self.venv / "bin" / "python"),
                "-c",
                "import site,sys,sysconfig;print(sys.base_prefix);print(sysconfig.get_config_var('LDLIBRARY'));print(site.getsitepackages()[0])",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.split()
        return Path(out[0]) / "lib" / out[1], Path(out[2])

    def launch(self, session: VoiceSession, log_path: Path) -> subprocess.Popen[str]:
        """Write the graph, start the app, and copy its output to ``log_path`` redacted."""
        (self.app_dir / "property.json").write_text(
            json.dumps(session.engine_config, indent=2)
        )
        python_lib, site_packages = self._python_paths()
        env = launch_env(self.app_dir, python_lib, site_packages, session.env)
        proc = subprocess.Popen(
            [str(self.venv / "bin" / "python"), "main.py"],
            cwd=self.app_dir,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        secrets = [v for k, v in session.env.items() if k.endswith("API_KEY")]
        threading.Thread(
            target=_copy_redacted, args=(proc.stdout, log_path, secrets), daemon=True
        ).start()
        return proc


def _copy_redacted(stream: IO[str] | None, log_path: Path, secrets: list[str]) -> None:
    if stream is None:
        return
    with open(log_path, "a") as log:
        for line in stream:
            log.write(redact(line, secrets))
            log.flush()
