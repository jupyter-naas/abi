"""Run a broker, an engine, and a wheel-installed worker as separate processes."""

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
        )
        clean_env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("PYTHONPATH", "ABI_SERVICE_TOKEN", "DEMO_SIGNING_KEY")
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
                    DEMO_NATS_URL=url,
                    DEMO_SIGNING_KEY=secrets.token_urlsafe(48),
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
                worker_env = dict(
                    clean_env,
                    ABI_NATS_URL=url,
                    ABI_SERVICE_TOKEN=(root / "token").read_text(),
                    DEMO_REPORT=str(report_path),
                )
                result = subprocess.run(
                    [worker_python, "-I", str(HERE / "worker.py")],
                    cwd=root,
                    env=worker_env,
                    timeout=180,
                    check=False,
                )
                report = json.loads(report_path.read_text())
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
