"""Serve a range selector above the embedded DepthAI Viewer."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread


class ModeMenu(ThreadingHTTPServer):
    def __init__(self, modes, port=8082):
        self.modes = tuple(modes)
        self.requested = self.selected = "far"
        self.markup = Path(__file__).with_name("mode_menu.html").read_bytes()
        super().__init__(("0.0.0.0", port), MenuHandler)

    def start(self):
        Thread(target=self.serve_forever, daemon=True).start()


class MenuHandler(BaseHTTPRequestHandler):
    def reply(self, status, content, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if self.path == "/":
            self.reply(200, self.server.markup, "text/html; charset=utf-8")
        elif self.path == "/tof-mode":
            self.reply(
                200,
                json.dumps(
                    {
                        "selected": self.server.selected,
                        "requested": self.server.requested,
                    }
                ).encode(),
            )
        else:
            self.reply(404, b"{}")

    def do_POST(self):
        if self.path != "/tof-mode":
            self.reply(404, b"{}")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1024:
                raise ValueError("Invalid request size")
            mode = json.loads(self.rfile.read(length))["mode"]
            if not isinstance(mode, str) or mode not in self.server.modes:
                raise ValueError("Invalid mode")
        except (ValueError, KeyError, TypeError):
            self.reply(400, b'{"error":"Invalid ToF mode"}')
            return
        self.server.requested = mode
        self.reply(200, b"{}")

    def log_message(self, format, *args):
        pass
