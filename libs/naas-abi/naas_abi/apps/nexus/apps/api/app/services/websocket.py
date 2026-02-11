"""
Real-time WebSocket service for NEXUS.

Handles:
- User presence tracking
- Live conversation updates
- Collaborative editing signals
- Notification delivery
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Set
import socketio
from fastapi import FastAPI
import logging

from app.core.config import settings
from app.api.endpoints.auth import decode_token
from app.services.refresh_token import is_access_token_revoked

logger = logging.getLogger(__name__)

# Create Socket.IO server with proper CORS (align with API CORS settings)
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=settings.cors_origins_list,
    logger=True,
    engineio_logger=True,
    allow_upgrades=True,
)

# In-memory presence tracking
# workspace_id -> set of user_ids
workspace_presence: Dict[str, Set[str]] = {}

# user_id -> set of workspace_ids they're viewing
user_workspaces: Dict[str, Set[str]] = {}


@sio.event
async def connect(sid, environ, auth):
    """Handle client connection."""
    logger.info(f"[WS] Connection attempt sid={sid}")

    # Accept Bearer token via Socket.IO auth payload or Authorization header
    token: str | None = None
    if isinstance(auth, dict):
        token = auth.get('token') or auth.get('authorization') or auth.get('Authorization')
        if token and token.lower().startswith('bearer '):
            token = token.split(' ', 1)[1].strip()

    if not token:
        header_auth = environ.get('HTTP_AUTHORIZATION')
        if header_auth and header_auth.lower().startswith('bearer '):
            token = header_auth.split(' ', 1)[1].strip()

    if not token:
        logger.warning("[WS] Missing token; rejecting connection")
        return False

    payload = decode_token(token)
    if not payload:
        logger.warning("[WS] Invalid token; rejecting connection")
        return False

    user_id = payload.get('sub')
    jti = payload.get('jti')
    if not user_id:
        logger.warning("[WS] Token missing subject; rejecting connection")
        return False

    if jti and await is_access_token_revoked(jti):
        logger.warning("[WS] Token revoked; rejecting connection")
        return False

    logger.info(f"[WS] Client connected sid={sid} user={user_id}")
    
    # Store user_id with session
    async with sio.session(sid) as session:
        session['user_id'] = user_id
        session['workspaces'] = set()
    
    return True


@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    async with sio.session(sid) as session:
        user_id = session.get('user_id')
        workspaces = session.get('workspaces', set())
    
    if not user_id:
        return
    
    # Remove from all workspaces
    for workspace_id in workspaces:
        if workspace_id in workspace_presence:
            workspace_presence[workspace_id].discard(user_id)
            
            # Notify others in workspace
            await sio.emit(
                'user_left',
                {'user_id': user_id, 'workspace_id': workspace_id},
                room=f'workspace:{workspace_id}',
                skip_sid=sid
            )
    
    # Clean up user tracking
    if user_id in user_workspaces:
        del user_workspaces[user_id]
    
    logger.info(f"[WS] Disconnected sid={sid} user={user_id}")


@sio.event
async def join_workspace(sid, data):
    """User joins a workspace room."""
    workspace_id = data.get('workspace_id')
    
    if not workspace_id:
        return {'error': 'workspace_id required'}
    
    async with sio.session(sid) as session:
        user_id = session.get('user_id')
        session['workspaces'].add(workspace_id)
    
    # Join Socket.IO room
    sio.enter_room(sid, f'workspace:{workspace_id}')
    
    # Track presence
    if workspace_id not in workspace_presence:
        workspace_presence[workspace_id] = set()
    workspace_presence[workspace_id].add(user_id)
    
    if user_id not in user_workspaces:
        user_workspaces[user_id] = set()
    user_workspaces[user_id].add(workspace_id)
    
    # Notify others
    await sio.emit(
        'user_joined',
        {
            'user_id': user_id,
            'workspace_id': workspace_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        },
        room=f'workspace:{workspace_id}',
        skip_sid=sid
    )
    
    # Return current presence list
    return {
        'workspace_id': workspace_id,
        'users': list(workspace_presence[workspace_id])
    }


@sio.event
async def leave_workspace(sid, data):
    """User leaves a workspace room."""
    workspace_id = data.get('workspace_id')
    
    if not workspace_id:
        return {'error': 'workspace_id required'}
    
    async with sio.session(sid) as session:
        user_id = session.get('user_id')
        session['workspaces'].discard(workspace_id)
    
    # Leave Socket.IO room
    sio.leave_room(sid, f'workspace:{workspace_id}')
    
    # Remove from presence
    if workspace_id in workspace_presence:
        workspace_presence[workspace_id].discard(user_id)
    
    if user_id in user_workspaces:
        user_workspaces[user_id].discard(workspace_id)
    
    # Notify others
    await sio.emit(
        'user_left',
        {'user_id': user_id, 'workspace_id': workspace_id},
        room=f'workspace:{workspace_id}',
        skip_sid=sid
    )
    
    return {'status': 'left', 'workspace_id': workspace_id}


@sio.event
async def typing_start(sid, data):
    """User started typing in a conversation."""
    workspace_id = data.get('workspace_id')
    conversation_id = data.get('conversation_id')
    
    async with sio.session(sid) as session:
        user_id = session.get('user_id')
    
    # Broadcast to workspace (excluding sender)
    await sio.emit(
        'user_typing',
        {
            'user_id': user_id,
            'conversation_id': conversation_id,
            'typing': True
        },
        room=f'workspace:{workspace_id}',
        skip_sid=sid
    )


@sio.event
async def typing_stop(sid, data):
    """User stopped typing."""
    workspace_id = data.get('workspace_id')
    conversation_id = data.get('conversation_id')
    
    async with sio.session(sid) as session:
        user_id = session.get('user_id')
    
    await sio.emit(
        'user_typing',
        {
            'user_id': user_id,
            'conversation_id': conversation_id,
            'typing': False
        },
        room=f'workspace:{workspace_id}',
        skip_sid=sid
    )


@sio.event
async def message_created(sid, data):
    """New message created - broadcast to workspace."""
    workspace_id = data.get('workspace_id')
    conversation_id = data.get('conversation_id')
    message = data.get('message')
    
    # Broadcast to all users in workspace
    await sio.emit(
        'new_message',
        {
            'conversation_id': conversation_id,
            'message': message,
            'timestamp': datetime.now(timezone.utc).isoformat()
        },
        room=f'workspace:{workspace_id}'
    )


@sio.event
async def cursor_position(sid, data):
    """User cursor position in collaborative editing."""
    workspace_id = data.get('workspace_id')
    document_id = data.get('document_id')
    position = data.get('position')
    
    async with sio.session(sid) as session:
        user_id = session.get('user_id')
    
    # Broadcast cursor position
    await sio.emit(
        'cursor_update',
        {
            'user_id': user_id,
            'document_id': document_id,
            'position': position
        },
        room=f'workspace:{workspace_id}',
        skip_sid=sid
    )


def get_workspace_presence(workspace_id: str) -> list[str]:
    """Get list of users currently in a workspace."""
    return list(workspace_presence.get(workspace_id, set()))


def get_user_workspaces(user_id: str) -> list[str]:
    """Get list of workspaces a user is currently viewing."""
    return list(user_workspaces.get(user_id, set()))


def init_websocket(app: FastAPI):
    """Initialize WebSocket support in FastAPI app.
    
    Socket.IO wraps the FastAPI app but delegates non-WebSocket requests.
    CORS is handled by both Socket.IO (for WS) and FastAPI middleware (for HTTP).
    """
    # Wrap with Socket.IO ASGI app
    socket_app = socketio.ASGIApp(
        sio,
        other_asgi_app=app,
        socketio_path='/ws/socket.io',  # Match the frontend path
        # Pass through FastAPI app for non-Socket.IO requests
        on_startup=None,
        on_shutdown=None
    )
    return socket_app
