"""``repo_access``: what the workspace owns, and what already exists is placed once."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from naas_abi.apps.nexus.apps.api.app.services.coding_environment import repo_access
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.adapters.secondary.memory import (
    MemoryCodingEnvironmentStore,
)
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.port import (
    CodingEnvironmentRecord,
    CodingWorkspace,
)
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.testing import (
    code_iam,
    kernel_services,
    place_repo,
    principal_of,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    org_of,
    workspace_container,
    workspace_of,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.placements import (
    SOURCES,
    place_many,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.engine.call_context import as_service_account


def _store(
    defaults: list[tuple[str, str]] = (),
    environments: list[tuple[str, str, str, str | None]] = (),
) -> MemoryCodingEnvironmentStore:
    """The records the placement sources read: the workspaces' default repository
    (``(workspace, repo)``) and the coding environments (``(id, workspace, user, repo)``)."""
    return MemoryCodingEnvironmentStore(
        workspaces=[
            CodingWorkspace(id=ws, organization_id="org-1", coding_default_repo_id=repo)
            for ws, repo in defaults
        ],
        environments=[
            CodingEnvironmentRecord(id=env, workspace_id=ws, user_id=user, repo_id=repo)
            for env, ws, user, repo in environments
        ],
    )


@pytest.fixture
def nexus() -> Iterator[NexusIam]:
    with code_iam() as world:
        yield world


def _placed(nexus: NexusIam, service: str, key: str) -> tuple[str, str]:
    """``(org, workspace)`` of the container a resource is placed in, ``-`` for none."""
    container = nexus.iam.resolve_placement(service, key)
    return org_of(container) or "-", workspace_of(container) or "-"


def test_the_sources_are_registered_for_the_startup() -> None:
    assert repo_access.workspace_repositories in SOURCES
    assert repo_access.workspace_environments in SOURCES


@pytest.mark.asyncio
async def test_a_repository_a_workspace_recorded_is_placed_in_it(nexus: NexusIam) -> None:
    _, repos = kernel_services(nexus)
    place_repo(nexus, repos, "abi/lib", None)
    place_repo(nexus, repos, "abi/docs", None)
    db = _store(
        defaults=[("ws-1", "abi/lib")],
        environments=[("env-1", "ws-2", "member", "abi/docs")],
    )
    found = await repo_access.workspace_repositories(db)
    assert await place_many(found) == 4
    assert _placed(nexus, "source_control", "abi%2Flib") == ("org-1", "ws-1")
    # Its branches and proposals take the repository's placement.
    assert _placed(nexus, "source_control", "abi%2Flib/main") == ("org-1", "ws-1")
    assert _placed(nexus, "source_control", "abi%2Fdocs") == ("org-1", "ws-2")


@pytest.mark.asyncio
async def test_a_repository_claimed_by_two_workspaces_is_left_on_the_platform(
    nexus: NexusIam,
) -> None:
    _, repos = kernel_services(nexus)
    place_repo(nexus, repos, "abi/lib", None)
    db = _store(defaults=[("ws-1", "abi/lib"), ("ws-2", "ABI/Lib")])
    assert await repo_access.workspace_repositories(db) == []


@pytest.mark.asyncio
async def test_a_repository_already_placed_is_never_moved(nexus: NexusIam) -> None:
    _, repos = kernel_services(nexus)
    place_repo(nexus, repos, "abi/theirs", "ws-2")
    db = _store(defaults=[("ws-1", "abi/theirs")])
    assert await repo_access.workspace_repositories(db) == []
    assert _placed(nexus, "source_control", "abi%2Ftheirs") == ("org-1", "ws-2")


@pytest.mark.asyncio
async def test_the_shared_repository_and_odd_ids_belong_to_no_workspace(nexus: NexusIam) -> None:
    db = _store(
        defaults=[
            ("ws-1", repo_access.settings.coding_repo_id.upper()),
            ("ws-2", "not a repo"),
            ("ws-3", "../escape/x"),
        ],
        environments=[("env-1", "ws-1", "member", "no-owner")],
    )
    assert await repo_access.workspace_repositories(db) == []


@pytest.mark.asyncio
async def test_an_environment_is_placed_in_the_workspace_it_was_provisioned_for(
    nexus: NexusIam,
) -> None:
    db = _store(
        environments=[
            ("env-1", "ws-1", "member", None),
            ("env-2", "ws-2", "other", None),
        ]
    )
    assert await place_many(await repo_access.workspace_environments(db)) == 2
    member, other = principal_of(nexus, "member"), principal_of(nexus, "other")
    assert _placed(nexus, "coding_environment", f"{member}/env-1") == ("org-1", "ws-1")
    assert _placed(nexus, "coding_environment", f"{other}/env-2") == ("org-1", "ws-2")


@pytest.mark.asyncio
async def test_an_environment_placed_elsewhere_stays_there(nexus: NexusIam) -> None:
    member = principal_of(nexus, "member")
    with as_service_account("engine"):
        nexus.iam.put_placement(
            "coding_environment", f"{member}/env-1", workspace_container("org-1", "ws-2")
        )
    db = _store(environments=[("env-1", "ws-1", "member", None)])
    assert await repo_access.workspace_environments(db) == []
