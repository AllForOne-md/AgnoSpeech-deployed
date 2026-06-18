"""Stdlib HTTP backend for the workbench.

No framework: a ThreadingHTTPServer serves the static design from ``web/`` and a
tiny JSON API that calls :mod:`agnospeech_workbench.pipeline` — which is itself
just the ``agnospeech`` library. Keeping it stdlib-only means the whole app
bundles into one PyInstaller executable with no web-server dependency.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .api_logic import handle_dataset, handle_edit, handle_release, handle_run
from .corpus import demo_corpus

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

_MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".woff2": "font/woff2",
}

class Handler(BaseHTTPRequestHandler):
    server_version = "AgnoSpeechWorkbench/0.9"

    def log_message(self, *args: Any) -> None:  # silence default stderr spam
        pass

    # --- helpers --------------------------------------------------------------
    def _send(self, code: int, body: bytes, mime: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: Any, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json")

    def _read_body(self) -> dict[str, Any]:
        n = int(self.headers.get("Content-Length", 0) or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    # --- routing --------------------------------------------------------------
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "":
            return self._serve_static("index.html")
        if path == "/api/demo":
            return self._json({"rows": demo_corpus()})
        if path.startswith("/static/"):
            return self._serve_static(path[len("/static/"):])
        if path in ("/style.css", "/app.js"):
            return self._serve_static(path.lstrip("/"))
        return self._send(404, b"not found", "text/plain")

    _API = {"/api/run": handle_run, "/api/edit": handle_edit, "/api/release": handle_release,
            "/api/dataset": handle_dataset}

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        fn = self._API.get(path)
        if fn is None:
            return self._send(404, b"not found", "text/plain")
        try:
            self._json(fn(self._read_body()))
        except Exception as exc:  # surface library errors to the UI
            self._json({"error": str(exc)}, code=400)

    # --- static ---------------------------------------------------------------
    def _serve_static(self, rel: str) -> None:
        target = (WEB_DIR / rel).resolve()
        if WEB_DIR not in target.parents and target != WEB_DIR:
            return self._send(403, b"forbidden", "text/plain")
        if not target.is_file():
            return self._send(404, b"not found", "text/plain")
        mime = _MIME.get(target.suffix, "application/octet-stream")
        self._send(200, target.read_bytes(), mime)


def make_server(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)
