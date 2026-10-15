"""Job bodies, kept apart from the module class so they test without a broker.

A job is declared on ``ABIModule`` with ``@job(..., triggers=(...))``:
``Every("1h")``, ``Cron("0 2 * * *")`` or ``OnEvent(...)``. JetStream fires the
trigger and one replica of this module runs it. Delivery is at least once, so a
job must tolerate running twice.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from naas_abi_sdk.jobs import JobContext

    from {{module_name_snake}} import ABIModule


async def heartbeat(module: ABIModule, ctx: JobContext) -> dict[str, Any]:
    """Record that the module ran. Replace with real work."""
    ctx.log(f"{module.module_id} is alive (attempt {ctx.attempt})")
    # The result is stored on the run record (Nexus System app, Jobs tab).
    return {"module": module.module_id, "at": datetime.now(UTC).isoformat()}
