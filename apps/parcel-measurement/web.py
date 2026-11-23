import asyncio
import json
from pathlib import Path
import queue
import threading

from aiohttp import web


class BrowserServer:
    def __init__(self, host, port):
        self.host, self.port = host, port
        self.commands = queue.Queue()
        self.lock = threading.Lock()
        self.state = {
            "calibration": {"phase": "idle"},
            "message": "Connecting to the camera…",
        }
        self.frame = None
        self.version = 0
        self.loop = None
        self.runner = None
        self.thread = None
        self.sockets = set()

    def publish(self, state, frame=None):
        with self.lock:
            self.state = state
            if frame is not None:
                self.frame = frame
            self.version += 1

    async def status(self, request):
        with self.lock:
            return web.json_response(self.state)

    async def command(self, request):
        try:
            data = await request.json() if request.can_read_body else {}
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object.")
            if request.match_info["action"] == "select":
                for key in ("generation", "index"):
                    if isinstance(data.get(key), bool) or not isinstance(
                        data.get(key), int
                    ):
                        raise ValueError(f"{key} must be an integer.")
            elif request.match_info["action"] != "calibrate":
                raise ValueError("Unknown action.")
        except (ValueError, json.JSONDecodeError) as error:
            return web.json_response({"error": str(error)}, status=400)
        self.commands.put((request.match_info["action"], data))
        return web.json_response({"queued": True})

    async def websocket(self, request):
        socket = web.WebSocketResponse(heartbeat=20)
        await socket.prepare(request)
        self.sockets.add(socket)

        async def send_snapshots():
            previous = -1
            while not socket.closed:
                with self.lock:
                    version = self.version
                    payload = {
                        "type": "snapshot",
                        "state": self.state,
                        "frame": self.frame,
                    }
                if previous != version:
                    await socket.send_json(payload)
                    previous = version
                await asyncio.sleep(0.05)

        sender = asyncio.create_task(send_snapshots())
        try:
            async for _ in socket:
                pass
        finally:
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
            self.sockets.discard(socket)
        return socket

    async def serve(self):
        app = web.Application(client_max_size=4096)
        app.router.add_get("/api/state", self.status)
        app.router.add_post("/api/{action}", self.command)
        app.router.add_get("/ws", self.websocket)
        frontend = Path(__file__).parent / "frontend"
        app.router.add_get(
            "/", lambda request: web.FileResponse(frontend / "index.html")
        )
        app.router.add_static("/static", frontend)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        await web.TCPSite(self.runner, self.host, self.port).start()

    def start(self):
        ready = threading.Event()
        errors = []

        def run():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            try:
                self.loop.run_until_complete(self.serve())
            except Exception as error:
                errors.append(error)
            finally:
                ready.set()
            if not errors:
                self.loop.run_forever()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        ready.wait()
        if errors:
            raise errors[0]

    def stop(self):
        if self.loop and self.runner:

            async def cleanup():
                await asyncio.gather(
                    *(socket.close() for socket in tuple(self.sockets))
                )
                await self.runner.cleanup()

            asyncio.run_coroutine_threadsafe(cleanup(), self.loop).result(timeout=5)
            self.loop.call_soon_threadsafe(self.loop.stop)
