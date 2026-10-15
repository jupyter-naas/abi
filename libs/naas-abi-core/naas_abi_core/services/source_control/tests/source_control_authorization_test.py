"""Source control authorizes every operation, in process and over NATS alike
(RFC §6.4); the forge user is always the call's, never a request field."""

from __future__ import annotations

import pytest
from naas_abi_core.engine.call_context import (
    CallContext,
    as_service_account,
    service_account,
    use_call_context,
)
from naas_abi_core.services.iam.IAMPorts import (
    PermissionDeniedError,
    ResourceNotFoundError,
)
from naas_abi_core.services.iam.tests.authorization_contract import (
    JWT_SECRET,
    AuthorizationContract,
    PrimaryServer,
    contract_iam,
    nats_server,
    wire,
)
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement
from naas_abi_core.services.source_control.adapters.primary.source_control__primary_adapter__NATS import (
    SourceControlPrimaryAdapterNATS,
)
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.adapters.secondary.SourceControlSecondaryAdapterNATSClient import (
    SourceControlSecondaryAdapterNATSClient,
)
from naas_abi_core.services.source_control.SourceControlPorts import (
    AccessDeniedError,
    BranchNotFoundError,
    RepoNotFoundError,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)

REPO = "acme/proj"
REPO_NAME = "abi:-:-:source_control:repo/acme%2Fproj"


def _facade(nats_url: str, identity: str) -> SourceControlService:
    return SourceControlService(
        SourceControlSecondaryAdapterNATSClient(nats_url, JWT_SECRET, identity)
    )


class SourceControlContract(AuthorizationContract):
    NOT_FOUND = (RepoNotFoundError,)

    @pytest.fixture
    def owner(self, contract_iam, tmp_path):
        return wire(SourceControlService(InMemoryAdapter()), contract_iam)

    def primary(self, owner):
        return SourceControlPrimaryAdapterNATS(owner, JWT_SECRET)

    def facade(self, nats_url, identity):
        return _facade(nats_url, identity)

    def prepare(self, owner):
        owner.ensure_repo(owner="acme", name="proj")

    def resource(self, owner):
        return REPO_NAME


class TestGetFile(SourceControlContract):
    ACTION = "source_control:GetFile"

    def call(self, service):
        return service.get_file(repo_id=REPO, path="README.md")


class TestAddCollaborator(SourceControlContract):
    """Granting write on a repository is an admin action (bug b)."""

    ACTION = "source_control:AddCollaborator"

    def call(self, service):
        return service.add_collaborator(repo_id=REPO, username="bob")


def _service() -> tuple[SourceControlService, IAMHarness, InMemoryAdapter]:
    iam = contract_iam()
    adapter = InMemoryAdapter()
    return wire(SourceControlService(adapter), iam), IAMHarness(iam), adapter


def test_a_token_is_minted_for_the_callers_own_forge_user_only():
    sc, h, adapter = _service()
    alice, bob = h.user("alice"), h.user("bob")
    with h.as_(actor="api", on_behalf_of=bob):
        sc.ensure_user(email="bob@example.com", username="bob")
    with h.as_(actor="api", on_behalf_of=alice):
        sc.ensure_user(email="alice@example.com", username="alice")
        # A request naming another user is ignored: the token is alice's.
        sc.mint_git_token(user_id="bob")
    assert adapter.find_user(external_id=alice.id) == "alice"
    with h.as_(actor="api", on_behalf_of=alice), pytest.raises(AccessDeniedError):
        # Nor can alice take over bob's forge user by naming it.
        sc.ensure_user(email="alice@example.com", username="bob")


def test_minting_needs_a_forge_user_of_ones_own():
    sc, h, _ = _service()
    carol = h.user("carol")
    with (
        h.as_(actor="api", on_behalf_of=carol),
        pytest.raises(Exception, match="ensure_user first"),
    ):
        sc.mint_git_token(user_id="carol")


def test_a_service_account_without_a_policy_cannot_mint():
    sc, h, _ = _service()
    h.service_account("ci-nightly")
    with h.as_(actor="ci-nightly"), pytest.raises(ResourceNotFoundError):
        sc.ensure_user(email="ci@example.com", username="ci")
    with h.as_(actor="ci-nightly"), pytest.raises(ResourceNotFoundError):
        sc.mint_git_token()


