"""ABI Desktop entry point.

Starts the local FastAPI backend on a free port, then opens a native
window (pywebview) pointed at it. Falls back to the default browser when
pywebview is not installed.

Run from source:
    uv run python -m naas_abi.apps.desktop.main

Build an executable:
    see naas_abi/apps/desktop/build.md
"""

from __future__ import annotations

import socket
import threading
import time

import httpx
import uvicorn

from .desktop_config import APP_NAME
from .server import create_app


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


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


def main() -> None:
    port = _free_port()
    url = f"http://127.0.0.1:{port}"

    app = create_app()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait_for_server(url)
    print(f"{APP_NAME} running at {url}")

    try:
        import webview  # type: ignore[import-not-found]

        window = webview.create_window(
            APP_NAME, url, width=1280, height=820, min_size=(900, 600)
        )
        del window
        webview.start()
    except ImportError:
        import webbrowser

        webbrowser.open(url)
        print("pywebview not installed — opened in browser. Ctrl+C to quit.")
        try:
            while thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    server.should_exit = True


if __name__ == "__main__":
    main()
