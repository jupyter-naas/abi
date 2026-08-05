from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.runtime.schema import (
    OsStatusResponse,
    RestartOsResponse,
)
from naas_abi.runtime.os_restart import (
    find_dev_project_root,
    is_restart_pending,
    read_restart_pending,
    schedule_os_restart,
)


class RuntimeService:
    @staticmethod
    async def restart_os() -> RestartOsResponse:
        result = schedule_os_restart()
        return RestartOsResponse(
            scheduled=result.scheduled,
            mode=result.mode,
            message=result.message,
        )

    @staticmethod
    async def os_status() -> OsStatusResponse:
        root = find_dev_project_root()
        pending = read_restart_pending(root) if root else None
        requested_at = None
        if pending and pending.get("requested_at") is not None:
            try:
                requested_at = float(pending["requested_at"])
            except (TypeError, ValueError):
                requested_at = None
        return OsStatusResponse(
            dev_runtime_available=root is not None,
            restarting=is_restart_pending(root),
            requested_at=requested_at,
        )
