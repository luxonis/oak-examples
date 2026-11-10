#!/usr/bin/env python3
"""Record every detected OAK camera to timestamped, persistent H.264 video."""

import argparse
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import math
import os
import re
from pathlib import Path
import shutil
import signal
import time

import av
import depthai as dai

from utils.image_quality import BrightnessReference, RawImageProcessor


MAX_WIDTH = 1920
MAX_HEIGHT = 1080
MAX_ISP_STREAMS_RVC4 = 3
SYNC_INTERVAL_SECONDS = 5
REPORT_INTERVAL_SECONDS = 10
GIB = 1024**3
RESUME_HEADROOM_BYTES = 512 * 1024**2
VALID_CLOCK_AFTER = datetime(2024, 1, 1, tzinfo=timezone.utc)
SESSION_STAMP = re.compile(
    r"^(\d{8}T\d{6}\.\d{6}Z)(?:_offline)?_cam[a-z]+\.(?:mkv|h264)$"
)


def recording_name(started_at, socket, offline=False):
    stamp = started_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    marker = "_offline" if offline else ""
    return f"{stamp}{marker}_{socket.name.lower().replace('_', '')}.mkv"


def recording_start(output_dir, now=None):
    """Use the last saved time if an offline boot resets the clock to 1970."""
    now = now or datetime.now(timezone.utc)
    latest = None
    for entry in os.scandir(output_dir):
        if not entry.is_file():
            continue
        match = SESSION_STAMP.fullmatch(entry.name)
        if not match:
            continue
        recorded_at = datetime.strptime(match.group(1), "%Y%m%dT%H%M%S.%fZ").replace(
            tzinfo=timezone.utc
        )
        latest = max(latest, recorded_at) if latest else recorded_at
        modified_at = datetime.fromtimestamp(entry.stat().st_mtime, timezone.utc)
        if modified_at >= VALID_CLOCK_AFTER:
            latest = max(latest, modified_at)
    if now >= VALID_CLOCK_AFTER and (latest is None or now > latest):
        return now, False
    estimated = max(now, latest or now) + timedelta(seconds=1)
    print(
        f"System clock is unset or behind existing recordings; "
        f"using estimated session time {estimated.isoformat()} "
        "and marking files offline",
        flush=True,
    )
    return estimated, True


def output_size(feature):
    if feature.width <= MAX_WIDTH and feature.height <= MAX_HEIGHT:
        return feature.width, feature.height
    return MAX_WIDTH, MAX_HEIGHT


