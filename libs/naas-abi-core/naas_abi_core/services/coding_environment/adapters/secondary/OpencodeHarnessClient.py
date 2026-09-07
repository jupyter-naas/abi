"""Minimal sync HTTP client for an OpenCode ``serve`` instance in a sandbox."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any


class OpencodeHarnessError(Exception):
    """Base error for harness HTTP failures."""


class OpencodeHarnessUnavailableError(OpencodeHarnessError):
    """Harness server is not reachable or not healthy."""


class OpencodeHarnessRequestError(OpencodeHarnessError):
    def __init__(self, status_code: int, body: str):
        super().__init__(f"opencode request failed ({status_code}): {body}")
        self.status_code = status_code
        self.body = body


def is_healthy(base_url: str, *, timeout_s: float = 1.0) -> bool:
    url = f"{base_url.rstrip('/')}/global/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:  # nosec B310
            payload = json.loads(resp.read().decode("utf-8"))
            return isinstance(payload, dict) and payload.get("healthy") is True
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return False


def wait_for_healthy(
    base_url: str, *, timeout_s: float = 15.0, poll_s: float = 0.25
) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if is_healthy(base_url):
            return True
        time.sleep(poll_s)
    return False


def _model_payload(model: str | None) -> dict[str, str] | None:
    if not model:
        return None
    model_value = model.strip()
    if not model_value or "/" not in model_value:
        return None
    provider_id, model_id = model_value.split("/", 1)
    provider_id = provider_id.strip()
    model_id = model_id.strip()
    if not provider_id or not model_id:
        return None
    return {"providerID": provider_id, "modelID": model_id}


def _request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout_s: float = 120.0,
) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # nosec B310
            body = resp.read().decode("utf-8").strip()
            if not body:
                return {}
            parsed = json.loads(body)
            return parsed if isinstance(parsed, dict) else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise OpencodeHarnessRequestError(exc.code, body) from exc
    except urllib.error.URLError as exc:
        raise OpencodeHarnessUnavailableError(str(exc)) from exc


def _extract_text(parts: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for part in parts:
        text = part.get("text") or part.get("content")
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())
    return "\n".join(chunks).strip()


def _extract_parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    parts = payload.get("parts")
    if isinstance(parts, list):
        return [part for part in parts if isinstance(part, dict)]
    message = payload.get("message")
    if isinstance(message, dict) and isinstance(message.get("parts"), list):
        return [part for part in message["parts"] if isinstance(part, dict)]
    return []


def create_session(base_url: str, *, title: str = "abi-coding-harness") -> str:
    payload = _request_json(
        "POST",
        f"{base_url.rstrip('/')}/session",
        {"title": title},
        timeout_s=30.0,
    )
    session_id = (
        payload.get("id")
        or payload.get("session", {}).get("id")
        or payload.get("session_id")
    )
    if not session_id:
        raise OpencodeHarnessRequestError(200, json.dumps(payload))
    return str(session_id)


def run_task(
    base_url: str,
    message: str,
    *,
    model: str | None = None,
    session_id: str | None = None,
    timeout_s: float = 600.0,
) -> dict[str, Any]:
    """Send a task to OpenCode and return assistant text plus session id."""
    if not wait_for_healthy(base_url, timeout_s=min(15.0, timeout_s)):
        return {"error": "OpenCode harness is not healthy", "session_id": session_id}

    active_session = session_id
    try:
        if not active_session:
            active_session = create_session(base_url)
        body: dict[str, Any] = {
            "parts": [{"type": "text", "text": message}],
            "noReply": False,
        }
        model_payload = _model_payload(model)
        if model_payload is not None:
            body["model"] = model_payload
        payload = _request_json(
            "POST",
            f"{base_url.rstrip('/')}/session/{active_session}/message",
            body,
            timeout_s=timeout_s,
        )
        text = _extract_text(_extract_parts(payload))
        return {
            "session_id": active_session,
            "completion": text,
            "raw_parts": _extract_parts(payload),
        }
    except OpencodeHarnessError as exc:
        return {"error": str(exc), "session_id": active_session}
