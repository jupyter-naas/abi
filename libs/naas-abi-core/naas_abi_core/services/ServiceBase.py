from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from naas_abi_core.engine.IEngine import IEngine
    from naas_abi_core.services.iam.IAMPorts import IIAMService

_WARNED_UNENFORCED: set[str] = set()


class ServiceBase:
    def __init__(self) -> None:
        self._services: IEngine.Services | None = None

    def set_services(self, services: "IEngine.Services") -> None:
        self._services = services

    @property
    def services_wired(self) -> bool:
        return self._services is not None

    @property
    def services(self) -> "IEngine.Services":
        assert self._services is not None, "Services are not wired"
        return self._services

    def wired_iam(self) -> Optional["IIAMService"]:
        """The engine's IAM once this service is wired into an engine that has
        it; None for a service used on its own, which does not enforce.

        A wired engine that offers no usable IAM is not that: the service then
        runs unenforced, which is logged once per service class, and an IAM the
        engine offers but that is not an ``IIAMService`` fails closed.
        """
        if self._services is None:
            return None
        from naas_abi_core.services.iam.IAMPorts import IIAMService

        available = getattr(self._services, "iam_available", None)
        if not callable(available):
            self._warn_unenforced("its services offer no IAM")
            return None
        if available() is not True:
            self._warn_unenforced("the engine has no IAM service")
            return None
        iam = self._services.iam  # type: ignore[union-attr]
        if not isinstance(iam, IIAMService):
            raise TypeError(
                f"{type(self).__name__} is wired with an IAM that is not an "
                f"IIAMService ({type(iam).__name__}); refusing to run unenforced"
            )
        return iam

    def _warn_unenforced(self, reason: str) -> None:
        name = type(self).__name__
        if name in _WARNED_UNENFORCED:
            return
        _WARNED_UNENFORCED.add(name)
        from naas_abi_core import logger

        logger.warning(f"{name} is wired but runs without IAM enforcement: {reason}")
