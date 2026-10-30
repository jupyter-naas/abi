"""P, People Intelligence's stand-in: agents A (``Recruiter``) and B (``Scout``),
an action of its own, ``dev_people:ExportReport`` on a ``report``, and a
container type of its own, ``dev_people:project``: a project inside a workspace,
whose reports a policy attached at the project reaches, and nothing else of the
workspace.

The agents answer without a model. ``Recruiter`` acts for the user it runs for:

* ``export <report>`` enforces the declared action: IAM decides with that
  user's grants in the workspace of the chat and this module's approved
  manifest; ``export <report> in <project>`` makes the same call inside the
  project (the report is named in it);
* ``project <id>`` registers a project in the workspace of the chat (a create
  on its name as placed: the user and this module both need
  ``dev_people:CreateProject`` there);
* ``policy <scope> <type>/<module>/<name> [under <parent>]`` creates, over
  NATS, a policy owned by ``scope`` letting its holders use that item, a
  sub-policy of ``parent`` if named: IAM refuses it as it refuses the user over
  REST when the user could not grant it or derive from the parent ("Grant only
  what you hold"), so the scenario shows the same refusal on both.
"""

from __future__ import annotations

import asyncio

from naas_abi_sdk import AgentDescriptor, BaseModule, ModuleDependencies
from naas_abi_sdk.call_context import current_call_context, inside
from naas_abi_sdk.permissions import default_manifest
from naas_abi_sdk.services.errors import NotFound, PermissionDenied, ServiceError

MODULE_ID = "dev.people"
# A manifest holds at least one statement: its own documents.
DEPENDENCIES = ModuleDependencies(services=("document",))
AGENT_INVOKE = ("agent.invoke.v1",)

SERVICE = "dev_people"
# Its own catalog, ``dev_people``: registered when its manifest is approved
# (``abi dev up`` approves dev modules), granted in Roles & permissions. A
# ``project`` is a container: a step of the names of the reports in it.
REPORTS = {
    "resource_types": [
        {"name": "report", "id": "path", "description": "A people report."},
        {
            "name": "project",
            "container": True,
            # Registered in a workspace only.
            "parents": ["nexus:workspace"],
            "description": "A people project, inside a workspace.",
        },
    ],
    "actions": [
        {
            "name": "ExportReport",
            "level": "read",
            "resource_types": ["report"],
            "description": "Export a people report.",
        },
        {
            "name": "GetProject",
            "level": "read",
            "resource_types": ["project"],
            "description": "Read a project: who may, finds it by its id.",
        },
        {
            "name": "CreateProject",
            "level": "write",
            "resource_types": ["project"],
            "creates": True,
            "description": "Register a project in a workspace.",
        },
        {
            "name": "DeleteProject",
            "level": "admin",
            "resource_types": ["project"],
            "deletes": True,
            "description": "Delete a project and what it holds.",
        },
    ],
}


USE = {"agent": "UseAgent", "app": "OpenApp", "workflow": "RunWorkflow"}


class EchoAgent:
    """An agent that needs no model: it says who answered."""

    def __init__(self, module: BaseModule, name: str) -> None:
        self.module = module
        self.name = name

    async def answer(self, prompt: str) -> str:
        # Nexus puts the user's profile before the message: the request is the
        # last line.
        request = (prompt.strip().splitlines() or [""])[-1].strip()
        if self.name == "Recruiter" and request.lower().startswith("project "):
            return await self.project(request[len("project ") :].strip())
        if self.name == "Recruiter" and request.lower().startswith("export"):
            words = request[len("export") :].split()
            report = words[0] if words else "q3"
            project = words[2] if len(words) == 3 and words[1] == "in" else None
            return await self.export(report, project)
        if self.name == "Recruiter" and request.lower().startswith("policy "):
            parts = request.split()
            parent = None
            if len(parts) == 5 and parts[3] == "under":
                parent = parts[4]
                parts = parts[:3]
            kind = parts[2].split("/")[0] if len(parts) == 3 else ""
            if kind not in USE:
                return (
                    f"{self.name}: say policy <scope> <type>/<module>/<name> "
                    f"[under <parent policy id>], <type> one of {', '.join(USE)}"
                )
            _, scope, item = parts
            document = {
                "version": "2026-10-13",
                "statements": [
                    {
                        "effect": "Allow",
                        "actions": [f"module:{USE[kind]}"],
                        "resources": [f"${{scope}}/module:{item}"],
                    }
                ],
            }
            try:
                created = await self.module.engine.services.iam.create_policy(
                    f"Use {item}", document, scope=scope, parent=parent
                )
            except ServiceError as exc:
                return f"{self.name}: policy refused ({type(exc).__name__}: {exc})"
            return f"{self.name}: policy {created['id']} created"
        return f"{self.name} of {MODULE_ID} answers: {request}"

    async def project(self, project: str) -> str:
        """Register a project in the workspace of the chat."""
        iam = self.module.engine.services.iam
        try:
            created = await iam.register_container(
                SERVICE, "project", project, parent=current_call_context().container
            )
        except ServiceError as exc:
            return (
                f"{self.name}: project {project} refused ({type(exc).__name__}: {exc})"
            )
        return f"{self.name}: project {created['name']} registered"

    async def export(self, report: str, project: str | None) -> str:
        """Export a report: in the workspace of the chat, or inside a project of
        it (the call is made in the project, so the report is named there)."""
        where = None
        if project is not None:
            where = await self.module.engine.services.iam.get_container(
                SERVICE, "project", project
            )
            if not where:
                return f"{self.name}: no project {project}"
        try:
            with inside(where or current_call_context().container):
                await self.module.require_action("ExportReport", "report", report)
        except (PermissionDenied, NotFound) as exc:
            return f"{self.name}: export of report {report} refused ({exc})"
        return f"{self.name}: report {report} exported" + (
            f" from project {project}" if project else ""
        )

    async def invoke(self, prompt, context):
        return await self.answer(str(prompt))

    async def stream_invoke(self, prompt, context):
        yield {"event": "message", "data": await self.answer(str(prompt))}
        yield {"event": "done", "data": "[DONE]"}


class ABIModule(BaseModule):
    module_id = MODULE_ID
    package_version = "0.1.0"
    iam_catalog = REPORTS
    dependencies = DEPENDENCIES
    # Creating, for the users it acts for, policies to use agents: a grant made
    # for a user is checked on both sides, so the module holds what it may
    # pass on, and the user's own holdings and sets decide.
    permissions = {
        **default_manifest(DEPENDENCIES),
        "statements": [
            *default_manifest(DEPENDENCIES)["statements"],
            {
                "sid": "PoliciesForItsUsers",
                "effect": "Allow",
                "actions": ["iam:CreatePolicy"],
                "resources": ["abi:iam:policy/*", "abi:*/iam:policy/*"],
            },
            {
                "sid": "AgentsItMayPassOn",
                "effect": "Allow",
                "actions": ["module:UseAgent"],
                "resources": ["abi:module:agent/*", "abi:*/module:agent/*"],
            },
        ],
    }
    agents = (
        AgentDescriptor("Recruiter", "Agent A of P", capabilities=AGENT_INVOKE),
        AgentDescriptor("Scout", "Agent B of P", capabilities=AGENT_INVOKE),
    )

    async def on_initialized(self) -> None:
        for descriptor in self.agents:
            self.expose_agent(descriptor.name, EchoAgent(self, descriptor.name))

    async def run(self) -> None:
        # Its agents and apps are served in the background: stay up until stopped.
        await asyncio.Event().wait()
