"""Hexagonal harness layer for ABI Desktop.

``HarnessPort`` is the driver-side port every AI coding harness adapter
implements (opencode, pi, ...). ``create_harness`` builds the adapter
selected by the ``harness`` settings key. Event models normalize each
harness's stream into the SSE wire shapes the web UI already consumes.

This package is standalone: it must never import ``naas_abi`` or
``naas_abi_core`` (PyInstaller bundle constraint).
"""

from .factory import KNOWN_HARNESSES, create_harness
from .models import (
    DoneEvent,
    ErrorEvent,
    HarnessEvent,
    HarnessModel,
    HarnessProvider,
    ReasoningEvent,
    TextEvent,
    ToolEvent,
)
from .port import HarnessError, HarnessPort, HarnessUnavailableError

__all__ = [
    "KNOWN_HARNESSES",
    "create_harness",
    "DoneEvent",
    "ErrorEvent",
    "HarnessEvent",
    "HarnessModel",
    "HarnessProvider",
    "ReasoningEvent",
    "TextEvent",
    "ToolEvent",
    "HarnessError",
    "HarnessPort",
    "HarnessUnavailableError",
]