class H264Writer:
    """Store encoded packets with their camera timestamps, without re-encoding."""

    def __init__(self, path, size, fps):
        self.file = path.open("xb", buffering=0)
        try:
            self.container = av.open(self.file, mode="w", format="matroska")
            self.stream = self.container.add_stream("h264", rate=fps)
            self.packet_time_base = Fraction(1, 1_000_000)
            self.stream.time_base = self.packet_time_base
            self.stream.width, self.stream.height = size
            self.start_time = None
        except BaseException:
            self.file.close()
            raise

    def write(self, encoded_frame):
        data = encoded_frame.getData()
        if self.start_time is None:
            self.start_time = encoded_frame.getTimestamp()
        elapsed = encoded_frame.getTimestamp() - self.start_time
        timestamp_us = round(elapsed.total_seconds() * 1_000_000)
        packet = av.Packet(data)
        packet.pts = packet.dts = timestamp_us
        packet.time_base = self.packet_time_base
        packet.stream = self.stream
        self.container.mux(packet)
        return len(data)

    def sync(self):
        os.fsync(self.file.fileno())

    def close(self):
        try:
            self.container.close()
            os.fsync(self.file.fileno())
        finally:
            self.file.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", help="Device ID or IP; omitted inside an OAK App")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.environ.get("OAKAGENT_STORAGE_SHARED", ".")) / "recordings",
        help="Recording directory (defaults to persistent OAK App shared storage)",
    )
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument(
        "--raw-auto-exposure",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Calibrate raw-only exposure at startup, then lock it (default: on)",
    )
    parser.add_argument(
        "--raw-exposure-settle-seconds",
        type=float,
        default=10.0,
        help="Seconds to calibrate raw exposure before locking it (default: 10)",
    )
    parser.add_argument(
        "--raw-exposure-us",
        type=int,
        default=10000,
        help="Initial raw exposure; fixed when --no-raw-auto-exposure is used",
    )
    parser.add_argument(
        "--raw-iso",
        type=int,
        default=400,
        help="Requested sensitivity for RVC4 raw-only camera paths",
    )
    parser.add_argument(
        "--raw-gamma",
        type=float,
        default=2.2,
        help="Raw tone-curve gamma (default: 2.2)",
    )
    parser.add_argument(
        "--raw-black-level",
        type=int,
        default=64,
        help="Raw sensor black level in 10-bit units (default: 64 for OV9282)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=float(os.environ["OAK_RECORD_DURATION"])
        if "OAK_RECORD_DURATION" in os.environ
        else None,
        help="Stop after this many seconds (for testing)",
    )
    parser.add_argument(
        "--max-recording-gb",
        type=float,
        default=float(os.environ.get("OAK_MAX_RECORDING_GB", "50")),
        help="Maximum storage used by this app's recordings",
    )
    parser.add_argument(
        "--min-free-gb",
        type=float,
        default=float(os.environ.get("OAK_MIN_FREE_GB", "5")),
        help="Free device storage to reserve",
    )
    args = parser.parse_args()
    if (
        args.fps <= 0
        or (args.duration is not None and args.duration <= 0)
        or args.max_recording_gb <= 0
        or args.min_free_gb < 0
        or not 1 <= args.raw_exposure_us <= 33000
        or not 100 <= args.raw_iso <= 1600
        or not math.isfinite(args.raw_exposure_settle_seconds)
        or args.raw_exposure_settle_seconds <= 0
        or not 0.1 <= args.raw_gamma <= 5
        or not 0 <= args.raw_black_level < 1023
    ):
        parser.error(
            "Invalid frame rate, duration, storage limit or raw image settings"
        )

    stop = False

    def request_stop(_signum, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    quota = int(args.max_recording_gb * GIB)
    reserve = int(args.min_free_gb * GIB)

    def storage_used():
        return sum(
            entry.stat().st_size
            for entry in os.scandir(args.output_dir)
            if entry.is_file()
        )

    while not stop:
        previous_bytes = storage_used()
        free_bytes = shutil.disk_usage(args.output_dir).free
        if previous_bytes < quota and free_bytes > reserve + RESUME_HEADROOM_BYTES:
            break
        print(
            f"Waiting for recording space: {previous_bytes / GIB:.1f} GiB used, "
            f"{free_bytes / GIB:.1f} GiB free",
            flush=True,
        )
        for _ in range(60):
            if stop:
                return
            time.sleep(0.5)
    if stop:
        return

    device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
    with dai.Pipeline(device) as pipeline:
        features = sorted(
            device.getConnectedCameraFeatures(), key=lambda cam: cam.socket.name
        )
        if not features:
            raise RuntimeError("No cameras detected")

        encoded_queues = {}
        raw_queues = {}
        raw_encoder_inputs = {}
        raw_controls = {}
        raw_processors = {}
        reference_queues = {}
        brightness = BrightnessReference()
        encoded_sizes = {}
        isp_limit = (
            MAX_ISP_STREAMS_RVC4
            if device.getPlatform() == dai.Platform.RVC4
            else len(features)
        )
        has_raw_cameras = len(features) > isp_limit
        for index, feature in enumerate(features):
            socket = feature.socket
            uses_isp = index < isp_limit
            size = output_size(feature) if uses_isp else (feature.width, feature.height)
            encoded_sizes[socket] = size
            print(
                f"Configuring {socket.name}: {feature.sensorName} {size[0]}x{size[1]} "
                f"at {args.fps} FPS (H.264)",
                flush=True,
            )
            camera = pipeline.create(dai.node.Camera)
            camera.setSensorType(feature.supportedTypes[0])
            if not uses_isp:
                if dai.CameraSensorType.MONO not in feature.supportedTypes:
                    raise RuntimeError(
                        f"Raw image processing requires a monochrome sensor: {socket.name}"
                    )
                camera.setSensorType(dai.CameraSensorType.MONO)
                processor = RawImageProcessor(
                    args.fps,
                    args.raw_exposure_us,
                    args.raw_iso,
                    auto_exposure=args.raw_auto_exposure,
                    gamma=args.raw_gamma,
                    black_level=args.raw_black_level,
                    settle_seconds=args.raw_exposure_settle_seconds,
                )
                raw_processors[socket] = processor
                camera.initialControl.setManualExposure(
                    processor.exposure_us, args.raw_iso
                )
            camera.build(socket, sensorFps=args.fps)
            encoder = pipeline.create(dai.node.VideoEncoder)
            encoder.setDefaultProfilePreset(
                args.fps, dai.VideoEncoderProperties.Profile.H264_MAIN
            )
            if uses_isp:
                camera.requestOutput(size, dai.ImgFrame.Type.NV12, fps=args.fps).link(
                    encoder.input
                )
                if has_raw_cameras and args.raw_auto_exposure:
                    # Small, non-blocking previews supply brightness statistics
                    # without moving full ISP recording frames through Python.
                    preview = camera.requestOutput(
                        (320, 200), dai.ImgFrame.Type.NV12, fps=min(2, args.fps)
                    )
                    reference_queues[socket] = preview.createOutputQueue(
                        maxSize=1, blocking=False
                    )
            else:
                raw_queues[socket] = camera.raw.createOutputQueue(
                    maxSize=16, blocking=True
                )
                raw_encoder_inputs[socket] = encoder.input.createInputQueue()
                raw_controls[socket] = camera.inputControl.createInputQueue(
                    maxSize=1, blocking=False
                )
            encoded_queues[socket] = encoder.out.createOutputQueue(
                maxSize=64, blocking=True
            )

        files = {}
        encoded_counts = {socket: 0 for socket in encoded_queues}
        raw_counts = {socket: 0 for socket in raw_queues}
        bytes_written = {socket: 0 for socket in encoded_queues}
        try:
            pipeline.start()
            print("Pipeline started.", flush=True)
            started_at, offline = recording_start(args.output_dir)
            started_monotonic = time.monotonic()
            for socket in encoded_queues:
                path = args.output_dir / recording_name(started_at, socket, offline)
                files[socket] = H264Writer(path, encoded_sizes[socket], args.fps)
                print(f"Recording {socket.name} -> {path}", flush=True)

            next_sync = time.monotonic() + SYNC_INTERVAL_SECONDS
            next_report = time.monotonic() + REPORT_INTERVAL_SECONDS
            while pipeline.isRunning() and not stop:
                if (
                    args.duration
                    and time.monotonic() - started_monotonic >= args.duration
                ):
                    break
                received = False
                # Drain encoded data before feeding more raw frames to avoid
                # backing up the encoder when the disk is temporarily slow.
                for socket, queue in encoded_queues.items():
                    frame = queue.tryGet()
                    if frame is None:
                        continue
                    bytes_written[socket] += files[socket].write(frame)
                    encoded_counts[socket] += 1
                    received = True
                new_reference = False
                calibrating_raw = any(
                    not processor.locked for processor in raw_processors.values()
                )
                now = time.monotonic()
                for socket, queue in reference_queues.items():
                    preview = queue.tryGet()
                    if (
                        preview is not None
                        and calibrating_raw
                        and now - started_monotonic >= 1
                    ):
                        brightness.observe(socket, preview, now)
                        new_reference = True
                if new_reference:
                    brightness.update(now)
                for socket, queue in raw_queues.items():
                    raw = queue.tryGet()
                    if raw is None:
                        continue
                    processor = raw_processors[socket]
                    was_locked = processor.locked
                    corrected, control = processor.convert(raw, brightness.target)
                    if processor.locked and not was_locked:
                        print(
                            f"Lighting locked for {socket.name}: {processor.exposure_us} us, "
                            f"gain {processor.digital_gain:.2f}x until recorder restart",
                            flush=True,
                        )
                    raw_encoder_inputs[socket].send(corrected)
                    if control is not None:
                        raw_controls[socket].send(control)
                    raw_counts[socket] += 1
                    received = True

                now = time.monotonic()
                if now >= next_sync:
                    for file in files.values():
                        file.sync()
                    if (
                        previous_bytes + sum(bytes_written.values()) >= quota
                        or shutil.disk_usage(args.output_dir).free <= reserve
                    ):
                        print(
                            "Storage limit reached; preserving existing recordings",
                            flush=True,
                        )
                        break
                    next_sync = now + SYNC_INTERVAL_SECONDS
                if now >= next_report:
                    print(
                        "Recorded "
                        + ", ".join(
                            f"{socket.name}: {encoded_counts[socket]} frames, "
                            f"{bytes_written[socket] / 1048576:.1f} MiB"
                            for socket in encoded_queues
                        ),
                        flush=True,
                    )
                    if raw_processors:
                        print(
                            f"Raw lighting (target luma {brightness.target:.0f}): "
                            + ", ".join(
                                f"{socket.name}: luma {processor.luma:.0f}, "
                                f"{processor.exposure_us} us, gain {processor.digital_gain:.2f}x "
                                f"({'locked' if processor.locked else 'calibrating'})"
                                for socket, processor in raw_processors.items()
                            ),
                            flush=True,
                        )
                    next_report = now + REPORT_INTERVAL_SECONDS
                if not received:
                    time.sleep(0.002)
        finally:
            for file in files.values():
                file.close()
            print("Recording stopped; files closed", flush=True)


if __name__ == "__main__":
    main()
