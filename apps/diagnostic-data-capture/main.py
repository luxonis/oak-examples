#!/usr/bin/env python3
"""Capture native DepthAI messages on the host, with optional RVC4 cameras."""

import argparse
from datetime import datetime, timedelta
import json
import hashlib
import math
import os
from pathlib import Path
import queue
import re
import signal
import sys
import tempfile
import threading
import time

os.environ.setdefault("DEPTHAI_TELEMETRY", "0")
os.environ.setdefault("DEPTHAI_AUTOCALIBRATION", "OFF")
import depthai as dai
from control import ControlServer
from preview import write_capture_preview


def create_visualizer(http_port, websocket_port):
    """Hide the SDK's generic URL banner; the app prints its own GUI URL.

    RemoteConnection writes through C++ stdout, so Python redirect_stdout is
    insufficient. Capture only construction, before starting the pipeline, and
    replay everything except the known banner lines. stderr remains untouched.
    """
    banner_prefixes = (
        b"To connect to the OAK visualizer use the following:",
        b"If you are opening the visualizer locally, ",
        b"If you are using peripheral mode and viewing from another machine, ",
        b"If you are using oakapp base image, ",
    )
    sys.stdout.flush()
    with tempfile.TemporaryFile() as captured:
        original_stdout = os.dup(1)
        try:
            os.dup2(captured.fileno(), 1)
            return dai.RemoteConnection(
                httpPort=http_port, webSocketPort=websocket_port
            )
        finally:
            os.dup2(original_stdout, 1)
            os.close(original_stdout)
            captured.seek(0)
            for line in captured:
                if not line.startswith(banner_prefixes):
                    sys.stdout.write(line.decode("utf-8", errors="replace"))
            sys.stdout.flush()


def preview_frame(frame):
    """Adapt GRAY8 for the bundled Visualizer without mutating saved messages."""
    if frame.getType() != dai.ImgFrame.Type.GRAY8:
        return frame
    # GRAY8 and RAW8 both carry one byte per pixel. The bundled viewer accepts
    # RAW8 (mono8), but rejects the GRAY8 enum used by Camera.requestOutput.
    preview = dai.ImgFrame()
    preview.setBufferMetadataFrom(frame)
    preview.setWidth(frame.getWidth())
    preview.setHeight(frame.getHeight())
    preview.setType(dai.ImgFrame.Type.RAW8)
    preview.setData(frame.getData())
    return preview


def positive_int(value):
    n = int(value)
    if n < 1 or n > 10000:
        raise ValueError("Frame count must be between 1 and 10000")
    return n


def positive_float(value):
    n = float(value)
    if not math.isfinite(n) or n <= 0:
        raise argparse.ArgumentTypeError("Must be a finite number greater than zero")
    return n


def image_width(value):
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not a whole number of pixels"
        ) from None
    if n < 2:
        raise argparse.ArgumentTypeError(f"{n} px is too narrow; use at least 2 pixels")
    return n


