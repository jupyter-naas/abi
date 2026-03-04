import dagster as dg
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration


class {{orchestration_name_pascal}}Orchestration(DagsterOrchestration):

    @classmethod
    def New(cls) -> "{{orchestration_name_pascal}}Orchestration":
        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=[],
                jobs=[],
                sensors=[],
            )
        )