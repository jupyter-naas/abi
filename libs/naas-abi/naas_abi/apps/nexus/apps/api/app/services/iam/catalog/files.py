"""Files: ``file/<drive>/<path>``, a user's own drives, and the platform's storage.

``<drive>`` is ``workspace`` or ``platform`` for the actions every role has by
level, and ``system`` for the admin-only actions that reach the whole object
storage tree of the workspace. ``organization`` is the organization drive, named
in the organization's container (``<org container>/nexus:file/organization/<path>``)
and decided by its own actions: its viewers and up read it, its admins and owners
write it, and a policy at the organization widens or narrows that per folder
(members writing ``operations/``, say). The drives a user owns (My drive, the storage
``abi-platform`` moves data through) are personal, platform-level types named
``<type>/<user>/<path>``: they belong to no workspace, and a user reaches
their own through ``PLATFORM_ACCESS`` below (and the object storage under
them through the kernel's ``roles.PLATFORM_TYPES``).
"""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype
from naas_abi_core.services.iam.catalog import PlatformAccess

TYPES = (
    rtype("file", id="path"),
    rtype("my_file", id="path", personal=True, platform=True),
    rtype("user_storage", id="path", personal=True, platform=True),
    rtype("root_storage", id="singleton", platform=True),
)

ACTIONS = (
    # The workspace drive and the shared platform drive.
    action("ListFiles", "list", "file", feature="files"),
    action("GetFile", "read", "file", feature="files"),
    action("PutFile", "write", "file", feature="files"),
    action("DeleteFile", "write", "file", feature="files"),
    # The system drive: every key of the object storage tree, an admin's.
    action("ListSystemFiles", "admin", "file", feature="files"),
    action("GetSystemFile", "admin", "file", feature="files"),
    action("PutSystemFile", "admin", "file", feature="files"),
    action("DeleteSystemFile", "admin", "file", feature="files"),
    # The organization drive, decided at the organization: read by its viewers and
    # up, written by its admins and owners (more through a policy there). The
    # ``files`` feature is the workspace's it is reached through (the route's).
    action("ListOrgFiles", "list", "file", feature="files"),
    action("GetOrgFile", "read", "file", feature="files"),
    action("PutOrgFile", "admin", "file", feature="files"),
    action("DeleteOrgFile", "admin", "file", feature="files"),
    # My drive.
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

# A user's own drive and storage: read by viewers, written by members.
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
