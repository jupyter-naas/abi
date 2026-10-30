from naas_abi_sdk.module import BaseModule, ModuleDependencies
from naas_abi_sdk.permissions import default_manifest, module_manifest


def _by_sid(document):
    return {s["sid"]: s for s in document["statements"]}


def test_defaults_reach_the_modules_own_namespaces_and_declared_services():
    manifest = default_manifest(
        ModuleDependencies(
            services=("document", "dataset", "kv", "triple_store", "bus", "secret")
        )
    )
    statements = _by_sid(manifest)
    assert statements["UseDocument"]["resources"] == [
        "abi:document:namespace/${module.id}",
        "abi:document:collection/${module.id}/*",
        "abi:document:document/${module.id}/*",
    ]
    assert statements["UseDataset"]["actions"] == ["dataset:*"]
    # Where the SDK's dataset facade writes (a module id is no dataset identifier).
    assert statements["UseDataset"]["resources"] == [
        "abi:dataset:namespace/default",
        "abi:dataset:dataset/default/*",
        "abi:dataset:catalog/-",
    ]
    assert statements["NoDatasetAdmin"]["effect"] == "Deny"
    assert statements["NoDatasetAdmin"]["actions"] == ["dataset:QueryUnchecked"]
    assert statements["NoDatasetAdmin"]["resources"] == [
        "abi:dataset:*",
        "abi:*/dataset:*",
    ]
    # Never every secret: the ones named after the module.
    assert statements["UseSecret"]["resources"] == [
        "abi:secret:secret/${module.id}%2F*"
    ]
    assert statements["UseKeyvalue"]["actions"] == ["keyvalue:*"]
    assert statements["UseKeyvalue"]["resources"] == [
        "abi:keyvalue:*",
        "abi:*/keyvalue:*",
    ]
    assert statements["UseTripleStore"]["resources"] == [
        # The platform's and those of every container (core's names.anywhere).
        "abi:triple_store:graph/*",
        "abi:*/triple_store:graph/*",
        "abi:triple_store:view/*",
        "abi:*/triple_store:view/*",
    ]
    # Its own ontologies only: a source names the module that loads it.
    assert statements["OwnOntologies"]["actions"] == ["triple_store:LoadSchema"]
    assert statements["OwnOntologies"]["resources"] == [
        "abi:triple_store:schema/module/${module.id}/*"
    ]
    # Bus topics are declared, never defaulted.
    assert not any("bus:" in a for s in manifest["statements"] for a in s["actions"])


def test_defaults_grant_no_admin_action_and_no_kept_mail():
    manifest = default_manifest(
        ModuleDependencies(services=("email", "source_control"))
    )
    statements = _by_sid(manifest)
    # Sending only: the kept copies hold users' sign-in codes.
    assert statements["UseEmail"]["actions"] == ["email:Send"]
    # Every source-control action but the one that grants access to a repository.
    assert statements["UseSourceControl"]["actions"] == ["source_control:*"]
    assert statements["NoSourceControlAdmin"]["effect"] == "Deny"
    assert statements["NoSourceControlAdmin"]["actions"] == [
        "source_control:AddCollaborator"
    ]


def test_module_dependencies_reach_those_modules_only():
    statements = _by_sid(
        default_manifest(ModuleDependencies(modules=("demo.research",)))
    )
    assert (
        "abi:discovery:agent/${module.project}/demo.research/*"
        in (statements["UseDependencies"]["resources"])
    )
    assert statements["FollowOwnRuns"]["resources"] == [
        "abi:discovery:run/${principal.id}/*",
        "abi:discovery:run/${user.id}/*",
    ]


def test_a_declared_manifest_replaces_the_defaults():
    declared = {
        "statements": [
            {"effect": "Allow", "actions": ["email:Send"], "resources": ["*"]}
        ]
    }

    class Mailer(BaseModule):
        dependencies = ModuleDependencies(services=("document",))
        permissions = declared

    manifest = module_manifest(Mailer)
    assert manifest["statements"] == declared["statements"]
    assert manifest["version"] == "2026-10-13"


def test_a_module_with_jobs_names_each_of_them():
    from naas_abi_sdk.jobs import Every, job

    class Ingest(BaseModule):
        module_id = "acme.ingest"

        @job(triggers=(Every("1h"),))
        async def nightly(self, ctx):
            return None

        @job()
        async def backfill(self, ctx):
            return None

    statements = _by_sid(module_manifest(Ingest))
    assert statements["OwnJobs"]["resources"] == [
        "abi:discovery:job/${module.project}/${module.id}/backfill",
        "abi:discovery:job/${module.project}/${module.id}/nightly",
        "abi:discovery:job_run/${module.project}/${module.id}/*",
    ]
    assert "OwnJobs" not in _by_sid(default_manifest(ModuleDependencies()))


def test_depending_on_the_identity_provider_never_asks_for_its_admin_app():
    manifest = default_manifest(ModuleDependencies(modules=("idp", "people")))
    deny = next(
        s for s in manifest["statements"] if s["sid"] == "NoIdentityProviderAdmin"
    )
    assert deny["effect"] == "Deny"
    assert deny["actions"] == ["discovery:OpenApp"]
    assert deny["resources"] == ["abi:discovery:app/${module.project}/idp/admin"]
    other = default_manifest(ModuleDependencies(modules=("people",)))
    assert all(s["sid"] != "NoIdentityProviderAdmin" for s in other["statements"])


REPORTS = {
    "resource_types": [{"name": "report", "id": "path"}],
    "actions": [
        {"name": "ExportReport", "level": "read", "resource_types": ["report"]}
    ],
}


def test_a_declared_catalog_travels_with_the_manifest_under_the_module_s_name():
    class Reports(BaseModule):
        module_id = "acme.reports"
        dependencies = ModuleDependencies(services=("document",))
        iam_catalog = REPORTS

    manifest = module_manifest(Reports)
    assert manifest["catalog"]["service"] == "acme_reports"
    assert manifest["catalog"]["version"] == 1
    assert manifest["catalog"]["actions"] == REPORTS["actions"]
    assert manifest["statements"]


def test_a_module_without_a_catalog_sends_none():
    class Plain(BaseModule):
        module_id = "plain"

    assert "catalog" not in module_manifest(Plain)


def test_catalog_names_follow_the_engine_s_rule():
    from naas_abi_sdk.permissions import catalog_service

    assert catalog_service("acme.people") == "acme_people"
    assert catalog_service("Acme-People") == "acme_people"
    assert catalog_service("9lives") == "m_9lives"
