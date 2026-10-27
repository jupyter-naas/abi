"""P, People Intelligence's stand-in: agents A (``Recruiter``) and B (``Scout``),
and an action of its own, ``dev_people:ExportReport`` on a ``report``.

The agents answer without a model. ``Recruiter`` acts for the user it runs for:

* ``export <report>`` enforces the declared action: IAM decides with that
  user's grants in the workspace of the chat and this module's approved
  manifest;
* ``policy <scope> <type>/<module>/<name>`` creates, over NATS, a policy owned
  by ``scope`` letting its holders use that item: IAM refuses it as it refuses
  the user over REST when the user could not grant it ("Grant only what you
  hold"), so the scenario shows the same refusal on both.
"""

from __future__ import annotations

import asyncio

from naas_abi_sdk import AgentDescriptor, BaseModule, ModuleDependencies
from naas_abi_sdk.permissions import default_manifest
from naas_abi_sdk.services.errors import NotFound, PermissionDenied, ServiceError

MODULE_ID = "dev.people"
# A manifest holds at least one statement: its own documents.
DEPENDENCIES = ModuleDependencies(services=("document",))
AGENT_INVOKE = ("agent.invoke.v1",)

# Its own catalog, ``dev_people``: registered when its manifest is approved
# (``abi dev up`` approves dev modules), granted in Roles & permissions.
REPORTS = {
    "resource_types": [
        {"name": "report", "id": "path", "description": "A people report."}
    ],
    "actions": [
        {
            "name": "ExportReport",
            "level": "read",
            "resource_types": ["report"],
            "description": "Export a people report.",
        }
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
        if self.name == "Recruiter" and request.lower().startswith("export"):
            report = request[len("export") :].strip() or "q3"
            try:
                await self.module.require_action("ExportReport", "report", report)
            except (PermissionDenied, NotFound) as exc:
                return f"{self.name}: export of report {report} refused ({exc})"
            return f"{self.name}: report {report} exported"
        if self.name == "Recruiter" and request.lower().startswith("policy "):
            _, scope, item = request.split(maxsplit=2)
            document = {
                "version": "2026-10-13",
                "statements": [
                    {
                        "effect": "Allow",
                        "actions": [f"module:{USE[item.split('/')[0]]}"],
                        "resources": [f"${{scope}}:module:{item}"],
                    }
                ],
            }
            try:
                created = await self.module.engine.services.iam.create_policy(
                    f"Use {item}", document, scope=scope
                )
            except ServiceError as exc:
                return f"{self.name}: policy refused ({type(exc).__name__}: {exc})"
            return f"{self.name}: policy {created['id']} created"
        return f"{self.name} of {MODULE_ID} answers: {request}"

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
                "resources": ["abi:*:*:iam:policy/*"],
            },
            {
                "sid": "AgentsItMayPassOn",
                "effect": "Allow",
                "actions": ["module:UseAgent"],
                "resources": ["abi:*:*:module:agent/*"],
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
