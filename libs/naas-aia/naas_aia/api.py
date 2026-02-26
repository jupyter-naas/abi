"""AIA API - SOUL."""

from pathlib import Path


def _package_dir() -> Path:
    return Path(__file__).parent


def load_soul() -> str:
    """Load SOUL.md from package."""
    soul = _package_dir() / "SOUL.md"
    if soul.exists():
        return soul.read_text()
    return ""
