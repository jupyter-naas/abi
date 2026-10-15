"""Run a broker, an engine, and wheel-installed modules as separate processes.

The broker admits two static users, ``engine`` and ``auth``, and asks the
engine (auth callout) about every other connection: each module logs in with
its own service key and gets the subjects its approved manifest allows. No
module holds a signing secret: the engine host creates one service account
and key per module (keys.json) and approves their manifests itself
(``iam.modules.auto_approve``, as ``abi dev up`` does).
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=HERE / "report.json")
    args = parser.parse_args()
    broker = shutil.which("nats-server")
    if not broker:
        raise SystemExit("Install nats-server with JetStream support first.")
    processes = []
    with tempfile.TemporaryDirectory(prefix="abi-module-demo-") as tmp:
        root = Path(tmp)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"nats://127.0.0.1:{port}"
        from naas_abi_core.engine.nats_nkeys import KeyPair

        engine_password, auth_password = (
            secrets.token_urlsafe(24),
            secrets.token_urlsafe(24),
        )
        callout = KeyPair.create()
        wheels = root / "wheels"
        for package in ("proto", "sdk"):
            run(
                "uv",
                "build",
                "--project",
                str(ROOT / f"libs/naas-abi-{package}"),
                "--out-dir",
                str(wheels),
                "--wheel",
            )
        run("uv", "venv", str(root / "worker-env"), "--python", sys.executable)
        worker_python = str(root / "worker-env/bin/python")
        run(
            "uv",
            "pip",
            "install",
            "--python",
            worker_python,
            *map(str, wheels.glob("*.whl")),
        )
        (root / "nats.conf").write_text(
            f'host: 127.0.0.1\nport: {port}\nmax_payload: 8388608\njetstream {{ store_dir: "{root}/jetstream" }}\n'
            "authorization {\n"
            "  users = [\n"
            f'    {{ user: engine, password: "{engine_password}", permissions: {{ publish: {{ deny: ["$SYS.>"] }}, subscribe: {{ deny: ["$SYS.>"] }} }} }}\n'
            f'    {{ user: auth, password: "{auth_password}", permissions: {{ subscribe: "$SYS.REQ.USER.AUTH", allow_responses: true }} }}\n'
            "  ]\n"
            f"  auth_callout {{ issuer: {callout.public_key}, auth_users: [engine, auth] }}\n"
            "}\n"
        )
        clean_env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PYTHONPATH", "ABI_SERVICE_KEY", "DEMO_CALLOUT_SEED")
        }
        with (
            (root / "broker.log").open("w") as broker_log,
            (root / "engine.log").open("w") as engine_log,
        ):
            try:
                processes.append(
                    subprocess.Popen(
                        [broker, "-c", str(root / "nats.conf")],
                        stdout=broker_log,
                        stderr=subprocess.STDOUT,
                    )
                )
                deadline = time.monotonic() + 10
                while True:
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                            break
                    except OSError:
                        if time.monotonic() > deadline:
                            raise RuntimeError("Broker did not start")
                        time.sleep(0.1)
                env = dict(
                    clean_env,
                    DEMO_DATA=tmp,
                    DEMO_NATS_URL=f"nats://engine:{engine_password}@127.0.0.1:{port}",
                    DEMO_AUTH_URL=f"nats://auth:{auth_password}@127.0.0.1:{port}",
                    DEMO_CALLOUT_SEED=callout.seed,
                    PYTHONPATH=str(HERE),
                )
                engine = subprocess.Popen(
                    [sys.executable, "-m", "engine_host"],
                    cwd=root,
                    env=env,
                    stdout=engine_log,
                    stderr=subprocess.STDOUT,
                )
                processes.append(engine)
                deadline = time.monotonic() + 90
                while not (root / "ready.json").exists():
                    if engine.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError(
                            "Engine startup failed:\n"
                            + (root / "engine.log").read_text()[-8000:]
                        )
                    time.sleep(0.2)
                report_path = root / "report.json"
                keys = json.loads((root / "keys.json").read_text())
                # The modules see the broker without a login: each brings its key.
                worker_env = dict(
                    clean_env,
                    ABI_NATS_URL=url,
                    DEMO_REPORT=str(report_path),
                )

                def as_module(module_id, **extra):
                    return dict(worker_env, ABI_SERVICE_KEY=keys[module_id], **extra)

                subprocess.run(
                    [worker_python, "-I", str(HERE / "discovery_demo.py")],
                    cwd=root,
                    env=dict(
                        worker_env,
                        DISCOVERY_REPORT_DIR=str(root),
                        DEMO_KEYS=str(root / "keys.json"),
                    ),
                    timeout=60,
                    check=True,
                )
                ergonomic_path = root / "ergonomic.json"
                ergonomic = subprocess.run(
                    [worker_python, "-I", str(HERE / "user_module.py")],
                    cwd=root,
                    env=as_module("demo.ergonomic", DEMO_REPORT=str(ergonomic_path)),
                    timeout=180,
                    check=False,
                )
                if ergonomic.returncode:
                    print((root / "engine.log").read_text()[-5000:])
                    raise SystemExit(1)
                result = subprocess.run(
                    [worker_python, "-I", str(HERE / "worker.py")],
                    cwd=root,
                    env=as_module("standalone-demo"),
                    timeout=180,
                    check=False,
                )
                # Keep the base worker's four-package isolation check intact.
                # A second environment exercises the optional LangChain facade.
                run("uv", "venv", str(root / "model-env"), "--python", sys.executable)
                model_python = str(root / "model-env/bin/python")
                run(
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    model_python,
                    *map(str, wheels.glob("*.whl")),
                    "langchain-core>=1,<2",
                )
                model_report = root / "models.json"
                subprocess.run(
                    [model_python, "-I", str(HERE / "model_module.py")],
                    cwd=root,
                    env=as_module("demo.models", DEMO_REPORT=str(model_report)),
                    timeout=60,
                    check=True,
                )
                agent_report = root / "model-agents.json"
                subprocess.run(
                    [sys.executable, "-I", str(HERE / "core_agent_consumer.py")],
                    cwd=root,
                    env=as_module(
                        "demo.agent-consumer",
                        DEMO_REPORT=str(agent_report),
                        DEMO_MODEL_PROVIDER_PID=str(engine.pid),
                    ),
                    timeout=60,
                    check=True,
                )
                report = json.loads(report_path.read_text())
                report["remote_model_agents"] = json.loads(agent_report.read_text())
                assert report["remote_model_agents"]["agent_pid"] != engine.pid
                report["remote_models"] = json.loads(model_report.read_text())
                report["ergonomic_module"] = json.loads(ergonomic_path.read_text())
                report["discovery"] = json.loads((root / "discovery.json").read_text())
                report.update(json.loads((root / "ready.json").read_text()))
                assert report["engine_pid"] != report["worker_pid"]
                email_files = list((root / "email").rglob("*.eml"))
                report["email_persisted"] = bool(email_files)
                report["broker_pid"] = processes[0].pid
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(json.dumps(report, indent=2) + "\n")
                print(f"Report: {args.report}")
                if result.returncode or not email_files:
                    print((root / "engine.log").read_text()[-5000:])
                    raise SystemExit(1)
            finally:
                for process in reversed(processes):
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()


if __name__ == "__main__":
    main()
