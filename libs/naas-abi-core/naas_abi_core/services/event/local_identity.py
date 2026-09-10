"""Identity for work started from a terminal (``abi chat``, git tooling agents).

A terminal has no Nexus session, but it has a git author. The actor becomes
``email-sha256:<sha256 of the lower-cased git user.email>``: the event log still
holds no readable email, and the deploying app can match the hash to an account
(Nexus: ``nexus:user_email_sha256`` in graph/nexus-identity).
"""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager

from naas_abi_core.services.event.context import (
    event_actor_user_id,
    event_triggered_via,
)

EMAIL_ACTOR_PREFIX = "email-sha256:"


def email_sha256(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def email_actor_id(email: str) -> str:
    return f"{EMAIL_ACTOR_PREFIX}{email_sha256(email)}"


def git_user_email() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    email = completed.stdout.strip()
    return email or None


@contextmanager
def bind_local_identity() -> Iterator[None]:
    """Stamp events published inside the block with the terminal user.

    An identity already set (e.g. by an API request) is left alone.
    """
    tokens = []
    if event_actor_user_id.get() is None:
        email = git_user_email()
        if email:
            tokens.append(
                (event_actor_user_id, event_actor_user_id.set(email_actor_id(email)))
            )
    if event_triggered_via.get() is None:
        tokens.append((event_triggered_via, event_triggered_via.set("cli")))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
