"""Small loopback control page for the diagnostic data capture app."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit
from typing import Callable


_INDEX = Path(__file__).with_name("index.html")
_MAX_BODY = 4096


class ControlServer:
    """Serve the capture controls and a read-only status endpoint.

    ``request_capture`` should enqueue work and return promptly. Device capture
    work belongs in the app's main loop, not in an HTTP request thread.
    """

    def __init__(self, host="127.0.0.1", port=8083, visualizer_port=8082,
                 get_status: Callable[[], dict] | None = None,
                 request_capture: Callable[[int, str], dict] | None = None):
        self.host = host
        self.port = int(port)
        self.visualizer_port = int(visualizer_port)
        self.get_status = get_status or (lambda: {})
        self.request_capture = request_capture or (lambda frames, output: {})
        self._server = None
        self._thread = None

    @property
    def url(self):
        if self._server is None:
            host, port = self.host, self.port
        else:
            host, port = self._server.server_address[:2]
        shown_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
        return f"http://{shown_host}:{port}/?visualizer_port={self.visualizer_port}"

    def start(self):
        if self._server is not None:
            return self
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "DiagnosticCaptureControl/1.0"

            def _send(self, status, body, content_type="application/json; charset=utf-8"):
                data = body if isinstance(body, bytes) else body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def _json(self, status, value):
                self._send(status, json.dumps(value, separators=(",", ":")))

            def do_GET(self):
                if urlsplit(self.path).path == "/api/status":
                    try:
                        self._json(200, owner.get_status())
                    except Exception as exc:
                        self._json(500, {"error": str(exc)})
                    return
                if urlsplit(self.path).path not in ("/", "/index.html"):
                    self._json(404, {"error": "not found"})
                    return
                try:
                    page = _INDEX.read_bytes()
                except OSError as exc:
                    self._json(500, {"error": f"control page unavailable: {exc}"})
                    return
                self._send(200, page, "text/html; charset=utf-8")

            def do_POST(self):
                if urlsplit(self.path).path != "/api/capture":
                    self._json(404, {"error": "not found"})
                    return
                if not self._same_origin():
                    self._json(403, {"error": "same-origin request required"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", ""))
                except ValueError:
                    self._json(400, {"error": "invalid Content-Length"})
                    return
                if length < 0 or length > _MAX_BODY:
                    self._json(413, {"error": "request body too large"})
                    return
                if self.headers.get_content_type() != "application/json":
                    self._json(415, {"error": "application/json required"})
                    return
                try:
                    payload = json.loads(self.rfile.read(length))
                    frames = payload["frames"]
                    output = payload["output"]
                    if (not isinstance(payload, dict) or isinstance(frames, bool)
                            or not isinstance(frames, int) or frames <= 0
                            or not isinstance(output, str) or not output.strip()
                            or len(output) > 2048):
                        raise ValueError("frames must be a positive integer and output a non-empty path")
                except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    self._json(400, {"error": str(exc) or "invalid request"})
                    return
                try:
                    result = owner.request_capture(frames, output.strip())
                except ValueError as exc:
                    self._json(400, {"error": str(exc)})
                except RuntimeError as exc:
                    self._json(409, {"error": str(exc)})
                except Exception as exc:
                    self._json(500, {"error": str(exc)})
                else:
                    self._json(202, result if isinstance(result, dict) else {"accepted": True})

            def _same_origin(self):
                host = self.headers.get("Host", "").lower()
                origin = self.headers.get("Origin", "")
                try:
                    parsed = urlsplit(origin)
                    expected_host = owner._authority().lower()
                    return (parsed.scheme == "http" and parsed.netloc.lower() == host
                            and host == expected_host and not parsed.username
                            and not parsed.password)
                except (ValueError, TypeError):
                    return False

            def log_message(self, fmt, *args):
                # Keep routine polling from flooding the app log.
                if self.path != "/api/status":
                    super().log_message(fmt, *args)

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        name="capture-control-http", daemon=True)
        self._thread.start()
        return self

    def _authority(self):
        if self._server is None:
            host, port = self.host, self.port
        else:
            host, port = self._server.server_address[:2]
        shown_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
        return f"{shown_host}:{port}"

    def close(self):
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._server = None
        self._thread = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *_exc):
        self.close()
