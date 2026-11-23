"""LibreOffice renders an office document as PDF, for a preview, kept apart from
the API process.

The converter parses user bytes with a large set of import filters, so each job
is a child process that gets:

- an environment of its own: ``PATH``, a locale, and a home and temporary
  directory in the job's folder. None of the API's variables, so none of its
  secrets, reach it;
- a LibreOffice profile of its own (``-env:UserInstallation``), in which links
  to other documents are never updated on load, references to untrusted
  locations are blocked and macros never run;
- a session of its own, with limits on address space, CPU time, written file
  size and open files (exec'd through ``prlimit``, or set on it right after it
  is spawned where ``prlimit`` is missing); at the deadline the whole session
  is killed;
- optionally a wrapper (``wrapper``), a command line the converter runs under,
  for a deployment that isolates it further (no network, another container).

``convert_to_pdf`` blocks: call it off the event loop.
"""

from __future__ import annotations

import os
import resource
import shlex
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

CONVERSION_TIMEOUT_SECONDS = 60
# Address space, CPU seconds, largest written file, open files.
_LIMITS = (
    (resource.RLIMIT_AS, 3 * 1024 * 1024 * 1024),
    (resource.RLIMIT_CPU, CONVERSION_TIMEOUT_SECONDS),
    (resource.RLIMIT_FSIZE, 256 * 1024 * 1024),
    (resource.RLIMIT_NOFILE, 1024),
)

# Link updates: 2 is "never" (Writer and Calc, Content/Update/Link).
PROFILE_SETTINGS = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="BlockUntrustedRefererLinks" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Writer/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>2</value></prop></item>
<item oor:path="/org.openoffice.Office.Calc/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>2</value></prop></item>
</oor:items>
"""


class ConversionFailed(Exception):
    """The converter did not produce a PDF (error, limit or deadline)."""


_LIMIT_FLAGS = {
    resource.RLIMIT_AS: "--as",
    resource.RLIMIT_CPU: "--cpu",
    resource.RLIMIT_FSIZE: "--fsize",
    resource.RLIMIT_NOFILE: "--nofile",
}


def limits_prefix() -> list[str]:
    """``prlimit`` (util-linux) with the limits, to exec the converter through:
    the limits hold from its first instruction, and no Python runs in the child
    between fork and exec. Empty when ``prlimit`` is not installed."""
    prlimit = shutil.which("prlimit")
    if not prlimit:
        return []
    return [prlimit, *(f"{_LIMIT_FLAGS[kind]}={value}" for kind, value in _LIMITS), "--"]


def _limit_spawned(pid: int) -> None:
    """Without ``prlimit``: the limits set on the child from here, right after
    it is spawned."""
    for kind, value in _LIMITS:
        try:
            resource.prlimit(pid, kind, (value, value))
        except (ValueError, OSError, AttributeError):
            pass


def converter_environment(job_dir: Path) -> dict[str, str]:
    """The whole environment the converter sees."""
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(job_dir),
        "TMPDIR": str(job_dir),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "SAL_USE_VCLPLUGIN": "svp",
    }


def converter_command(
    soffice: str, profile_dir: Path, out_dir: Path, input_path: Path, wrapper: str = ""
) -> list[str]:
    return [
        *shlex.split(wrapper),
        soffice,
        f"-env:UserInstallation={profile_dir.as_uri()}",
        "--headless",
        "--invisible",
        "--norestore",
        "--nolockcheck",
        "--nodefault",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(input_path),
    ]


def convert_to_pdf(
    soffice: str,
    filename: str,
    content: bytes,
    *,
    wrapper: str = "",
    timeout: float = CONVERSION_TIMEOUT_SECONDS,
) -> bytes:
    """The PDF LibreOffice renders from ``content`` (named ``filename``)."""
    with tempfile.TemporaryDirectory(prefix="nexus-office-preview-") as tmp:
        job_dir = Path(tmp)
        profile_dir = job_dir / "profile"
        (profile_dir / "user").mkdir(parents=True)
        (profile_dir / "user" / "registrymodifications.xcu").write_text(
            PROFILE_SETTINGS, encoding="utf-8"
        )
        out_dir = job_dir / "out"
        out_dir.mkdir()
        input_path = job_dir / Path(filename).name
        input_path.write_bytes(content)
        output_path = out_dir / f"{input_path.stem}.pdf"

        prefix = limits_prefix()
        process = subprocess.Popen(  # nosec B603 - fixed argv, no shell
            [*prefix, *converter_command(soffice, profile_dir, out_dir, input_path, wrapper)],
            cwd=job_dir,
            env=converter_environment(job_dir),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        if not prefix:
            _limit_spawned(process.pid)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_session(process)
            raise ConversionFailed("conversion timed out") from None
        finally:
            # Anything the converter left running in its session goes too.
            _kill_session(process)
        if process.returncode != 0 or not output_path.is_file():
            raise ConversionFailed(f"converter exited with {process.returncode}")
        return output_path.read_bytes()


def _kill_session(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
