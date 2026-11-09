"""Device-free tests for timestamp matching, camera roles, and capture control."""

import http.client
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

import depthai as dai
from control import ControlServer
from main import CaptureApp, FrameMatcher, camera_roles


class FakeFrame:
    def __init__(self, timestamp):
        self.timestamp = timestamp

    def getTimestampDevice(self):
        return SimpleNamespace(total_seconds=lambda: self.timestamp)


class FakeCalibration:
    def getStereoLeftCameraId(self):
        return dai.CameraBoardSocket.CAM_B

    def getStereoRightCameraId(self):
        return dai.CameraBoardSocket.CAM_C


class FakeDevice:
    def readCalibration(self):
        return FakeCalibration()

    def getConnectedCameraFeatures(self):
        return []

    def getDeviceId(self):
        return "fake-id"

    def getDeviceName(self):
        return "fake-oak"

    def getOSVersion(self):
        return "fake-os"


class MatcherTests(unittest.TestCase):
    def test_takes_frames_within_skew_tolerance(self):
        matcher = FrameMatcher(("left", "right"), 0.01)
        left, right = FakeFrame(1.0), FakeFrame(1.009)
        matcher.add("left", left)
        matcher.add("right", right)

        group = matcher.take()

        self.assertIs(group["left"], left)
        self.assertIs(group["right"], right)
        self.assertIsNone(matcher.take())

    def test_drops_oldest_frame_when_skew_exceeds_tolerance(self):
        matcher = FrameMatcher(("left", "right"), 0.01)
        stale, aligned = FakeFrame(2.0), FakeFrame(2.02)
        newer_left, right = FakeFrame(2.015), FakeFrame(2.021)
        matcher.add("left", stale)
        matcher.add("left", newer_left)
        matcher.add("right", right)

        group = matcher.take()

        self.assertIs(group["left"], newer_left)
        self.assertIs(group["right"], right)
        self.assertIsNone(matcher.take())

    def test_each_stream_buffer_is_bounded(self):
        matcher = FrameMatcher(("left", "right"), 0.01)
        frames = [FakeFrame(float(i)) for i in range(10)]
        for frame in frames:
            matcher.add("left", frame)

        self.assertEqual(len(matcher.buffers["left"]), 8)
        self.assertIs(matcher.buffers["left"][0], frames[2])


class CameraRoleTests(unittest.TestCase):
    def test_optional_rgb_stereo_and_tof_roles(self):
        features = [
            SimpleNamespace(socket=dai.CameraBoardSocket.CAM_B, name="mono-left",
                            supportedTypes=[dai.CameraSensorType.MONO]),
            SimpleNamespace(socket=dai.CameraBoardSocket.CAM_C, name="mono-right",
                            supportedTypes=[dai.CameraSensorType.MONO]),
            SimpleNamespace(socket=dai.CameraBoardSocket.CAM_A, name="color",
                            supportedTypes=[dai.CameraSensorType.COLOR]),
            SimpleNamespace(socket=dai.CameraBoardSocket.CAM_D, name="tof",
                            supportedTypes=[dai.CameraSensorType.TOF]),
        ]

        roles = camera_roles(features, FakeCalibration())

        self.assertEqual(set(roles), {"left", "right", "rgb", "tof"})
        self.assertIs(roles["tof"], features[3])

    def test_available_stereo_cameras_do_not_require_rgb_or_tof(self):
        features = [
            SimpleNamespace(socket=dai.CameraBoardSocket.CAM_B, name="left",
                            supportedTypes=[dai.CameraSensorType.MONO]),
            SimpleNamespace(socket=dai.CameraBoardSocket.CAM_C, name="right",
                            supportedTypes=[dai.CameraSensorType.MONO]),
        ]

        self.assertEqual(set(camera_roles(features, FakeCalibration())), {"left", "right"})


