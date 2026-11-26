"""Device-free tests for arguments, camera roles, and capture control."""

import argparse
import http.client
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import tempfile
import zipfile

import depthai as dai

# Make the standalone example modules importable during test discovery.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from control import ControlServer
from main import CaptureApp, arguments, camera_roles, image_width, preview_frame


class PreviewEncodingTests(unittest.TestCase):
    def test_gray_preview_preserves_pixels_and_original_capture_message(self):
        frame = dai.ImgFrame()
        frame.setWidth(4)
        frame.setHeight(2)
        frame.setType(dai.ImgFrame.Type.GRAY8)
        frame.setSequenceNum(42)
        frame.setData([0, 1, 2, 3, 4, 5, 254, 255])
        preview = preview_frame(frame)
        self.assertEqual(preview.getType(), dai.ImgFrame.Type.RAW8)
        self.assertEqual(frame.getType(), dai.ImgFrame.Type.GRAY8)
        self.assertEqual(preview.getData().tolist(), frame.getData().tolist())
        self.assertEqual((preview.getWidth(), preview.getHeight()), (4, 2))
        self.assertEqual(preview.getSequenceNum(), 42)
        self.assertIsNot(preview, frame)

    def test_supported_preview_types_are_not_copied_or_changed(self):
        for typ in (
            dai.ImgFrame.Type.NV12,
            dai.ImgFrame.Type.RAW16,
            dai.ImgFrame.Type.RAW8,
        ):
            frame = dai.ImgFrame()
            frame.setType(typ)
            self.assertIs(preview_frame(frame), frame)


class WidthArgumentTests(unittest.TestCase):
    def test_accepts_whole_pixel_widths(self):
        self.assertEqual(image_width("2"), 2)
        self.assertEqual(image_width("20000"), 20000)

    def test_explains_invalid_widths(self):
        for value, reason in (
            ("1", "at least 2 pixels"),
            ("0", "at least 2 pixels"),
            ("640.5", "whole number of pixels"),
            ("wide", "whole number of pixels"),
        ):
            with self.subTest(value=value), self.assertRaisesRegex(
                argparse.ArgumentTypeError, reason
            ):
                image_width(value)


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


class CameraRoleTests(unittest.TestCase):
    def test_optional_rgb_stereo_and_tof_roles(self):
        features = [
            SimpleNamespace(
                socket=dai.CameraBoardSocket.CAM_B,
                name="mono-left",
                supportedTypes=[dai.CameraSensorType.MONO],
            ),
            SimpleNamespace(
                socket=dai.CameraBoardSocket.CAM_C,
                name="mono-right",
                supportedTypes=[dai.CameraSensorType.MONO],
            ),
            SimpleNamespace(
                socket=dai.CameraBoardSocket.CAM_A,
                name="color",
                supportedTypes=[dai.CameraSensorType.COLOR],
            ),
            SimpleNamespace(
                socket=dai.CameraBoardSocket.CAM_D,
                name="tof",
                supportedTypes=[dai.CameraSensorType.TOF],
            ),
        ]

        roles = camera_roles(features, FakeCalibration())

        self.assertEqual(set(roles), {"left", "right", "rgb", "tof"})
        self.assertIs(roles["tof"], features[3])

    def test_available_stereo_cameras_do_not_require_rgb_or_tof(self):
        features = [
            SimpleNamespace(
                socket=dai.CameraBoardSocket.CAM_B,
                name="left",
                supportedTypes=[dai.CameraSensorType.MONO],
            ),
            SimpleNamespace(
                socket=dai.CameraBoardSocket.CAM_C,
                name="right",
                supportedTypes=[dai.CameraSensorType.MONO],
            ),
        ]

        self.assertEqual(
            set(camera_roles(features, FakeCalibration())), {"left", "right"}
        )


