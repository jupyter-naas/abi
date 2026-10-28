"""Which module scope an app is (core ``services/iam/module_scopes``).

Every app is a module's: ``app/<module>/<name>`` of the ``module`` catalog, and
``module:OpenApp`` in the workspace decides who lists it, opens it, and gets a
link or a grant to it. An engine module's app id is ``<module path>:<app dir>``
(the module path is the engine module's configured key); a remote module's is
``remote/<module id>:<app>``.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
from naas_abi_core.services.iam.module_scopes import APP

REMOTE_PREFIX = "remote/"


def app_scope(app_id: str) -> ModuleScope | None:
    """``app_id``'s module scope; None for an id that names no module's app."""
    rest = app_id.removeprefix(REMOTE_PREFIX)
    module, _, name = rest.rpartition(":")
    if not module or not name:
        return None
    return ModuleScope(APP, module, name)
