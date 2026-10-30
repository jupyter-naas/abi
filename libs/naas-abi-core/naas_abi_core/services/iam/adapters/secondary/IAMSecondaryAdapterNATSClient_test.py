"""IAM through an actual NATS server: the primary and the core client."""

from __future__ import annotations

import asyncio
import threading
from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from naas_abi_core.engine import nats_runtime
from naas_abi_core.engine.call_context import CallContext, Principal, use_call_context
from naas_abi_core.engine.nats_auth import RenewingTokenSource
from naas_abi_core.engine.nats_rpc_integration_test import (  # noqa: F401 - pytest fixture
    SECRET,
    broker,
)
from naas_abi_core.engine.nats_test_tokens import OTHER_TOKENS, TEST_TOKENS
from naas_abi_core.services.iam import module_scopes, roles
from naas_abi_core.services.iam.adapters.primary.iam__primary_adapter__NATS import (
    IAMPrimaryAdapterNATS,
)
from naas_abi_core.services.iam.adapters.secondary.IAMSecondaryAdapterNATSClient import (
    IAMSecondaryAdapterNATSClient,
)
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMPorts import (
    IAMConflictError,
    IAMNotFoundError,
    PermissionDeniedError,
    RevisionConflictError,
)
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.names import PLATFORM, UNRESOLVED
from naas_abi_core.services.iam.tests import grant_contract as grants
from naas_abi_core.services.iam.tests import owned_scope_contract as owned
from naas_abi_core.services.iam.tests import sub_policy_contract as subs
from naas_abi_core.services.iam.tests.iam_harness import (
    NEXUS,
    TRIPLE_STORE,
    document,
    graph,
    org,
    statement,
    workspace,
)
from naas_abi_proto.iam.v1 import iam_pb2 as pb

pytestmark = pytest.mark.integration
BROKER = pytest.mark.parametrize("broker", [1024 * 1024], indirect=True)


@pytest.fixture
def iam_host(broker):  # noqa: F811 - imported pytest fixture
    url, _ = broker
    service = IAMService(IAMStoreMemory())
    service.bootstrap()
    service._register_catalog(TRIPLE_STORE)
    service._register_catalog(NEXUS)
    primary = IAMPrimaryAdapterNATS(service, SECRET)
    connection = nats_runtime.get_connection(url)
    nats_runtime.run_coro(primary.start(connection))
    nats_runtime.run_coro(connection.flush())
    clients: list[IAMSecondaryAdapterNATSClient] = []

    def client(
        identity: str, tokens=TEST_TOKENS, subject: str | None = None
    ) -> IAMSecondaryAdapterNATSClient:
        found = IAMSecondaryAdapterNATSClient(
            url, tokens.source(identity, subject=subject)
        )
        clients.append(found)
        return found

    try:
        yield SimpleNamespace(url=url, service=service, client=client)
    finally:
        for found in clients:
            found.close()
        nats_runtime.run_coro(primary.stop())
        nats_runtime.close()


@BROKER
def test_invitations_and_idp_bindings_round_trip(iam_host):
    engine = iam_host.client("engine")
    ws1 = _register(iam_host, "ws-1")
    grant = engine.create_pending_grant("builtin", "Bob@Example.com", roles.MEMBER, ws1)
    assert (grant.provider, grant.email, grant.scope) == (
        "builtin",
        "bob@example.com",
        ws1,
    )
    assert grant.created_at is not None
    assert engine.list_pending_grants(email="bob@example.com") == [grant]
    assert engine.list_pending_grants(provider="acme") == []

    bob = engine.ensure_user(
        "https://idp.example",
        "bob",
        provider="builtin",
        email="bob@example.com",
        email_verified=True,
    )
    claimed = engine.claim_pending_grants(bob.id)
    assert [(a.policy_id, a.principal_id, a.scope) for a in claimed] == [
        (roles.MEMBER, bob.id, ws1)
    ]
    assert engine.claim_pending_grants(bob.id) == []
    assert engine.list_pending_grants() == []
    other = engine.create_pending_grant(
        "builtin", "x@example.com", roles.VIEWER, workspace("w", "o")
    )
    assert engine.revoke_pending_grant(other.id) is True
    assert engine.revoke_pending_grant(other.id) is False

    binding = engine.bind_idp_group("acme", "Sales", roles.VIEWER, ws1)
    assert binding.group_id.startswith("grp_") and binding.attachment_id
    assert engine.list_idp_bindings(provider="acme") == [binding]
    assert engine.unbind_idp_group("acme", "Sales", roles.VIEWER, ws1)
    assert engine.list_idp_bindings() == []
    with pytest.raises(ValueError):
        engine.create_pending_grant("builtin", "not-an-email", roles.MEMBER, ws1)
    # A module that was granted nothing cannot invite.
    module = iam_host.client("module")
    with pytest.raises((PermissionDeniedError, IAMNotFoundError)):
        module.create_pending_grant("builtin", "y@example.com", roles.MEMBER, ws1)


