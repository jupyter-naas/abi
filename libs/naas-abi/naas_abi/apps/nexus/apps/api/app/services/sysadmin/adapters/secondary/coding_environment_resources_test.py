import asyncio
import json

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.coding_environment_resources import (
    CodingEnvironmentResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ReadOnlyResourcesContract,
    ServiceResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    InvalidResource,
    ResourceNotFound,
    UnsupportedOperation,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_core.services.coding_environment.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentPorts import (
    AccessDeniedError,
    WorkspaceTemplate,
)
from naas_abi_core.services.coding_environment.CodingEnvironmentService import (
    CodingEnvironmentService,
)


def run(coro):
    return asyncio.run(coro)


class _Orchestrator(InMemoryAdapter):
    """In-memory orchestrator with three templates."""

    def list_templates(self):
        return [
            WorkspaceTemplate(id=f"tmpl-{n}", name=n, active_version_id=f"v-{n}")
            for n in ("docker", "kubernetes", "local")
        ]


class _NoAdminListing(InMemoryAdapter):
    def list_all_environments(self):
        raise NotImplementedError("this orchestrator cannot list every user")


def _seeded(adapter=None) -> CodingEnvironmentService:
    service = CodingEnvironmentService(adapter or _Orchestrator())
    # The seed text rides in the template so the contract can find it in the JSON.
    for name, value in fixtures.SEED_ITEMS.items():
        service.provision(user_id=f"user-{name}", template_id=value.decode(), name=name)
    return service


class TestCodingEnvironmentResourcesEnvironments(ServiceResourcesContract):
    base = "environments"
    sized = False

    def assert_shown(self, shown, text):
        assert json.loads(shown)["template"] == text

    @pytest.fixture
    def resources(self):
        return CodingEnvironmentResources(_seeded())


class TestCodingEnvironmentResourcesTemplates(ReadOnlyResourcesContract):
    base = "templates"

    @pytest.fixture
    def resources(self):
        return CodingEnvironmentResources(_seeded())


def test_root_holds_environments_and_templates():
    resources = CodingEnvironmentResources(_seeded())

    entries = run(resources.list("")).entries

    assert [(e.id, e.kind) for e in entries] == [
        ("environments", "container"),
        ("templates", "container"),
    ]


def test_environments_span_every_user_with_owner_and_phase():
    service = _seeded()
    service.provision(user_id="user-zed", template_id="tmpl-docker", name="alpha")
    resources = CodingEnvironmentResources(service)

    entries = run(resources.list("environments")).entries
    alphas = [e for e in entries if e.name == "alpha"]
    detail = json.loads(run(resources.read(alphas[1].id)).content.text)

    assert [e.attributes["owner"] for e in alphas] == ["user-alpha", "user-zed"]
    assert all(e.attributes["phase"] == "running" and e.modified for e in entries)
    assert detail["owner"] == "user-zed"
    assert detail["template"] == "tmpl-docker"
    assert detail["agent_ready"] is True


def test_deleting_an_environment_goes_through_the_service():
    service = _seeded()
    resources = CodingEnvironmentResources(service)
    (alpha,) = [e for e in run(resources.list("environments")).entries if e.name == "alpha"]

    run(resources.delete(alpha.id))

    assert "alpha" not in {s.name for s in service.list_all_environments()}


def test_templates_cannot_be_deleted_and_nothing_is_written():
    resources = CodingEnvironmentResources(_seeded())

    with pytest.raises(UnsupportedOperation):
        run(resources.delete("templates/tmpl-docker"))
    with pytest.raises(UnsupportedOperation):
        run(resources.write("environments/new", b"{}"))
    with pytest.raises(UnsupportedOperation):
        run(resources.download("templates/tmpl-docker", max_bytes=100))


def test_without_admin_listing_environments_open_by_id():
    service = _seeded(_NoAdminListing())
    (some,) = service.list_environments(user_id="user-beta")
    resources = CodingEnvironmentResources(service)

    page = run(resources.list("environments"))
    entry = run(resources.stat(f"environments/{some.id}"))

    assert resources.capabilities.lookup is True
    assert (page.listable, page.entries) == (False, ())
    assert (entry.name, entry.attributes["owner"]) == ("beta", "user-beta")


def test_unknown_ids_and_containers():
    resources = CodingEnvironmentResources(_seeded())

    for missing in ("nope", "environments/ws-404", "templates/tmpl-404", "environments/a/b"):
        with pytest.raises(ResourceNotFound):
            run(resources.stat(missing))
    with pytest.raises(InvalidResource):
        run(resources.read("environments"))


class _DeniedOrchestrator(_Orchestrator):
    def list_all_environments(self):
        raise AccessDeniedError("admin token revoked", status=403)


def test_orchestrator_errors_say_why():
    resources = CodingEnvironmentResources(CodingEnvironmentService(_DeniedOrchestrator()))

    with pytest.raises(SourceUnavailable) as exc:
        run(resources.list("environments"))
    assert "admin token revoked" in exc.value.reason


def test_root_counts_environments_and_templates():
    entries = {e.id: e for e in run(CodingEnvironmentResources(_seeded()).list("")).entries}

    assert entries["environments"].attributes["count"] == "3"
    assert entries["environments"].attributes["summary"] == "3 workspaces across every user"
    assert entries["templates"].attributes["count"] == "3"
    assert entries["templates"].attributes["summary"] == "3 templates"


def test_root_count_is_omitted_when_the_backend_cannot_list_everyone():
    entries = {
        e.id: e
        for e in run(CodingEnvironmentResources(_seeded(_NoAdminListing())).list("")).entries
    }

    assert "count" not in entries["environments"].attributes
    assert entries["environments"].attributes["summary"] == "Open a workspace by its id"


def test_environments_read_as_a_status_view():
    resources = CodingEnvironmentResources(_seeded())
    (alpha,) = [e for e in run(resources.list("environments")).entries if e.name == "alpha"]

    detail = run(resources.read(alpha.id))

    assert alpha.attributes["summary"] == "user-alpha · first value"
    assert detail.view["type"] == "status"
    assert detail.view["phase"] == "running"
    assert detail.view["fields"]["Owner"] == "user-alpha"
    assert detail.view["fields"]["Agent"] == "Ready"
    assert detail.view["created_at"] == alpha.modified


def test_templates_read_as_a_sheet_and_search_filters_by_name():
    resources = CodingEnvironmentResources(_seeded())

    detail = run(resources.read("templates/tmpl-docker"))
    found = run(resources.list("templates", query="KUBER")).entries

    assert detail.view == {
        "type": "status",
        "phase": "template",
        "fields": {"Template": "docker", "Id": "tmpl-docker", "Active version": "v-docker"},
    }
    assert resources.capabilities.search is True
    assert [e.name for e in found] == ["kubernetes"]
    assert [e.name for e in run(resources.list("environments", query="bet")).entries] == ["beta"]
