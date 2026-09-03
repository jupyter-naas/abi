"""Abi tools for Nexus Code sandboxes (Slides-parity).

When a repo is open and a local sandbox sidecar is bound, tools read/write the
live checkout. Otherwise they return a clear unavailable message.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi_core.services.agent.context import (
    coder_workspace_base,
    coding_active_branch,
    coding_active_repo,
)
from naas_abi_core.services.agent.tools.workspace_tools import _call as _sidecar_call

_NO_SANDBOX = (
    "No coding sandbox is connected to this session. Open a repository in Code "
    "and wait for the sandbox runtime to become ready."
)


def _coding_context() -> dict[str, str | None]:
    return {
        "repo_id": coding_active_repo.get(),
        "branch": coding_active_branch.get(),
        "sidecar_bound": bool(coder_workspace_base.get()),
    }


def coding_tools() -> list[BaseTool]:
    @tool(return_direct=False)
    def read_coding_file(path: str) -> dict[str, Any]:
        """Read a UTF-8 text file from the open coding sandbox checkout."""
        result = _sidecar_call("read_file", {"path": path})
        result["coding_context"] = _coding_context()
        return result

    @tool(return_direct=False)
    def write_coding_file(path: str, content: str) -> dict[str, Any]:
        """Create or overwrite a file in the open coding sandbox checkout."""
        result = _sidecar_call("write_file", {"path": path, "content": content})
        result["coding_context"] = _coding_context()
        return result

    @tool(return_direct=False)
    def list_coding_dir(path: str = ".") -> dict[str, Any]:
        """List files and directories under ``path`` in the coding sandbox."""
        result = _sidecar_call("list_dir", {"path": path})
        result["coding_context"] = _coding_context()
        return result

    @tool(return_direct=False)
    def run_in_coding_sandbox(command: str, cwd: str = ".") -> dict[str, Any]:
        """Run a shell command in the coding sandbox checkout."""
        result = _sidecar_call(
            "run_terminal", {"command": command, "cwd": cwd, "timeout_s": 120}
        )
        result["coding_context"] = _coding_context()
        return result

    return [read_coding_file, write_coding_file, list_coding_dir, run_in_coding_sandbox]
