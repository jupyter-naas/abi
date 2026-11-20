"""Nexus org/workspace admin tools for AbiAgent.

Call Nexus services in-process with a fresh DB session. Caller identity comes
from ``agent_user_id`` (set by the chat stream boundary). Mutating membership
is IAM's, as for the FastAPI adapters: each change passes the asking user (``by``),
whose rights IAM checks (an admin can never give, change or take an owner's role).
"""

from __future__ import annotations

import asyncio
import contextvars
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, TypeVar

from langchain_core.tools import BaseTool, tool
from naas_abi_core.services.agent.context import agent_user_id

from naas_abi.agents.feature.context import turn_workspace_id
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MembershipDenied

T = TypeVar("T")

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_WS_ROLES = frozenset({"admin", "member", "viewer"})
_ORG_ROLES = frozenset({"owner", "admin", "member"})


def _run_async(coro: Awaitable[T]) -> T:
    """Run an async coroutine from a sync tool call.

    Agent tool execution usually happens on a worker thread (no running loop).
    If a loop is already running, offload ``asyncio.run`` to a fresh thread so
    asyncpg sessions are not shared across loops.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: list[T] = []
    error: list[BaseException] = []

    def _target() -> None:
        try:
            result.append(asyncio.run(coro))
        except BaseException as exc:  # noqa: BLE001
            error.append(exc)

    import threading

    # The caller's identity goes with the work (a new thread starts with none).
    thread = threading.Thread(
        target=contextvars.copy_context().run, args=(_target,), daemon=True
    )
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0]


def _require_user_id() -> str | dict[str, str]:
    user_id = agent_user_id.get()
    if not user_id:
        return {
            "error": (
                "No authenticated user on this agent session. "
                "Open the right AI pane while signed in and try again."
            )
        }
    return user_id


def _tool_error(exc: BaseException) -> dict[str, str]:
    """Log the real exception; never return DSNs or secrets to the model/UI."""
    logger = __import__("logging").getLogger(__name__)
    logger.exception("nexus admin tool failed: %s", type(exc).__name__)
    return {"error": "Nexus admin operation failed. Check server logs for details."}


def _resolve_database_url() -> str:
    """Resolve the Nexus DB URL from one explicit source of truth.

    Prefer ``NEXUS_DATABASE_URL`` / ``DATABASE_URL``, then ABIModule nexus_config,
    then ``POSTGRES_*`` (URL-encoded), then Settings. Fail loudly when absent.
    """
    import os
    from urllib.parse import quote_plus

    for key in ("NEXUS_DATABASE_URL", "DATABASE_URL"):
        explicit = (os.getenv(key) or "").strip()
        if explicit:
            return explicit

    try:
        from naas_abi import ABIModule

        url = ABIModule.get_instance().configuration.nexus_config.database_url
        if isinstance(url, str) and url.strip():
            return url.strip()
    except Exception as exc:  # noqa: BLE001
        logger = __import__("logging").getLogger(__name__)
        logger.debug("ABIModule nexus database_url unavailable: %s", exc)

    pg_host = (os.getenv("POSTGRES_HOST") or "").strip()
    pg_user = (os.getenv("POSTGRES_USER") or "").strip()
    pg_password = os.getenv("POSTGRES_PASSWORD")
    pg_port = (os.getenv("POSTGRES_PORT") or "5432").strip() or "5432"
    pg_db = (os.getenv("POSTGRES_DB") or "nexus").strip() or "nexus"
    if pg_host and pg_user and pg_password is not None:
        return (
            f"postgresql+asyncpg://{quote_plus(pg_user)}:{quote_plus(pg_password)}"
            f"@{pg_host}:{pg_port}/{pg_db}"
        )

    try:
        from naas_abi.apps.nexus.apps.api.app.core import config as nexus_config

        url = str(nexus_config.settings.database_url).strip()
        if url:
            return url
    except Exception as exc:
        raise RuntimeError(
            "Nexus database URL unavailable for admin tools; "
            "set NEXUS_DATABASE_URL or POSTGRES_*"
        ) from exc

    raise RuntimeError(
        "Nexus database URL unavailable for admin tools; "
        "set NEXUS_DATABASE_URL or POSTGRES_*"
    )


async def _with_db(
    fn: Callable[[Any], Awaitable[T]],
) -> T:
    # Fresh engine per call: agent tools often run via asyncio.run() on a
    # worker thread, so they must not reuse the API process's asyncpg pool.
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    engine = create_async_engine(_resolve_database_url(), pool_pre_ping=True)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        async with session_factory() as db:
            try:
                out = await fn(db)
                await db.commit()
                return out
            except Exception:
                await db.rollback()
                raise
    finally:
        await engine.dispose()


def _workspace_service(db: Any) -> Any:
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (
        WorkspaceSecondaryAdapterPostgres,
    )
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
        WorkspaceService,
    )

    return WorkspaceService(adapter=WorkspaceSecondaryAdapterPostgres(db=db))


def _organization_service(db: Any) -> Any:
    from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
        OrganizationSecondaryAdapterPostgres,
    )
    from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
        OrganizationService,
    )

    return OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))


def _auth_service(db: Any) -> Any:
    from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.secondary.postgres import (
        AuthSecondaryAdapterPostgres,
    )
    from naas_abi.apps.nexus.apps.api.app.services.auth.service import AuthService

    return AuthService(adapter=AuthSecondaryAdapterPostgres(db=db))


def _people_service(db: Any) -> Any:
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.people_port import (
        build_people_service,
    )

    return build_people_service(db)


async def _caller(db: Any, user_id: str) -> Any:
    """The asking user, as the people service names who invites (``by``)."""
    from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import User

    record = await _auth_service(db).get_user(user_id)
    return User.model_construct(
        id=user_id,
        email=getattr(record, "email", None),
        name=getattr(record, "name", None),
    )


async def _invite_limits(
    user_id: str,
    email: str,
    *,
    endpoint: str,
    organization_id: str | None,
    workspace_id: str | None,
) -> dict[str, Any] | None:
    """The invite routes' limits, for the agent's invitations too: the asking
    user's and the address's, and the organization's day of invitation mail. An
    error to report when one is reached, else None."""
    from fastapi import HTTPException

    from naas_abi.apps.nexus.apps.api.app.services.rate_limit import (
        check_invitation_mail_quota,
        check_rate_limit,
    )

    try:
        await check_rate_limit(f"user:{user_id}", endpoint)
        await check_rate_limit(f"email:{email}", endpoint)
        await check_invitation_mail_quota(organization_id, workspace_id)
    except HTTPException as exc:
        return {"error": str(exc.detail), "email": email}
    return None


async def _create_or_link(
    db: Any,
    user_id: str,
    *,
    limits_endpoint: str,
    workspace_id: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """``PeopleService.create_or_link`` for the asking user: the person's account
    made or linked, given ``grants`` on the asker's behalf (IAM decides), and
    mailed. The answer never tells whether the account was made or linked. The
    invite routes' limits apply (``limits_endpoint``: whose counters)."""
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.people_port import (
        people_http_error,
        people_status,
        provider_view,
    )

    limited = await _invite_limits(
        user_id,
        kwargs["email"],
        endpoint=limits_endpoint,
        organization_id=kwargs.get("organization_id"),
        workspace_id=workspace_id,
    )
    if limited is not None:
        return limited
    try:
        result = await _people_service(db).create_or_link(
            by=await _caller(db, user_id), **kwargs
        )
    except MembershipDenied:
        raise
    except Exception as exc:
        answer = people_http_error(exc)
        if answer is None:
            raise
        return {"error": str(answer.detail), "email": kwargs.get("email")}
    user = result.user
    return {
        "status": "added",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "status": people_status(user.status),
        },
        "provider": provider_view(result.provider),
        "sign_in_email_sent": result.sign_in_email_sent,
        "warning": result.warning,
    }


