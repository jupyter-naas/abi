"""``ServiceBase.wired_iam``: when a wired service runs without enforcement."""

from __future__ import annotations

import pytest

from naas_abi_core import logger
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services import ServiceBase as service_base
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.ServiceBase import ServiceBase


class _Service(ServiceBase):
    pass


@pytest.fixture
def warnings():
    service_base._WARNED_UNENFORCED.clear()
    seen: list[str] = []
    sink = logger.add(lambda message: seen.append(str(message)), level="WARNING")
    yield seen
    logger.remove(sink)
    service_base._WARNED_UNENFORCED.clear()


def test_a_service_used_on_its_own_does_not_enforce_and_says_nothing(warnings):
    assert _Service().wired_iam() is None
    assert warnings == []


def test_a_wired_service_gets_the_engines_iam():
    iam = IAMService(IAMStoreMemory())
    service = _Service()
    service.set_services(IEngine.Services(iam=iam))
    assert service.wired_iam() is iam


def test_a_wired_service_without_iam_runs_unenforced_and_warns_once(warnings):
    for _ in range(2):
        service = _Service()
        service.set_services(IEngine.Services())
        assert service.wired_iam() is None
        service.wired_iam()
    assert len(warnings) == 1 and "_Service" in warnings[0]


def test_services_that_cannot_say_whether_they_have_iam_warn(warnings):
    class Opaque:
        pass

    service = _Service()
    service.set_services(Opaque())  # type: ignore[arg-type]
    assert service.wired_iam() is None
    assert len(warnings) == 1 and "no IAM" in warnings[0]


def test_an_iam_that_is_not_an_iam_service_fails_closed():
    class Fake:
        def iam_available(self) -> bool:
            return True

        iam = object()

    service = _Service()
    service.set_services(Fake())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="refusing to run unenforced"):
        service.wired_iam()
