from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
from urllib.parse import urlencode


class FrontendServer:
    def __init__(self, host: str, port: int, directory: Path):
        if not (directory / "index.html").is_file():
            raise FileNotFoundError(
                f"Frontend build missing from {directory}. "
                "Run npm --prefix frontend ci and npm --prefix frontend run build."
            )
        handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
        self._server = ThreadingHTTPServer((host, port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self.host = host

    @property
    def port(self):
        return self._server.server_port

    def url(self, websocket_port: int):
        host = "127.0.0.1" if self.host == "0.0.0.0" else self.host
        host = f"[{host}]" if ":" in host else host
        query = urlencode({"ws_url": f"ws://{host}:{websocket_port}"})
        return f"http://{host}:{self.port}/?{query}"

    def start(self):
        self._thread.start()

    def stop(self):
        if self._thread.is_alive():
            self._server.shutdown()
            self._thread.join()
        self._server.server_close()
