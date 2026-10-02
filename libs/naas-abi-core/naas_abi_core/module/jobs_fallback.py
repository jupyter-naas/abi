"""Job declarations when ``naas-abi-sdk`` is not installed (core without ``[nats]``).

Jobs only run in NATS mode, which needs the SDK. Without it, modules that declare
jobs must still import and load: these stand-ins keep the declarations (the
engine then logs that they are not hosted) and validate nothing.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, ClassVar

JOBS_AVAILABLE = False


@dataclass(frozen=True)
class Cron:
    expression: str
    time_zone: str = ""


@dataclass(frozen=True)
class Every:
    interval: str | timedelta


@dataclass(frozen=True)
class OnEvent:
    subject: str | None = None
    event_type: str | None = None


@dataclass(frozen=True)
class JobDescriptor:
    name: str
    description: str = ""
    triggers: tuple[Any, ...] = ()
    max_concurrency: int = 1
    timeout: timedelta | None = None
    max_attempts: int = 1
    contract_major: int = 1


@dataclass
class JobContext:
    run_id: str
    job: str
    attempt: int
    trigger: dict[str, str]
    payload: dict[str, Any]
    cancelled: asyncio.Event = field(default_factory=asyncio.Event)
    logs: list[str] = field(default_factory=list)

    def log(self, message: str) -> None:
        self.logs.append(str(message))


def job(
    name: str | None = None,
    description: str = "",
    *,
    triggers: tuple[Any, ...] = (),
    max_concurrency: int = 1,
    timeout: timedelta | None = None,
    max_attempts: int = 1,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorate(method: Callable[..., Any]) -> Callable[..., Any]:
        method.__abi_job__ = JobDescriptor(  # type: ignore[attr-defined]
            name=name or method.__name__,
            description=description,
            triggers=tuple(triggers),
            max_concurrency=max_concurrency,
            timeout=timeout,
            max_attempts=max_attempts,
        )
        return method

    return decorate


class JobsMixin:
    jobs: tuple[Any, ...] = ()
    _decorated_jobs: ClassVar[dict[str, str]] = {}
    _sync_jobs: ClassVar[bool] = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        decorated = {
            attr.__abi_job__.name: (attr_name, attr.__abi_job__)
            for attr_name, attr in vars(cls).items()
            if hasattr(attr, "__abi_job__")
        }
        declared = list(cls.jobs)
        declared += [
            d for _, d in decorated.values() if all(d is not j for j in declared)
        ]
        cls.jobs = tuple(declared)
        inherited = dict(getattr(cls, "_decorated_jobs", {}))
        inherited.update({n: attr_name for n, (attr_name, _) in decorated.items()})
        cls._decorated_jobs = inherited

    @property
    def _job_handlers(self) -> dict[str, Callable[..., Any]]:
        handlers = self.__dict__.get("_abi_job_handlers")
        if handlers is None:
            handlers = {n: getattr(self, a) for n, a in self._decorated_jobs.items()}
            self.__dict__["_abi_job_handlers"] = handlers
        return handlers

    def expose_job(self, name: str, handler: Callable[..., Any]) -> None:
        self._job_handlers[name] = handler

    def missing_job_handlers(self) -> set[str]:
        return {j.name for j in self.jobs} - set(self._job_handlers)
