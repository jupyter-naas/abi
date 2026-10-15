from naas_abi_sdk.module import BaseModule, ModuleDependencies
from naas_abi_sdk.permissions import default_manifest, module_manifest


def _by_sid(document):
    return {s["sid"]: s for s in document["statements"]}


def test_defaults_reach_the_modules_own_namespaces_and_declared_services():
    manifest = default_manifest(
        ModuleDependencies(
            services=("document", "dataset", "kv", "triple_store", "bus")
        )
    )
    statements = _by_sid(manifest)
    assert statements["UseDocument"]["resources"] == [
        "abi:-:-:document:namespace/${module.id}",
        "abi:-:-:document:collection/${module.id}/*",
        "abi:-:-:document:document/${module.id}/*",
    ]
    assert statements["UseDataset"]["actions"] == ["dataset:*"]
    # Where the SDK's dataset facade writes (a module id is no dataset identifier).
    assert statements["UseDataset"]["resources"] == [
        "abi:-:-:dataset:namespace/default",
        "abi:-:-:dataset:dataset/default/*",
        "abi:-:-:dataset:catalog/-",
    ]
    assert statements["UseKeyvalue"]["actions"] == ["keyvalue:*"]
    assert statements["UseTripleStore"]["resources"] == ["abi:*:*:triple_store:*"]
    # Bus topics are declared, never defaulted.
    assert not any("bus:" in a for s in manifest["statements"] for a in s["actions"])


def test_module_dependencies_reach_those_modules_only():
    statements = _by_sid(
        default_manifest(ModuleDependencies(modules=("demo.research",)))
    )
    assert (
        "abi:-:-:discovery:agent/${module.project}/demo.research/*"
        in (statements["UseDependencies"]["resources"])
    )
    assert statements["FollowOwnRuns"]["resources"] == [
        "abi:-:-:discovery:run/${principal.id}/*",
        "abi:-:-:discovery:run/${user.id}/*",
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
        "abi:-:-:discovery:job/${module.project}/${module.id}/backfill",
        "abi:-:-:discovery:job/${module.project}/${module.id}/nightly",
        "abi:-:-:discovery:job_run/${module.project}/${module.id}/*",
    ]
    assert "OwnJobs" not in _by_sid(default_manifest(ModuleDependencies()))