def _register(iam_host, ws: str, org_id: str = "org-1") -> str:
    """Register an organisation and a workspace of it over NATS, as Nexus does
    with ``api``; the workspace's name."""
    api = iam_host.client("api")
    api.register_container("nexus", "organization", org_id)
    return api.register_container("nexus", "workspace", ws, parent=org(org_id)).name


@BROKER
def test_containers_round_trip(iam_host):
    api = iam_host.client("api")
    record = api.register_container("nexus", "organization", "org-1")
    assert (record.service, record.type, record.id, record.parent) == (
        "nexus",
        "organization",
        "org-1",
        PLATFORM,
    )
    ws1 = api.register_container("nexus", "workspace", "ws-1", parent=org())
    assert ws1.name == workspace("ws-1")
    # Again under the same parent: nothing changes; under another: refused.
    assert api.register_container("nexus", "workspace", "ws-1", parent=org()) == ws1
    with pytest.raises(IAMConflictError):
        api.register_container("nexus", "workspace", "ws-1")
    with pytest.raises(IAMNotFoundError):
        api.register_container("nexus", "workspace", "ws-2", parent=org("org-9"))
    # Reading a path needs an action of the type on it: the module holds none, so
    # a workspace that exists reads as one that does not; api holds nexus:*.
    module = iam_host.client("module")
    assert module.container("nexus", "workspace", "ws-1") is None
    assert module.container("nexus", "workspace", "ws-9") is None
    assert api.container("nexus", "workspace", "ws-1") == workspace("ws-1")
    # A module holds no create or delete action on the type.
    with pytest.raises((PermissionDeniedError, IAMNotFoundError)):
        module.register_container("nexus", "workspace", "ws-3", parent=org())
    with pytest.raises((PermissionDeniedError, IAMNotFoundError)):
        module.delete_container("nexus", "workspace", "ws-1")
    assert api.delete_container("nexus", "workspace", "ws-1") is True
    assert api.container("nexus", "workspace", "ws-1") is None
    assert api.delete_container("nexus", "workspace", "ws-1") is False
    with use_call_context(
        CallContext(
            principal=Principal(id="api", kind="service_account", name="api"),
            container=workspace("ws-1"),
        )
    ):
        assert iam_host.service.call_container() == UNRESOLVED


@BROKER
def test_a_listing_over_nats_is_the_callers(iam_host):
    from naas_abi_core.services.iam.listing import FunctionLister, ListedResource
    from naas_abi_core.services.iam.names import resource_name

    engine = iam_host.client("engine")
    ws1, ws2 = _register(iam_host, "ws-1"), _register(iam_host, "ws-2")
    bob = engine.ensure_user("https://idp.example", "bob")
    engine.attach_policy(roles.ADMIN, bob.id, ws1)

    def graphs(query):
        return [
            ListedResource(
                resource_name("triple_store", "graph", iri, container=where),
                iri,
                label=iri.upper(),
            )
            for where, iri in ((ws1, "a"), (ws1, "b"), (ws2, "c"))
        ]

    iam_host.service.register_lister("triple_store", "graph", FunctionLister(graphs))
    user = iam_host.client("api")
    with use_call_context(
        CallContext(
            principal=Principal(id="api", kind="service_account", name="api"),
            on_behalf_of=Principal(id=bob.id, kind="user"),
        )
    ):
        page = user.list_resources("triple_store", "graph", scope=ws1, limit=1)
        assert [(i.name, i.id, i.label) for i in page.items] == [
            (graph("a"), "a", "A")
        ]
        assert page.listed and page.next_cursor == graph("a")
        rest = user.list_resources(
            "triple_store", "graph", scope=ws1, cursor=page.next_cursor
        )
        assert [i.name for i in rest.items] == [graph("b")] and rest.next_cursor is None
        assert user.list_resources("triple_store", "graph", scope=ws2).items == ()
    stranger = iam_host.client("module")
    assert stranger.list_resources("triple_store", "graph", scope=ws1).items == ()
    # A type with no lister: offered as wildcards.
    assert engine.list_resources("triple_store", "view").listed is False
    with pytest.raises(IAMNotFoundError):
        engine.list_resources("nope", "graph")


