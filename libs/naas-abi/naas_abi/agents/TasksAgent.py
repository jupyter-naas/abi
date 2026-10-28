from naas_abi.agents.feature import (
    FEATURE_RECURSION_LIMIT,
    build_feature_agent,
    configured_feature_model,
    feature_handoff_intents,
    feature_system_prompt,
)
from naas_abi_core.services.agent.IntentAgent import (
    AgentConfiguration,
    AgentSharedState,
    Intent,
    IntentAgent,
)

_API = "naas_abi/apps/nexus/apps/api"
_SERVICE = f"{_API}/app/services/tasks"
_WEB = "naas_abi/apps/nexus/apps/web/src"
_PAGE = f"{_WEB}/app/workspace/[workspaceId]/tasks"

TASKS_CODE_MAP = f"""API (hexagonal domain, mounted at /api/tasks):
- {_SERVICE}/tasks__schema.py: Task, Iteration, Comment, ActivityEntry, TasksSettings, event kinds (ACTIVITY_KINDS), limits.
- {_SERVICE}/service.py: TasksService (iterations, create/update/archive/delete, carry-over, comments and replies, activity, the sidebar feed, settings validation, GitHub issue URLs).
- {_SERVICE}/port.py, {_SERVICE}/adapters/secondary/postgres.py, {_SERVICE}/adapters/secondary/memory.py: the store port and its adapters.
- {_SERVICE}/adapters/primary/tasks__primary_adapter__FastAPI.py: the routes and their access rules (workspace access, `tasks` feature, owner/admin for settings).
- {_API}/migrations/0059_add_tasks.sql, 0060_task_settings.sql, 0061_task_events.sql, 0062_task_github_issue.sql: the tables.
Web:
- {_PAGE}/tasks.tsx: the page (scope tabs, Board / Table / Gallery / Calendar layouts, New task form, drawer).
- {_PAGE}/components/task-drawer.tsx, task-create-dialog.tsx, task-card.tsx: task panel (comments, replies, activity), creation form, cards.
- {_PAGE}/lib/task-schema.ts and use-tasks.ts: properties, saved views, scope logic.
- {_PAGE}/settings/tasks-settings.tsx: the settings page.
- {_WEB}/lib/tasks.ts, {_WEB}/lib/task-events.ts, {_WEB}/stores/tasks.ts: API client, event summaries, shared store.
- {_WEB}/components/shell/sidebar/tasks-section.tsx: the sidebar dashboard and activity feed.
Decision record: docs/adr/20261023_workspace_tasks.md.
Agent: naas_abi/agents/TasksAgent.py and naas_abi/tools/tasks_tools.py."""

TASKS_CAPABILITIES = """- Tasks live in stages (Inbox first, Done last, custom stages between) and in weekly iterations: the Current, Last and Next iteration tabs, plus Inbox (requests to triage) and Backlog (triaged, no iteration).
- Each task has a title, Markdown content, stage, assignees (workspace members), priority, labels, due date, iteration and an optional GitHub issue URL. Its workspace and created / updated by and at are set by the server.
- Layouts: Board (stage columns, drag a card to change its stage, drop it on a tab to move it), Table, Gallery, Calendar; saved views per user with search, filters, sort and grouping.
- Comments with one level of replies; authors remove their own comments, owners and admins remove anyone's.
- Every change is recorded: the task's Activity tab and the sidebar activity feed (newest first, configurable in settings).
- Archive (recoverable) or delete (for everyone). "Move unfinished to next" carries every task that is not Done to the next iteration.
- Settings (owners and admins): iteration length and start day, stages, priorities, default stage of new tasks, suggested labels, activity feed (on/off, event kinds, length).
- Feature flag `tasks`: owners and admins by default; an organization or workspace override can open it to members."""

_HANDOFF_PHRASES = (
    "create a task",
    "what's in the current iteration",
    "move this task to review",
    "assign the task to",
    "comment on the task",
    "what changed in tasks",
    "change the task stages",
    "crée une tâche",
    "quelles tâches sont dans l'itération en cours",
    "assigne la tâche à",
    "ajoute un commentaire sur la tâche",
)


class TasksAgent(IntentAgent):
    """Office agent for Nexus Tasks.

    Run: LOG_LEVEL=DEBUG uv run abi chat naas_abi TasksAgent
    """

    name: str = "Tasks"
    description: str = (
        "Office agent for Nexus Tasks. Lists, creates, updates, moves, assigns, "
        "archives and deletes tasks, comments and replies on them, carries "
        "unfinished work over, reports what changed, changes the tasks "
        "settings, and explains how Tasks is built, from the code."
    )
    logo_url: str = (
        "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png"
    )
    recursion_limit: int = FEATURE_RECURSION_LIMIT
    system_prompt: str = feature_system_prompt(
        name="Tasks",
        class_name="TasksAgent",
        feature="Tasks",
        role="You run the workspace's tasks for the user: every action of the Tasks page, done with your tools.",
        context=(
            "On the Tasks page you receive an open-feature block (feature: tasks, "
            "and open_task_id when a task is open in the drawer). Your tools act "
            "as the signed-in user with the same rules as the page: a member "
            "without the tasks feature, or a non-admin changing settings, is refused."
        ),
        tasks="""1. "What can I do here?": answer from <capabilities>, with real numbers from list_tasks when it helps.
2. Acting on tasks: create_task, update_task (stage, scope, assignees, labels, priority, due date, content, GitHub issue), archive_task, delete_task, carry_over_unfinished_tasks. Resolve the task by title when the user names it; default to the open task. Report what changed from the tool result.
3. Comments: get_task shows the threads and their ids; add_task_comment (reply_to for a reply); delete_task_comment.
4. "What happened?": get_tasks_activity, for one task or the whole workspace.
5. Settings: get_tasks_settings, then update_tasks_settings (owners and admins). For stages and priorities, send the full ordered list and keep the existing keys.
6. Deleting: always ask the user before calling delete_task with confirm=True, and offer archive_task instead.
7. "How is it built?": read the files in <code_map> first, then explain with paths.""",
        capabilities=TASKS_CAPABILITIES,
        code_map=TASKS_CODE_MAP,
        constraints="- Never delete a task without the user's explicit confirmation in this conversation.",
    )
    suggestions: list[dict] = [
        {
            "label": "What can you do?",
            "value": "What can I do with Tasks in this workspace?",
        },
        {
            "label": "Current iteration",
            "value": "Summarize the current iteration: tasks by stage, who is on what, and what is overdue.",
        },
        {"label": "New task", "value": "Create a task in the current iteration: "},
        {"label": "What changed?", "value": "What changed in Tasks recently?"},
    ]

    @staticmethod
    def handoff_intents() -> list[Intent]:
        return feature_handoff_intents("Tasks", _HANDOFF_PHRASES)

    @staticmethod
    def get_tools() -> list:
        from naas_abi.tools.nexus_source_tools import nexus_source_tools
        from naas_abi.tools.tasks_tools import tasks_tools

        return tasks_tools() + nexus_source_tools()

    @classmethod
    def get_chat_model_id(cls) -> str:
        return configured_feature_model()

    @classmethod
    def get_chat_model_ids(cls) -> list[str]:
        return [configured_feature_model()]

    @classmethod
    def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
        model_id: str | None = None,
    ) -> "TasksAgent":
        return build_feature_agent(
            cls,
            tools=cls.get_tools(),
            intents=cls.handoff_intents(),
            agent_shared_state=agent_shared_state,
            agent_configuration=agent_configuration,
            model_id=model_id,
        )
