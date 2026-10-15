"""The account shows organization member values where it has none of its own.

Org admins set a member's picture, organization and job title in Organization
Settings > Users. When the account (Account Settings > Profile) leaves one of
those empty, the account shows the member value instead: from the organization
the user joined first that sets it. Values only ever flow org -> account; an
organization never shows the account's values for these fields.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

FALLBACK_FIELDS = ("avatar", "organization", "job_title")


def effective_account_values(
    account: Mapping[str, Any], member_profiles: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    """``account`` with FALLBACK_FIELDS filled from ``member_profiles`` (oldest first)."""
    effective = dict(account)
    profiles = list(member_profiles)
    for field in FALLBACK_FIELDS:
        if effective.get(field):
            continue
        effective[field] = next(
            (p.get(field) for p in profiles if p.get(field)), effective.get(field)
        )
    return effective
