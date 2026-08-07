from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

import httpx
from naas_abi.config.dotenv_secrets import (
    clear_dotenv_secret,
    is_usable_secret_value,
    write_dotenv_secret,
)

GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
DEFAULT_GITHUB_SCOPES = "repo read:user"


@dataclass
class DeviceSession:
    session_id: str
    device_code: str
    user_code: str
    verification_uri: str
    interval: int
    expires_at: float
    client_id: str
    status: str = "pending"
    error: str | None = None
    github_login: str | None = None


@dataclass
class _DeviceStore:
    sessions: dict[str, DeviceSession] = field(default_factory=dict)
    lock: Lock = field(default_factory=Lock)


_DEVICE_STORE = _DeviceStore()


def _resolve_client_id() -> str:
    client_id = (os.environ.get("GITHUB_OAUTH_CLIENT_ID") or "").strip()
    if not client_id:
        raise RuntimeError(
            "GitHub OAuth is not configured. Set GITHUB_OAUTH_CLIENT_ID in .env "
            "(create an OAuth app at https://github.com/settings/developers and "
            "enable Device Flow), or paste a personal access token instead."
        )
    return client_id


def _prune_expired(now: float | None = None) -> None:
    ts = now if now is not None else time.time()
    with _DEVICE_STORE.lock:
        expired = [
            sid
            for sid, session in _DEVICE_STORE.sessions.items()
            if session.expires_at <= ts
        ]
        for sid in expired:
            _DEVICE_STORE.sessions.pop(sid, None)


class GitHubConnectService:
    @staticmethod
    async def status() -> dict[str, Any]:
        from naas_abi import ABIModule

        engine = ABIModule.get_instance().engine
        module_installed = (
            "naas_abi_marketplace.applications.github" in engine.modules
        )
        client_id = (os.environ.get("GITHUB_OAUTH_CLIENT_ID") or "").strip()
        token = GitHubConnectService._read_token()
        github_login: str | None = None
        connected = False
        if is_usable_secret_value(token):
            github_login = await GitHubConnectService._fetch_login(token or "")
            # Usable token counts as connected even if GitHub is briefly unreachable.
            connected = True
        return {
            "module_installed": module_installed,
            "connected": connected,
            "oauth_available": bool(client_id),
            "github_login": github_login,
            "agent_name": "GitHub",
            "ready": connected and module_installed,
        }

    @staticmethod
    def _read_token() -> str | None:
        try:
            from naas_abi import ABIModule

            secret = ABIModule.get_instance().engine.services.secret.get(
                "GITHUB_ACCESS_TOKEN"
            )
        except Exception:  # noqa: BLE001
            secret = os.environ.get("GITHUB_ACCESS_TOKEN")
        if secret is None:
            return None
        return str(secret).strip() or None

    @staticmethod
    def disconnect() -> dict[str, Any]:
        clear_dotenv_secret("GITHUB_ACCESS_TOKEN")
        return {
            "connected": False,
            "restart_required": True,
            "message": "GitHub credentials cleared. Connect again, then restart OS.",
        }

    @staticmethod
    async def start_device_flow() -> dict[str, Any]:
        _prune_expired()
        client_id = _resolve_client_id()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GITHUB_DEVICE_CODE_URL,
                headers={"Accept": "application/json"},
                data={"client_id": client_id, "scope": DEFAULT_GITHUB_SCOPES},
            )
            response.raise_for_status()
            payload = response.json()

        session_id = uuid.uuid4().hex
        session = DeviceSession(
            session_id=session_id,
            device_code=str(payload["device_code"]),
            user_code=str(payload["user_code"]),
            verification_uri=str(payload["verification_uri"]),
            interval=max(int(payload.get("interval", 5)), 3),
            expires_at=time.time() + float(payload.get("expires_in", 900)),
            client_id=client_id,
        )
        with _DEVICE_STORE.lock:
            _DEVICE_STORE.sessions[session_id] = session

        return {
            "session_id": session_id,
            "user_code": session.user_code,
            "verification_uri": session.verification_uri,
            "interval": session.interval,
            "expires_in": max(int(session.expires_at - time.time()), 0),
        }

    @staticmethod
    async def poll_device_flow(session_id: str) -> dict[str, Any]:
        _prune_expired()
        with _DEVICE_STORE.lock:
            session = _DEVICE_STORE.sessions.get(session_id)
        if session is None:
            return {"status": "expired", "connected": False}

        if session.status == "complete":
            return {
                "status": "complete",
                "connected": True,
                "github_login": session.github_login,
            }
        if session.status == "error":
            return {
                "status": "error",
                "connected": False,
                "detail": session.error or "GitHub authorization failed",
            }

        if time.time() >= session.expires_at:
            with _DEVICE_STORE.lock:
                _DEVICE_STORE.sessions.pop(session_id, None)
            return {"status": "expired", "connected": False}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GITHUB_ACCESS_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": session.client_id,
                    "device_code": session.device_code,
                    "grant_type": "urn:ietf:params:oauth:2.0:device_code",
                },
            )
            payload = response.json()

        error = payload.get("error")
        if error in {"authorization_pending", "slow_down"}:
            return {
                "status": "pending",
                "connected": False,
                "interval": session.interval,
            }

        if error:
            session.status = "error"
            session.error = str(payload.get("error_description") or error)
            return {
                "status": "error",
                "connected": False,
                "detail": session.error,
            }

        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token.strip():
            session.status = "error"
            session.error = "GitHub returned an empty access token"
            return {
                "status": "error",
                "connected": False,
                "detail": session.error,
            }

        write_dotenv_secret("GITHUB_ACCESS_TOKEN", access_token.strip())
        session.status = "complete"
        session.github_login = await GitHubConnectService._fetch_login(access_token.strip())
        return {
            "status": "complete",
            "connected": True,
            "github_login": session.github_login,
            "restart_required": True,
            "message": "GitHub connected. Restart OS to load credentials.",
        }

    @staticmethod
    async def save_personal_access_token(token: str) -> dict[str, Any]:
        cleaned = token.strip()
        if not cleaned:
            raise ValueError("Token cannot be empty")
        write_dotenv_secret("GITHUB_ACCESS_TOKEN", cleaned)
        login = await GitHubConnectService._fetch_login(cleaned)
        return {
            "connected": True,
            "github_login": login,
            "restart_required": True,
            "message": "GitHub token saved. Restart OS to load credentials.",
        }

    @staticmethod
    async def _fetch_login(access_token: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    "https://api.github.com/user",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
                if response.status_code != 200:
                    return None
                data = response.json()
                login = data.get("login")
                return str(login) if login else None
        except Exception:
            return None
