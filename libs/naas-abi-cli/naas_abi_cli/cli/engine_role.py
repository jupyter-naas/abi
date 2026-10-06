"""The engine role of CLI commands that load an engine.

In NATS mode one engine serves the kernel services. A command like ``abi chat``
serves them itself when no engine does, and is a client of the serving one
otherwise (docs/adr/20261006_single-serving-engine.md).
"""

import os


def use_auto_engine_role() -> None:
    """Make engines of this process ``auto``, unless ``ABI_ENGINE_ROLE`` is set."""
    os.environ.setdefault("ABI_ENGINE_ROLE", "auto")
