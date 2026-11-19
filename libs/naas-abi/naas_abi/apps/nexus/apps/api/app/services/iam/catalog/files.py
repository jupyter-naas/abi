"""Files: the views of the file system (the object storage) and the platform's storage.

Each view is decided by IAM alone, no workspace flag:

* **Workspace Files**: ``file/workspace/<path>`` in the workspace, every role by level.
* **Organization Files**: ``file/organization/<path>`` in the organization's
  container (``<org container>/nexus:file/organization/<path>``), decided by its own
  actions: its viewers and up read it, its admins and owners write it, and a policy
  at the organization widens or narrows that per folder (members writing
  ``operations/``, say).
* **My Files** (``my_file/<user>/<path>``) and the storage ``abi-platform`` moves data
  through (``user_storage``): personal, platform-level types; a user reaches their own
  through ``PLATFORM_ACCESS`` below (and the object storage under them through the
  kernel's ``roles.PLATFORM_TYPES``).
* **Platform Files** (``naas_abi/platform-drive``): ``platform_file/platform/<path>``,
  platform-level and ``policy_only``: no role holds it, owners included; a policy at
  the platform grants it, the platform admin holds it. The object storage refuses its
  objects to every role too, so a grant names both halves (the ADR
  ``20261119_file_views_by_iam``): ``nexus:*PlatformFile*`` on
  ``abi:nexus:platform_file/*`` and ``object_storage:*Object*`` on
  ``abi:object_storage:object/naas_abi/platform-drive/*``.
* **System Files** (every key of the object storage): ``system_file/system/<path>``,
  platform-level and ``policy_only``: the platform admin's alone.

The ``*SystemFile`` actions on ``file/system/...`` decided System Files in a
workspace, for its admins (with the workspace flag ``system_drive_enabled``). They
stay declared, since IAM refuses a catalog dropping an action a policy names, and
authorize nothing: no route asks for them.
"""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype
from naas_abi_core.services.iam.catalog import PlatformAccess

_DEPRECATED = "Deprecated: authorizes nothing (System Files is system_file, at the platform)."

TYPES = (
    rtype("file", id="path"),
    rtype("my_file", id="path", personal=True, platform=True),
    rtype("user_storage", id="path", personal=True, platform=True),
    rtype("root_storage", id="singleton", platform=True),
    rtype(
        "platform_file",
        id="path",
        platform=True,
        policy_only=True,
        description="Platform Files: naas_abi/platform-drive, shared by the whole platform.",
    ),
    rtype(
        "system_file",
        id="path",
        platform=True,
        policy_only=True,
        description="System Files: every key of the object storage.",
    ),
)

ACTIONS = (
    # Workspace Files.
    action("ListFiles", "list", "file", feature="files"),
    action("GetFile", "read", "file", feature="files"),
    action("PutFile", "write", "file", feature="files"),
    action("DeleteFile", "write", "file", feature="files"),
    # Deprecated (catalog 12): System Files moved to ``system_file`` at the platform.
    # Kept declared for the policies that may name them; no route asks for them.
    action("ListSystemFiles", "admin", "file", feature="files", description=_DEPRECATED),
    action("GetSystemFile", "admin", "file", feature="files", description=_DEPRECATED),
    action("PutSystemFile", "admin", "file", feature="files", description=_DEPRECATED),
    action("DeleteSystemFile", "admin", "file", feature="files", description=_DEPRECATED),
    # Organization Files, decided at the organization: read by its viewers and
    # up, written by its admins and owners (more through a policy there). The
    # ``files`` feature is the workspace's it is reached through (the route's).
    action("ListOrgFiles", "list", "file", feature="files"),
    action("GetOrgFile", "read", "file", feature="files"),
    action("PutOrgFile", "admin", "file", feature="files"),
    action("DeleteOrgFile", "admin", "file", feature="files"),
    # Platform Files: nobody's until a policy at the platform grants it.
    action("ListPlatformFiles", "list", "platform_file", description="List Platform Files."),
    action("GetPlatformFile", "read", "platform_file", description="Read a Platform File."),
    action(
        "PutPlatformFile",
        "write",
        "platform_file",
        description="Create, change or move a Platform File.",
    ),
    action("DeletePlatformFile", "write", "platform_file", description="Delete a Platform File."),
    # System Files: every key of the object storage, the platform admin's.
    action(
        "ListObjectStoreFiles",
        "list",
        "system_file",
        description="List System Files: any folder of the object storage.",
    ),
    action(
        "GetObjectStoreFile",
        "read",
        "system_file",
        description="Read any file of the object storage (System Files).",
    ),
    action(
        "PutObjectStoreFile",
        "write",
        "system_file",
        description="Create, change or move any file of the object storage (System Files).",
    ),
    action(
        "DeleteObjectStoreFile",
        "write",
        "system_file",
        description="Delete any file of the object storage (System Files).",
    ),
    # My Files.
    action("ListMyFiles", "list", "my_file"),
    action("GetMyFile", "read", "my_file"),
    action("PutMyFile", "write", "my_file"),
    action("DeleteMyFile", "write", "my_file"),
    # ``/api/platform/storage``: the caller's own ``users/<id>/`` namespace.
    action("ListUserStorage", "list", "user_storage"),
    action("GetUserStorage", "read", "user_storage"),
    action("PutUserStorage", "write", "user_storage"),
    # ``root=true``: the whole datastore, every tenant's and the platform's.
    action("ReadRootStorage", "read", "root_storage"),
    action("WriteRootStorage", "admin", "root_storage"),
)

# A user's My Files and storage: read by viewers, written by members.
PLATFORM_ACCESS = (
    PlatformAccess(
        ("my_file/${principal.id}", "my_file/${principal.id}/*"),
        viewer=("ListMyFiles", "GetMyFile"),
        member=("PutMyFile", "DeleteMyFile"),
    ),
    PlatformAccess(
        ("user_storage/${principal.id}", "user_storage/${principal.id}/*"),
        viewer=("ListUserStorage", "GetUserStorage"),
        member=("PutUserStorage",),
    ),
)
