from __future__ import annotations

import os

from fastapi import Depends
from naas_abi.apps.nexus.apps.api.app.services.code.adapters.secondary.local_filesystem import (
    LocalFilesystemAdapter,
)
from naas_abi.apps.nexus.apps.api.app.services.code.adapters.secondary.my_drive_filesystem import (
    MyDriveFilesystemAdapter,
)
from naas_abi.apps.nexus.apps.api.app.services.code.adapters.secondary.opencode_http import (
    OpencodeHttpAdapter,
    get_broadcast_logs_adapter,
)
from naas_abi.apps.nexus.apps.api.app.services.code.filesystem_service import CodeFilesystemService
from naas_abi.apps.nexus.apps.api.app.services.code.opencode_service import CodeOpencodeService
from naas_abi.apps.nexus.apps.api.app.services.code.workdir_sync_service import (
    CodeWorkdirSyncService,
)
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__dependencies import (
    get_files_service,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService


def get_code_filesystem_service(
    files_service: FilesService = Depends(get_files_service),
) -> CodeFilesystemService:
    backend = os.environ.get("CODE_SANDBOX_BACKEND", "my_drive").strip().lower()
    if backend == "local":
        return CodeFilesystemService(adapter=LocalFilesystemAdapter())
    return CodeFilesystemService(adapter=MyDriveFilesystemAdapter(files_service=files_service))


def get_code_workdir_sync_service(
    files_service: FilesService = Depends(get_files_service),
) -> CodeWorkdirSyncService:
    return CodeWorkdirSyncService(files_service=files_service)


def get_code_opencode_service(
    sync_service: CodeWorkdirSyncService = Depends(get_code_workdir_sync_service),
) -> CodeOpencodeService:
    return CodeOpencodeService(
        adapter=OpencodeHttpAdapter(),
        sync_service=sync_service,
    )


def get_code_logs_adapter():
    return get_broadcast_logs_adapter()
