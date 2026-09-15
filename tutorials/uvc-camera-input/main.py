from __future__ import annotations

import os
import time
from pathlib import Path

import cv2
import depthai as dai
import numpy as np

from utils.arguments import initialize_argparser


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").strip()
    except OSError:
        return ""


def linux_usb_video_candidates() -> list[tuple[str, str]]:
    """Return Linux video nodes that are backed by a USB device."""
    sysfs_video = Path("/sys/class/video4linux")
    if not sysfs_video.exists():
        return []

    candidates: list[tuple[str, str]] = []
    for video_dir in sorted(sysfs_video.glob("video*"), key=lambda item: item.name):
        device_path = (video_dir / "device").resolve(strict=False).as_posix()
        if "/usb" not in device_path:
            continue

        node = f"/dev/{video_dir.name}"
        name = read_text(video_dir / "name") or "USB video device"
        candidates.append((node, name))

    return candidates


def capture_candidates(requested_device: str) -> list[tuple[str, str]]:
    if requested_device != "auto":
        return [(requested_device, requested_device)]

    candidates = linux_usb_video_candidates()
    if candidates:
        return candidates

    if os.name == "nt":
        return [("0", "OpenCV camera index 0")]

    return []


def as_opencv_source(device: str) -> int | str:
    return int(device) if device.isdecimal() else device


def decode_fourcc(value: float) -> str:
    code = int(value)
    if code == 0:
        return "unknown"
    return "".join(chr((code >> (8 * index)) & 0xFF) for index in range(4)).strip()


def open_capture(
    requested_device: str,
    width: int,
    height: int,
    fps: int,
    fourcc: str,
    buffer_size: int,
) -> tuple[cv2.VideoCapture, str, np.ndarray]:
    candidates = capture_candidates(requested_device)
    errors: list[str] = []

    for device, label in candidates:
        source = as_opencv_source(device)
        backend = (
            cv2.CAP_V4L2
            if isinstance(source, str) and source.startswith("/dev/")
            else cv2.CAP_ANY
        )
        cap = cv2.VideoCapture(source, backend)
        if not cap.isOpened():
            errors.append(f"{device} ({label}) did not open")
            cap.release()
            continue

        if buffer_size > 0:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, buffer_size)
        if fourcc:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)

        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            ok, frame = cap.read()
            if ok and frame is not None and frame.size:
                return cap, device, normalize_bgr(frame)
            time.sleep(0.05)

        errors.append(f"{device} ({label}) opened but produced no frames")
        cap.release()

    if not candidates:
        raise RuntimeError("no USB video devices were found")

    raise RuntimeError("; ".join(errors))


