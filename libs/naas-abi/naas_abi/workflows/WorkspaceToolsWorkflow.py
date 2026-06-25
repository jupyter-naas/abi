"""Workspace filesystem tools for server-side abi agents (Option B).

These LangChain tools let an in-process abi agent read and write files **inside
the user's Coder coding workspace** (~/project), not on the abi server. They do
this by calling a small exec sidecar running in that workspace over the shared
docker network. The target sidecar (base URL + bearer secret) is resolved
per-request and carried in ContextVars set by the OpenAI shim from the caller's
per-workspace token — so an agent always acts on the authenticated user's own
workspace and never one supplied by the client.
"""

from __future__ import annotations

from typing import Any

import httpx
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.services.agent.context import (
    coder_workspace_base,
    coder_workspace_secret,
)
from pydantic import BaseModel, Field

_TIMEOUT = 30.0
_NO_WORKSPACE = (
    "No coding workspace is connected to this session, so filesystem tools are "
    "unavailable. These tools only work from inside a coding workspace (the IDE)."
)


class WriteFileParams(BaseModel):
    path: str = Field(
        ...,
        description="File path relative to the project root (~/project), e.g. 'src/main.py'.",
    )
    content: str = Field(..., description="The full content to write to the file.")


class ReadFileParams(BaseModel):
    path: str = Field(..., description="File path relative to the project root (~/project).")


class ListDirParams(BaseModel):
    path: str = Field(
        default=".",
        description="Directory path relative to the project root (~/project). Defaults to the root.",
    )


class WorkspaceToolsWorkflow:
    """Exposes workspace filesystem operations as agent tools backed by the
    in-workspace exec sidecar."""

    def _call(self, tool: str, payload: dict[str, Any]) -> dict[str, Any]:
        base = coder_workspace_base.get()
        if not base:
            return {"error": _NO_WORKSPACE}
        secret = coder_workspace_secret.get() or ""
        try:
            resp = httpx.post(
                f"{base.rstrip('/')}/tools/{tool}",
                json=payload,
                headers={"Authorization": f"Bearer {secret}"},
                timeout=_TIMEOUT,
            )
            return resp.json()
        except Exception as exc:  # noqa: BLE001 - report failure back to the agent
            return {"error": f"workspace tool '{tool}' failed: {exc}"}

    def write_file(self, params: WriteFileParams) -> dict[str, Any]:
        return self._call("write_file", {"path": params.path, "content": params.content})

    def read_file(self, params: ReadFileParams) -> dict[str, Any]:
        return self._call("read_file", {"path": params.path})

    def list_dir(self, params: ListDirParams) -> dict[str, Any]:
        return self._call("list_dir", {"path": params.path})

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="write_file",
                description=(
                    "Create or overwrite a file in the user's coding workspace at ~/project. "
                    "Use this to actually write code/files to the workspace (not just show them)."
                ),
                func=lambda **kwargs: self.write_file(WriteFileParams(**kwargs)),
                args_schema=WriteFileParams,
            ),
            StructuredTool(
                name="read_file",
                description="Read a file from the user's coding workspace at ~/project.",
                func=lambda **kwargs: self.read_file(ReadFileParams(**kwargs)),
                args_schema=ReadFileParams,
            ),
            StructuredTool(
                name="list_dir",
                description="List the contents of a directory in the user's coding workspace at ~/project.",
                func=lambda **kwargs: self.list_dir(ListDirParams(**kwargs)),
                args_schema=ListDirParams,
            ),
        ]
