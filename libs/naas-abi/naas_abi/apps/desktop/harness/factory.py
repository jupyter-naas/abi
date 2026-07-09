"""Factory: build the harness adapter selected by app settings."""

from __future__ import annotations

from typing import Mapping

from .adapters.opencode import OpencodeHarnessAdapter
from .adapters.pi import PiHarnessAdapter
from .port import HarnessPort

KNOWN_HARNESSES = ("opencode", "pi")


def create_harness(settings: Mapping[str, str]) -> HarnessPort:
    """Build a :class:`HarnessPort` from desktop settings.

    Reads ``harness`` ("opencode" | "pi", default "opencode") plus
    ``workspace_root`` and the harness-specific binary key
    (``opencode_bin`` / ``pi_bin``).
    """
    harness = (settings.get("harness") or "opencode").strip().lower()
    workspace_root = settings.get("workspace_root") or "."

    if harness == "opencode":
        return OpencodeHarnessAdapter(
            workspace_root=workspace_root,
            opencode_bin=settings.get("opencode_bin") or "opencode",
        )
    if harness == "pi":
        return PiHarnessAdapter(
            workspace_root=workspace_root,
            pi_bin=settings.get("pi_bin") or "pi",
        )
    raise ValueError(
        f"unknown harness {harness!r}; expected one of {', '.join(KNOWN_HARNESSES)}"
    )
