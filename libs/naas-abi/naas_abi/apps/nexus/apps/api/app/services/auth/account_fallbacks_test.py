from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.auth.account_fallbacks import (
    effective_account_values,
)


def test_account_values_win() -> None:
    account = {"name": "Alice", "avatar": "/me.png", "organization": "Own", "job_title": "CTO"}
    members = [{"avatar": "/org.png", "organization": "Acme", "job_title": "Partner"}]

    assert effective_account_values(account, members) == account


def test_empty_account_fields_take_the_first_org_that_sets_them() -> None:
    account = {"name": "Alice", "avatar": None, "organization": "", "job_title": None, "bio": None}
    members = [
        {"avatar": None, "organization": "Acme", "job_title": None},
        {"avatar": "/org-b.png", "organization": "Beta", "job_title": "Partner"},
    ]

    assert effective_account_values(account, members) == {
        "name": "Alice",
        "avatar": "/org-b.png",
        "organization": "Acme",
        "job_title": "Partner",
        "bio": None,  # not a fallback field
    }


def test_no_memberships_keep_the_account_as_is() -> None:
    account = {"avatar": None, "organization": None, "job_title": None}
    assert effective_account_values(account, []) == account
