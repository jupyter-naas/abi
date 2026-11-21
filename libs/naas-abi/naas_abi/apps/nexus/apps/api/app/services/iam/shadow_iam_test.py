"""A copy of an IAM decides as the IAM it was copied from (``shadow_iam``)."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam import container_defaults
from naas_abi.apps.nexus.apps.api.app.services.iam import policy_tree_test as previous
from naas_abi.apps.nexus.apps.api.app.services.iam.policy_tree_test import (  # noqa: F401
    _remote_agents,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.shadow_iam import shadow_of


@pytest.mark.asyncio
async def test_a_copy_decides_as_the_original(nexus_db):
    nexus = previous._world()
    with nexus.installed():
        subjects = previous._subjects(nexus)
        await previous._upgrade(nexus, nexus_db)
        async with nexus_db() as db:
            await container_defaults.migrate(db)
        nexus.iam.invalidate()
        before = previous._iam_decisions(nexus, subjects)
        original = nexus.iam
        nexus.iam = shadow_of(original)
        try:
            copied = previous._iam_decisions(nexus, subjects)
        finally:
            nexus.iam = original
    assert copied == before
    assert any(before.values())