def arguments(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--device",
        help="Device IP or ID; required when discovery finds multiple devices",
    )
    p.add_argument(
        "--expected-id", help="Refuse a different device at the supplied address"
    )
    p.add_argument(
        "--standalone",
        action="store_true",
        help="Run inside an OAK App with persistent device storage",
    )
    p.add_argument("--output", type=Path)
    p.add_argument("--frames", type=positive_int, default=5)
    p.add_argument(
        "--warmup",
        type=positive_float,
        default=5.0,
        help="Minimum live-stream warmup in seconds",
    )
    p.add_argument("--fps", type=positive_float, default=10.0)
    p.add_argument(
        "--width",
        type=image_width,
        default=1280,
        help="Maximum image width in pixels; capped at each sensor width, rounded down to even, "
        "preserves sensor aspect ratio",
    )
    p.add_argument("--port", type=int, default=8083, help="Capture control page port")
    p.add_argument("--visualizer-port", type=int, default=8082)
    p.add_argument("--websocket-port", type=int, default=8765)
    p.add_argument("--capture-timeout", type=positive_float, default=60.0)
    p.add_argument(
        "--auto-capture",
        action="store_true",
        help="Capture once after warmup and exit (for batch testing)",
    )
    p.add_argument(
        "--no-gui",
        action="store_true",
        help="Use with --auto-capture for unattended capture",
    )
    a = p.parse_args(argv)
    a.storage_root = None
    if a.standalone:
        storage = os.environ.get("OAKAGENT_STORAGE_APP")
        if not storage:
            p.error("--standalone requires OAKAGENT_STORAGE_APP from oak-agent")
        if a.device:
            p.error("--device is for host mode; standalone uses the local device")
        if (a.port, a.visualizer_port, a.websocket_port) != (8083, 8082, 8765):
            p.error("Standalone uses ports 8083, 8082 and 8765 behind the app proxy")
        a.storage_root = Path(storage).resolve() / "captures"
    a.output = a.output or a.storage_root or Path("captures")
    if a.storage_root and not a.output.resolve().is_relative_to(a.storage_root):
        p.error(
            "Standalone output must be inside the app's persistent captures directory"
        )
    if a.no_gui and not a.auto_capture:
        p.error("--no-gui requires --auto-capture")
    if len({a.port, a.visualizer_port, a.websocket_port}) != 3 or any(
        not 1024 <= x <= 65535 for x in (a.port, a.visualizer_port, a.websocket_port)
    ):
        p.error("Use three distinct ports between 1024 and 65535")
    return a


def write_json(path, data):
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def camera_roles(features, calibration):
    """Prefer calibrated stereo roles, then the standard socket/name convention."""
    roles = {}
    left, right = (
        calibration.getStereoLeftCameraId(),
        calibration.getStereoRightCameraId(),
    )
    for f in features:
        if dai.CameraSensorType.TOF in f.supportedTypes:
            role = "tof"
        elif f.socket == left or f.name.lower() == "left":
            role = "left"
        elif f.socket == right or f.name.lower() == "right":
            role = "right"
        elif f.socket == dai.CameraBoardSocket.CAM_B:
            role = "left"
        elif f.socket == dai.CameraBoardSocket.CAM_C:
            role = "right"
        elif dai.CameraSensorType.COLOR in f.supportedTypes:
            role = "rgb"
        else:
            role = f.socket.name.lower()
        if role in roles:
            role += "_" + f.socket.name.lower()
        roles[role] = f
    return roles


