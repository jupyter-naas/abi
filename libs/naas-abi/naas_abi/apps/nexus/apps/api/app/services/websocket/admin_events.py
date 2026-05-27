"""Relay platform LogProcess events to the Socket.IO ``admin_events`` room.

We install a tap on ``EventService.publish`` so every event the engine
publishes — regardless of whether its subclass had been imported at
startup time — is serialized through ``EventCodec`` and broadcast as a
``platform_event`` Socket.IO message.

We tap ``publish`` rather than calling ``subscribe`` per subclass because
``BusService.subscribe`` requires the subclass to exist at registration
time, which silently drops event types loaded later in the process.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

ADMIN_EVENTS_ROOM = "admin_events"
PLATFORM_EVENT = "platform_event"

_relay_installed: bool = False


def _emit_event_threadsafe(loop: asyncio.AbstractEventLoop, payload: dict[str, Any]) -> None:
    """Schedule a Socket.IO emit from a non-async bus subscriber thread."""
    from naas_abi.apps.nexus.apps.api.app.services.websocket.runtime import sio

    async def _emit() -> None:
        try:
            await sio.emit(PLATFORM_EVENT, payload, room=ADMIN_EVENTS_ROOM)
        except Exception:
            logger.exception("[admin-events] sio.emit failed")

    try:
        asyncio.run_coroutine_threadsafe(_emit(), loop)
    except RuntimeError:
        logger.debug("[admin-events] event loop closed; dropping event")


def _relay(loop: asyncio.AbstractEventLoop, event: Any) -> None:
    from naas_abi_core.services.event import EventCodec

    try:
        payload = EventCodec.to_event_dict(event)
        payload["_seq"] = getattr(event, "_seq", None)
        payload["_stored_at"] = getattr(event, "_stored_at", None) or None
        payload = json.loads(json.dumps(payload, default=str))
    except Exception:
        logger.exception("[admin-events] failed to serialize event")
        return
    logger.debug("[admin-events] emit %s", payload.get("_class_uri"))
    _emit_event_threadsafe(loop, payload)


def start_admin_event_relay() -> None:
    """Install a tap on ``EventService.publish`` and relay events to SIO.

    Idempotent: a second call is a no-op once the tap is installed. Safe
    to call when no engine/event service is available — it logs and
    returns instead of raising.
    """
    global _relay_installed
    if _relay_installed:
        logger.info("[admin-events] relay already installed; skipping")
        return

    try:
        from naas_abi import ABIModule

        engine = ABIModule.get_instance().engine
    except Exception:
        logger.warning("[admin-events] ABIModule engine not available; relay disabled")
        return

    if not engine.services.events_available():
        logger.warning("[admin-events] EventService not configured; relay disabled")
        return

    event_service = engine.services.events

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("[admin-events] no running event loop; relay disabled")
        return

    original_publish = event_service.publish

    def _wrapped_publish(event: Any):  # type: ignore[no-redef]
        stored = original_publish(event)
        try:
            _relay(loop, event)
        except Exception:
            logger.exception("[admin-events] relay tap failed")
        return stored

    event_service.publish = _wrapped_publish  # type: ignore[assignment]
    _relay_installed = True
    logger.info("[admin-events] relay installed via EventService.publish tap")
