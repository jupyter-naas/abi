import os
import subprocess
import sys
from pathlib import Path

REEXEC_ENV_VAR = "LOCAL_UV_RAN"
ABI_PROJECT_MARKERS = (
    "naas-abi-cli",
    "naas-abi-core",
    "naas-abi-marketplace",
    "[tool.uv.sources]",
)


def _is_abi_project(pyproject_path: Path) -> bool:
    try:
        pyproject_content = pyproject_path.read_text(encoding="utf-8").lower()
    except OSError:
        return False

    return any(marker in pyproject_content for marker in ABI_PROJECT_MARKERS)


def find_abi_project_root(start_path: Path | None = None) -> Path | None:
    current_path = (start_path or Path.cwd()).resolve()

    for candidate in (current_path, *current_path.parents):
        pyproject_path = candidate / "pyproject.toml"
        if pyproject_path.exists() and _is_abi_project(pyproject_path):
            return candidate

    return None


def maybe_rerun_in_project_context(argv: list[str]) -> bool:
    if os.getenv(REEXEC_ENV_VAR):
        return False
    if os.getenv("PYTEST_CURRENT_TEST") is not None or os.getenv("PYTEST_VERSION"):
        return False
    if "pytest" in Path(sys.argv[0]).name:
        return False

    project_root = find_abi_project_root()
    if project_root is None:
        return False

    arguments = [
        "uv",
        "run",
        "--project",
        str(project_root),
        "--active",
        "abi",
        *argv,
    ]

    try:
        subprocess.run(
            arguments,
            cwd=str(project_root),
            env={**os.environ, REEXEC_ENV_VAR: "true"},
            check=True,
        )
    except FileNotFoundError:
        return False
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode) from error

    return True
