"""Workspace tasks (weekly iterations, board view), behind the ``tasks`` feature.

Reading the board, the feed and the comments is a viewer's; changing tasks,
iterations and one's own comments a member's; the settings and others'
comments an admin's. Every action also needs ``UseFeature`` on ``tasks``, which
a policy grants, never a role.
"""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (rtype("task"),)

ACTIONS = (
    action("ListTasks", "read", "task", feature="tasks"),
    action("UpdateTasks", "write", "task", feature="tasks"),
    action("ManageTasks", "admin", "task", feature="tasks"),
)
