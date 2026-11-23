from __future__ import annotations

from datetime import datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services import audit
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import (
    ADD_MEMBER,
    REMOVE_MEMBER,
    GroupChange,
)


@pytest.mark.asyncio
async def test_a_group_change_is_logged_under_who_asked(monkeypatch) -> None:
    logged: list[tuple[str, dict]] = []

    async def log(action: str, **kwargs) -> None:
        logged.append((action, kwargs))

    monkeypatch.setattr(audit, "log_audit_event", log)
    at = datetime(2026, 1, 1)
    await audit.audit_group_change(
        GroupChange(ADD_MEMBER, "grp_admins", "usr_bob", "abi:nexus:organization/acme", "alice", at)
    )
    await audit.audit_group_change(
        GroupChange(REMOVE_MEMBER, "grp_people", "usr_bob", None, None, at)
    )

    assert logged == [
        (
            "group_member_added",
            {
                "user_id": "alice",
                "resource_type": "iam_group",
                "resource_id": "grp_admins",
                "details": {"member_id": "usr_bob", "container": "abi:nexus:organization/acme"},
            },
        ),
        (
            "group_member_removed",
            {
                "user_id": None,
                "resource_type": "iam_group",
                "resource_id": "grp_people",
                "details": {"member_id": "usr_bob", "container": None},
            },
        ),
    ]
