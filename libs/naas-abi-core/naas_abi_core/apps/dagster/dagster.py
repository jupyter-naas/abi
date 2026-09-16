from typing import cast

from dagster import Definitions

from naas_abi_core.apps.dagster.DatasetCompaction import dataset_compaction_definitions
from naas_abi_core.engine.Engine import Engine
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration

engine = Engine()
engine.load()

all_definitions: list[Definitions] = []

if engine.services.dataset_available():
    all_definitions.append(dataset_compaction_definitions(engine.services.dataset))

for module in engine.modules.values():
    for orchestration in module.orchestrations:
        if issubclass(orchestration, DagsterOrchestration):
            assert issubclass(orchestration, DagsterOrchestration), (
                "Orchestration must be a subclass of DagsterOrchestration"
            )
            dagster_orchestration_cls = cast(
                type[DagsterOrchestration],
                orchestration,
            )
            dagster_orchestration: DagsterOrchestration = (
                dagster_orchestration_cls.New()
            )
            definitions = dagster_orchestration.definitions

            all_definitions.append(definitions)

if all_definitions:
    definitions = Definitions.merge(*all_definitions)
else:
    definitions = Definitions()
