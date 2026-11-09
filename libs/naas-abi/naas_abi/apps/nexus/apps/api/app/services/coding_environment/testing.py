"""Tests of the code section: a real IAM, the kernel services wired with it, and
each request run as ``api`` for the signed-in user (as Nexus's identity
middleware does).

Workspaces ``ws-1`` and ``ws-2`` of ``org-1``. In ``ws-1``: ``owner``, ``admin``,
``member`` and ``viewer``; ``other`` is a member of ``ws-2`` only and ``both`` of
each; ``stranger`` holds nothing. The ``code`` feature is on for every role unless
a test turns it off for one.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import parse_qs

from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import KNOWN_FEATURE_KEYS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    SERVICE,
    WORKSPACE,
    org_container,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.engine.call_context import (
    CallContext,
    as_service_account,
    service_account,
    use_call_context,
    user,
)
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.coding_environment.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter as EnvironmentInMemoryAdapter,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentService import (
    CodingEnvironmentService,
)
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER
from naas_abi_core.services.iam.names import encode_segment
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter as SourceControlInMemoryAdapter,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
    repo_key,
)

ROLES = ("owner", "admin", "member", "viewer")


def code_flags(*, without_code: tuple[str, ...] = ()) -> FeatureFlagsConfig:
    """Every feature on for every role, bar ``code`` for the roles named."""
    everything = list(KNOWN_FEATURE_KEYS)
    without = [key for key in everything if key != "code"]
    return FeatureFlagsConfig(
        enabled_features=everything,
        role_baseline={role: without if role in without_code else everything for role in ROLES},
    )


@contextmanager
def code_iam(*, without_code: tuple[str, ...] = ()) -> Iterator[NexusIam]:
    nexus = NexusIam(code_flags(without_code=without_code))
    one = nexus.workspace("org-1", "ws-1")
    two = nexus.workspace("org-1", "ws-2")
    organization = org_container("org-1")
    for name in ROLES:
        nexus.grant(name, name, one)
        nexus.grant(name, name, organization)
    nexus.grant("both", "member", one)
    nexus.grant("both", "member", two)
    nexus.grant("other", "member", two)
    nexus.user("stranger")
    with nexus.installed():
        yield nexus


def principal_of(nexus: NexusIam, user_id: str) -> str:
    """The IAM principal of a Nexus user: what a verified session names."""
    with as_service_account("api"):
        return str(nexus.iam.ensure_user(LEGACY_NEXUS_ISSUER, user_id, provider="nexus").id)


class AsUser:
    """ASGI middleware: each request runs as ``api`` on behalf of ``holder['user']``,
    in the workspace its query names."""

    def __init__(self, app, nexus: NexusIam, holder: dict[str, str]) -> None:
        self.app, self.nexus, self.holder = app, nexus, holder

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        query = parse_qs(scope.get("query_string", b"").decode())
        workspace = (query.get("workspace_id") or [None])[0]
        context = CallContext(
            principal=service_account("api"),
            on_behalf_of=user(principal_of(self.nexus, self.holder["user"])),
            container=self.nexus.iam.container(SERVICE, WORKSPACE, workspace)
            if workspace
            else None,
        )
        with use_call_context(context):
            await self.app(scope, receive, send)


def kernel_services(
    nexus: NexusIam,
) -> tuple[CodingEnvironmentService, SourceControlService]:
    """The kernel services of the code section, wired with the test's IAM."""
    environments = CodingEnvironmentService(EnvironmentInMemoryAdapter())
    repos = SourceControlService(SourceControlInMemoryAdapter())
    for service in (environments, repos):
        service.set_services(IEngine.Services(iam=nexus.iam))
    return environments, repos


def place_repo(
    nexus: NexusIam,
    repos: SourceControlService,
    repo_id: str,
    workspace: str | None,
    *,
    org: str = "org-1",
) -> None:
    """Create ``repo_id`` and place it (with its branches and proposals) in
    ``workspace``; none leaves it on the platform."""
    owner, name = repo_id.split("/", 1)
    key = encode_segment(repo_key(repo_id))
    with as_service_account("engine"):
        repos.ensure_repo(owner=owner, name=name)
        if workspace is not None:
            container = workspace_container(org, workspace)
            nexus.iam.put_placement("source_control", key, container)
            nexus.iam.put_placement("source_control", f"{key}/*", container)
