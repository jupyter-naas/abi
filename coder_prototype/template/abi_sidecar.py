#!/usr/bin/env python3
"""abi workspace tool-exec sidecar.

A tiny, dependency-free HTTP service that runs INSIDE a Coder coding workspace
and lets the (server-side) abi agent perform filesystem operations against the
workspace's project directory. The abi server reaches it over the shared docker
network by container DNS name. Every request is bearer-authenticated with a
per-workspace secret, and every path is realpath-jailed under the project root.

Env:
  ABI_SIDECAR_SECRET  shared bearer secret (required; empty disables auth -> dev only)
  ABI_SIDECAR_ROOT    project root to jail under (default: ~/project)
  ABI_SIDECAR_PORT    listen port (default: 8378)
"""

from __future__ import annotations

import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.realpath(os.environ.get("ABI_SIDECAR_ROOT") or os.path.expanduser("~/project"))
SECRET = os.environ.get("ABI_SIDECAR_SECRET", "")
PORT = int(os.environ.get("ABI_SIDECAR_PORT", "8378"))
MAX_BODY = 8 * 1024 * 1024


def _resolve(rel_path: str) -> str:
    """Resolve a caller path under ROOT, rejecting escapes."""
    candidate = os.path.realpath(os.path.join(ROOT, rel_path.lstrip("/")))
    if candidate != ROOT and not candidate.startswith(ROOT + os.sep):
        raise ValueError(f"path escapes project root: {rel_path}")
    return candidate


def _write_file(body: dict) -> dict:
    path = body["path"]
    content = body.get("content", "")
    target = _resolve(path)
    os.makedirs(os.path.dirname(target) or ROOT, exist_ok=True)
    data = content.encode("utf-8")
    with open(target, "wb") as fh:
        fh.write(data)
    return {"ok": True, "path": os.path.relpath(target, ROOT), "bytes": len(data)}


def _read_file(body: dict) -> dict:
    target = _resolve(body["path"])
    with open(target, "rb") as fh:
        raw = fh.read(MAX_BODY)
    try:
        text = raw.decode("utf-8")
        return {"ok": True, "path": os.path.relpath(target, ROOT), "content": text}
    except UnicodeDecodeError:
        return {"ok": True, "path": os.path.relpath(target, ROOT), "binary": True, "bytes": len(raw)}


def _list_dir(body: dict) -> dict:
    target = _resolve(body.get("path", "."))
    entries = []
    for name in sorted(os.listdir(target)):
        full = os.path.join(target, name)
        entries.append({"name": name, "type": "dir" if os.path.isdir(full) else "file"})
    return {"ok": True, "path": os.path.relpath(target, ROOT), "entries": entries}


TOOLS = {"write_file": _write_file, "read_file": _read_file, "list_dir": _list_dir}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence default stderr logging
        pass

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self) -> bool:
        if not SECRET:
            return True
        header = self.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else ""
        return hmac.compare_digest(token, SECRET)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"ok": True, "root": ROOT})
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if not self.path.startswith("/tools/"):
            self._send(404, {"ok": False, "error": "not found"})
            return
        if not self._authed():
            self._send(401, {"ok": False, "error": "unauthorized"})
            return
        tool = self.path[len("/tools/"):]
        fn = TOOLS.get(tool)
        if fn is None:
            self._send(404, {"ok": False, "error": f"unknown tool: {tool}"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}") if length else {}
            self._send(200, fn(body))
        except (ValueError, KeyError) as exc:
            self._send(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001 - surface to caller
            self._send(500, {"ok": False, "error": str(exc)})


if __name__ == "__main__":
    os.makedirs(ROOT, exist_ok=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
