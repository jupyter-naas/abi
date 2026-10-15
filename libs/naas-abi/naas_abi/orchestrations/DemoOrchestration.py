from naas_abi_core.orchestrations.DagsterOrchestration import DagsterOrchestration
from naas_abi_core.utils.LegacyExtras import raise_missing_extra


class DemoOrchestration(DagsterOrchestration):
    """An empty Dagster orchestration, for projects without NATS (legacy, see
    ``DagsterOrchestration``). Dagster is imported in ``New`` so the module
    loads without the ``naas-abi-core[dagster]`` extra."""

    @classmethod
    def New(cls) -> "DemoOrchestration":
        try:
            import dagster as dg
        except ModuleNotFoundError as error:
            raise_missing_extra(error, cls.__name__)
        return cls(
            definitions=dg.Definitions(
                assets=[],
                schedules=[],
                jobs=[],
                sensors=[],
            )
        )