@BROKER
def test_administration_round_trip(iam_host):
    engine = iam_host.client("engine")
    bob = engine.ensure_user("https://idp.example", "bob", email="bob@example.com")
    assert bob.kind == "user" and bob.email == "bob@example.com"
    assert bob.created_at is not None
    assert engine.get_principal(bob.id) == bob

    sales = engine.create_group("sales")
    engine.add_group_member(sales.id, bob.id)
    assert engine.list_group_members(sales.id) == [bob.id]
    mapping = engine.map_idp_group("acme", "Sales", sales.id)
    assert engine.list_idp_group_mappings(sales.id) == [mapping]

    policy = engine.create_policy(
        "read", document(statement("Allow", ["triple_store:Query"], ["*"], sid="Read"))
    )
    assert policy.revision == 1 and policy.document.statements[0].sid == "Read"
    attachment = engine.attach_policy(policy.id, sales.id)
    assert attachment in engine.list_attachments(principal_id=sales.id)
    ws1 = _register(iam_host, "ws-1")
    viewer = engine.attach_policy(roles.VIEWER, bob.id, ws1)
    assert viewer.scope == ws1

    explanation = engine.explain("triple_store:Query", graph("a"), principal_id=bob.id)
    assert explanation.allowed
    assert explanation.statement is not None
    assert explanation.statement.via_group == sales.id

    updated = engine.update_policy(
        policy.id,
        expected_revision=1,
        document=document(statement("Allow", ["triple_store:Insert"], ["*"])),
    )
    assert updated.revision == 2
    with pytest.raises(RevisionConflictError):
        engine.update_policy(policy.id, expected_revision=1, name="stale")
    with pytest.raises(IAMConflictError):
        engine.delete_policy(policy.id)  # still attached
    assert engine.detach_policy(policy.id, sales.id) is True
    engine.delete_policy(policy.id)
    with pytest.raises(IAMNotFoundError):
        engine.get_policy(policy.id)

    assert engine.suspend_principal(bob.id).status == "suspended"
    assert engine.resume_principal(bob.id).status == "active"
    page = engine.list_principals("user", limit=10)
    assert [p.id for p in page.items] == [bob.id] and page.next_after is None

    placement = engine.put_placement("document", "nexus-ws-1/*", ws1)
    assert placement.container == ws1
    assert engine.list_placements("document") == [placement]
    assert engine.delete_placement("document", "nexus-ws-1/*") is True
    assert engine.register_catalog(TRIPLE_STORE.to_dict()) is True


@BROKER
def test_decisions_are_about_the_verified_caller(iam_host):
    engine = iam_host.client("engine")
    account = engine.create_service_account("module/acme/people")
    module = iam_host.client("module/acme/people", subject=account.id)
    own = "abi:document:collection/people/contacts"
    assert not module.authorize("document:Find", own).allowed  # not approved yet
    submitted = module.submit_manifest(
        "people",
        "acme",
        document(
            statement(
                "Allow",
                ["document:*"],
                ["abi:document:collection/${module.id}/*"],
            )
        ),
    )
    assert submitted.manifest.status == "pending"
    assert engine.approve_manifest(account.id).status == "approved"
    other = "abi:document:collection/billing/invoices"
    assert module.authorize("document:Find", own).allowed
    assert not module.authorize("document:Find", other).allowed
    assert module.filter("document:Find", [other, own]).allowed == [own]
    # IAM's own operations need iam:* actions, which a module does not hold.
    with pytest.raises(IAMNotFoundError):
        module.create_policy("mine", document(statement("Allow", ["*"], ["*"])))


@BROKER
def test_a_remote_caller_gets_the_prefix_hints_in_process_gives(iam_host):
    """Services push lists down from ``filter(action, ()).prefix_hints``, and
    read none as "nothing can be allowed": the client must carry them."""
    engine = iam_host.client("engine")
    people = engine.create_service_account("people")
    policy = engine.create_policy(
        "people-graphs",
        document(statement("Allow", ["triple_store:Query"], [graph("people-*")])),
    )
    engine.attach_policy(policy.id, people.id)
    module = iam_host.client("people", subject=people.id)
    remote = module.filter("triple_store:Query", ()).prefix_hints
    with use_call_context(
        CallContext(
            principal=Principal(id=people.id, kind="service_account", name="people")
        )
    ):
        assert remote == iam_host.service.filter("triple_store:Query", ()).prefix_hints
    assert remote
    iam_host.client("engine").create_service_account("nobody")
    assert iam_host.client("nobody").filter("triple_store:Query", ()).prefix_hints == []