def normalize_bgr(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    if frame.shape[2] == 4:
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    return frame


class UvcCamera(dai.node.ThreadedHostNode):
    def __init__(self) -> None:
        super().__init__()
        self.out = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )
        self._device = "auto"
        self._width = 1920
        self._height = 1080
        self._fps = 5
        self._fourcc = ""
        self._buffer_size = 4
        self._max_frames = 0
        self._fps_log_interval = 5.0

    def build(
        self,
        device: str,
        width: int,
        height: int,
        fps: int,
        fourcc: str,
        buffer_size: int,
        max_frames: int,
        fps_log_interval: float,
    ) -> "UvcCamera":
        self._device = device
        self._width = width
        self._height = height
        self._fps = fps
        self._fourcc = fourcc
        self._buffer_size = buffer_size
        self._max_frames = max_frames
        self._fps_log_interval = fps_log_interval
        return self

    def run(self) -> None:
        try:
            cap, selected_device, first_frame = open_capture(
                self._device,
                self._width,
                self._height,
                self._fps,
                self._fourcc,
                self._buffer_size,
            )
        except RuntimeError as exc:
            print(f"Failed to open UVC camera: {exc}")
            self.stopPipeline()
            return

        print(f"Capturing UVC camera from {selected_device}")
        self._log_actual_format(cap, first_frame)

        frame_count = 0
        window_frames = 0
        run_start = time.monotonic()
        window_start = run_start
        failed_reads = 0
        pending_frame: np.ndarray | None = first_frame

        try:
            while self.isRunning():
                if pending_frame is None:
                    ok, frame = cap.read()
                    if not ok or frame is None or not frame.size:
                        failed_reads += 1
                        if failed_reads > 50:
                            print("UVC camera stopped producing frames.")
                            self.stopPipeline()
                            break
                        time.sleep(0.02)
                        continue
                    frame = normalize_bgr(frame)
                else:
                    frame = pending_frame
                    pending_frame = None

                failed_reads = 0
                self.out.send(self._make_img_frame(frame))
                frame_count += 1
                window_frames += 1

                now = time.monotonic()
                window_elapsed = now - window_start
                if (
                    self._fps_log_interval > 0
                    and window_elapsed >= self._fps_log_interval
                ):
                    print(
                        f"UVC delivered FPS: {window_frames / window_elapsed:.2f} "
                        f"over {window_elapsed:.1f}s"
                    )
                    window_start = now
                    window_frames = 0

                if self._max_frames and frame_count >= self._max_frames:
                    elapsed = time.monotonic() - run_start
                    measured_fps = frame_count / elapsed if elapsed > 0 else 0.0
                    print(
                        f"Sent {frame_count} UVC frames in {elapsed:.2f}s "
                        f"({measured_fps:.2f} FPS); stopping."
                    )
                    self.stopPipeline()
                    break
        finally:
            cap.release()

    def _log_actual_format(self, cap: cv2.VideoCapture, frame: np.ndarray) -> None:
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or frame.shape[1]
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or frame.shape[0]
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        actual_fourcc = decode_fourcc(cap.get(cv2.CAP_PROP_FOURCC))
        requested_fourcc = self._fourcc or "default"
        print(
            "UVC format: "
            f"requested={self._width}x{self._height}@{self._fps}, "
            f"actual={actual_width}x{actual_height}@{actual_fps:.2f}, "
            f"fourcc={requested_fourcc}->{actual_fourcc}, "
            f"buffers={self._buffer_size}, "
            f"frame={frame.shape[1]}x{frame.shape[0]}"
        )

    def _make_img_frame(self, frame: np.ndarray) -> dai.ImgFrame:
        frame = np.ascontiguousarray(frame)
        img_frame = dai.ImgFrame()
        img_frame.setCvFrame(frame, dai.ImgFrame.Type.BGR888i)
        return img_frame


def configure_manip(
    pipeline: dai.Pipeline,
    source: dai.Node.Output,
    width: int,
    height: int,
) -> dai.Node.Output:
    manip = pipeline.create(dai.node.ImageManip)
    manip.inputImage.setBlocking(False)
    manip.setMaxOutputFrameSize(width * height * 3)
    manip.initialConfig.setOutputSize(width, height)
    manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888i)
    source.link(manip.inputImage)
    return manip.out


def main() -> None:
    _, args = initialize_argparser()

    output_width = args.output_width or args.width
    output_height = args.output_height or args.height

    visualizer = dai.RemoteConnection(httpPort=args.http_port)
    device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
    print("Device Information:", device.getDeviceInfo())

    with dai.Pipeline(device) as pipeline:
        print("Creating pipeline...")

        uvc = pipeline.create(UvcCamera).build(
            device=args.uvc_device,
            width=args.width,
            height=args.height,
            fps=args.fps,
            fourcc=args.fourcc,
            buffer_size=args.buffer_size,
            max_frames=args.max_frames,
            fps_log_interval=args.fps_log_interval,
        )
        processed = configure_manip(pipeline, uvc.out, output_width, output_height)

        visualizer.addTopic("UVC camera", processed, "images")

        print("Pipeline created.")
        pipeline.start()
        visualizer.registerPipeline(pipeline)

        while pipeline.isRunning():
            key = visualizer.waitKey(1)
            if key == ord("q"):
                print("Got q key from the remote connection!")
                break


if __name__ == "__main__":
    main()
