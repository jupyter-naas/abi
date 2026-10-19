"""The code section: coding environments, repositories and code review.

Repositories and environments are kernel resources (``source_control`` and
``coding_environment``, placed in the workspace), and the kernel decides on them
with the user's role. What the routes ask of the ``nexus`` catalog is the gate
of the section: the ``code`` feature, and the level of what the route does
(viewers read, members write). The default repository is a setting of the
workspace.
"""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (
    rtype("code", id="singleton"),
    rtype("code_settings", id="singleton"),
)

ACTIONS = (
    # Browse repositories, branches, proposals and checks; see one's environments.
    action("ReadCode", "read", "code", feature="code"),
    # Create repositories, branches and environments, comment, review, merge,
    # open an environment (it hands out a session).
    action("WriteCode", "write", "code", feature="code"),
    action("SetDefaultRepo", "admin", "code_settings", feature="code"),
)
