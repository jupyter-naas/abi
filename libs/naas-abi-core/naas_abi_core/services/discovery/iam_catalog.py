"""The ``discovery`` action catalog (RFC §6.4, "discovery").

Every resource is platform-level. A module registers only under its own
service account. Invoking an agent, chatting with a module's model, opening an
app and triggering or cancelling a job need the caller's policy: a READY
provider is not enough. A run is personal: its owner is the call's user, or the
actor when the call is on behalf of no one.
"""

from __future__ import annotations

from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType

SERVICE = "discovery"
SUBJECT_PREFIX = "abi.discovery.*.v1"


def _action(
    name: str,
    level: str,
    types: tuple[str, ...],
    *subjects: str,
    creates: bool = False,
    description: str = "",
) -> ActionSpec:
    return ActionSpec(
        name=name,
        level=level,  # type: ignore[arg-type]
        resource_types=types,
        creates=creates,
        subjects=tuple(
            s if s.startswith("abi.") else f"{SUBJECT_PREFIX}.{s}" for s in subjects
        ),
        description=description,
    )


CATALOG = ActionCatalog(
    service=SERVICE,
    version=1,
    resource_types=(
        ResourceType("module", id="path", placement="platform"),
        ResourceType("agent", id="path", placement="platform"),
        ResourceType("model", id="path", placement="platform"),
        ResourceType("app", id="path", placement="platform"),
        ResourceType("job", id="path", placement="platform"),
        ResourceType(
            "run",
            id="path",
            placement="platform",
            personal=True,
            description="run/<owner>/<project>/<invocation id>: an agent run.",
        ),
        ResourceType(
            "job_run",
            id="path",
            placement="platform",
            description="job_run/<project>/<module id>/<job>/<run id>.",
        ),
    ),
    actions=(
        _action("ListModules", "list", ("module",), "list_modules"),
        _action("GetModule", "read", ("module",), "get_module"),
        _action("Register", "write", ("module",), "register"),
        _action("Renew", "write", ("module",), "renew"),
        _action("Unregister", "write", ("module",), "unregister"),
        _action("Evict", "admin", ("module",), "evict"),
        _action("ListAgents", "list", ("agent",)),
        _action(
            "InvokeAgent",
            "write",
            ("agent", "run"),
            "abi.agent.*.*.*.*.v1.submit",
            creates=True,
        ),
        _action(
            "GetAgentRun",
            "read",
            ("run",),
            "abi.agent.*.*.*.*.v1.status",
            "abi.agent.*.*.*.*.v1.event",
        ),
        _action("CancelAgentRun", "write", ("run",), "abi.agent.*.*.*.*.v1.cancel"),
        _action("ChatModel", "read", ("model",), "abi.mod.*.*.*.model.*.chat"),
        _action("ListApps", "list", ("app",)),
        _action("OpenApp", "read", ("app",), "abi.mod.*.*.*.app.*.http"),
        _action("ListJobs", "list", ("job",)),
        _action("TriggerJob", "write", ("job",), "abi.jobs.*.trigger.>"),
        _action("ScheduleJob", "write", ("job",), "abi.jobs.*.schedule.>"),
        _action("ListJobRuns", "list", ("job_run",)),
        _action("GetJobRun", "read", ("job_run",)),
        _action("CancelJobRun", "write", ("job_run",), "abi.jobs.*.cancel.>"),
    ),
)
