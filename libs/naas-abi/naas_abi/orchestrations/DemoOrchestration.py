import dagster as dg
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration


class DemoOrchestration(DagsterOrchestration):

    @classmethod
    def New(cls) -> "DemoOrchestration":
        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=[],
                jobs=[],
                sensors=[],
            )
        )