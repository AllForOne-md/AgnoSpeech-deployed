#!/usr/bin/env python3
"""Launch the AgnoSpeech Local Privatization Workbench.

Starts the stdlib backend on a loopback port, then opens the UI in a native
window via pywebview when available, otherwise in the default browser. Designed
so the whole thing PyInstaller-bundles into one double-clickable executable.
"""

from __future__ import annotations

import os
import sys
import threading

from agnospeech_workbench.server import make_server

APP_TITLE = "AgnoSpeech — Local Privatization Workbench"


def _serve_forever(server) -> None:
    """Headless/server mode — no window, just serve until interrupted."""
    print("Native window disabled (AGNO_NO_WINDOW) — server-only mode.", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass


def main() -> int:
    host = os.environ.get("AGNO_HOST", "127.0.0.1")
    port = int(os.environ.get("AGNO_PORT", "0"))
    server = make_server(host, port)
    host, port = server.server_address[0], server.server_address[1]
    url = f"http://{host}:{port}/"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"AgnoSpeech workbench running at {url}  (offline · on-device)", flush=True)

    try:
        if os.environ.get("AGNO_NO_WINDOW"):
            _serve_forever(server)
        else:
            # Prefer a native window; fall back to the browser.
            try:
                import webview  # type: ignore

                webview.create_window(APP_TITLE, url, width=1280, height=860, min_size=(980, 680))
                webview.start()
            except Exception:
                import webbrowser

                webbrowser.open(url)
                print("Native window unavailable — opened in your browser.", flush=True)
                print("Press Ctrl+C to stop.", flush=True)
                try:
                    threading.Event().wait()
                except KeyboardInterrupt:
                    pass
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
