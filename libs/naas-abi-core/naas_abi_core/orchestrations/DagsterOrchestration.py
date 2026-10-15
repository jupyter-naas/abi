from typing import TYPE_CHECKING

from naas_abi_core.orchestrations.Orchestrations import Orchestrations
from naas_abi_core.utils.LegacyExtras import raise_missing_extra

if TYPE_CHECKING:
    from dagster import Definitions


class DagsterOrchestration(Orchestrations):
    """A module's Dagster definitions, which ``naas_abi_core.apps.dagster``
    merges and serves.

    Legacy, for projects without NATS, to be removed in the next major: NATS
    projects schedule with module jobs. Dagster comes with the
    ``naas-abi-core[dagster]`` extra. This class imports without it, so a
    module's orchestrations load in any install; ``New`` and the Dagster app
    need it.
    """

    __definitions: "Definitions"

    def __init__(self, definitions: "Definitions"):
        self.__definitions = definitions

    @property
    def definitions(self) -> "Definitions":
        return self.__definitions

    @classmethod
    def New(cls) -> "DagsterOrchestration":
        try:
            from dagster import Definitions
        except ModuleNotFoundError as error:
            raise_missing_extra(error, cls.__name__)
        return cls(definitions=Definitions())
