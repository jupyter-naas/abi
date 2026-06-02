import dagster as dg
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration


class XOrchestration(DagsterOrchestration):

    @classmethod
    def New(cls) -> "XOrchestration":
        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=[],
                jobs=[],
                sensors=[],
            )
        )