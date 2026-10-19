"""The engine's IAM, as Nexus reaches it.

Nexus runs inside the engine and asks the engine's IAM service (in process).
Without one (Nexus alone) every decision is a refusal: there is no other source
of authorization. Tests install their own with ``configure``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.oidc.adapters.secondary.engine import (
    default_iam,
)


class IAMUnavailableError(RuntimeError):
    """Nexus has no IAM service to ask: it authorizes nothing."""


IamGetter = Callable[[], Any | None]

_getter: IamGetter = default_iam


def configure(getter: IamGetter | None) -> IamGetter:
    """Replace where IAM comes from (tests); ``None`` restores the engine's.
    Returns the previous getter."""
    global _getter
    previous = _getter
    _getter = getter if getter is not None else default_iam
    return previous


def iam() -> Any:
    """The IAM service, or ``IAMUnavailableError``."""
    service = _getter()
    if service is None:
        raise IAMUnavailableError("IAM is not available: Nexus authorizes nothing")
    return service
