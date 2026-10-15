"""The nine staff-system folders, shared by the workspace drive and the platform drive."""

from __future__ import annotations

from functools import cache
from pathlib import Path

from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import MODULE_ROOT
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.objects import object_exists
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

README_NAME = "README.md"
# The nine staff system functions, S1 to S9.
STAFF_FOLDERS = (
    "personnel",
    "intelligence",
    "operations",
    "logistics",
    "plans",
    "signals",
    "training",
    "finance",
    "external",
)
STAFF_FOLDERS_MARKER_ROOT = f"{MODULE_ROOT}/.scaffolded/staff-folders"
# drives/utils/staff_folders.py -> nexus/assets/staff_folders
_TEMPLATES_DIR = Path(__file__).resolve().parents[7] / "assets" / "staff_folders"


@cache
def staff_folder_readme(folder: str) -> str:
    """The folder's own text followed by the layout section shared by all nine."""
    body = (_TEMPLATES_DIR / f"{folder}.md").read_text(encoding="utf-8")
    layout = (_TEMPLATES_DIR / "_layout.md").read_text(encoding="utf-8")
    return body.rstrip("\n") + "\n" + layout


def write_staff_folders(storage: ObjectStorageService, root: str) -> None:
    """Create the nine folders and their README under *root*, keeping anything already there."""
    for folder in STAFF_FOLDERS:
        prefix = f"{root}/{folder}"
        if not object_exists(storage, prefix, FilesService.folder_marker):
            storage.put_object(prefix, FilesService.folder_marker, b"")
        if not object_exists(storage, prefix, README_NAME):
            storage.put_object(prefix, README_NAME, staff_folder_readme(folder).encode("utf-8"))
