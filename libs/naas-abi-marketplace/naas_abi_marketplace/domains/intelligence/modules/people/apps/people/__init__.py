"""People Search - a configurable people directory over the personnel graph.

    person + experience  ->  graph (ontology-backed)  ->  datasets  ->  app

The app itself holds no people. ``scripts/export_people_from_graph.py`` runs the
personnel competency queries and writes nine typed tables through the dataset
service; this module serves them, shaped by ``config.yaml``.

See ``README.md`` for how to point it at another population, and ``AGENTS.md``
for what configuration may and may not change.
"""

from fastapi import FastAPI
from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)
from naas_abi_core.services.dataset.DatasetService import DatasetService


class ABIModule(BaseModule):
    """Registers People Search with the ABI engine.

    The dataset service is declared as a dependency because the engine gates
    service access on this list: without it, ``engine.services.dataset`` is not
    reachable from here and every page would be empty.
    """

    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[DatasetService],
    )

    class Configuration(ModuleConfiguration):
        """
        module: naas_abi_marketplace.domains.personnel.apps.people
        enabled: true
        """

    def api(self, app: FastAPI) -> None:
        from naas_abi_marketplace.domains.personnel.apps.people.api.routes import router

        app.include_router(router, prefix="/api/personnel-people")
