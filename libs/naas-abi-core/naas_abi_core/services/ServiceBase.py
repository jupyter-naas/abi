from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from naas_abi_core.engine.IEngine import IEngine


class ServiceBase:
    
    def __init__(self) -> None:
        self._services: Optional["IEngine.Services"] = None

    def set_services(self, services: "IEngine.Services") -> None:
        self._services = services

    @property
    def services_wired(self) -> bool:
        return self._services is not None

    @property
    def services(self) -> "IEngine.Services":
        assert self._services is not None, "Services are not wired"
        return self._services