class CaptureApp:
    def __init__(self, args, device):
        self.args, self.device = args, device
        self.calibration = device.readCalibration()
        self.features = device.getConnectedCameraFeatures()
        self.roles = camera_roles(self.features, self.calibration)
        self.requests = queue.Queue(maxsize=1)
        self.lock = threading.Lock()
        self.state = dict(
            state="starting",
            frames=args.frames,
            output=str(args.output.resolve()),
            saved_path=None,
            completed_frames=0,
            warmup_remaining=args.warmup,
            device=dict(
                id=device.getDeviceId(),
                name=device.getDeviceName(),
                os=device.getOSVersion(),
                sdk=dai.__version__,
            ),
            streams=[],
            storage_location="device" if getattr(args, "standalone", False) else "host",
        )
        self.active = None
        self.manifest = None
        self.ready_at = None
        self.started = time.monotonic()

    def status(self):
        with self.lock:
            return dict(self.state)

    def update(self, **kwargs):
        with self.lock:
            self.state.update(kwargs)

    def request(self, request):
        value = request.get("frames", self.args.frames)
        if isinstance(value, bool) or str(value) != str(int(value)):
            raise ValueError("Frame count must be an integer")
        frames = positive_int(value)
        output = request.get("output", str(self.args.output))
        if not isinstance(output, str) or not output.strip() or "\x00" in output:
            raise ValueError("Output must be a nonempty directory path")
        output = str(Path(output).expanduser().resolve())
        storage_root = getattr(self.args, "storage_root", None)
        if storage_root and not Path(output).is_relative_to(storage_root):
            raise ValueError(f"Device captures must stay inside {storage_root}")
        with self.lock:
            if self.state["state"] not in ("ready", "complete", "error"):
                raise RuntimeError("Wait for warmup or the current capture to finish")
            self.requests.put_nowait((frames, output))
            self.state.update(
                state="queued",
                frames=frames,
                output=output,
                error=None,
                saved_path=None,
                completed_frames=0,
            )
        return {"accepted": True, "frames": frames, "output": output}

    def start_capture(self, frames, output):
        stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S_%f%z")
        name = re.sub(r"[^a-zA-Z0-9_-]", "_", self.device.getDeviceName())
        folder = Path(output) / f"{name}_{self.device.getDeviceId()}_{stamp}"
        folder.mkdir(parents=True, exist_ok=False)
        self.active = folder
        self.update(saved_path=str(folder), completed_frames=0)
        self.manifest = None
        self.capture_start = time.monotonic()
        self.manifest = dict(
            schema_version=1,
            status="capturing",
            date=datetime.now().astimezone().isoformat(),
            model_name=self.device.getDeviceName(),
            mxId=self.device.getDeviceId(),
            platform=self.device.getPlatform().name,
            os_version=self.device.getOSVersion(),
            dai_version=dai.__version__,
            settings=dict(
                fps=self.args.fps,
                max_width=self.args.width,
                frames=frames,
                warmup_seconds=self.args.warmup,
                synchronization="DepthAI Sync node on host, device timestamps",
                sync_tolerance_ms=self.sync_threshold * 1000,
                camera_undistortion=False,
                tof_grid="standard ToF optical grid (SDK default distortion correction)",
                tof_profile="MID_RANGE",
            ),
            source_sha256={
                name: hashlib.sha256(
                    Path(__file__).with_name(name).read_bytes()
                ).hexdigest()
                for name in ("main.py", "control.py", "index.html", "preview.py")
            },
            streams=self.streams,
            cameras=[
                dict(
                    socket=f.socket.name,
                    sensor=f.sensorName,
                    name=f.name,
                    width=f.width,
                    height=f.height,
                    types=[x.name for x in f.supportedTypes],
                )
                for f in self.features
            ],
            requested_frames=frames,
            frames=[],
            capture_seconds=None,
        )
        write_json(folder / "metadata.json", self.manifest)
        self.calibration.eepromToJsonFile(str(folder / "calib.json"))
        for stream in self.streams:
            (folder / stream).mkdir()
        # Consume only frames whose device-synchronized host timestamp is newer than the trigger.
        self.trigger_timestamp = dai.Clock.now().total_seconds()
        self.update(state="capturing", completed_frames=0, saved_path=str(folder))

    def save_group(self, group):
        times = [f.getTimestampDevice().total_seconds() for f in group.values()]
        # Shared decimal microsecond key keeps existing capture/replay pairing compatible.
        key = str(round(min(times) * 1000000))
        record = dict(
            timestamp=key, skew_ms=(max(times) - min(times)) * 1000, streams={}
        )
        for name, msg in group.items():
            stem = self.active / name / f"{name}_{key}"
            msg.save(str(stem))
            path = stem.with_suffix(".dai")
            if not path.is_file() or path.stat().st_size == 0:
                raise IOError(f"DepthAI did not save {path}")
            record["streams"][name] = dict(
                file=str(path.relative_to(self.active)),
                width=msg.getWidth(),
                height=msg.getHeight(),
                type=msg.getType().name,
                sequence=msg.getSequenceNum(),
                timestamp_device_seconds=msg.getTimestampDevice().total_seconds(),
                exposure_us=round(msg.getExposureTime().total_seconds() * 1000000),
                sensitivity_iso=msg.getSensitivity(),
                bytes=path.stat().st_size,
            )
        self.manifest["frames"].append(record)
        write_json(self.active / "metadata.json", self.manifest)
        self.update(completed_frames=len(self.manifest["frames"]))
        if len(self.manifest["frames"]) == self.manifest["requested_frames"]:
            self.finish("complete")

    def finish(self, status, error=None):
        if self.active and self.manifest:
            if status == "complete":
                try:
                    self.manifest["preview"] = write_capture_preview(
                        self.active, self.manifest
                    )
                except Exception as exc:
                    self.manifest["preview_error"] = str(exc)
                    error = f"Capture saved, but preview could not be generated: {exc}"
            self.manifest.update(
                status=status,
                capture_seconds=time.monotonic() - self.capture_start,
                finished=datetime.now().astimezone().isoformat(),
            )
            if error:
                self.manifest["error"] = error
            write_json(self.active / "metadata.json", self.manifest)
        print(
            json.dumps(dict(event=status, path=str(self.active), error=error)),
            flush=True,
        )
        self.active = None
        self.update(state=status, error=error)

    def run(self):
        a = self.args
        visualizer = (
            None if a.no_gui else create_visualizer(a.visualizer_port, a.websocket_port)
        )
        server = None
        with dai.Pipeline(self.device) as pipeline:
            outputs, self.streams = {}, {}
            for role, f in self.roles.items():
                if dai.CameraSensorType.TOF in f.supportedTypes:
                    tof = pipeline.create(dai.node.ToF).build(
                        f.socket, dai.ToFConfig.Profile.MID_RANGE, a.fps
                    )
                    for suffix, out in [
                        ("depth", tof.depth),
                        ("confidence", tof.confidence),
                    ]:
                        name = f"{role}_{suffix}"
                        outputs[name] = out
                        self.streams[name] = dict(
                            socket=f.socket.name, kind=name, geometry="native ToF"
                        )
                else:
                    cam = pipeline.create(dai.node.Camera).build(f.socket)
                    width = min(a.width, f.width)
                    width -= width % 2
                    height = max(2, round(width * f.height / f.width) // 2 * 2)
                    typ = (
                        dai.ImgFrame.Type.GRAY8
                        if role in ("left", "right")
                        or dai.CameraSensorType.COLOR not in f.supportedTypes
                        else dai.ImgFrame.Type.NV12
                    )
                    outputs[role] = cam.requestOutput(
                        (width, height),
                        typ,
                        dai.ImgResizeMode.STRETCH,
                        a.fps,
                        enableUndistortion=False,
                    )
                    self.streams[role] = dict(
                        socket=f.socket.name,
                        kind="camera",
                        resolution=[width, height],
                        geometry="unrectified full FOV",
                    )
            if not outputs:
                raise RuntimeError("No supported cameras connected")
            queues = {
                name: out.createOutputQueue(maxSize=8, blocking=False)
                for name, out in outputs.items()
            }
            # Only complete sets within half a frame interval leave the Sync node.
            self.sync_threshold = 0.5 / a.fps
            sync = pipeline.create(dai.node.Sync)
            sync.setRunOnHost(True)
            sync.setTimestampSource(dai.node.Sync.TimestampSource.DEVICE)
            sync.setSyncThreshold(timedelta(seconds=self.sync_threshold))
            for name, out in outputs.items():
                out.link(sync.inputs[name])
                sync.inputs[name].setBlocking(False)
            sync_queue = sync.out.createOutputQueue(maxSize=8, blocking=False)
            preview_queues = {}
            self.update(streams=list(outputs), state="warming_up")
            pipeline.start()
            print("Pipeline started.", flush=True)
            first_seen = {}
            last_seen = {}
            auto_requested = False
            try:
                if visualizer:
                    visualizer.registerPipeline(pipeline)
                    for name in outputs:
                        preview_queues[name] = visualizer.addTopic(
                            name, "Capture streams", maxSize=2, blocking=False
                        )
                    server = ControlServer(
                        "127.0.0.1",
                        a.port,
                        a.visualizer_port,
                        self.status,
                        lambda frames, output: self.request(
                            dict(frames=frames, output=output)
                        ),
                        standalone=a.standalone,
                    )
                    server.start()
                    if a.standalone:
                        print(
                            "Capture GUI: open the app frontend URL shown by oakctl.",
                            flush=True,
                        )
                    else:
                        print(f"Capture GUI: {server.url}", flush=True)
                while pipeline.isRunning():
                    now = time.monotonic()
                    for name, q in queues.items():
                        messages = q.tryGetAll()
                        if messages and name in preview_queues:
                            preview_queues[name].send(preview_frame(messages[-1]))
                        if messages:
                            first_seen.setdefault(name, now)
                            last_seen[name] = now
                    groups = sync_queue.tryGetAll()
                    if self.ready_at is None and len(first_seen) == len(outputs):
                        self.ready_at = max(first_seen.values()) + a.warmup
                    if (
                        self.ready_at is not None
                        and self.status()["state"] == "warming_up"
                    ):
                        remaining = max(0, self.ready_at - now)
                        self.update(warmup_remaining=round(remaining, 1))
                        if remaining == 0:
                            self.update(state="ready")
                    if (
                        now - self.started > a.capture_timeout + a.warmup
                        and self.ready_at is None
                    ):
                        raise TimeoutError("Not all detected streams produced frames")
                    # Streams that never started are reported by the check above.
                    if any(
                        now - seen > a.capture_timeout for seen in last_seen.values()
                    ):
                        raise TimeoutError("A detected camera stopped producing frames")
                    if (
                        a.auto_capture
                        and not auto_requested
                        and self.status()["state"] == "ready"
                    ):
                        self.request(dict(frames=a.frames, output=str(a.output)))
                        auto_requested = True
                    try:
                        request = self.requests.get_nowait()
                    except queue.Empty:
                        request = None
                    if request:
                        try:
                            self.start_capture(*request)
                        except Exception as exc:
                            self.finish("error", str(exc))
                    if self.active:
                        try:
                            for group in groups:
                                frames = {name: group[name] for name in outputs}
                                if all(
                                    f.getTimestamp().total_seconds()
                                    > self.trigger_timestamp
                                    for f in frames.values()
                                ):
                                    self.save_group(frames)
                                if not self.active:
                                    break
                            if (
                                self.active
                                and now - self.capture_start > a.capture_timeout
                            ):
                                raise TimeoutError(
                                    "Timed out waiting for synchronized frames"
                                )
                        except Exception as exc:
                            self.finish("error", str(exc))
                    if (
                        a.auto_capture
                        and auto_requested
                        and self.status()["state"] in ("complete", "error")
                    ):
                        if self.status()["state"] == "error":
                            raise RuntimeError(self.status()["error"])
                        return
                    if visualizer and visualizer.waitKey(1) == ord("q"):
                        return
                    time.sleep(0.005)
                raise RuntimeError("Pipeline stopped unexpectedly")
            finally:
                if self.active:
                    self.finish(
                        "incomplete", "Application stopped before capture completed"
                    )
                if server:
                    server.close()
                if visualizer:
                    for name in preview_queues:
                        visualizer.removeTopic(name)


def main():
    args = arguments()
    if args.standalone:
        info = None
    elif args.device:
        info = dai.DeviceInfo(args.device)
    else:
        devices = dai.Device.getAllAvailableDevices()
        if len(devices) != 1:
            raise RuntimeError(
                f"Found {len(devices)} devices. Select one explicitly with --device."
            )
        info = devices[0]
    with dai.Device() if info is None else dai.Device(info) as device:
        if device.getPlatform() != dai.Platform.RVC4:
            raise RuntimeError("This example requires an RVC4 device")
        if args.expected_id and device.getDeviceId() != args.expected_id:
            raise RuntimeError("Device identity does not match --expected-id")
        CaptureApp(args, device).run()


def stop_on_signal(_signum, _frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    # oak-agent forwards SIGTERM when stopping the container. Reuse the normal
    # cleanup path so partial captures are marked and the device is released.
    signal.signal(signal.SIGTERM, stop_on_signal)
    try:
        main()
    except KeyboardInterrupt:
        print("Stopped.", flush=True)
