"""
Real-time WebSocket service for NEXUS.

Handles:
- User presence tracking
- Live conversation updates
- Collaborative editing signals
- Notification delivery
"""

import logging
from datetime import datetime

import socketio
from fastapi import FastAPI, HTTPException
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.auth.credentials import (
    SESSION,
    bearer_credential,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import authz

logger = logging.getLogger(__name__)

# Create Socket.IO server with proper CORS (align with API CORS settings)
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[],
    logger=True,
    engineio_logger=True,
    allow_upgrades=True,
)

# In-memory presence tracking
# workspace_id -> set of user_ids
workspace_presence: dict[str, set[str]] = {}

# user_id -> set of workspace_ids they're viewing
user_workspaces: dict[str, set[str]] = {}


def _workspace_in_session(session: dict, workspace_id: str) -> bool:
    workspaces = session.get("workspaces")
    if not isinstance(workspaces, set):
        return False
    return workspace_id in workspaces


def _may_broadcast(session: dict, workspace_id: str) -> bool:
    """Decided by IAM when the user joined the room (``Broadcast``): a viewer
    follows a workspace but sends nothing into it."""
    allowed = session.get("broadcast")
    return isinstance(allowed, set) and workspace_id in allowed


@sio.event
async def connect(sid, environ, auth):
    """Handle client connection."""
    logger.info(f"[WS] Connection attempt sid={sid}")

    # Accept Bearer token via Socket.IO auth payload or Authorization header
    token: str | None = None
    if isinstance(auth, dict):
        token = auth.get("token") or auth.get("authorization") or auth.get("Authorization")
        if token and token.lower().startswith("bearer "):
            token = token.split(" ", 1)[1].strip()

    if not token:
        header_auth = environ.get("HTTP_AUTHORIZATION")
        if header_auth and header_auth.lower().startswith("bearer "):
            token = header_auth.split(" ", 1)[1].strip()

    if not token:
        # A sign-in through an identity provider: its session cookie.
        cookie_user = await _cookie_session_user(environ)
        if cookie_user is None:
            logger.warning("[WS] Missing token; rejecting connection")
            return False
        return await _accept(sid, cookie_user)

    # The socket takes a session and nothing else: not an API key, not a coding
    # agent's key, not a link (app, preview, remote app grant), not an agent's
    # delegation. A session token that is expired, revoked, or of a suspended
    # user is no credential at all.
    credential = await bearer_credential(token)
    if credential is None:
        logger.warning("[WS] Invalid token; rejecting connection")
        return False
    if credential.kind != SESSION:
        logger.warning(f"[WS] A {credential.kind} credential is no session; rejecting connection")
        return False

    return await _accept(sid, credential.user_id)


async def _cookie_session_user(environ: dict) -> str | None:
    """The user of the handshake's session cookie, if it names a live session."""
    from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
    from naas_abi.apps.nexus.apps.api.app.services.oidc import runtime as oidc_runtime
    from starlette.datastructures import Headers

    secret = oidc_runtime.session_secret(Headers({"cookie": environ.get("HTTP_COOKIE", "")}))
    if secret is None:
        return None
    try:
        async with AsyncSessionLocal() as db:
            session = await oidc_runtime.RUNTIME.service(db).resolve(secret)
    except Exception:  # noqa: BLE001 - fail closed
        logger.exception("[WS] session lookup failed")
        return None
    return session.user_id if session is not None else None


async def _accept(sid: str, user_id: str) -> bool:
    logger.info(f"[WS] Client connected sid={sid} user={user_id}")

    # Store user_id with session
    async with sio.session(sid) as session:
        session["user_id"] = user_id
        session["workspaces"] = set()
        session["broadcast"] = set()

    return True


@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    async with sio.session(sid) as session:
        user_id = session.get("user_id")
        workspaces = session.get("workspaces", set())

    if not user_id:
        return

    # Remove from all workspaces
    for workspace_id in workspaces:
        if workspace_id in workspace_presence:
            workspace_presence[workspace_id].discard(user_id)

            # Notify others in workspace
            await sio.emit(
                "user_left",
                {"user_id": user_id, "workspace_id": workspace_id},
                room=f"workspace:{workspace_id}",
                skip_sid=sid,
            )

    # Clean up user tracking
    if user_id in user_workspaces:
        del user_workspaces[user_id]

    logger.info(f"[WS] Disconnected sid={sid} user={user_id}")


