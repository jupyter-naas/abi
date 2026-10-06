"""Passwords that ABI has shipped as defaults and must never authenticate.

Earlier CLI versions wrote these into ``.env`` for the seeded admin account, and
they are published in this repository, so they are refused at login and
rejected whenever a password is set.
"""

from __future__ import annotations

# The exact values ABI has shipped. The seeder bcrypt-checks existing admin
# hashes against these, so keep the list short.
SHIPPED_DEFAULT_PASSWORDS: tuple[str, ...] = ("Admin1234!", "admin", "admin1234")

_KNOWN_DEFAULT_PASSWORDS = frozenset(
    p.casefold()
    for p in (*SHIPPED_DEFAULT_PASSWORDS, "admin1234!", "abi", "password", "changeme")
)


def is_known_default_password(password: str | None) -> bool:
    return (password or "").strip().casefold() in _KNOWN_DEFAULT_PASSWORDS
