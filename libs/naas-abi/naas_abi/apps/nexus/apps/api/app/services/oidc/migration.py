"""Moving the users of the old built-in login to the built-in identity provider
(RFC §13).

The command (``abi user migrate``) makes each such person exist at the provider:
the same email, a new ``sub``. Nothing else changes yet: the account is linked at
the person's first sign-in with that address verified (``OidcSignInService``),
which keeps its IAM roles, groups and data. No password moves: the provider
signs people in with a code mailed to the address.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from naas_abi.apps.nexus.apps.api.app.services.oidc.port import OidcUser
from naas_abi.apps.nexus.apps.api.app.services.oidc.service import (
    PLACEHOLDER_EMAIL_DOMAIN,
    representable_email,
)

Outcome = Literal["created", "exists", "would_create", "skipped", "failed"]


@dataclass(frozen=True)
class MigratedUser:
    user_id: str
    email: str
    outcome: Outcome
    detail: str | None = None


# What the provider answers about a person (``ProvisionedUser`` of the identity
# service): only ``created`` and ``disabled`` are read.
Provisioner = Callable[[str, str], Any]
Finder = Callable[[str], Any | None]


def migrate_users(
    users: list[OidcUser],
    *,
    provision: Provisioner,
    find: Finder,
    apply: bool,
) -> list[MigratedUser]:
    """Make every user's email exist at the provider (``apply``), or say what
    would be done. One user's failure never stops the others."""
    results: list[MigratedUser] = []
    for user in users:
        email = user.email.strip().lower()
        if email.endswith("@" + PLACEHOLDER_EMAIL_DOMAIN) or not representable_email(email):
            results.append(
                MigratedUser(user.id, email, "skipped", "no email the provider can mail a code to")
            )
            continue
        try:
            if not apply:
                found = find(email)
                results.append(
                    MigratedUser(user.id, email, "exists" if found is not None else "would_create")
                )
                continue
            made = provision(email, user.name)
        except NotImplementedError as exc:
            # Every user would answer the same: stop, the provider is not one to provision.
            raise exc
        except Exception as exc:  # noqa: BLE001 - reported per user
            results.append(MigratedUser(user.id, email, "failed", str(exc)))
            continue
        outcome: Outcome = "created" if getattr(made, "created", False) else "exists"
        detail = "disabled at the provider" if getattr(made, "disabled", False) else None
        results.append(MigratedUser(user.id, email, outcome, detail))
    return results