@BROKER
def test_api_calls_on_behalf_of_the_current_user(iam_host):
    engine = iam_host.client("engine")
    bob = engine.ensure_user("https://idp.example", "bob")
    engine.attach_policy(roles.VIEWER, bob.id, _register(iam_host, "ws-1"))
    api = iam_host.client("api")
    assert api.authorize("triple_store:Insert", graph("a")).allowed
    on_behalf = CallContext(
        principal=Principal(id="api", kind="service_account", name="api"),
        on_behalf_of=Principal(id=bob.id, kind="user"),
    )
    with use_call_context(on_behalf):
        assert api.authorize("triple_store:Query", graph("a")).allowed
        decision = api.authorize("triple_store:Insert", graph("a"))
        assert (decision.allowed, decision.visible) == (False, True)
        with pytest.raises(PermissionDeniedError):
            api.require("triple_store:Insert", graph("a"))

        class GraphNotFound(LookupError):
            pass

        with pytest.raises(GraphNotFound):
            api.require(
                "triple_store:Insert",
                graph("b", workspace="ws-2"),
                not_found=GraphNotFound,
            )


@BROKER
def test_a_declared_action_is_named_by_iam_in_the_container_of_the_call(iam_host):
    iam_host.service._register_catalog(module_scopes.CATALOG)
    iam_host.service._register_catalog(
        module_scopes.module_catalog(
            {
                "version": 1,
                "resource_types": [{"name": "report", "id": "path"}],
                "actions": [
                    {"name": "Export", "level": "read", "resource_types": ["report"]}
                ],
            },
            "acme.reports",
        )
    )
    engine = iam_host.client("engine")
    ws1 = _register(iam_host, "ws-1")
    ws2 = _register(iam_host, "ws-2")
    bob = engine.ensure_user("https://idp.example", "bob")
    engine.attach_policy(roles.ADMIN, bob.id, ws1)
    # No role holds a declared action: a policy grants it.
    reports = engine.create_policy(
        "reports",
        {
            "version": "2026-10-13",
            "statements": [
                {
                    "effect": "Allow",
                    "actions": ["acme_reports:*"],
                    "resources": ["${scope}/acme_reports:*"],
                }
            ],
        },
        scope=ws1,
    )
    engine.attach_policy(reports.id, bob.id, ws1)
    api = iam_host.client("api")
    on_behalf = CallContext(
        principal=Principal(id="api", kind="service_account", name="api"),
        on_behalf_of=Principal(id=bob.id, kind="user"),
        container=ws1,
    )
    with use_call_context(on_behalf):
        decision, resource = api.authorize_declared(
            "acme_reports:Export", "report", ["q3"]
        )
        assert decision.allowed
        assert resource == f"{ws1}/acme_reports:report/q3"
        refused, elsewhere = api.authorize_declared(
            "acme_reports:Export", "report", ["q3"], container=ws2
        )
        assert not refused.allowed and elsewhere == f"{ws2}/acme_reports:report/q3"
        # A container IAM does not know names nothing: not found.
        unknown, named = api.authorize_declared(
            "acme_reports:Export", "report", ["q3"], container=workspace("ws-9")
        )
        assert (unknown.allowed, unknown.visible) == (False, False)
        assert named == workspace("ws-9")
    with use_call_context(replace(on_behalf, container=None)):
        _, platform = api.authorize_declared("acme_reports:Export", "report", ["q3"])
        assert platform == "abi:acme_reports:report/q3"
        with pytest.raises(IAMNotFoundError):
            api.authorize_declared("triple_store:Query", "graph", ["a"])


