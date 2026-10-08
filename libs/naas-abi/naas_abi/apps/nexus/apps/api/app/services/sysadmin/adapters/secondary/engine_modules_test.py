import asyncio
from types import SimpleNamespace as NS

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.engine_modules import (
    EngineModules,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import EngineModuleSourceContract
from naas_abi_sdk.jobs import Every, JobDescriptor


class _Broken:
    name = "Broken"

    @property
    def agents(self):
        raise RuntimeError("agents not loaded")


@pytest.fixture
def source():
    acme = NS(
        name="Acme jobs",
        description="",
        agents=[object()],
        orchestrations=[],
        ontologies=[],
        jobs=(JobDescriptor("nightly", triggers=(Every("1h"),)),),
    )
    quiet = NS(name="", description="", agents=[], orchestrations=[], ontologies=[])
    return EngineModules(lambda: {"acme.jobs": acme, "acme.quiet": quiet})


class TestEngineModules(EngineModuleSourceContract):
    pass


def test_a_module_that_fails_to_describe_itself_is_still_listed():
    modules = asyncio.run(EngineModules(lambda: {"acme.broken": _Broken()}).list_modules())

    assert [(m.module_id, m.name, m.agents) for m in modules] == [("acme.broken", "Broken", 0)]
