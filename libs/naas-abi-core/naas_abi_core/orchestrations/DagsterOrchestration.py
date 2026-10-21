import functools
import inspect
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

from naas_abi_core.orchestrations.Orchestrations import Orchestrations
from naas_abi_core.utils.LegacyExtras import raise_missing_extra

if TYPE_CHECKING:
    from dagster import Definitions

F = TypeVar("F", bound=Callable[..., Any])


def as_engine(fn: F) -> F:
    """Run a Dagster op, asset, sensor or schedule body as the engine's
    service account.

    Dagster calls these bodies from its own run workers and code-server
    threads, with no caller: without this, every engine call they make is
    anonymous, which IAM denies. Put it under the Dagster decorator, as the
    innermost one, so Dagster still reads the function's own signature.
    """
    from naas_abi_core.engine.call_context import as_service_account

    if inspect.isgeneratorfunction(fn):

        @functools.wraps(fn)
        def generate(*args: Any, **kwargs: Any) -> Any:
            with as_service_account("engine"):
                yield from fn(*args, **kwargs)

        return generate  # type: ignore[return-value]

    @functools.wraps(fn)
    def run(*args: Any, **kwargs: Any) -> Any:
        with as_service_account("engine"):
            return fn(*args, **kwargs)

    return run  # type: ignore[return-value]


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