@BROKER
def test_token_exchange_and_revocation_over_nats(iam_host):
    from naas_abi_core.engine.nats_auth import (
        AGENT_AUDIENCE,
        API_KEY_AUDIENCE,
        InvalidServiceTokenError,
    )
    from naas_abi_core.services.iam.IAMPorts import (
        TOKEN_TYPE_API_KEY,
        TOKEN_TYPE_JWT,
        TOKEN_TYPE_SESSION,
        KeyRefusedError,
        TokenExchange,
    )

    engine = iam_host.client("engine")
    bob = engine.ensure_user("https://idp.example", "bob")
    api = iam_host.client("api")
    issued = api.exchange_token(
        TokenExchange(
            subject_token=bob.id,
            subject_token_type=TOKEN_TYPE_SESSION,
            audience=AGENT_AUDIENCE,
            scope=(
                {
                    "effect": "Allow",
                    "actions": ["triple_store:Query"],
                    "resources": ["*"],
                },
            ),
        )
    )
    claims = iam_host.service.verifier().verify(issued.token)
    assert claims.subject == bob.id and claims.actor is not None
    assert claims.scope is not None and claims.scope[0]["actions"] == [
        "triple_store:Query"
    ]
    assert issued.audience == AGENT_AUDIENCE and issued.expires_at > 0

    # A refused subject is a refused credential, not a failure of the call.
    with pytest.raises(KeyRefusedError):
        api.exchange_token(
            TokenExchange(
                subject_token="abi_pk_aaaaaaaaaaaaaaaa_x",
                subject_token_type=TOKEN_TYPE_API_KEY,
                audience=API_KEY_AUDIENCE,
            )
        )
    with pytest.raises(InvalidServiceTokenError):
        api.exchange_token(
            TokenExchange(
                subject_token="not.a.jwt",
                subject_token_type=TOKEN_TYPE_JWT,
                audience=API_KEY_AUDIENCE,
            )
        )
    # The requester needs the action: a module does not hold it.
    account = engine.create_service_account("module/acme/people")
    module = iam_host.client("module/acme/people", subject=account.id)
    with pytest.raises(PermissionDeniedError):
        module.exchange_token(
            TokenExchange(
                subject_token=bob.id,
                subject_token_type=TOKEN_TYPE_SESSION,
                audience=AGENT_AUDIENCE,
            )
        )

    engine.revoke_tokens(bob.id)
    with pytest.raises(InvalidServiceTokenError, match="revoked"):
        iam_host.service.verifier().verify(issued.token)


