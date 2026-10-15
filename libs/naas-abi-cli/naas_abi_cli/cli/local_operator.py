"""Who in-process work started from a terminal runs as.

A terminal has no session: the local operator runs the engine. Its work is the
engine's own (``engine``), acting for the terminal's git author when one is
known, as ``bind_local_identity`` names it, so events still say who chatted.
Without a context, every engine call would be anonymous, which IAM denies.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace


@contextmanager
def as_local_operator() -> Iterator[None]:
    from naas_abi_core.engine.call_context import (
        current_call_context,
        service_account,
        use_call_context,
    )
    from naas_abi_core.services.event.local_identity import bind_local_identity

    with (
        bind_local_identity(),
        use_call_context(
            replace(current_call_context(), principal=service_account("engine"))
        ),
    ):
        yield
