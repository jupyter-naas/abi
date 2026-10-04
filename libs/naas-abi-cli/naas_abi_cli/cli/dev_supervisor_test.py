import os
import signal
import subprocess
import sys
import threading
import time

import pytest

from naas_abi_cli.cli.dev_supervisor import supervise


class _Child:
    """A child process that exits with ``code`` once waited on."""

    def __init__(self, code: int, runs_for: float = 0.0) -> None:
        self.code, self.runs_for = code, runs_for
        self.terminated = False

    def wait(self, timeout: float | None = None) -> int:
        return self.code

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.terminated = True


def _run(codes, *, restart="on-failure", durations=None, stop_after=None):
    clock = {"now": 0.0}
    sleeps: list[float] = []
    log: list[str] = []
    stopped = threading.Event()
    spawned: list[list[str]] = []
    durations = list(durations or [0.0] * len(codes))

    def spawn(command):
        spawned.append(command)
        if stop_after is not None and len(spawned) > stop_after:
            raise AssertionError("restarted after being stopped")
        clock["now"] += durations[len(spawned) - 1]
        if stop_after is not None and len(spawned) == stop_after:
            stopped.set()
        return _Child(codes[len(spawned) - 1])

    class _Stopped:
        def is_set(self):
            return stopped.is_set()

        def wait(self, seconds):
            sleeps.append(seconds)
            return stopped.is_set()

    code = supervise(
        ["module"],
        restart=restart,
        spawn=spawn,
        stopped=_Stopped(),
        clock=lambda: clock["now"],
        initial_backoff=1.0,
        max_backoff=4.0,
        stable_seconds=60.0,
        log=log.append,
    )
    return code, len(spawned), sleeps, log


def test_a_failing_module_is_restarted_with_growing_backoff():
    code, runs, sleeps, log = _run([1, 1, 1, 1, 0])

    assert (code, runs) == (0, 5)
    assert sleeps == [1.0, 2.0, 4.0, 4.0]
    assert "exited with code 1; restarting in 1s" in log[0]


def test_the_backoff_resets_after_a_stable_run():
    _, _, sleeps, _ = _run([1, 1, 1, 0], durations=[0.0, 0.0, 120.0, 0.0])

    assert sleeps == [1.0, 2.0, 1.0]


def test_a_clean_exit_ends_on_failure_but_not_always():
    assert _run([0])[:2] == (0, 1)
    _, runs, sleeps, _ = _run([0, 0], restart="always", stop_after=2)
    assert runs == 2 and sleeps == [1.0]


def test_never_does_not_restart():
    assert _run([2], restart="never")[:2] == (2, 1)


def test_a_stopped_supervisor_does_not_restart():
    code, runs, _, _ = _run([143, 1], stop_after=1)

    assert runs == 1


def _supervisor(*command: str, backoff: str = "0.05") -> subprocess.Popen:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "naas_abi_cli.cli.dev_supervisor",
            "--initial-backoff",
            backoff,
            "--",
            *command,
        ],
        start_new_session=True,  # like `abi dev up`: its own process group
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def test_a_real_module_is_restarted_until_it_succeeds(tmp_path):
    counter = tmp_path / "runs"
    script = (
        "import pathlib, sys\n"
        f"p = pathlib.Path({str(counter)!r})\n"
        "n = int(p.read_text()) + 1 if p.exists() else 1\n"
        "p.write_text(str(n))\n"
        "sys.exit(0 if n == 3 else 1)\n"
    )

    process = _supervisor(sys.executable, "-c", script)
    out, _ = process.communicate(timeout=30)

    assert process.returncode == 0, out
    assert counter.read_text() == "3"
    assert out.decode().count("restarting in") == 2


@pytest.mark.skipif(sys.platform == "win32", reason="process groups")
def test_signalling_the_group_stops_the_module_and_the_supervisor(tmp_path):
    ready = tmp_path / "ready"
    script = (
        "import pathlib, time\n"
        f"pathlib.Path({str(ready)!r}).write_text('1')\n"
        "time.sleep(60)\n"
    )
    process = _supervisor(sys.executable, "-c", script)
    deadline = time.monotonic() + 15
    while not ready.exists() and time.monotonic() < deadline:
        time.sleep(0.05)

    os.killpg(process.pid, signal.SIGTERM)  # what `abi dev down` does

    process.communicate(timeout=20)
    with pytest.raises(ProcessLookupError):
        os.killpg(process.pid, 0)  # nobody left in the group
