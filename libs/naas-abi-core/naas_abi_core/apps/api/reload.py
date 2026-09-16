"""Source roots for local API reload, including ABI submodule layouts."""
from pathlib import Path


def reload_directories(project_root: Path) -> list[str]:
    # Native watchers do not reliably follow libs/* symlinks into .abi/libs.
    # Watch that real source directory explicitly when this project uses it.
    candidates = [project_root / name for name in ("src", "libs", ".abi/libs")]
    return list(dict.fromkeys(str(path.resolve()) for path in candidates if path.is_dir()))