def test_over_nats_the_token_is_the_callers_whatever_the_request_names():
    sc, h, adapter = _service()
    alice = h.user("alice")
    with nats_server() as url:
        server = PrimaryServer(url, SourceControlPrimaryAdapterNATS(sc, JWT_SECRET))
        server.start()
        remote = _facade(url, "api")
        try:
            with h.as_(actor="api", on_behalf_of=alice):
                remote.ensure_user(
                    email="alice@example.com", username="alice", external_id="bob"
                )
                assert remote.mint_git_token(user_id="bob")
        finally:
            remote.adapter.close()
            server.stop()
    assert adapter.find_user(external_id=alice.id) == "alice"
    assert adapter.find_user(external_id="bob") is None


def test_a_repository_is_placed_in_the_target_workspace_and_others_cannot_claim_it():
    sc, h, _ = _service()
    h.admin("put_scope", "org-1", "ws-1")
    h.admin("put_scope", "org-1", "ws-2")
    with use_call_context(
        CallContext(principal=service_account("engine"), workspace_id="ws-1")
    ):
        sc.ensure_repo(owner="acme", name="team")
    assert h.iam.resolve_placement("source_control", "acme%2Fteam") == (
        "org-1",
        "ws-1",
    )
    assert h.iam.resolve_placement("source_control", "acme%2Fteam/main") == (
        "org-1",
        "ws-1",
    )
    bob = h.user("bob")
    h.grant(bob.id, statement("Allow", ["source_control:*"], ["abi:org-1:ws-2:*"]))
    with (
        use_call_context(
            CallContext(
                principal=service_account("api"),
                on_behalf_of=h.context(bob).principal,
                workspace_id="ws-2",
            )
        ),
        pytest.raises(RepoNotFoundError),
    ):
        sc.ensure_repo(owner="acme", name="team")


def test_a_repository_that_predates_iam_stays_on_the_platform():
    sc, h, adapter = _service()
    adapter.ensure_repo(owner="acme", name="legacy")
    h.admin("put_scope", "org-1", "ws-1")
    bob = h.user("bob")
    h.grant(bob.id, statement("Allow", ["source_control:*"], ["abi:org-1:ws-1:*"]))
    with (
        use_call_context(
            CallContext(
                principal=service_account("api"),
                on_behalf_of=h.context(bob).principal,
                workspace_id="ws-1",
            )
        ),
        pytest.raises(RepoNotFoundError),
    ):
        sc.ensure_repo(owner="acme", name="legacy")
    assert h.iam.resolve_placement("source_control", "acme%2Flegacy") == ("-", "-")


def test_lists_keep_what_the_caller_may_list():
    sc, h, _ = _service()
    with as_service_account("engine"):
        sc.ensure_repo(owner="acme", name="a")
        sc.ensure_repo(owner="acme", name="b")
        sc.create_branch(repo_id="acme/a", name="feature", from_ref="main")
    bob = h.user("bob")
    h.grant(
        bob.id,
        statement(
            "Allow",
            ["source_control:ListRepos", "source_control:ListContents"],
            ["abi:-:-:source_control:repo/acme%2Fa"],
        ),
        statement(
            "Allow",
            ["source_control:ListBranches"],
            ["abi:-:-:source_control:branch/acme%2Fa/feature"],
        ),
    )
    with h.as_(actor="api", on_behalf_of=bob):
        assert [r.name for r in sc.list_repos()] == ["a"]
        assert [b.name for b in sc.list_branches(repo_id="acme/a")] == ["feature"]
        with pytest.raises(RepoNotFoundError):
            sc.list_branches(repo_id="acme/b")


def test_writing_a_branch_needs_the_branch_action():
    sc, h, _ = _service()
    with as_service_account("engine"):
        sc.ensure_repo(owner="acme", name="a")
    bob = h.user("bob")
    main = "abi:-:-:source_control:branch/acme%2Fa/main"

    def write() -> None:
        sc.upsert_file(
            repo_id="acme/a", path="x.txt", content="x", message="m", branch="main"
        )

    with h.as_(actor="api", on_behalf_of=bob), pytest.raises(BranchNotFoundError):
        write()
    h.grant(bob.id, statement("Allow", ["source_control:ListBranches"], [main]))
    with h.as_(actor="api", on_behalf_of=bob), pytest.raises(PermissionDeniedError):
        write()
    h.grant(bob.id, statement("Allow", ["source_control:UpsertFile"], [main]))
    with h.as_(actor="api", on_behalf_of=bob):
        write()
