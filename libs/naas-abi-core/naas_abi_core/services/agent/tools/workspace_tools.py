"""Generic coding-workspace tools available to every agent.

These let any agent read/write files inside the caller's Coder coding workspace
(~/project) by calling a small exec sidecar running in that workspace, reached
over the docker network. The target sidecar (base URL + bearer secret) is
resolved per-request from the ``coder_workspace_*`` ContextVars, set at the
request boundary (the OpenAI shim) from the caller's per-workspace token — so an
agent always acts on the authenticated user's own workspace.

When no workspace is bound to the request (the common non-coding case), every
tool returns a clear, harmless message instead of acting.

Uses stdlib ``urllib`` (not httpx) to avoid adding a dependency to the core.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from langchain_core.tools import BaseTool, Tool, tool
from naas_abi_core.services.agent.context import (
    coder_workspace_base,
    coder_workspace_secret,
)

_TIMEOUT = 30
_NO_WORKSPACE = (
    "No coding workspace is connected to this session, so filesystem tools are "
    "unavailable. They only work from inside a coding workspace (the IDE)."
)

# Tool metadata flag: the Agent only binds tools carrying this to the model when
# a coding workspace is bound to the current request.
REQUIRES_WORKSPACE_KEY = "requires_coder_workspace"


def _call(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    base = coder_workspace_base.get()
    if not base:
        return {"error": _NO_WORKSPACE}
    # Only ever talk to the internal http(s) sidecar — reject any other scheme
    # (defends against file:/custom-scheme open; the base is server-minted).
    if not base.startswith(("http://", "https://")):
        return {"error": f"invalid workspace base url: {base}"}
    secret = coder_workspace_secret.get() or ""
    req = urllib.request.Request(
        f"{base.rstrip('/')}/tools/{tool_name}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {secret}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310  # nosec B310
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode("utf-8"))
        except Exception:
            return {"error": f"workspace tool '{tool_name}' failed: HTTP {exc.code}"}
    except Exception as exc:  # noqa: BLE001 - report failure back to the agent
        return {"error": f"workspace tool '{tool_name}' failed: {exc}"}


def workspace_tools() -> list[Tool | BaseTool]:
    @tool(return_direct=False)
    def write_file(path: str, content: str) -> dict:
        """Create or overwrite a file in the user's coding workspace at ~/project.

        Use this to actually write code or files into the workspace (not just
        show them). ``path`` is relative to the project root (e.g. 'src/main.py').
        ``content`` is the full file content.
        """
        return _call("write_file", {"path": path, "content": content})

    @tool(return_direct=False)
    def read_file(path: str) -> dict:
        """Read a file from the user's coding workspace at ~/project.

        ``path`` is relative to the project root.
        """
        return _call("read_file", {"path": path})

    @tool(return_direct=False)
    def list_dir(path: str = ".") -> dict:
        """List the contents of a directory in the user's coding workspace at ~/project.

        ``path`` is relative to the project root (defaults to the root).
        """
        return _call("list_dir", {"path": path})

    tools = [write_file, read_file, list_dir]
    # Mark these so the Agent only exposes them to the model when a coding
    # workspace is actually bound to the request (see Agent._requires_workspace).
    for t in tools:
        t.metadata = {**(t.metadata or {}), REQUIRES_WORKSPACE_KEY: True}
    return tools
