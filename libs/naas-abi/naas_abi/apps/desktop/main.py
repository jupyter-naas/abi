"""ABI Desktop entry point.

Starts the local FastAPI backend on a stable dev port (default 54242),
then opens a native window (pywebview) pointed at it. Falls back to the
default browser when pywebview is not installed.

Run from source:
    uv run python libs/naas-abi/naas_abi/apps/desktop/run.py
    uv run python libs/naas-abi/naas_abi/apps/desktop/run.py --browser-only

Browser-only dev (no pywebview, no PyInstaller):
    ABI_DESKTOP_BROWSER=1 uv run python .../run.py

Fixed dev URL (override with ABI_DESKTOP_PORT):
    http://127.0.0.1:54242

Build an executable:
    see naas_abi/apps/desktop/build.md
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from typing import Any

import httpx
import uvicorn

from .api.server import create_app
from .config.desktop_config import APP_NAME, DEFAULT_SERVER_PORT, DESKTOP_PACKAGE_DIR


def _port_available(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def _pid_on_port(port: int) -> int | None:
    try:
        out = subprocess.check_output(
            ["lsof", "-ti", f":{port}"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    if not lines:
        return None
    try:
        return int(lines[0])
    except ValueError:
        return None


def _port_in_use_message(port: int) -> str:
    pid = _pid_on_port(port)
    if pid is not None:
        return f"Port {port} in use (PID {pid}) — kill PID or set ABI_DESKTOP_PORT"
    return f"Port {port} in use — kill the process or set ABI_DESKTOP_PORT"


def resolve_server_port(*, allow_fallback: bool = True) -> int:
    """Resolve the listen port from ABI_DESKTOP_PORT or the default."""
    raw = os.environ.get("ABI_DESKTOP_PORT", "").strip()
    if raw:
        try:
            port = int(raw)
        except ValueError:
            print(f"Invalid ABI_DESKTOP_PORT: {raw!r}", file=sys.stderr)
            raise SystemExit(1) from None
        if not (1 <= port <= 65535):
            print(
                f"Invalid ABI_DESKTOP_PORT: {port} (must be 1-65535)", file=sys.stderr
            )
            raise SystemExit(1)
        if not _port_available(port):
            print(_port_in_use_message(port), file=sys.stderr)
            raise SystemExit(1)
        return port

    port = DEFAULT_SERVER_PORT
    if _port_available(port):
        return port

    if allow_fallback and _port_available(port + 1):
        print(
            f"Warning: {_port_in_use_message(port)}; using {port + 1} instead.",
            file=sys.stderr,
        )
        return port + 1

    print(_port_in_use_message(port), file=sys.stderr)
    raise SystemExit(1)


def _wait_for_server(url: str, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{url}/api/health", timeout=1.0).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.1)
    raise RuntimeError("backend did not start in time")


def _bind_finder_drop(window: Any, api_url: str) -> None:
    """pywebview bridge: Finder drops expose full paths only on the Python side."""
    try:
        from webview.dom import DOMEventHandler
    except ImportError:
        return

    def on_drop(e: dict[str, Any]) -> None:
        try:
            active = window.evaluate_js(
                "typeof window.__isFileTreeDropActive==='function'"
                "&&window.__isFileTreeDropActive()"
            )
        except Exception:
            active = False
        if not active:
            return
        files = (e.get("dataTransfer") or {}).get("files") or []
        paths = [
            f["pywebviewFullPath"]
            for f in files
            if isinstance(f, dict) and f.get("pywebviewFullPath")
        ]
        if not paths:
            return
        try:
            target_dir = window.evaluate_js(
                "typeof window.__getDropTargetDir==='function'"
                "?window.__getDropTargetDir():''"
            )
        except Exception:
            target_dir = ""
        try:
            response = httpx.post(
                f"{api_url}/api/files/import-local",
                json={"paths": paths, "dir": target_dir or ""},
                timeout=60.0,
            )
            if response.status_code == 200:
                payload = json.dumps(response.json())
                dir_json = json.dumps(target_dir or "")
                window.evaluate_js(
                    "window.__onUploadComplete && "
                    f"window.__onUploadComplete({payload}, {dir_json})"
                )
            else:
                detail = json.dumps(response.text[:200])
                window.evaluate_js(
                    f"window.__onUploadFailed && window.__onUploadFailed({detail})"
                )
        except Exception as exc:
            detail = json.dumps(str(exc)[:200])
            window.evaluate_js(
                f"window.__onUploadFailed && window.__onUploadFailed({detail})"
            )

    def on_dragover(_e: dict[str, Any]) -> None:
        return None

    drop_handler = DOMEventHandler(
        on_drop,
        prevent_default=True,
        stop_propagation=True,
        stop_immediate_propagation=True,
    )
    dragover_handler = DOMEventHandler(
        on_dragover,
        prevent_default=True,
        stop_propagation=False,
        stop_immediate_propagation=False,
    )

    def attach() -> bool:
        try:
            tree = window.dom.get_element("#file-tree")
            if tree is None:
                return False
            tree.events.drop += drop_handler
            tree.events.dragover += dragover_handler
            return True
        except Exception:
            return False

    if attach():
        return

    # Fallback: document-level drop when #file-tree is not yet in the DOM.
    try:
        doc_handler = DOMEventHandler(
            on_drop,
            prevent_default=True,
            stop_propagation=True,
            stop_immediate_propagation=True,
        )
        window.dom.document.events.drop += doc_handler
        window.dom.document.events.dragover += dragover_handler
    except Exception:
        pass


def _app_icon_path() -> str | None:
    """macOS Dock icon when running from source (bundled .app sets it via PyInstaller)."""
    icns = DESKTOP_PACKAGE_DIR / "assets" / "abi-desktop.icns"
    return str(icns) if icns.is_file() else None


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} local server")
    parser.add_argument(
        "--browser-only",
        action="store_true",
        help="serve on localhost and open the system browser (skip pywebview)",
    )
    parser.add_argument(
        "--no-open-browser",
        action="store_true",
        help="with --browser-only, print the URL but do not launch a browser tab",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="auto-reload Python on change (browser-only dev; refresh JS/CSS manually)",
    )
    return parser.parse_args(argv)


def browser_only_mode(argv: list[str] | None = None) -> bool:
    """True when --browser-only or ABI_DESKTOP_BROWSER is set."""
    if _truthy_env("ABI_DESKTOP_BROWSER"):
        return True
    return _parse_args(argv).browser_only


def reload_enabled(argv: list[str] | None = None) -> bool:
    """True when --reload or ABI_DESKTOP_RELOAD is set."""
    if _truthy_env("ABI_DESKTOP_RELOAD"):
        return True
    return _parse_args(argv).reload


def _start_browser(url: str, *, open_browser: bool) -> None:
    print(f"Open {url}")
    if open_browser:
        webbrowser.open(url)
    print("Ctrl+C to quit.")


def _start_webview(url: str) -> None:
    import webview  # type: ignore[import-not-found]

    window = webview.create_window(
        APP_NAME, url, width=1280, height=820, min_size=(900, 600)
    )

    def on_start() -> None:
        _bind_finder_drop(window, url)

    icon = _app_icon_path()
    if icon:
        webview.start(on_start, window, icon=icon)
    else:
        webview.start(on_start, window)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    browser_only = args.browser_only or _truthy_env("ABI_DESKTOP_BROWSER")
    reload = args.reload or _truthy_env("ABI_DESKTOP_RELOAD")
    port = resolve_server_port()
    url = f"http://127.0.0.1:{port}"

    app = create_app()

    if browser_only:
        if reload:
            print(
                "Hot reload enabled for Python (gui/web JS and CSS still need a manual refresh)."
            )
        _start_browser(url, open_browser=not args.no_open_browser)
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            reload=reload,
            reload_dirs=[str(DESKTOP_PACKAGE_DIR)] if reload else None,
        )
        return

    if reload:
        print(
            "Warning: --reload is ignored without --browser-only; "
            "restart the server manually for Python changes.",
            file=sys.stderr,
        )

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait_for_server(url)
    print(f"{APP_NAME} running at {url}")

    try:
        _start_webview(url)
    except ImportError:
        _start_browser(url, open_browser=True)
        try:
            while thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    server.should_exit = True


if __name__ == "__main__":
    main()
