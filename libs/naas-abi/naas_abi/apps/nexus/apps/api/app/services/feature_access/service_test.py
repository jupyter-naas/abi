"""Workspace settings > General › Features and Agents/Apps over a real IAM and a
SQLite database: each choice is what the workspace's allow-list, "<W> access",
offers; IAM decides every write as the caller, a Deny elsewhere still wins, and a
statement written on the policy's page is left alone.

Acme offers Chat and Files and the module acme.sales; its workspace Alpha offers Chat
and Files. Olivia owns both (in "Alpha admins", so she holds what Alpha offers); Bob,
Carol and Dave are members of Alpha, and "Alpha members" holds "Alpha access" as the
workspace group will (S2); Erin is given an admin role at Alpha by hand, outside the
groups, so she holds IAM's rights there and no feature; root is a platform admin."""

from __future__ import annotations

from datetime import datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.models import UserModel
from naas_abi.apps.nexus.apps.api.app.services.feature_access.adapters.secondary.postgres import (  # noqa: E501
    SqlFeaturePolicyStore,
)
from naas_abi.apps.nexus.apps.api.app.services.feature_access.port import FeatureChange
from naas_abi.apps.nexus.apps.api.app.services.feature_access.service import (
    FeatureAccessService,
    OfferChange,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
    CONTAINER_DEFAULTS,
    SqlDefaultsStore,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    nexus_resource,
    org_container,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
    Offer,
    offer_document,
    offer_of,
    with_offer,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
    EngineIamGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.testing import MemoryAudit
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (  # noqa: E501
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import OrganizationService
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (  # noqa: E501
    WorkspaceSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceCreateInput
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import WorkspaceService
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam import module_scopes
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError, PermissionDeniedError

NOW = datetime(2026, 1, 1)
FEATURES = ["chat", "files", "marketplace"]
ALPHA = workspace_container("acme", "alpha")
USE = "nexus:UseFeature"


def _features(*keys: str) -> dict:
    return {
        "version": "2026-10-13",
        "statements": [
            {
                "effect": "Allow",
                "actions": [USE],
                "resources": [f"${{scope}}/nexus:feature/{k}" for k in keys],
            }
        ],
    }


def _forget() -> None:
    CONTAINER_DEFAULTS._known.clear()
    CONTAINER_DEFAULTS._missing.clear()
    CONTAINER_DEFAULTS.session_factory = None


@pytest.fixture
def enabled_features() -> list[str]:
    """The deployment's features (a test class may enable more)."""
    return FEATURES


@pytest.fixture
def nexus(enabled_features):
    _forget()
    world = NexusIam(
        FeatureFlagsConfig(enabled_features=enabled_features), features_with_roles=False
    )
    with world.installed():
        yield world
    _forget()


@pytest.fixture
async def acme(nexus, nexus_db):
    """Acme and Alpha made as the routes make them, their offers set."""
    async with nexus_db() as db:
        for user_id in ("olivia", "bob", "carol", "dave", "frank", "erin", "root"):
            db.add(
                UserModel(
                    id=user_id,
                    email=f"{user_id}@example.com",
                    name=user_id.title(),
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        await db.flush()
        orgs = OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))
        await orgs.create_organization(
            name="Acme", slug="acme", owner_id="olivia", now=NOW, org_id="acme"
        )
        workspaces = WorkspaceService(adapter=WorkspaceSecondaryAdapterPostgres(db=db))
        await workspaces.create_workspace(
            WorkspaceCreateInput(
                name="Alpha", slug="alpha", owner_id="olivia", organization_id="acme", id="alpha"
            )
        )
        await db.commit()
        store = SqlDefaultsStore(db)
        org_record = await store.get(org_container("acme"))
        record = await store.get(ALPHA)
    for user_id in ("bob", "carol", "dave"):
        await MEMBERSHIPS.grant(user_id, "member", ALPHA)
    nexus.platform_admin("root")
    with use_call_context(NexusIam.context("root")):
        nexus.iam.update_policy(
            org_record.access_policy_id,
            expected_revision=1,
            document=offer_document(Offer.of(modules=["acme.sales"], features=["chat", "files"])),
        )
        access = nexus.iam.get_policy(record.access_policy_id)
        nexus.iam.update_policy(
            record.access_policy_id,
            expected_revision=access.revision,
            document=offer_document(Offer.of(features=["chat", "files"])),
        )
    # As the workspace group will (S2): everyone in Alpha holds what it offers.
    with as_service_account("api"):
        nexus.iam.attach_policy(record.access_policy_id, record.members_group_id, ALPHA)
    return record


@pytest.fixture
def audit() -> MemoryAudit:
    return MemoryAudit()


@pytest.fixture
def service(nexus_db, audit) -> FeatureAccessService:
    return FeatureAccessService(
        EngineIamGateway(),
        SqlFeaturePolicyStore(nexus_db),
        audit,
        container_of=AUTHZ.container_of,
        defaults_of=CONTAINER_DEFAULTS.record_of,
        features=lambda: FEATURES,
    )


def _uses(nexus: NexusIam, user: str, key: str) -> bool:
    with use_call_context(NexusIam.context(user)):
        return nexus.iam.authorize(USE, nexus_resource("feature", container=ALPHA, id=key)).allowed


def _rows(state: dict) -> dict[str, dict]:
    return {row["key"]: row for row in state["features"]}


def _access(nexus: NexusIam, acme) -> object:
    with as_service_account("api"):
        return nexus.iam.get_policy(acme.access_policy_id)


@pytest.mark.asyncio
async def test_everyone_and_nobody_are_what_the_workspaces_access_policy_offers(
    nexus, acme, service, audit
):
    rows = _rows(await service.read("olivia", "alpha"))
    assert (rows["chat"]["choice"], rows["files"]["choice"]) == ("everyone", "everyone")
    assert rows["chat"]["policy"]["id"] == acme.access_policy_id
    assert all(_uses(nexus, user, "chat") for user in ("bob", "carol", "dave", "olivia"))

    state = await service.save(
        "olivia", "alpha", [FeatureChange("chat", "nobody"), FeatureChange("files", "everyone")]
    )
    assert state["errors"] == {}
    rows = _rows(state)
    assert (rows["chat"]["choice"], rows["files"]["choice"]) == ("nobody", "everyone")
    # One policy, the workspace's access: no "Feature · X" policy is made.
    assert offer_of(_access(nexus, acme).document).features == {"files"}
    assert not any(_uses(nexus, user, "chat") for user in ("bob", "dave"))
    # Olivia owns Acme: she holds its offer from above, as before.
    assert _uses(nexus, "olivia", "chat")
    assert audit.phases("feature-access.nobody") == ["requested", "succeeded"]
    with as_service_account("api"):
        names = {p.name for p in nexus.iam.list_policies(scope=ALPHA).items}
    assert not any(name.startswith("Feature · ") for name in names)

    state = await service.save("olivia", "alpha", [FeatureChange("chat", "everyone")])
    assert _rows(state)["chat"]["choice"] == "everyone" and _uses(nexus, "dave", "chat")


@pytest.mark.asyncio
async def test_a_feature_given_brings_its_naas_abi_agent_and_takes_it_back(nexus, acme, service):
    """Access › Features: a feature given (Everyone) offers its Naas Abi agent with it (Files:
    the Files agent), taken back with it (Nobody)."""
    files_agent = ("naas_abi", "Files")
    await service.save("olivia", "alpha", [FeatureChange("files", "nobody")])
    # The organization does not offer it: the feature is given alone, without an error.
    state = await service.save("olivia", "alpha", [FeatureChange("files", "everyone")])
    assert state["errors"] == {}
    offer = offer_of(_access(nexus, acme).document)
    assert "files" in offer.features and files_agent not in offer.agents

    # Offered by the organization (naas_abi whole): it comes and goes with the feature.
    await service.save_offer(
        "root", org_container("acme"), [OfferChange("agents", "naas_abi", "*", True)]
    )
    await service.save("olivia", "alpha", [FeatureChange("files", "nobody")])
    assert files_agent not in offer_of(_access(nexus, acme).document).agents
    state = await service.save("olivia", "alpha", [FeatureChange("files", "everyone")])
    assert state["errors"] == {}
    assert files_agent in offer_of(_access(nexus, acme).document).agents


@pytest.mark.asyncio
async def test_only_is_refused_per_feature(nexus, acme, service):
    state = await service.save(
        "olivia",
        "alpha",
        [
            FeatureChange("chat", "only", (nexus.principal("bob"),)),
            FeatureChange("files", "nobody"),
        ],
    )
    assert "not a workspace setting" in state["errors"]["chat"]
    assert set(state["errors"]) == {"chat"}
    assert _rows(state)["chat"]["choice"] == "everyone"
    assert _rows(state)["files"]["choice"] == "nobody"


@pytest.mark.asyncio
async def test_a_newcomer_to_the_workspace_gets_what_it_offers(nexus, acme, service):
    assert not _uses(nexus, "frank", "chat")
    await MEMBERSHIPS.grant("frank", "member", ALPHA)
    assert _uses(nexus, "frank", "chat")
    await MEMBERSHIPS.revoke("frank", ALPHA)
    assert not _uses(nexus, "frank", "chat")


@pytest.mark.asyncio
async def test_a_caller_who_does_not_hold_the_feature_cannot_change_it(nexus, acme, service):
    await service.save("olivia", "alpha", [FeatureChange("chat", "nobody")])
    nexus.grant("erin", "admin", ALPHA)  # IAM's rights at Alpha, outside its groups: no feature
    rows = _rows(await service.read("erin", "alpha"))
    assert not rows["chat"]["editable"] and "do not hold Chat" in rows["chat"]["reason"]
    state = await service.save("erin", "alpha", [FeatureChange("chat", "everyone")])
    assert set(state["errors"]) == {"chat"}
    assert not _uses(nexus, "dave", "chat")
    # Not only this service's rule: IAM refuses her the widening itself.
    access = _access(nexus, acme)
    widened = offer_document(Offer.of(features=["chat", "files"]))
    with use_call_context(NexusIam.context("erin")), pytest.raises(PermissionDeniedError):
        nexus.iam.update_policy(
            acme.access_policy_id, expected_revision=access.revision, document=widened
        )


@pytest.mark.asyncio
async def test_a_feature_the_organization_does_not_offer_is_said_and_refused(nexus, acme, service):
    rows = _rows(await service.read("root", "alpha"))
    assert (rows["chat"]["offered"], rows["marketplace"]["offered"]) == (True, False)
    assert rows["marketplace"]["held"] and rows["marketplace"]["editable"]
    state = await service.save("root", "alpha", [FeatureChange("marketplace", "everyone")])
    assert "not offered in this workspace's organization" in state["errors"]["marketplace"]
    assert _rows(state)["marketplace"]["choice"] == "nobody"


@pytest.mark.asyncio
async def test_a_deny_elsewhere_wins_and_other_policies_are_listed(nexus, acme, service):
    dave = nexus.principal("dave")
    deny = {
        **_features("chat"),
        "statements": [{**_features("chat")["statements"][0], "effect": "Deny"}],
    }
    with use_call_context(NexusIam.context("root")):
        no_chat = nexus.iam.create_policy("No chat for Dave", deny, scope=ALPHA)
        nexus.iam.attach_policy(no_chat.id, dave, ALPHA)
        both = nexus.iam.create_policy(
            "Workspace features", _features("chat", "files"), scope=ALPHA
        )
        nexus.iam.attach_policy(both.id, acme.members_group_id, ALPHA)
    assert not _uses(nexus, "dave", "chat") and _uses(nexus, "carol", "chat")
    rows = _rows(await service.read("olivia", "alpha"))
    also = {(a["name"], a["effect"], a["attached"]) for a in rows["chat"]["also"]}
    assert {("No chat for Dave", "Deny", True), ("Workspace features", "Allow", True)} <= also
    # The workspace's access policy is the choice, never listed beside it.
    assert "Alpha access" not in {a["name"] for a in rows["chat"]["also"]}
    assert rows["chat"]["choice"] == "everyone" and rows["chat"]["editable"]


@pytest.mark.asyncio
async def test_a_feature_allowed_on_the_policy_page_is_shown_read_only(nexus, acme, service):
    access = _access(nexus, acme)
    document = offer_document(Offer.of(features=["files"]))
    document["statements"].append({**_features("chat")["statements"][0], "sid": "ByHand"})
    with use_call_context(NexusIam.context("root")):
        nexus.iam.update_policy(
            acme.access_policy_id, expected_revision=access.revision, document=document
        )
    row = _rows(await service.read("olivia", "alpha"))["chat"]
    assert row["choice"] == "everyone"
    assert row["hand_edited"] and not row["editable"] and "policy page" in row["reason"]
    state = await service.save("olivia", "alpha", [FeatureChange("chat", "nobody")])
    assert "chat" in state["errors"] and _uses(nexus, "dave", "chat")


@pytest.mark.asyncio
async def test_a_batch_naming_an_unknown_feature_or_nobody_changes_nothing(nexus, acme, service):
    for changes in (
        [FeatureChange("chat", "nobody"), FeatureChange("tasks", "everyone")],
        [FeatureChange("chat", "only")],
        [FeatureChange("chat", "everyone"), FeatureChange("chat", "nobody")],
    ):
        with pytest.raises(ValueError):
            await service.save("olivia", "alpha", changes)
    assert _rows(await service.read("olivia", "alpha"))["chat"]["choice"] == "everyone"
    assert await service.managed_among(["pol_none"]) == {}


@pytest.mark.asyncio
async def test_access_policies_still_marks_the_policies_an_older_general_wrote(
    nexus, acme, nexus_db, service, audit
):
    from naas_abi.apps.nexus.apps.api.app.services.iam_admin.service import IamAdminService

    with use_call_context(NexusIam.context("root")):
        older = nexus.iam.create_policy("Feature · Chat", _features("chat"), scope=ALPHA)
    await SqlFeaturePolicyStore(nexus_db).put("alpha", "chat", older.id)
    admin = IamAdminService(
        EngineIamGateway(), audit, managed_from=SqlFeaturePolicyStore(nexus_db).managed_among
    )
    listed = (await admin.list_policies("olivia", scope=ALPHA))["items"]
    marks = {p["id"]: p["managed_from"] for p in listed}
    assert marks[older.id] == "general"
    assert marks[acme.access_policy_id] is None


# -- agents, apps, workflows and pipelines ------------------------------------------------


def _uses_agent(nexus: NexusIam, user: str, module: str, name: str) -> bool:
    resource = module_scopes.scope_resource("agent", module, name, container=ALPHA)
    with use_call_context(NexusIam.context(user)):
        return nexus.iam.authorize("module:UseAgent", resource).allowed


@pytest.mark.asyncio
async def test_agents_and_apps_are_offered_in_the_workspaces_access_policy(
    nexus, acme, service, audit
):
    state = await service.read_offer("olivia", "alpha")
    assert state["editable"] and state["offered"]["agents"] == []
    assert not _uses_agent(nexus, "dave", "acme.sales", "SalesAgent")
    state = await service.save_offer(
        "olivia", "alpha", [OfferChange("agents", "acme.sales", "SalesAgent", True)]
    )
    assert state["offered"]["agents"] == [{"module": "acme.sales", "name": "SalesAgent"}]
    assert _uses_agent(nexus, "dave", "acme.sales", "SalesAgent")
    assert not _uses_agent(nexus, "dave", "acme.sales", "OtherAgent")
    assert audit.phases("workspace-offer.update") == ["requested", "succeeded"]
    # Features are kept: one policy, sections apart.
    assert offer_of(_access(nexus, acme).document).features == {"chat", "files"}
    # Beyond what the organization offers: IAM refuses it (it would grant nothing),
    # nothing changes.
    with pytest.raises(ValueError, match="would grant nothing"):
        await service.save_offer(
            "olivia", "alpha", [OfferChange("agents", "other.module", "X", True)]
        )
    state = await service.save_offer(
        "olivia", "alpha", [OfferChange("agents", "acme.sales", "SalesAgent", False)]
    )
    assert state["offered"]["agents"] == []
    assert not _uses_agent(nexus, "dave", "acme.sales", "SalesAgent")


def _uses_source(nexus: NexusIam, user: str, source: str) -> bool:
    with use_call_context(NexusIam.context(user)):
        resource = nexus_resource("search_source", container=ALPHA, id=source)
        return nexus.iam.authorize("nexus:UseSearchSource", resource).allowed


@pytest.mark.asyncio
async def test_search_sources_are_offered_in_the_workspaces_access_policy(
    nexus, acme, service, audit
):
    """Settings › Search writes the sources into "<W> access", as the caller: within
    the organization's offer, the other sections kept."""
    with use_call_context(NexusIam.context("root")):
        org = nexus.iam.get_policy(_access(nexus, acme).parent_id)
        nexus.iam.update_policy(
            org.id,
            expected_revision=org.revision,
            document=with_offer(
                org.document,
                offer_of(org.document).merged(Offer.of(search_sources=["chat", "web.wikipedia"])),
            ),
        )
    assert not _uses_source(nexus, "dave", "web.wikipedia")
    state = await service.save_search_sources(
        "olivia", "alpha", {"web.wikipedia": True, "chat": True}
    )
    assert state["offered"]["search_sources"] == ["chat", "web.wikipedia"]
    assert _uses_source(nexus, "dave", "web.wikipedia")
    assert audit.phases("workspace-offer.search-sources") == ["requested", "succeeded"]
    assert offer_of(_access(nexus, acme).document).features == {"chat", "files"}
    # Beyond the organization's offer: refused, nothing changes.
    with pytest.raises(ValueError, match="would grant nothing"):
        await service.save_search_sources("olivia", "alpha", {"web.duckduckgo": True})
    with pytest.raises(ValueError, match="Not a search source"):
        await service.save_search_sources("olivia", "alpha", {"web.bing": True})
    state = await service.save_search_sources("olivia", "alpha", {"web.wikipedia": False})
    assert state["offered"]["search_sources"] == ["chat"]
    assert not _uses_source(nexus, "dave", "web.wikipedia")


def _uses_model(nexus: NexusIam, user: str, model: str) -> bool:
    with use_call_context(NexusIam.context(user)):
        resource = nexus_resource("model", container=ALPHA, id=model)
        return nexus.iam.authorize("nexus:UseModel", resource).allowed


@pytest.mark.asyncio
async def test_the_models_a_workspace_uses_are_its_offers(nexus, acme, service, audit):
    """The Models section: the models W uses (``*``: every one) and its default model,
    written into "<W> access" as the caller, within the organization's offer. A list
    needs its default; the other sections are kept."""
    with use_call_context(NexusIam.context("root")):
        org = nexus.iam.get_policy(_access(nexus, acme).parent_id)
        nexus.iam.update_policy(
            org.id,
            expected_revision=org.revision,
            document=with_offer(
                org.document, offer_of(org.document).merged(Offer.of(models=["*"]))
            ),
        )
    state = await service.set_models("olivia", "alpha", ["qwen-3.8"], "qwen-3.8")
    assert state["models"] == {
        "offered": ["qwen-3.8"],
        "default": "qwen-3.8",
        "every": False,
        "available": [],
    }
    assert audit.phases("workspace-offer.models") == ["requested", "succeeded"]
    assert _uses_model(nexus, "dave", "qwen-3.8")
    assert not _uses_model(nexus, "dave", "gpt-x")
    assert offer_of(_access(nexus, acme).document).features == {"chat", "files"}
    with pytest.raises(ValueError, match="default"):
        await service.set_models("olivia", "alpha", ["qwen-3.8", "gpt-x"], None)
    state = await service.set_models("olivia", "alpha", ["*"], None)
    assert {k: state["models"][k] for k in ("offered", "default", "every")} == {
        "offered": ["*"],
        "default": None,
        "every": True,
    }
    assert _uses_model(nexus, "dave", "gpt-x")


# -- ontologies ---------------------------------------------------------------------------

# The deployment's ontology files, as Settings › Ontologies names them.
ONTOLOGY_FILES = [
    {"id": "core:bfo.ttl", "path": "/o/ontologies/modules/BFO.ttl", "name": "BFO core"},
    {"id": "core:agent.ttl", "path": "/o/ontologies/modules/Agent.ttl", "name": "Agent"},
    {"id": "acme.sales:sales.ttl", "path": "/o/ontologies/modules/Sales.ttl", "name": "Sales"},
]
# Who may assign every file to Alpha (``AssignOntology`` in Acme): its owner, root.
ASSIGNERS = ("olivia", "root")


async def ontology_catalog(user, workspace_id: str):
    """Every file, and those ``user`` may assign: the caller's own (``AssignOntology``)."""
    entries = [{**f, "module": f["id"].split(":")[0]} for f in ONTOLOGY_FILES]
    user_id = getattr(user, "id", user)
    return entries, {e["id"] for e in entries} if user_id in ASSIGNERS else set()


@pytest.fixture
def ontologies(nexus, acme, nexus_db, audit) -> FeatureAccessService:
    """The service with the deployment's ontology files; Acme allows every one (as
    ``ontologies_offer_v1`` writes it) and Alpha offers BFO by its seed's ref."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import ontologies_offer

    with use_call_context(NexusIam.context("root")):
        access = nexus.iam.get_policy(acme.access_policy_id)
        org = nexus.iam.get_policy(access.parent_id)
        nexus.iam.update_policy(
            org.id,
            expected_revision=org.revision,
            document=ontologies_offer.with_ontologies(org.document, org_container("acme"), []),
        )
        nexus.iam.update_policy(
            access.id,
            expected_revision=access.revision,
            document=with_offer(
                access.document,
                offer_of(access.document).merged(Offer.of(ontologies=["Core:BFO.ttl"])),
            ),
        )
    return FeatureAccessService(
        EngineIamGateway(),
        SqlFeaturePolicyStore(nexus_db),
        audit,
        container_of=AUTHZ.container_of,
        defaults_of=CONTAINER_DEFAULTS.record_of,
        features=lambda: FEATURES,
        ontology_catalog=ontology_catalog,
    )


def _ontology_rows(state: dict) -> dict[str, dict]:
    return {row["id"]: row for row in state["ontologies"]["rows"]}


class TestOntologies:
    """The offer's ontologies, on a deployment with the ontology feature (its levels
    use every file the offer names)."""

    @pytest.fixture
    def enabled_features(self) -> list[str]:
        return [*FEATURES, "ontology"]

    @pytest.mark.asyncio
    async def test_the_offer_reads_its_ontologies_and_what_the_caller_may_assign(
        self, nexus, acme, ontologies
    ):
        state = await ontologies.read_offer("olivia", "alpha")
        assert state["ontologies"]["offered"] == ["Core:BFO.ttl"]
        assert state["ontologies"]["error"] is None
        rows = _ontology_rows(state)
        # Every file of the deployment, by label; the offer's ref matched to its file.
        assert [row["label"] for row in state["ontologies"]["rows"]] == [
            "Agent",
            "BFO core",
            "Sales",
        ]
        assert rows["core:bfo.ttl"]["offered"] and not rows["core:agent.ttl"]["offered"]
        assert rows["core:bfo.ttl"]["module"] == "core"
        assert all(row["editable"] and row["assignable"] for row in rows.values())
        # A workspace's admin who may not assign: what is offered stays removable, the
        # others are read-only and say who gives them.
        await MEMBERSHIPS.grant("frank", "admin", ALPHA)
        rows = _ontology_rows(await ontologies.read_offer("frank", "alpha"))
        assert rows["core:bfo.ttl"]["editable"] and not rows["core:bfo.ttl"]["assignable"]
        assert not rows["core:agent.ttl"]["editable"]
        assert "AssignOntology" in rows["core:agent.ttl"]["reason"]

    @pytest.mark.asyncio
    async def test_an_offered_ref_outside_the_catalog_is_shown_and_can_be_removed(
        self, nexus, acme, ontologies
    ):
        with use_call_context(NexusIam.context("root")):
            access = nexus.iam.get_policy(acme.access_policy_id)
            nexus.iam.update_policy(
                access.id,
                expected_revision=access.revision,
                document=with_offer(
                    access.document,
                    offer_of(access.document).merged(Offer.of(ontologies=["gone:Old.ttl"])),
                ),
            )
        row = _ontology_rows(await ontologies.read_offer("olivia", "alpha"))["gone:Old.ttl"]
        assert row["offered"] and not row["available"] and row["editable"]
        state = await ontologies.save_ontologies("olivia", "alpha", {"gone:Old.ttl": False})
        assert state["ontologies"]["offered"] == ["Core:BFO.ttl"]

    @pytest.mark.asyncio
    async def test_an_admin_of_the_organization_adds_an_ontology_and_its_workspace_admin_removes_it(
        self, nexus, acme, ontologies, audit
    ):
        state = await ontologies.save_ontologies("olivia", "alpha", {"core:agent.ttl": True})
        assert state["ontologies"]["offered"] == ["Core:BFO.ttl", "core:agent.ttl"]
        assert _ontology_rows(state)["core:agent.ttl"]["offered"]
        assert audit.phases("workspace-offer.ontologies") == ["requested", "succeeded"]
        # The other sections are kept: one policy, sections apart.
        assert offer_of(_access(nexus, acme).document).features == {"chat", "files"}
        # A workspace's admin may remove one (by its file, whatever ref named it), not add.
        await MEMBERSHIPS.grant("frank", "admin", ALPHA)
        state = await ontologies.save_ontologies("frank", "alpha", {"core:bfo.ttl": False})
        assert state["ontologies"]["offered"] == ["core:agent.ttl"]
        with pytest.raises(PermissionDeniedError, match="AssignOntology"):
            await ontologies.save_ontologies("frank", "alpha", {"core:bfo.ttl": True})
        assert offer_of(_access(nexus, acme).document).ontologies == {"core:agent.ttl"}

    @pytest.mark.asyncio
    async def test_an_ontology_outside_the_catalog_or_no_change_is_refused(
        self, nexus, acme, ontologies
    ):
        with pytest.raises(ValueError, match="catalog"):
            await ontologies.save_ontologies("olivia", "alpha", {"nope:Nope.ttl": True})
        with pytest.raises(ValueError):
            await ontologies.save_ontologies("olivia", "alpha", {})
        # Taking back what is not offered changes nothing.
        state = await ontologies.save_ontologies("olivia", "alpha", {"core:agent.ttl": False})
        assert state["ontologies"]["offered"] == ["Core:BFO.ttl"]

    @pytest.mark.asyncio
    async def test_a_member_cannot_change_the_ontologies(self, nexus, acme, ontologies):
        with pytest.raises((PermissionDeniedError, IAMNotFoundError)):
            await ontologies.save_ontologies("dave", "alpha", {"core:bfo.ttl": False})
        assert offer_of(_access(nexus, acme).document).ontologies == {"Core:BFO.ttl"}


@pytest.mark.asyncio
async def test_the_offer_has_no_ontologies_where_the_deployment_lists_none(nexus, acme, service):
    assert (await service.read_offer("olivia", "alpha"))["ontologies"] is None


# -- the dataset namespaces a workspace (or an organization) does not use --------------

DATASET_TABLES = [("timesheets", "hours"), ("timesheets", "days"), ("hr", "pay")]


@pytest.fixture
def datasets(nexus_db, audit) -> FeatureAccessService:
    async def dataset_catalog() -> list[tuple[str, str]]:
        return list(DATASET_TABLES)

    return FeatureAccessService(
        EngineIamGateway(),
        SqlFeaturePolicyStore(nexus_db),
        audit,
        container_of=AUTHZ.container_of,
        defaults_of=CONTAINER_DEFAULTS.record_of,
        features=lambda: FEATURES,
        dataset_catalog=dataset_catalog,
    )


def _dataset_rows(state: dict) -> dict[str, dict]:
    return {row["namespace"]: row for row in state["rows"]}


class TestDatasets:
    @pytest.mark.asyncio
    async def test_every_shared_namespace_is_offered_until_the_workspace_closes_it(
        self, nexus, acme, datasets, audit
    ):
        state = await datasets.read_datasets("olivia", "alpha")
        assert state["editable"] and state["error"] is None
        assert state["access_policy"]["id"] == acme.access_policy_id
        assert [row["namespace"] for row in state["rows"]] == ["hr", "timesheets"]
        rows = _dataset_rows(state)
        assert (rows["timesheets"]["tables"], rows["hr"]["tables"]) == (2, 1)
        # Each namespace lists its datasets, A to Z, each offered or not (Settings › Datasets
        # unfolds them, as a module its items).
        assert [d["name"] for d in rows["timesheets"]["datasets"]] == ["days", "hours"]
        assert all(d["offered"] and d["editable"] for d in rows["timesheets"]["datasets"])
        assert [d["name"] for d in rows["hr"]["datasets"]] == ["pay"]
        assert all(row["offered"] and row["editable"] for row in rows.values())

        state = await datasets.set_datasets("olivia", "alpha", {"hr": False})
        assert not _dataset_rows(state)["hr"]["offered"]
        assert offer_of(_access(nexus, acme).document).datasets_closed == {"hr"}
        # One policy, sections apart: the features are kept.
        assert offer_of(_access(nexus, acme).document).features == {"chat", "files"}
        assert audit.phases("workspace-offer.datasets") == ["requested", "succeeded"]

        # Reopening lifts a Deny of the workspace's bound: the platform admin's alone (IAM),
        # as for the Maps items a workspace closes.
        with pytest.raises(PermissionDeniedError):
            await datasets.set_datasets("olivia", "alpha", {"hr": True})
        state = await datasets.set_datasets("root", "alpha", {"HR": True})
        assert _dataset_rows(state)["hr"]["offered"]
        assert offer_of(_access(nexus, acme).document).datasets_closed == frozenset()

    @pytest.mark.asyncio
    async def test_another_policy_of_the_workspace_closes_namespaces_for_its_holders(
        self, nexus, acme, datasets
    ):
        """The Policy picker on another policy: the namespaces it closes are its own, within
        what "<W> access" uses (a namespace the workspace closes stays closed there)."""
        grants = _grants(nexus)
        await datasets.set_datasets("olivia", "alpha", {"timesheets": False})
        state = await datasets.read_datasets("olivia", "alpha", grants.id)
        assert state["policy"]["id"] == grants.id and state["editable"]
        assert state["access_policy"]["id"] == acme.access_policy_id
        rows = _dataset_rows(state)
        assert rows["timesheets"]["closed_above"] and not rows["timesheets"]["editable"]
        assert rows["hr"]["offered"] and rows["hr"]["editable"]

        state = await datasets.set_datasets("olivia", "alpha", {"hr": False}, grants.id)
        assert not _dataset_rows(state)["hr"]["offered"]
        with as_service_account("api"):
            assert offer_of(nexus.iam.get_policy(grants.id).document).datasets_closed == {"hr"}
        assert offer_of(_access(nexus, acme).document).datasets_closed == {"timesheets"}
        with pytest.raises(ValueError, match="open it there first"):
            await datasets.set_datasets("olivia", "alpha", {"timesheets": True}, grants.id)

    @pytest.mark.asyncio
    async def test_what_the_organization_closes_no_workspace_reopens(self, nexus, acme, datasets):
        # "<O> access" is the platform's: its admin closes a namespace for every workspace.
        org = org_container("acme")
        state = await datasets.set_datasets("root", org, {"timesheets": False})
        assert not _dataset_rows(state)["timesheets"]["offered"]

        row = _dataset_rows(await datasets.read_datasets("olivia", "alpha"))["timesheets"]
        assert not row["offered"] and row["closed_above"] and not row["editable"]
        assert "Acme access" in row["reason"]
        with pytest.raises(ValueError, match="Acme access"):
            await datasets.set_datasets("olivia", "alpha", {"timesheets": True})

    @pytest.mark.asyncio
    async def test_a_closed_namespace_gone_from_the_deployment_is_still_listed(
        self, nexus, acme, datasets
    ):
        await datasets.set_datasets("olivia", "alpha", {"archive": False})
        row = _dataset_rows(await datasets.read_datasets("olivia", "alpha"))["archive"]
        assert (row["tables"], row["available"], row["offered"]) == (0, False, False)

    @pytest.mark.asyncio
    async def test_a_namespace_is_offered_whole_or_dataset_by_dataset(self, nexus, acme, datasets):
        state = await datasets.set_datasets("olivia", "alpha", {"timesheets/hours": False})
        row = _dataset_rows(state)["timesheets"]
        assert row["offered"]  # the namespace stays, one of its datasets goes
        assert {d["name"]: d["offered"] for d in row["datasets"]} == {"days": True, "hours": False}
        assert offer_of(_access(nexus, acme).document).datasets_closed == {"timesheets/hours"}

        # Closing the namespace covers its datasets, nothing to pick in it; the dataset's own
        # closure stays (taking it out would lift a Deny). Changing a Deny "<W> access" already
        # carries is refused to whoever it restricts (IAM), so the platform admin closes it here.
        state = await datasets.set_datasets("root", "alpha", {"timesheets": False})
        assert offer_of(_access(nexus, acme).document).datasets_closed == {
            "timesheets",
            "timesheets/hours",
        }
        row = _dataset_rows(state)["timesheets"]
        assert not row["offered"]
        assert not any(d["offered"] or d["editable"] for d in row["datasets"])
        # A dataset of a closed namespace is not reopened alone.
        with pytest.raises(ValueError, match="namespace"):
            await datasets.set_datasets("olivia", "alpha", {"timesheets/days": True})

        # Reopening the namespace offers it whole.
        state = await datasets.set_datasets("root", "alpha", {"timesheets": True})
        assert offer_of(_access(nexus, acme).document).datasets_closed == frozenset()
        assert all(d["offered"] for d in _dataset_rows(state)["timesheets"]["datasets"])

    @pytest.mark.asyncio
    async def test_a_dataset_the_organization_closes_no_workspace_reopens(
        self, nexus, acme, datasets
    ):
        org = org_container("acme")
        await datasets.set_datasets("root", org, {"hr/pay": False})
        row = _dataset_rows(await datasets.read_datasets("olivia", "alpha"))["hr"]
        assert row["offered"] and not row["closed_above"]
        (pay,) = row["datasets"]
        assert not pay["offered"] and pay["closed_above"] and not pay["editable"]
        with pytest.raises(ValueError, match="Acme access"):
            await datasets.set_datasets("olivia", "alpha", {"hr/pay": True})

    @pytest.mark.asyncio
    async def test_a_namespace_must_be_named_and_plain(self, nexus, acme, datasets):
        for changes in ({}, {"a/b/c": False}, {"a/": False}, {"*": False}, {" hr": False}):
            with pytest.raises(ValueError):
                await datasets.set_datasets("olivia", "alpha", changes)

    @pytest.mark.asyncio
    async def test_a_member_cannot_close_a_namespace(self, nexus, acme, datasets):
        assert not (await datasets.read_datasets("dave", "alpha"))["editable"]
        with pytest.raises((PermissionDeniedError, IAMNotFoundError)):
            await datasets.set_datasets("dave", "alpha", {"hr": False})
        assert offer_of(_access(nexus, acme).document).datasets_closed == frozenset()


@pytest.mark.asyncio
async def test_the_datasets_say_so_where_the_deployment_lists_none(nexus, acme, service):
    state = await service.read_datasets("olivia", "alpha")
    assert state["rows"] == [] and "no dataset" in state["error"]


# -- another policy of the workspace, edited as Features and Modules edit "<W> access" ----


def _grants(nexus: NexusIam) -> object:
    """A policy Alpha owns beside its offer, granting Files."""
    with use_call_context(NexusIam.context("root")):
        return nexus.iam.create_policy(
            "Analysts grants", offer_document(Offer.of(features=["files"])), scope=ALPHA
        )


@pytest.mark.asyncio
async def test_features_read_and_save_another_policy_of_the_workspace(nexus, acme, service):
    grants = _grants(nexus)
    state = await service.read("olivia", "alpha", grants.id)
    assert state["policy"]["name"] == "Analysts grants"
    assert state["access_policy"]["name"] == "Alpha access"
    # "<W> access" first, then the workspace's other policies.
    names = [p["name"] for p in state["policies"]]
    assert names[0] == "Alpha access" and "Analysts grants" in names
    rows = _rows(state)
    assert rows["chat"]["choice"] == "nobody" and rows["chat"]["editable"]
    # Its ceiling is the workspace's offer: Alpha does not offer the marketplace.
    assert rows["marketplace"]["offered"] is False
    assert "Alpha access" in {a["name"] for a in rows["chat"]["also"]}

    saved = await service.save("olivia", "alpha", [FeatureChange("chat", "everyone")], grants.id)
    assert saved["errors"] == {}
    assert _rows(saved)["chat"]["choice"] == "everyone"
    with as_service_account("api"):
        assert offer_of(nexus.iam.get_policy(grants.id).document).features == {"chat", "files"}
    # "<W> access" is left as it was.
    assert offer_of(_access(nexus, acme).document).features == {"chat", "files"}

    # Even the platform admin, who holds it: the workspace's offer allows it first.
    refused = await service.save(
        "root", "alpha", [FeatureChange("marketplace", "everyone")], grants.id
    )
    assert "Alpha access allows it first" in refused["errors"]["marketplace"]


@pytest.mark.asyncio
async def test_modules_read_and_save_another_policy_of_the_workspace(nexus, acme, service):
    grants = _grants(nexus)
    state = await service.read_offer("olivia", "alpha", grants.id)
    assert state["policy"]["id"] == grants.id and state["editable"]
    change = OfferChange("agents", "acme.sales", "*", True)
    saved = await service.save_offer("olivia", "alpha", [change], grants.id)
    assert saved["offered"]["agents"] == [{"module": "acme.sales", "name": "*"}]
    with as_service_account("api"):
        assert offer_of(nexus.iam.get_policy(grants.id).document).agents == {("acme.sales", "*")}
    assert offer_of(_access(nexus, acme).document).agents == frozenset()


@pytest.mark.asyncio
async def test_search_sources_models_and_files_save_another_policy_of_the_workspace(
    nexus, acme, service
):
    """The settings column's Policy picker drives every page under Features: Search's
    sources, Models and Files write the policy picked (``policy_id``) as Modules does,
    "<W> access" left as it was."""
    widened = Offer.of(search_sources=["chat"], models=["*"])
    with use_call_context(NexusIam.context("root")):
        for policy in (nexus.iam.get_policy(_access(nexus, acme).parent_id), _access(nexus, acme)):
            nexus.iam.update_policy(
                policy.id,
                expected_revision=policy.revision,
                document=with_offer(policy.document, offer_of(policy.document).merged(widened)),
            )
    before = offer_of(_access(nexus, acme).document)
    grants = _grants(nexus)

    state = await service.save_search_sources("olivia", "alpha", {"chat": True}, grants.id)
    assert state["policy"]["id"] == grants.id
    assert state["offered"]["search_sources"] == ["chat"]
    state = await service.set_models("olivia", "alpha", ["qwen-3.8"], "qwen-3.8", grants.id)
    assert state["policy"]["id"] == grants.id
    assert state["models"]["offered"] == ["qwen-3.8"]
    state = await service.set_files("olivia", "alpha", {"system_files": "off"}, grants.id)
    assert state["policy"]["id"] == grants.id

    with as_service_account("api"):
        granted = offer_of(nexus.iam.get_policy(grants.id).document)
    assert granted.search_sources == {"chat"}
    assert granted.models == {"qwen-3.8"} and granted.default_model == "qwen-3.8"
    assert offer_of(_access(nexus, acme).document) == before


@pytest.mark.asyncio
async def test_a_policy_of_another_scope_is_not_edited_here(nexus, acme, service):
    with use_call_context(NexusIam.context("root")):
        elsewhere = nexus.iam.create_policy(
            "Org grants", _features("chat"), scope=org_container("acme")
        )
    with pytest.raises(IAMNotFoundError):
        await service.read("olivia", "alpha", elsewhere.id)
    with pytest.raises(IAMNotFoundError):
        await service.save_offer(
            "olivia", "alpha", [OfferChange("agents", "acme.sales", "*", True)], elsewhere.id
        )
    with pytest.raises(IAMNotFoundError):
        await service.set_files("olivia", "alpha", {"system_files": "off"}, elsewhere.id)


# -- access levels: a cap in "<W> access", a grant in another policy ---------------------


def _may(nexus: NexusIam, user: str, action: str, resource: str) -> bool:
    with use_call_context(NexusIam.context(user)):
        return nexus.iam.authorize(action, resource).allowed


@pytest.mark.asyncio
async def test_a_cap_in_the_offer_keeps_everyone_to_a_level(nexus, acme, service):
    view = nexus_resource("view", container=ALPHA, id="v1")
    assert _may(nexus, "carol", "nexus:CreateView", view)
    state = await service.read_levels("olivia", "alpha", "feature")
    assert state["mode"] == "cap" and state["editable"]
    rows = {r["name"]: r for r in state["rows"]}
    # Only the features the deployment enables; no cap: their highest level.
    assert set(rows) <= set(FEATURES)
    assert rows["chat"]["level"] == rows["chat"]["choices"][-1]

    saved = await service.save_levels(
        "olivia", "alpha", "service", {"service:triple_store": "read"}
    )
    assert {r["name"]: r["level"] for r in saved["rows"]}["triple_store"] == "read"
    with as_service_account("api"):
        document = nexus.iam.get_policy(acme.access_policy_id).document
    caps = [s for s in document.statements if (s.sid or "").startswith("AccessLevelCap")]
    assert caps and all(s.effect == "Deny" for s in caps)
    # The offer's own sections are kept as they were.
    assert offer_of(document).features == {"chat", "files"}

    with pytest.raises(ValueError):
        await service.save_levels(
            "olivia", "alpha", "service", {"service:triple_store": "everything"}
        )


@pytest.mark.asyncio
async def test_a_cap_on_a_feature_denies_its_actions_above_the_level(nexus, acme, service):
    from naas_abi.apps.nexus.apps.api.app.services.iam import access_levels

    view = nexus_resource("view", container=ALPHA, id="v1")
    assert _may(nexus, "carol", "nexus:CreateView", view)
    with use_call_context(NexusIam.context("root")):
        access = nexus.iam.get_policy(acme.access_policy_id)
        nexus.iam.update_policy(
            access.id,
            expected_revision=access.revision,
            document=access_levels.with_levels(access.document, "cap", {"feature:graph": "read"}),
        )
    # A Member still reads (below the cap), and no longer writes (above it).
    assert _may(nexus, "carol", "nexus:GetView", view)
    assert not _may(nexus, "carol", "nexus:CreateView", view)


@pytest.mark.asyncio
async def test_another_policy_grants_a_level_to_its_holders(nexus, acme, service):
    grants = _grants(nexus)
    state = await service.read_levels("root", "alpha", "service", grants.id)
    assert state["mode"] == "grant"
    assert {r["name"]: r["level"] for r in state["rows"]}["secret"] == "none"
    saved = await service.save_levels(
        "root", "alpha", "service", {"service:secret": "read"}, grants.id
    )
    assert {r["name"]: r["level"] for r in saved["rows"]}["secret"] == "read"
    with as_service_account("api"):
        document = nexus.iam.get_policy(grants.id).document
    granted = [s for s in document.statements if (s.sid or "").startswith("AccessLevelGrant")]
    assert granted and granted[0].effect == "Allow"
    # "<W> access" holds no cap for it.
    with as_service_account("api"):
        access_doc = nexus.iam.get_policy(acme.access_policy_id).document
    assert not [s for s in access_doc.statements if (s.sid or "").startswith("AccessLevel")]


# -- Organization › Access: the same reads and writes on "<O> access" ---------------------


@pytest.mark.asyncio
async def test_the_organization_pages_edit_its_offer_and_reach_its_workspaces(nexus, acme, service):
    acme_org = org_container("acme")
    state = await service.read("root", acme_org)
    assert state["access_policy"]["name"] == state["policy"]["name"]
    assert state["policies"][0]["id"] == state["access_policy"]["id"]
    rows = _rows(state)
    assert rows["chat"]["choice"] == "everyone" and rows["chat"]["offered"]

    # The platform admin takes chat out of "<O> access": Alpha may not offer it any more.
    saved = await service.save("root", acme_org, [FeatureChange("chat", "nobody")])
    assert saved["errors"] == {} and _rows(saved)["chat"]["choice"] == "nobody"
    assert _rows(await service.read("olivia", "alpha"))["chat"]["offered"] is False

    # A cap in "<O> access" reaches the people of its workspaces (its Denies are their bound's).
    view = nexus_resource("view", container=ALPHA, id="v1")
    assert _may(nexus, "carol", "nexus:CreateView", view)
    capped = await service.save_levels("root", acme_org, "feature", {"feature:graph": "read"})
    assert capped["mode"] == "cap"
    assert not _may(nexus, "carol", "nexus:CreateView", view)

    offer = await service.read_offer("root", acme_org)
    assert offer["policy"]["id"] == state["access_policy"]["id"]
    assert offer["offered"]["agents"] == [{"module": "acme.sales", "name": "*"}]


def test_a_feature_brings_its_office_agent_and_agents_brings_abi():
    from naas_abi.apps.nexus.apps.api.app.services.feature_access.service import (
        ABI_AGENT,
        feature_agents,
        with_feature,
    )

    assert feature_agents("files") == [("naas_abi", "Files")]
    assert ABI_AGENT in feature_agents("agents") and (
        "naas_abi",
        "Agent Catalog",
    ) in feature_agents("agents")
    assert feature_agents("chat") == []
    given = with_feature(Offer(), "agents", True)
    assert "agents" in given.features and ABI_AGENT in given.agents
    taken = with_feature(given, "agents", False)
    assert "agents" not in taken.features and ABI_AGENT not in taken.agents
    # The platform's offer is features alone.
    assert with_feature(Offer(), "files", True, agents=False).agents == frozenset()
