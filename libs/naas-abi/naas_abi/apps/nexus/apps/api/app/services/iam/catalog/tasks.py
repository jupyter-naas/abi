"""Workspace tasks (``/api/tasks`` and the Tasks agent), behind the ``tasks`` feature.

``task/<task_id>`` is one task with its comments and history; ``task/-`` is the
workspace's board: listing, creating, the activity feed. ``task_iteration/<id>``
is one week (``-``: the list, and opening the week of a date) and
``task_settings`` the workspace's stages, priorities, rhythm and feed.

A comment's author removes it with ``DeleteTaskComment`` (the domain service
checks the authorship); removing someone else's is ``ModerateTaskComments``.
"""

from naas_abi.apps.nexus.apps.api.app.services.iam.catalog.dsl import action, rtype

TYPES = (
    rtype("task"),
    rtype("task_iteration"),
    rtype("task_settings", id="singleton"),
)

ACTIONS = (
    # The board, the backlog, every task of the workspace (``task/-``).
    action("ListTasks", "list", "task", feature="tasks"),
    # One task's history, or the workspace's feed (``task/-``).
    action("ListTaskActivity", "read", "task", feature="tasks"),
    action("ListTaskComments", "read", "task", feature="tasks"),
    action("CreateTask", "write", "task", feature="tasks"),
    # Edit, archive and restore.
    action("UpdateTask", "write", "task", feature="tasks"),
    action("DeleteTask", "write", "task", feature="tasks"),
    action("AddTaskComment", "write", "task", feature="tasks"),
    # One's own comment (and its replies).
    action("DeleteTaskComment", "write", "task", feature="tasks"),
    # Someone else's comment.
    action("ModerateTaskComments", "admin", "task", feature="tasks"),
    action("ListTaskIterations", "list", "task_iteration", feature="tasks"),
    # The iteration of a date, created when missing (``task_iteration/-``).
    action("CreateTaskIteration", "write", "task_iteration", feature="tasks"),
    # Its goal.
    action("UpdateTaskIteration", "write", "task_iteration", feature="tasks"),
    # Moves its unfinished tasks to the iteration after it.
    action("CarryOverTasks", "write", "task_iteration", feature="tasks"),
    action("GetTaskSettings", "read", "task_settings", feature="tasks"),
    action("UpdateTaskSettings", "admin", "task_settings", feature="tasks"),
)