@sio.event
async def join_workspace(sid, data):
    """User joins a workspace room."""
    workspace_id = data.get("workspace_id")

    if not workspace_id:
        return {"error": "workspace_id required"}

    async with sio.session(sid) as session:
        user_id = session.get("user_id")
        if not user_id:
            return {"error": "unauthorized"}

    try:
        await authz.require("GetPresence", user=user_id, workspace=workspace_id)
    except HTTPException:
        logger.warning(
            "[WS] Workspace join denied sid=%s user=%s workspace=%s",
            sid,
            user_id,
            workspace_id,
        )
        return {"error": "workspace access denied"}

    can_broadcast = await authz.allowed("Broadcast", user=user_id, workspace=workspace_id)

    async with sio.session(sid) as session:
        workspaces = session.get("workspaces")
        if not isinstance(workspaces, set):
            workspaces = set()
            session["workspaces"] = workspaces
        workspaces.add(workspace_id)
        broadcast = session.get("broadcast")
        if not isinstance(broadcast, set):
            broadcast = set()
            session["broadcast"] = broadcast
        if can_broadcast:
            broadcast.add(workspace_id)
        else:
            broadcast.discard(workspace_id)

    # Join Socket.IO room
    sio.enter_room(sid, f"workspace:{workspace_id}")

    # Track presence
    if workspace_id not in workspace_presence:
        workspace_presence[workspace_id] = set()
    workspace_presence[workspace_id].add(user_id)

    if user_id not in user_workspaces:
        user_workspaces[user_id] = set()
    user_workspaces[user_id].add(workspace_id)

    # Notify others
    await sio.emit(
        "user_joined",
        {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "timestamp": datetime.now(UTC).isoformat(),
        },
        room=f"workspace:{workspace_id}",
        skip_sid=sid,
    )

    # Return current presence list
    return {"workspace_id": workspace_id, "users": list(workspace_presence[workspace_id])}


@sio.event
async def leave_workspace(sid, data):
    """User leaves a workspace room."""
    workspace_id = data.get("workspace_id")

    if not workspace_id:
        return {"error": "workspace_id required"}

    async with sio.session(sid) as session:
        user_id = session.get("user_id")
        session["workspaces"].discard(workspace_id)
        session.get("broadcast", set()).discard(workspace_id)

    # Leave Socket.IO room
    sio.leave_room(sid, f"workspace:{workspace_id}")

    # Remove from presence
    if workspace_id in workspace_presence:
        workspace_presence[workspace_id].discard(user_id)

    if user_id in user_workspaces:
        user_workspaces[user_id].discard(workspace_id)

    # Notify others
    await sio.emit(
        "user_left",
        {"user_id": user_id, "workspace_id": workspace_id},
        room=f"workspace:{workspace_id}",
        skip_sid=sid,
    )

    return {"status": "left", "workspace_id": workspace_id}


@sio.event
async def typing_start(sid, data):
    """User started typing in a conversation."""
    workspace_id = data.get("workspace_id")
    conversation_id = data.get("conversation_id")

    async with sio.session(sid) as session:
        user_id = session.get("user_id")
        if not _workspace_in_session(session, workspace_id):
            return {"error": "workspace not joined"}
        if not _may_broadcast(session, workspace_id):
            return {"error": "broadcast not allowed"}

    # Broadcast to workspace (excluding sender)
    await sio.emit(
        "user_typing",
        {"user_id": user_id, "conversation_id": conversation_id, "typing": True},
        room=f"workspace:{workspace_id}",
        skip_sid=sid,
    )


@sio.event
async def typing_stop(sid, data):
    """User stopped typing."""
    workspace_id = data.get("workspace_id")
    conversation_id = data.get("conversation_id")

    async with sio.session(sid) as session:
        user_id = session.get("user_id")
        if not _workspace_in_session(session, workspace_id):
            return {"error": "workspace not joined"}
        if not _may_broadcast(session, workspace_id):
            return {"error": "broadcast not allowed"}

    await sio.emit(
        "user_typing",
        {"user_id": user_id, "conversation_id": conversation_id, "typing": False},
        room=f"workspace:{workspace_id}",
        skip_sid=sid,
    )


@sio.event
async def message_created(sid, data):
    """New message created - broadcast to workspace."""
    workspace_id = data.get("workspace_id")
    conversation_id = data.get("conversation_id")
    message = data.get("message")

    async with sio.session(sid) as session:
        if not _workspace_in_session(session, workspace_id):
            return {"error": "workspace not joined"}
        if not _may_broadcast(session, workspace_id):
            return {"error": "broadcast not allowed"}

    # Broadcast to all users in workspace
    await sio.emit(
        "new_message",
        {
            "conversation_id": conversation_id,
            "message": message,
            "timestamp": datetime.now(UTC).isoformat(),
        },
        room=f"workspace:{workspace_id}",
    )