@BROKER
def test_a_personal_key_is_created_and_listed_over_nats(iam_host):
    from datetime import UTC, datetime, timedelta

    from naas_abi_core.engine.nats_auth import CODING_AUDIENCE

    engine = iam_host.client("engine")
    bob = engine.ensure_user("https://idp.example", "bob")
    scope = (
        {"effect": "Allow", "actions": ["triple_store:Query"], "resources": ["*"]},
    )
    created = engine.create_key(
        bob.id,
        description="env",
        audience=CODING_AUDIENCE,
        resource="env-1",
        scope=scope,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    assert created.value.startswith("abi_pk_")
    [listed] = engine.list_keys(bob.id)
    assert (listed.kind, listed.audience, listed.resource) == (
        "personal",
        CODING_AUDIENCE,
        "env-1",
    )
    assert listed.scope == scope and listed.secret_hash == ""
    with pytest.raises(ValueError, match="audience"):
        engine.create_key(bob.id, audience="abi:session")


@BROKER
def test_invalid_policies_list_every_error(iam_host):
    engine = iam_host.client("engine")
    with pytest.raises(ValueError) as invalid:
        engine.create_policy(
            "bad",
            document(
                statement("Allow", ["triple_store:Teleport"], ["*"]),
                statement("Allow", ["triple_store:Query"], ["graph/x"]),
            ),
        )
    assert "triple_store:Teleport" in str(invalid.value)
    assert "graph/x" in str(invalid.value)


@BROKER
def test_a_wrong_secret_is_unauthenticated(iam_host):
    impostor = iam_host.client("engine", tokens=OTHER_TOKENS)
    with pytest.raises(RuntimeError, match="UNAUTHENTICATED"):
        impostor.authorize("triple_store:Query", graph("a"))


@BROKER
def test_changes_are_published(iam_host):
    import nats

    received: list[int] = []
    ready = threading.Event()

    async def listen():
        nc = await nats.connect(iam_host.url)

        async def on_change(msg):
            received.append(pb.ChangeEvent.FromString(msg.data).revision)
            ready.set()

        await nc.subscribe("abi.iam.v1.changed", cb=on_change)
        await nc.flush()
        return nc

    nc = nats_runtime.run_coro(listen())
    try:
        iam_host.client("engine").ensure_user("https://idp.example", "carol")
        assert ready.wait(5)
        assert received[-1] == iam_host.service.store.revision()
    finally:
        nats_runtime.run_coro(nc.close())


def test_malformed_requests_never_reach_the_service():
    service = Mock()
    primary = IAMPrimaryAdapterNATS(service, SECRET)
    request = SimpleNamespace(
        data=b"\xff",
        headers={"Nats-Auth-Token": TEST_TOKENS.token("engine")},
        respond=AsyncMock(),
    )
    try:
        asyncio.run(primary._handle(request, operation="authorize"))
        response = pb.AuthorizeResponse.FromString(request.respond.call_args.args[0])
        assert response.error.code == "INVALID_ARGUMENT"
        service.authorize.assert_not_called()
    finally:
        primary._dispatch.close()


@BROKER
@pytest.mark.parametrize("scenario", owned.SCENARIOS, ids=lambda s: s.__name__)
def test_owned_scenarios_over_nats(iam_host, scenario):
    """The same policies and groups of an org or a workspace, each call made over
    NATS as the user (a user's own token, as Nexus acts as its signed-in user)."""

    @contextmanager
    def as_user(record):
        source = RenewingTokenSource(
            record.id,
            lambda: TEST_TOKENS.issue(record.id, subject=record.id, kind="user"),
        )
        client = IAMSecondaryAdapterNATSClient(iam_host.url, source)
        try:
            yield client
        finally:
            client.close()

    scenario(iam_host.service, as_user)


@BROKER
@pytest.mark.parametrize("scenario", grants.SCENARIOS, ids=lambda s: s.__name__)
def test_grant_scenarios_over_nats(iam_host, scenario):
    """Grant only what you hold, each call made over NATS as the user, its
    token narrowed when the scenario says: the same refusals, by their code."""

    @contextmanager
    def as_user(record, scope=None):
        source = RenewingTokenSource(
            record.id,
            lambda: TEST_TOKENS.issue(
                record.id, subject=record.id, kind="user", scope=scope
            ),
        )
        client = IAMSecondaryAdapterNATSClient(iam_host.url, source)
        try:
            yield client
        finally:
            client.close()

    scenario(iam_host.service, as_user)


@BROKER
@pytest.mark.parametrize("scenario", subs.SCENARIOS, ids=lambda s: s.__name__)
def test_sub_policy_scenarios_over_nats(iam_host, scenario):
    """Sub-policies, each call made over NATS as the user: the same decisions,
    and the same refusals by their code and message."""

    @contextmanager
    def as_user(record):
        source = RenewingTokenSource(
            record.id,
            lambda: TEST_TOKENS.issue(record.id, subject=record.id, kind="user"),
        )
        client = IAMSecondaryAdapterNATSClient(iam_host.url, source)
        try:
            yield client
        finally:
            client.close()

    scenario(iam_host.service, as_user)


@BROKER
def test_a_narrowed_parent_narrows_its_sub_policies_over_nats_at_once(iam_host):
    """Parent P allows agents a and b, sub-policy S every agent: removing b from
    P over NATS refuses b to S's holder at the next decision, on the serving
    engine and in another process that hears the change event."""
    import nats

    t = subs.tree(iam_host.service)
    api = iam_host.client("api")
    for_bob = CallContext(
        principal=Principal(id="api", kind="service_account", name="api"),
        on_behalf_of=Principal(id=t.bob.id, kind="user"),
    )
    other = IAMService(iam_host.service.store)
    heard = threading.Event()

    async def listen():
        nc = await nats.connect(iam_host.url)

        async def on_change(_msg):
            other.refresh_if_changed()
            heard.set()

        await nc.subscribe("abi.iam.v1.changed", cb=on_change)
        await nc.flush()
        return nc

    nc = nats_runtime.run_coro(listen())
    try:
        with use_call_context(for_bob):
            assert api.authorize(subs.USE, subs.agent("b")).allowed
            assert other.authorize(subs.USE, subs.agent("b")).allowed
        heard.clear()
        narrowed = iam_host.client("engine").update_policy(
            t.parent.id, expected_revision=1, document=subs.allow(subs.agents("a"))
        )
        assert narrowed.revision == 2
        assert heard.wait(5)
        with use_call_context(for_bob):
            assert api.authorize(subs.USE, subs.agent("a")).allowed
            assert not api.authorize(subs.USE, subs.agent("b")).allowed
            assert other.authorize(subs.USE, subs.agent("a")).allowed
            assert not other.authorize(subs.USE, subs.agent("b")).allowed
    finally:
        nats_runtime.run_coro(nc.close())