class CaptureRequestStateTests(unittest.TestCase):
    def test_new_request_clears_previous_capture_path_and_progress(self):
        args = SimpleNamespace(frames=5, output=Path("/tmp/diagnostic"), warmup=5)
        app = CaptureApp(args, FakeDevice())
        app.update(state="complete", saved_path="/previous/capture", completed_frames=5)
        app.request({"frames": 3, "output": "/tmp/diagnostic"})
        self.assertEqual(app.status()["state"], "queued")
        self.assertIsNone(app.status()["saved_path"])
        self.assertEqual(app.status()["completed_frames"], 0)

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
        self.assertEqual(
            self.app.requests.get_nowait(), (3, str(Path("/tmp/example").resolve()))
        )

    def test_request_rejects_bad_counts_and_empty_output(self):
        self.app.update(state="ready")
        for request in (
            {"frames": True},
            {"frames": 0},
            {"frames": 10001},
            {"frames": 2, "output": "  "},
        ):
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

        self.server = ControlServer(
            port=0,
            visualizer_port=8123,
            get_status=lambda: dict(self.status),
            request_capture=request_capture,
        ).start()
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
        headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(body)),
            "Host": host or f"{self.host}:{self.port}",
        }
        if origin is not None:
            headers["Origin"] = origin
        return self.request("POST", "/api/capture", body, headers)

    def test_status_page_and_visualizer_url_are_served(self):
        status, body = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), self.status)
        self.assertIn("visualizer_port=8123", self.server.url)
        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"DepthAI Visualizer", body)
        self.assertEqual(self.request("GET", "/missing")[0], 404)

    def test_valid_capture_request_is_queued_after_warmup(self):
        self.status["state"] = "ready"
        status, body = self.post(
            {"frames": 4, "output": " /tmp/run "}, origin=self.origin
        )

        self.assertEqual(status, 202)
        self.assertEqual(
            json.loads(body), {"accepted": True, "frames": 4, "output": "/tmp/run"}
        )
        self.assertEqual(self.calls, [(4, "/tmp/run")])
        self.assertEqual(self.status["state"], "queued")

    def test_warmup_and_active_capture_conflicts_return_409(self):
        for state in ("warming_up", "capturing"):
            self.status["state"] = state
            status, body = self.post(
                {"frames": 1, "output": "/tmp/run"}, origin=self.origin
            )
            self.assertEqual(status, 409)
            self.assertIn(b"warmup", body)

    def test_accepts_localhost_and_port_forwarded_origins(self):
        self.status["state"] = "ready"
        for authority in (f"localhost:{self.port}", "localhost:9000", "127.0.0.1:9000"):
            with self.subTest(authority=authority):
                status, _ = self.post(
                    {"frames": 1, "output": "/tmp/run"},
                    origin=f"http://{authority}",
                    host=authority,
                )
                self.assertEqual(status, 202)
                self.status["state"] = "ready"

    def test_rejects_cross_origin_and_missing_origin_posts(self):
        value = {"frames": 1, "output": "/tmp/run"}
        self.assertEqual(self.post(value, origin="http://attacker.invalid")[0], 403)
        self.assertEqual(self.post(value)[0], 403)
        self.assertEqual(
            self.post(value, origin=self.origin, host="attacker.invalid")[0], 403
        )
        # DNS rebinding: a foreign name resolving to loopback has matching Origin and Host.
        self.assertEqual(
            self.post(
                value,
                origin=f"http://attacker.invalid:{self.port}",
                host=f"attacker.invalid:{self.port}",
            )[0],
            403,
        )
        self.assertEqual(self.calls, [])

    def test_rejects_invalid_payload_and_content_type(self):
        for value in (
            {"frames": True, "output": "/tmp/run"},
            {"frames": 0, "output": "/tmp/run"},
            {"frames": 2, "output": " "},
            [],
        ):
            with self.subTest(value=value):
                self.assertEqual(self.post(value, origin=self.origin)[0], 400)
        self.assertEqual(
            self.post(
                {"frames": 1, "output": "/tmp/run"},
                origin=self.origin,
                content_type="text/plain",
            )[0],
            415,
        )

    def test_rejects_oversized_payload(self):
        body = b" " * 4097
        status, _ = self.request(
            "POST",
            "/api/capture",
            body,
            {
                "Host": f"{self.host}:{self.port}",
                "Origin": self.origin,
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            },
        )
        self.assertEqual(status, 413)

    def test_download_contains_only_completed_capture_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "sample"
            (folder / "rgb").mkdir(parents=True)
            payloads = {
                "rgb/frame.dai": b"native-frame-bytes",
                "calib.json": b"{}",
                "preview.jpg": b"jpeg",
            }
            for name, value in payloads.items():
                (folder / name).write_bytes(value)
            (folder / "unrelated.txt").write_text("not part of the capture")
            manifest = {
                "status": "complete",
                "preview": "preview.jpg",
                "frames": [{"streams": {"rgb": {"file": "rgb/frame.dai"}}}],
            }
            (folder / "metadata.json").write_text(json.dumps(manifest))
            self.status.update(state="complete", saved_path=str(folder))
            code, body = self.request("GET", "/api/download?capture=sample")
            self.assertEqual(code, 200)
            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(
                    set(archive.namelist()),
                    {f"sample/{n}" for n in (*payloads, "metadata.json")},
                )
                for name, value in payloads.items():
                    self.assertEqual(archive.read(f"sample/{name}"), value)
            self.assertEqual(self.request("GET", "/api/download?capture=old")[0], 409)
            manifest["frames"][0]["streams"]["rgb"]["file"] = "../outside.dai"
            (folder / "metadata.json").write_text(json.dumps(manifest))
            self.assertEqual(
                self.request("GET", "/api/download?capture=sample")[0], 409
            )
            self.status["state"] = "capturing"
            self.assertEqual(
                self.request("GET", "/api/download?capture=sample")[0], 404
            )

    def test_standalone_accepts_device_https_origin_but_not_foreign_origin(self):
        self.server.standalone = True
        self.status["state"] = "ready"
        value = {"frames": 1, "output": "/storage/captures"}
        authority = "10.11.0.33:9000"
        self.assertEqual(
            self.post(value, origin=f"https://{authority}", host=authority)[0], 202
        )
        self.assertEqual(
            self.post(value, origin="https://evil.example", host=authority)[0], 403
        )
        self.assertEqual(
            self.post(value, origin="https://evil.example", host="evil.example")[0], 403
        )


