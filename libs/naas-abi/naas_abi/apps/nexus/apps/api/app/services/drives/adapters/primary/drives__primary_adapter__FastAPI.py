"""``/api/platform/drives``: the platform's drives (Platform Settings > Drives).

Read-only. The route declares ``nexus:ListDrives`` on ``abi:nexus:drive/-``, which
no role holds: the platform admin does, or whoever a policy grants it. Each row is
the drive as the engine configures it (type, provider, location) and whether it
answers; never an access key, a secret or an endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from naas_abi.apps.nexus.apps.api.app.services.drives.port import Drive, DriveStatus
from naas_abi.apps.nexus.apps.api.app.services.drives.runtime import get_drive_service
from naas_abi.apps.nexus.apps.api.app.services.drives.service import DriveService
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import guard
from pydantic import BaseModel

router = APIRouter()

LIST = "-"


class PlatformDriveLocation(BaseModel):
    label: str
    value: str


class PlatformDrive(BaseModel):
    id: str
    name: str
    type: str
    provider: str
    adapter: str
    location: list[PlatformDriveLocation]
    status: DriveStatus


def platform_drive(drive: Drive) -> PlatformDrive:
    description = drive.description
    return PlatformDrive(
        id=description.id,
        name=description.name,
        type=description.type,
        provider=description.provider,
        adapter=description.adapter,
        location=[
            PlatformDriveLocation(label=part.label, value=part.value)
            for part in description.location
        ],
        status=drive.status,
    )


@router.get(
    "",
    response_model=list[PlatformDrive],
    dependencies=[guard("ListDrives", workspace=None, literal=LIST)],
)
async def list_drives(service: DriveService = Depends(get_drive_service)) -> list[PlatformDrive]:
    """Every drive of the platform, each with whether its storage answers."""
    return [platform_drive(drive) for drive in await service.list()]
