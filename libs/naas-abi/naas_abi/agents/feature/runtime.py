"""Request context, access checks, and safe results for feature agent tools.

Every feature tool follows the same rules as the HTTP adapter it mirrors:
the signed-in user and Nexus workspace come from the chat boundary
(``agent_user_id`` / ``agent_workspace_id``), membership is checked with the
workspace service, and DB work runs on a fresh session (see
``nexus_admin_tools._with_db``: tools run on worker threads, so they must not
reuse the API process's asyncpg pool).

Read request ContextVars *before* ``run`` / ``run_db``: those may hop to a
fresh thread, which starts with an empty context.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from typing import Any, TypeVar
from uuid import uuid4

from naas_abi.agents.tools.nexus_admin_tools import (
    _require_user_id,
    _run_async,
    _with_db,
    _workspace_service,
)
from naas_abi_core.services.agent.context import agent_workspace_id

T = TypeVar("T")

_logger = logging.getLogger(__name__)
_NO_WORKSPACE = "No workspace on this session. Open the chat pane from a workspace."


def tool_context() -> tuple[str, str] | dict[str, str]:
    """(user_id, workspace_id) for this turn, or an error dict for the model."""
    user_id = _require_user_id()
    if isinstance(user_id, dict):
        return user_id
    workspace_id = (agent_workspace_id.get() or "").strip()
    if not workspace_id:
        return {"error": _NO_WORKSPACE}
    return user_id, workspace_id


def run(coro: Awaitable[T]) -> T:
    """Run a coroutine from a sync tool."""
    return _run_async(coro)


def run_db(fn: Callable[[Any], Awaitable[T]]) -> T:
    """Run ``fn(db)`` on a fresh Nexus DB session, committed on success."""
    return _run_async(_with_db(fn))


async def require_member(
    db: Any, user_id: str, workspace_id: str
) -> str | dict[str, str]:
    """Workspace role, or an error dict. Same check as ``require_workspace_access``."""
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
        WorkspacePermissionError,
    )

    try:
        return await _workspace_service(db).require_workspace_access(
            user_id=user_id, workspace_id=workspace_id
        )
    except WorkspacePermissionError:
        return {"error": "You do not have access to this workspace."}


def check_member(user_id: str, workspace_id: str) -> str | dict[str, str]:
    """Sync wrapper around ``require_member`` for tools with no other DB work."""

    async def _run(db: Any) -> str | dict[str, str]:
        return await require_member(db, user_id, workspace_id)

    return run_db(_run)


async def workspace_seed(db: Any, workspace_id: str) -> Any | None:
    """The config seed (``organizations[].workspaces[]``) for this workspace."""
    from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import (
        workspace_seed_for_slug,
    )

    workspace = await _workspace_service(db).get_workspace(workspace_id)
    return workspace_seed_for_slug(getattr(workspace, "slug", None))


@contextmanager
def bound_session(db: Any) -> Iterator[None]:
    """Make ``db`` the current Nexus session for registry-wired services.

    Registry services (agents, skills, workspaces) read their session from
    ``PostgresSessionRegistry``; the HTTP layer binds one per request (see
    ``get_service_registry``). Tools bind their own fresh session the same way.
    """
    from naas_abi.apps.nexus.apps.api.app.core.postgres_session_registry import (
        PostgresSessionRegistry,
    )

    registry = PostgresSessionRegistry.instance()
    session_id = f"agent-tool-{uuid4().hex}"
    registry.bind(session_id=session_id, db=db)
    token = registry.set_current_session(session_id)
    try:
        yield
    finally:
        registry.reset_current_session(token)
        registry.unbind(session_id)


def request_context(user_id: str) -> Any:
    """IAM request context for services that take one (agents, skills, secrets)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.port import (
        RequestContext,
        TokenData,
    )

    return RequestContext(
        token_data=TokenData(user_id=user_id, scopes={"*"}, is_authenticated=True)
    )


def feature_tool_error(feature: str, exc: BaseException) -> dict[str, str]:
    """Log the real exception; never hand DSNs or stack traces to the model."""
    _logger.exception("%s tool failed: %s", feature, type(exc).__name__)
    return {"error": f"{feature} operation failed. Check server logs for details."}


def guarded(feature: str, fn: Callable[[], T]) -> T | dict[str, str]:
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        return feature_tool_error(feature, exc)


def jsonable(value: Any) -> Any:
    """Dataclasses, pydantic models, and datetimes as plain JSON values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return jsonable(asdict(value))
    if hasattr(value, "model_dump"):
        return jsonable(value.model_dump())
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(v) for v in value]
    return str(value)


def clip(text: object, limit: int = 300) -> str:
    value = str(text or "")
    return value if len(value) <= limit else value[: limit - 1] + "…"


def matches(query: str, *fields: object) -> bool:
    """Case-insensitive substring match across fields. Empty query matches."""
    needle = (query or "").strip().lower()
    if not needle:
        return True
    return any(needle in str(field or "").lower() for field in fields)
