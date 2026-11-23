"""A copy of an IAM decides as the IAM it was copied from (``shadow_iam``)."""

from __future__ import annotations

import json

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam import container_defaults
from naas_abi.apps.nexus.apps.api.app.services.iam import policy_tree_test as previous
from naas_abi.apps.nexus.apps.api.app.services.iam.policy_tree_test import (  # noqa: F401
    _remote_agents,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.shadow_iam import shadow_of, snapshot, store_of
from naas_abi_core.services.iam.IAMService import IAMService


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


@pytest.mark.asyncio
async def test_a_copy_kept_as_json_decides_as_the_original(nexus_db):
    # The access move keeps IAM as it was before it (``access_model``): its report
    # is read from that copy after a restart, so it goes through JSON.
    nexus = previous._world()
    with nexus.installed():
        subjects = previous._subjects(nexus)
        await previous._upgrade(nexus, nexus_db)
        async with nexus_db() as db:
            await container_defaults.migrate(db)
        nexus.iam.invalidate()
        before = previous._iam_decisions(nexus, subjects)
        kept = json.loads(json.dumps(snapshot(nexus.iam)))
        original = nexus.iam
        nexus.iam = IAMService(store_of(kept))
        try:
            copied = previous._iam_decisions(nexus, subjects)
        finally:
            nexus.iam = original
    assert copied == before
    assert any(before.values())
