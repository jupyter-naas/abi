"""What each group of the access model is for: given at its creation, and to the groups
made before by each start (``describe_groups``)."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.iam.group_descriptions import (
    describe_groups,
    described,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    org_container,
    workspace_container,
)
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.names import PLATFORM

ORG = org_container("acme")
WS = workspace_container("acme", "ws-1")


def test_each_kind_of_group_says_what_it_is_for():
    kinds = {
        "level": described("Viewers", owner=PLATFORM, level=True),
        "members": described("Members", owner=PLATFORM, level=True),
        "platform admins": described("Platform admins", owner=PLATFORM),
        "workspace": described("Alpha workspace", owner=WS, membership_of=WS),
        "workspace admins": described("Alpha admins", owner=WS, membership_of=WS),
        "org admins": described("Acme admins", owner=ORG),
        "org people": described("Acme people", owner=ORG, membership_of=ORG),
        "runners": described("Workflow runners", owner=ORG),
        "models": described("Models · all", owner=PLATFORM),
    }
    assert all(kinds.values()), [k for k, v in kinds.items() if not v]
    assert len(set(kinds.values())) == len(kinds)  # one sentence per kind
    assert "belong to none of its workspaces" in kinds["org people"]
    # A group someone made: theirs to describe.
    assert described("Recruiters", owner=WS) is None
    assert described("Alpha admins", owner=PLATFORM) is None


def test_a_start_describes_the_groups_made_before_and_keeps_what_was_written(team):
    with as_service_account("engine"):
        models = team.iam.create_group("Models · all")
        written = team.iam.create_group("Platform admins", description="Ours.")
        custom = team.iam.create_group("Recruiters")
    assert models.description is None

    describe_groups(team.iam)
    describe_groups(team.iam)  # again: nothing more to do

    with as_service_account("engine"):
        assert team.iam.get_group(models.id).description == described(
            "Models · all", owner=PLATFORM
        )
        assert team.iam.get_group(written.id).description == "Ours."
        assert team.iam.get_group(custom.id).description is None