class StandaloneTests(unittest.TestCase):
    def test_host_and_standalone_storage_defaults(self):
        self.assertEqual(arguments([]).output, Path("captures"))
        with patch.dict(os.environ, {"OAKAGENT_STORAGE_APP": "/storage/app"}):
            args = arguments(["--standalone"])
            self.assertEqual(args.output, Path("/storage/app/captures"))
            app = CaptureApp(args, FakeDevice())
            self.assertEqual(app.status()["storage_location"], "device")
            app.update(state="ready")
            with self.assertRaisesRegex(ValueError, "must stay inside"):
                app.request({"frames": 1, "output": "/tmp/outside"})
            app.request({"frames": 1, "output": "/storage/app/captures/session"})
            self.assertEqual(
                app.requests.get_nowait(), (1, "/storage/app/captures/session")
            )

    def test_standalone_requires_runtime_storage_and_rejects_external_device(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "sys.stderr", new_callable=io.StringIO
        ):
            with self.assertRaises(SystemExit):
                arguments(["--standalone"])
        with patch.dict(os.environ, {"OAKAGENT_STORAGE_APP": "/storage/app"}), patch(
            "sys.stderr", new_callable=io.StringIO
        ):
            for options in (
                ["--device", "10.11.0.33"],
                ["--output", "/tmp/ephemeral"],
                ["--port", "9999"],
            ):
                with self.subTest(options=options), self.assertRaises(SystemExit):
                    arguments(["--standalone", *options])


if __name__ == "__main__":
    unittest.main()