def _record_to_dict(record: Any) -> dict[str, Any]:
    if record is None:
        return {}
    if hasattr(record, "__dataclass_fields__"):
        out: dict[str, Any] = {}
        for key in record.__dataclass_fields__:
            value = getattr(record, key)
            if isinstance(value, datetime):
                out[key] = value.isoformat()
            else:
                out[key] = value
        return out
    if isinstance(record, dict):
        return record
    return {"value": str(record)}


def nexus_admin_tools() -> list[BaseTool]:
    @tool
    def list_organizations() -> Any:
        """List organizations the signed-in user belongs to (id, name, slug)."""
        user_id = _require_user_id()
        if isinstance(user_id, dict):
            return user_id

        async def _run(db: Any) -> Any:
            rows = await _organization_service(db).list_organizations(user_id=user_id)
            return [_record_to_dict(row) for row in rows]

        try:
            return _run_async(_with_db(_run))
        except MembershipDenied as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def list_workspaces(organization_id: str = "") -> Any:
        """List workspaces visible to the signed-in user.

        Pass organization_id to list workspaces under that org (must be a member).
        Leave organization_id empty to list all workspaces the user belongs to.
        """
        user_id = _require_user_id()
        if isinstance(user_id, dict):
            return user_id
        org_id = (organization_id or "").strip()

        async def _run(db: Any) -> Any:
            if org_id:
                org = _organization_service(db)
                role = await org.get_organization_role(user_id=user_id, org_id=org_id)
                if role is None:
                    return {"error": "Not a member of this organization", "organization_id": org_id}
                rows = await org.list_workspaces(org_id=org_id, user_id=user_id)
                return [_record_to_dict(row) for row in rows]
            rows = await _workspace_service(db).list_workspaces(user_id=user_id)
            return [_record_to_dict(row) for row in rows]

        try:
            return _run_async(_with_db(_run))
        except MembershipDenied as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def create_workspace(name: str, slug: str, organization_id: str) -> Any:
        """Create a workspace under an organization. Caller becomes owner.

        Requires org owner or admin. slug must be lowercase letters, digits, hyphens.
        """
        user_id = _require_user_id()
        if isinstance(user_id, dict):
            return user_id
        name = (name or "").strip()
        slug = (slug or "").strip().lower()
        organization_id = (organization_id or "").strip()
        if not name or not slug or not organization_id:
            return {"error": "name, slug, and organization_id are required"}
        if not _SLUG_RE.match(slug):
            return {
                "error": "slug must be lowercase letters, digits, and hyphens only",
                "slug": slug,
            }

        async def _run(db: Any) -> Any:
            from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import (
                WorkspaceCreateInput,
            )
            from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
                WorkspaceSlugAlreadyExistsError,
            )

            org = _organization_service(db)
            role = await org.get_organization_role(user_id=user_id, org_id=organization_id)
            if role not in ("owner", "admin"):
                return {
                    "error": "Only organization owners/admins can create workspaces",
                    "organization_id": organization_id,
                    "role": role,
                }
            try:
                record = await _workspace_service(db).create_workspace(
                    WorkspaceCreateInput(
                        name=name,
                        slug=slug,
                        owner_id=user_id,
                        organization_id=organization_id,
                    )
                )
            except WorkspaceSlugAlreadyExistsError:
                return {"error": "Slug already exists", "slug": slug}
            return {"status": "created", "workspace": _record_to_dict(record)}

        try:
            return _run_async(_with_db(_run))
        except MembershipDenied as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def list_workspace_members(workspace_id: str = "") -> Any:
        """List members of a workspace (email, name, role, user_id, is_you).

        Defaults to the current chat workspace when workspace_id is omitted.
        is_you marks the signed-in user asking, so "what is my role?" is
        answered from the row, not guessed.
        """
        user_id = _require_user_id()
        if isinstance(user_id, dict):
            return user_id
        workspace_id = (workspace_id or "").strip() or turn_workspace_id()
        if not workspace_id:
            return {"error": "workspace_id is required"}

        async def _run(db: Any) -> Any:
            from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
                WorkspacePermissionError,
            )

            ws = _workspace_service(db)
            try:
                await ws.require_workspace_access(user_id=user_id, workspace_id=workspace_id)
            except WorkspacePermissionError:
                return {"error": "No access to this workspace", "workspace_id": workspace_id}
            rows = await ws.list_workspace_members(workspace_id=workspace_id)
            return [
                {**_record_to_dict(row), "is_you": row.user_id == user_id}
                for row in rows
            ]

        try:
            return _run_async(_with_db(_run))
        except MembershipDenied as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def invite_workspace_member(
        email: str,
        workspace_id: str = "",
        role: str = "member",
        name: str = "",
    ) -> Any:
        """Add a person by email to a workspace: their platform account is made,
        or the one their email already has is linked.

        Requires workspace owner/admin. role: admin, member, or viewer. Grants the
        workspace role only (no organization role). The person is mailed: a
        sign-in link when new, a notice when they already had an account.
        Defaults to the current chat workspace when workspace_id is omitted.
        """
        user_id = _require_user_id()
        if isinstance(user_id, dict):
            return user_id
        email = (email or "").strip().lower()
        workspace_id = (workspace_id or "").strip() or turn_workspace_id()
        role = (role or "member").strip().lower()
        display_name = (name or "").strip() or None
        if not email or not workspace_id:
            return {"error": "email and workspace_id are required"}
        if role not in _WS_ROLES:
            return {"error": f"role must be one of {sorted(_WS_ROLES)}", "role": role}

        async def _run(db: Any) -> Any:
            from naas_abi.apps.nexus.apps.api.app.services.workspaces.people_port import (
                Grant,
            )

            ws = _workspace_service(db)
            caller_role = await ws.get_workspace_role(user_id=user_id, workspace_id=workspace_id)
            if caller_role not in ("owner", "admin"):
                return {
                    "error": "Only workspace owners/admins can invite members",
                    "workspace_id": workspace_id,
                    "role": caller_role,
                }
            workspace = await ws.get_workspace(workspace_id)
            if workspace is None:
                return {"error": "Workspace not found", "workspace_id": workspace_id}
            # The workspace role only: a workspace admin never grants an org role.
            return await _create_or_link(
                db,
                user_id,
                limits_endpoint="/api/workspaces/members/invite",
                workspace_id=workspace_id,
                email=email,
                name=display_name,
                provider=None,
                grants=[Grant("workspace", workspace_id, role)],  # type: ignore[arg-type]
                may_grant_owner=False,
                organization_id=workspace.organization_id,
            )

        try:
            return _run_async(_with_db(_run))
        except MembershipDenied as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def remove_workspace_member(user_id_to_remove: str, workspace_id: str = "") -> Any:
        """Remove a member from a workspace. Requires workspace owner/admin.

        Defaults to the current chat workspace when workspace_id is omitted.
        """
        user_id = _require_user_id()
        if isinstance(user_id, dict):
            return user_id
        target = (user_id_to_remove or "").strip()
        workspace_id = (workspace_id or "").strip() or turn_workspace_id()
        if not target or not workspace_id:
            return {"error": "user_id_to_remove and workspace_id are required"}
        if target == user_id:
            return {"error": "Cannot remove yourself from the workspace"}

        async def _run(db: Any) -> Any:
            ws = _workspace_service(db)
            caller_role = await ws.get_workspace_role(user_id=user_id, workspace_id=workspace_id)
            if caller_role not in ("owner", "admin"):
                return {
                    "error": "Only workspace owners/admins can remove members",
                    "workspace_id": workspace_id,
                    "role": caller_role,
                }
            removed = await ws.remove_workspace_member(
                workspace_id=workspace_id, user_id=target, by=user_id
            )
            if not removed:
                return {"error": "Member not found", "user_id": target}
            return {"status": "removed", "user_id": target, "workspace_id": workspace_id}

        try:
            return _run_async(_with_db(_run))
        except MembershipDenied as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def update_workspace_member_role(
        user_id_to_update: str,
        role: str,
        workspace_id: str = "",
    ) -> Any:
        """Update a workspace member's role (admin/member/viewer).

        Requires workspace owner/admin. Defaults to the current chat workspace
        when workspace_id is omitted.
        """
        user_id = _require_user_id()
        if isinstance(user_id, dict):
            return user_id
        target = (user_id_to_update or "").strip()
        workspace_id = (workspace_id or "").strip() or turn_workspace_id()
        role = (role or "").strip().lower()
        if not target or not workspace_id or not role:
            return {"error": "user_id_to_update, role, and workspace_id are required"}
        if role not in _WS_ROLES:
            return {"error": f"role must be one of {sorted(_WS_ROLES)}", "role": role}

        async def _run(db: Any) -> Any:
            ws = _workspace_service(db)
            caller_role = await ws.get_workspace_role(user_id=user_id, workspace_id=workspace_id)
            if caller_role not in ("owner", "admin"):
                return {
                    "error": "Only workspace owners/admins can update members",
                    "workspace_id": workspace_id,
                    "role": caller_role,
                }
            changed = await ws.update_workspace_member(
                workspace_id=workspace_id,
                user_id=target,
                updates={"role": role},
                by=user_id,
            )
            if not changed:
                return {"error": "Member not found", "user_id": target}
            return {
                "status": "updated",
                "user_id": target,
                "workspace_id": workspace_id,
                "role": role,
            }

        try:
            return _run_async(_with_db(_run))
        except MembershipDenied as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def list_organization_members(organization_id: str) -> Any:
        """List members of an organization (email, name, role, user_id).

        Caller must be an organization member.
        """
        user_id = _require_user_id()
        if isinstance(user_id, dict):
            return user_id
        organization_id = (organization_id or "").strip()
        if not organization_id:
            return {"error": "organization_id is required"}

        async def _run(db: Any) -> Any:
            org = _organization_service(db)
            role = await org.get_organization_role(user_id=user_id, org_id=organization_id)
            if role is None:
                return {"error": "Not a member of this organization", "organization_id": organization_id}
            rows = await org.list_members(org_id=organization_id)
            return [_record_to_dict(row) for row in rows]

        try:
            return _run_async(_with_db(_run))
        except MembershipDenied as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def invite_organization_member(
        organization_id: str,
        email: str,
        role: str = "member",
        name: str = "",
        workspace_id: str = "",
        workspace_role: str = "member",
    ) -> Any:
        """Add a person by email to an organization: their platform account is
        made, or the one their email already has is linked.

        Requires org owner/admin. role: owner (owners only), admin, or member.
        Optionally also give them a role in one of its workspaces (workspace_id).
        The person is mailed: a sign-in link when new, a notice otherwise.
        """
        user_id = _require_user_id()
        if isinstance(user_id, dict):
            return user_id
        organization_id = (organization_id or "").strip()
        email = (email or "").strip().lower()
        role = (role or "member").strip().lower()
        display_name = (name or "").strip() or None
        workspace_id = (workspace_id or "").strip()
        workspace_role = (workspace_role or "member").strip().lower()
        if not organization_id or not email:
            return {"error": "organization_id and email are required"}
        if role not in _ORG_ROLES:
            return {"error": f"role must be one of {sorted(_ORG_ROLES)}", "role": role}
        if workspace_id and workspace_role not in _WS_ROLES:
            return {
                "error": f"workspace_role must be one of {sorted(_WS_ROLES)}",
                "workspace_role": workspace_role,
            }

        async def _run(db: Any) -> Any:
            from naas_abi.apps.nexus.apps.api.app.services.workspaces.people_port import (
                Grant,
            )

            org = _organization_service(db)
            caller_role = await org.get_organization_role(
                user_id=user_id, org_id=organization_id
            )
            if caller_role not in ("owner", "admin"):
                return {
                    "error": "Only organization owners/admins can invite members",
                    "organization_id": organization_id,
                    "role": caller_role,
                }
            grants = [Grant("organization", organization_id, role)]  # type: ignore[arg-type]
            if workspace_id:
                org_workspaces = await org.list_all_workspaces(org_id=organization_id)
                if workspace_id not in {ws.id for ws in org_workspaces}:
                    return {
                        "error": "workspace_id must belong to this organization",
                        "organization_id": organization_id,
                        "workspace_id": workspace_id,
                    }
                grants.append(Grant("workspace", workspace_id, workspace_role))  # type: ignore[arg-type]
            out = await _create_or_link(
                db,
                user_id,
                limits_endpoint="/api/organizations/members/invite",
                workspace_id=workspace_id or None,
                email=email,
                name=display_name,
                provider=None,
                grants=grants,
                may_grant_owner=caller_role == "owner",
                organization_id=organization_id,
            )
            if "error" not in out:
                member = await org.get_organization_member(
                    org_id=organization_id, user_id=out["user"]["id"]
                )
                out["member"] = _record_to_dict(member) if member else None
            return out

        try:
            return _run_async(_with_db(_run))
        except MembershipDenied as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def remove_organization_member(organization_id: str, user_id_to_remove: str) -> Any:
        """Remove a member from an organization. Requires org owner/admin."""
        user_id = _require_user_id()
        if isinstance(user_id, dict):
            return user_id
        organization_id = (organization_id or "").strip()
        target = (user_id_to_remove or "").strip()
        if not organization_id or not target:
            return {"error": "organization_id and user_id_to_remove are required"}
        if target == user_id:
            return {"error": "Cannot remove yourself from the organization"}

        async def _run(db: Any) -> Any:
            org = _organization_service(db)
            caller_role = await org.get_organization_role(
                user_id=user_id, org_id=organization_id
            )
            if caller_role not in ("owner", "admin"):
                return {
                    "error": "Only organization owners/admins can remove members",
                    "organization_id": organization_id,
                    "role": caller_role,
                }
            removed = await org.remove_member(
                org_id=organization_id, user_id=target, by=user_id
            )
            if not removed:
                return {
                    "error": "Member not found or is the organization owner",
                    "user_id": target,
                }
            return {
                "status": "removed",
                "user_id": target,
                "organization_id": organization_id,
            }

        try:
            return _run_async(_with_db(_run))
        except MembershipDenied as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def update_organization_member_role(
        organization_id: str,
        user_id_to_update: str,
        role: str,
    ) -> Any:
        """Update an organization member's role (owner/admin/member).

        Requires org owner/admin. Cannot change your own role.
        """
        user_id = _require_user_id()
        if isinstance(user_id, dict):
            return user_id
        organization_id = (organization_id or "").strip()
        target = (user_id_to_update or "").strip()
        role = (role or "").strip().lower()
        if not organization_id or not target or not role:
            return {
                "error": "organization_id, user_id_to_update, and role are required"
            }
        if role not in _ORG_ROLES:
            return {"error": f"role must be one of {sorted(_ORG_ROLES)}", "role": role}
        if target == user_id:
            return {"error": "Cannot change your own organization role"}

        async def _run(db: Any) -> Any:
            org = _organization_service(db)
            caller_role = await org.get_organization_role(
                user_id=user_id, org_id=organization_id
            )
            if caller_role not in ("owner", "admin"):
                return {
                    "error": "Only organization owners/admins can update member roles",
                    "organization_id": organization_id,
                    "role": caller_role,
                }
            member = await org.update_member_role(
                org_id=organization_id, user_id=target, role=role, by=user_id
            )
            if member is None:
                return {"error": "Member not found", "user_id": target}
            return {"status": "updated", "member": _record_to_dict(member)}

        try:
            return _run_async(_with_db(_run))
        except MembershipDenied as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def update_my_profile(
        name: str = "",
        organization: str = "",
        job_title: str = "",
        bio: str = "",
    ) -> Any:
        """Update the signed-in user's own profile fields.

        Only provided (non-empty) fields are changed: name, organization, job_title, bio.
        Email changes stay in the authenticated settings UI (re-auth / confirm).
        """
        user_id = _require_user_id()
        if isinstance(user_id, dict):
            return user_id

        payload = {
            "name": name.strip() or None,
            "organization": organization.strip() or None,
            "job_title": job_title.strip() or None,
            "bio": bio.strip() or None,
        }
        if not any(payload.values()):
            return {"error": "Provide at least one of: name, organization, job_title, bio"}

        async def _run(db: Any) -> Any:
            from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
                UserNotFoundError,
            )

            try:
                user = await _auth_service(db).update_profile(
                    user_id=user_id,
                    name=payload["name"],
                    organization=payload["organization"],
                    job_title=payload["job_title"],
                    bio=payload["bio"],
                )
            except UserNotFoundError:
                return {"error": "User not found"}
            return {
                "status": "updated",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "organization": user.organization,
                    "job_title": user.job_title,
                    "bio": getattr(user, "bio", None),
                },
            }

        try:
            return _run_async(_with_db(_run))
        except MembershipDenied as exc:
            return {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    return [
        list_organizations,
        list_workspaces,
        create_workspace,
        list_workspace_members,
        invite_workspace_member,
        remove_workspace_member,
        update_workspace_member_role,
        list_organization_members,
        invite_organization_member,
        remove_organization_member,
        update_organization_member_role,
        update_my_profile,
    ]