class CaptureRequestStateTests(unittest.TestCase):
    def setUp(self):
        args = SimpleNamespace(frames=5, output=Path("captures"), warmup=5.0)
        self.app = CaptureApp(args, FakeDevice())

    def test_warmup_blocks_capture_then_ready_queues_request(self):
        for state in ("starting", "warming_up"):
            self.app.update(state=state, warmup_remaining=1.5)
            with self.assertRaisesRegex(RuntimeError, "Wait for warmup"):
                self.app.request({"frames": 3, "output": "/tmp/example"})

        self.assertEqual(self.app.status()["warmup_remaining"], 1.5)
        self.app.update(state="ready", warmup_remaining=0)
        result = self.app.request({"frames": 3, "output": "/tmp/example"})

        self.assertTrue(result["accepted"])
        self.assertEqual(result["frames"], 3)
        self.assertEqual(self.app.status()["state"], "queued")
        self.assertEqual(self.app.requests.get_nowait(), (3, str(Path("/tmp/example").resolve())))

    def test_request_rejects_bad_counts_and_empty_output(self):
        self.app.update(state="ready")
        for request in ({"frames": True}, {"frames": 0}, {"frames": 10001},
                        {"frames": 2, "output": "  "}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                self.app.request(request)


class ControlHTTPTests(unittest.TestCase):
    def setUp(self):
        self.status = {"state": "warming_up", "warmup_remaining": 2.0}
        self.calls = []

        def request_capture(frames, output):
            self.calls.append((frames, output))
            if self.status["state"] != "ready":
                raise RuntimeError("Wait for warmup or the current capture to finish")
            self.status.update(state="queued", frames=frames, output=output)
            return {"accepted": True, "frames": frames, "output": output}

        self.server = ControlServer(port=0, visualizer_port=8123,
                                    get_status=lambda: dict(self.status),
                                    request_capture=request_capture).start()
        self.host, self.port = self.server._server.server_address[:2]

    def tearDown(self):
        self.server.close()

    @property
    def origin(self):
        return f"http://{self.host}:{self.port}"

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=3)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        payload = response.read()
        conn.close()
        return response.status, payload

    def post(self, value, origin=None, host=None, content_type="application/json"):
        body = json.dumps(value).encode()
        headers = {"Content-Type": content_type, "Content-Length": str(len(body)),
                   "Host": host or f"{self.host}:{self.port}"}
        if origin is not None:
            headers["Origin"] = origin
        return self.request("POST", "/api/capture", body, headers)

    def test_status_page_and_visualizer_url_are_served(self):
        status, body = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), self.status)
        self.assertIn(f"visualizer_port=8123", self.server.url)
        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"DepthAI Visualizer", body)
        self.assertEqual(self.request("GET", "/missing")[0], 404)

    def test_valid_capture_request_is_queued_after_warmup(self):
        self.status["state"] = "ready"
        status, body = self.post({"frames": 4, "output": " /tmp/run "}, origin=self.origin)

        self.assertEqual(status, 202)
        self.assertEqual(json.loads(body), {"accepted": True, "frames": 4, "output": "/tmp/run"})
        self.assertEqual(self.calls, [(4, "/tmp/run")])
        self.assertEqual(self.status["state"], "queued")

    def test_warmup_and_active_capture_conflicts_return_409(self):
        for state in ("warming_up", "capturing"):
            self.status["state"] = state
            status, body = self.post({"frames": 1, "output": "/tmp/run"}, origin=self.origin)
            self.assertEqual(status, 409)
            self.assertIn(b"warmup", body)

    def test_rejects_cross_origin_and_missing_origin_posts(self):
        value = {"frames": 1, "output": "/tmp/run"}
        self.assertEqual(self.post(value, origin="http://attacker.invalid")[0], 403)
        self.assertEqual(self.post(value)[0], 403)
        self.assertEqual(self.post(value, origin=self.origin, host="attacker.invalid")[0], 403)
        self.assertEqual(self.calls, [])

    def test_rejects_invalid_payload_and_content_type(self):
        for value in ({"frames": True, "output": "/tmp/run"},
                      {"frames": 0, "output": "/tmp/run"},
                      {"frames": 2, "output": " "}, []):
            with self.subTest(value=value):
                self.assertEqual(self.post(value, origin=self.origin)[0], 400)
        self.assertEqual(self.post({"frames": 1, "output": "/tmp/run"}, origin=self.origin,
                                   content_type="text/plain")[0], 415)

    def test_rejects_oversized_payload(self):
        body = b" " * 4097
        status, _ = self.request("POST", "/api/capture", body,
            {"Host": f"{self.host}:{self.port}", "Origin": self.origin,
             "Content-Type": "application/json", "Content-Length": str(len(body))})
        self.assertEqual(status, 413)


if __name__ == "__main__":
    unittest.main()