@sio.event
async def cursor_position(sid, data):
    """User cursor position in collaborative editing."""
    workspace_id = data.get("workspace_id")
    document_id = data.get("document_id")
    position = data.get("position")

    async with sio.session(sid) as session:
        user_id = session.get("user_id")
        if not _workspace_in_session(session, workspace_id):
            return {"error": "workspace not joined"}
        if not _may_broadcast(session, workspace_id):
            return {"error": "broadcast not allowed"}

    # Broadcast cursor position
    await sio.emit(
        "cursor_update",
        {"user_id": user_id, "document_id": document_id, "position": position},
        room=f"workspace:{workspace_id}",
        skip_sid=sid,
    )


@sio.event
async def join_admin_events(sid, data=None):
    """Subscribe a connected client to the platform admin event stream.

    Membership is the platform administrator's (``nexus:ManageSystem``, decided
    by IAM on every join, so a role granted or taken away after the socket
    connected counts; managed with PATCH /api/admin/users/{id}, bootstrapped from
    config ``users``); anyone else receives an error and is not added to the
    room. Once joined, the client receives every ``platform_event`` emitted by
    the EventService relay.
    """
    from naas_abi.apps.nexus.apps.api.app.services.websocket.admin_events import (
        ADMIN_EVENTS_ROOM,
    )

    async with sio.session(sid) as session:
        user_id = session.get("user_id")

    if not user_id or not await authz.allowed("ManageSystem", user=user_id):
        logger.warning("[WS] admin events join denied sid=%s user=%s", sid, user_id)
        return {"error": "superadmin required"}

    sio.enter_room(sid, ADMIN_EVENTS_ROOM)
    logger.info("[WS] admin events join sid=%s user=%s room=%s", sid, user_id, ADMIN_EVENTS_ROOM)
    return {"status": "joined", "room": ADMIN_EVENTS_ROOM}


@sio.event
async def leave_admin_events(sid, data=None):
    from naas_abi.apps.nexus.apps.api.app.services.websocket.admin_events import (
        ADMIN_EVENTS_ROOM,
    )

    sio.leave_room(sid, ADMIN_EVENTS_ROOM)
    return {"status": "left", "room": ADMIN_EVENTS_ROOM}


def get_workspace_presence(workspace_id: str) -> list[str]:
    """Get list of users currently in a workspace."""
    return list(workspace_presence.get(workspace_id, set()))


def get_user_workspaces(user_id: str) -> list[str]:
    """Get list of workspaces a user is currently viewing."""
    return list(user_workspaces.get(user_id, set()))


def init_websocket(app: FastAPI):
    """Initialize WebSocket support in FastAPI app.

    In embedded ABI mode, we must mount Socket.IO in-place on the shared app.
    In standalone mode, this also works and avoids replacing the root ASGI app.
    CORS is handled by both Socket.IO (for WS) and FastAPI middleware (for HTTP).
    """
    ws_path = getattr(settings, "websocket_path", "/ws/socket.io")
    cors_origins = list(getattr(app.state, "abi_cors_origins", [settings.frontend_url]))
    sio.eio.cors_allowed_origins = cors_origins
    logger.info("[WS] Configured origins: %s", cors_origins)
    mount_prefix = ws_path.rsplit("/", 1)[0] if "/" in ws_path.strip("/") else "/ws"
    if not mount_prefix.startswith("/"):
        mount_prefix = f"/{mount_prefix}"
    if mount_prefix == "":
        mount_prefix = "/ws"

    if not getattr(app.state, "_nexus_socketio_mounted", False):
        logger.info(
            "[WS] Mounting Socket.IO app at prefix=%s (raw_path=%s)",
            mount_prefix,
            ws_path,
        )
        socket_app = socketio.ASGIApp(
            sio,
            # Disable internal path filtering because mount path rewriting can differ
            # between HTTP and WebSocket scopes across ASGI stacks.
            socketio_path=None,
            on_startup=None,
            on_shutdown=None,
        )
        app.mount(mount_prefix, socket_app)
        app.state._nexus_socketio_mounted = True
    else:
        logger.info("[WS] Socket.IO app already mounted")

    return app
