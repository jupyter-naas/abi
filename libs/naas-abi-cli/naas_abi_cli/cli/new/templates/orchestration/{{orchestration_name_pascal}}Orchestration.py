import dagster as dg
from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration


class {{orchestration_name_pascal}}Orchestration(DagsterOrchestration):
    """Dagster definitions for a project without NATS (legacy, to be removed in
    the next major). Needs the naas-abi-core[dagster] extra."""

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