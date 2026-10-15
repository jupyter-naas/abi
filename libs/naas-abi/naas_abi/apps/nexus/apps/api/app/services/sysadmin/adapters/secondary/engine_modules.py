"""Modules loaded in this engine process (``engine.modules``)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.job_summaries import (
    summarize_job,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import EngineModule


def _count(module: Any, attribute: str) -> int:
    try:
        return len(getattr(module, attribute, ()) or ())
    except Exception:  # noqa: BLE001 - one broken module must not hide the others
        return 0


def _text(module: Any, attribute: str) -> str:
    try:
        value = getattr(module, attribute, "")
    except Exception:  # noqa: BLE001
        return ""
    return value if isinstance(value, str) else ""


class EngineModules:
    def __init__(self, modules: Callable[[], Mapping[str, Any]]) -> None:
        self._modules = modules

    async def list_modules(self) -> list[EngineModule]:
        found = []
        for module_id, module in sorted(self._modules().items()):
            try:
                jobs = tuple(summarize_job(j) for j in getattr(module, "jobs", ()) or ())
            except Exception:  # noqa: BLE001
                jobs = ()
            found.append(
                EngineModule(
                    module_id=module_id,
                    name=_text(module, "name"),
                    description=_text(module, "description"),
                    agents=_count(module, "agents"),
                    orchestrations=_count(module, "orchestrations"),
                    ontologies=_count(module, "ontologies"),
                    jobs=jobs,
                )
            )
        return found
