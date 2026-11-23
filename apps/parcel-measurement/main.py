import argparse
import base64
from collections import OrderedDict, deque
from dataclasses import dataclass
from datetime import timedelta
import json
from pathlib import Path
import queue
import signal
import time

import cv2
import depthai as dai
import numpy as np

from depthai_nodes.message import (
    ParcelDetectorConfig,
    ParcelMeasurements,
    SupportPlaneCalibrationControl,
)
from depthai_nodes.node import (
    ParcelDetector,
    ParcelDimensioner,
    PlaneCalibrationConfig,
    SupportPlaneCalibrator,
)

from domain import CalibrationPhase, CalibrationSession, ParcelTracker
from geometry import CameraProjection, reference_key, transformed_imu
from web import BrowserServer


RGB_SIZE = (2000, 1500)
MONO_SIZE = (1280, 800)
DEPTH_SIZE = (768, 480)
DEFAULT_FPS = 10


@dataclass
class SceneFrame:
    cloud: dai.PointCloudData
    color: dai.ImgFrame
    left: dai.ImgFrame
    right: dai.ImgFrame
    image: np.ndarray
    points: np.ndarray
    projection: CameraProjection
    generation: int

    @property
    def sequence(self):
        return self.cloud.getSequenceNum()


def stamp(message, reference):
    message.setBufferMetadataFrom(reference)
    return message


def jpeg(image):
    success, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not success:
        raise RuntimeError("Could not encode the camera image.")
    return base64.b64encode(encoded).decode("ascii")


class SceneSource(dai.node.ThreadedHostNode):
    def __init__(self):
        super().__init__()
        self.outputs = {
            name: self.createOutput(name)
            for name in ("cloud", "color", "left", "right", "imu", "overlay")
        }
        self.messages = queue.Queue(maxsize=16)

    def submit(self, messages):
        self.messages.put(messages, timeout=1)

    def run(self):
        while self.isRunning():
            try:
                messages = self.messages.get(timeout=0.05)
            except queue.Empty:
                continue
            for name, message in messages:
                self.outputs[name].send(message)


def create_capture(pipeline, fps):
    streams = {}
    for role, socket in (
        ("color", dai.CameraBoardSocket.CAM_A),
        ("left", dai.CameraBoardSocket.CAM_B),
        ("right", dai.CameraBoardSocket.CAM_C),
    ):
        camera = pipeline.create(dai.node.Camera).build(socket, sensorFps=fps)
        streams[role] = camera.requestOutput(
            RGB_SIZE if role == "color" else MONO_SIZE,
            dai.ImgFrame.Type.NV12 if role == "color" else dai.ImgFrame.Type.GRAY8,
            fps=fps,
            enableUndistortion=False,
        )
    depth = pipeline.create(dai.node.NeuralDepth).build(
        streams["left"], streams["right"], dai.DeviceModelZoo.NEURAL_DEPTH_LARGE
    )
    if depth.getInputSize(dai.DeviceModelZoo.NEURAL_DEPTH_LARGE) != DEPTH_SIZE:
        raise RuntimeError(
            f"NeuralDepth LARGE has unexpected input size {depth.getInputSize(dai.DeviceModelZoo.NEURAL_DEPTH_LARGE)}."
        )
    cloud = pipeline.create(dai.node.PointCloud)
    cloud.initialConfig.setOrganized(True)
    depth.depth.link(cloud.inputDepth)
    streams["depth"] = depth.depth
    streams["pointCloud"] = cloud.outputPointCloud
    sync = pipeline.create(dai.node.Sync)
    sync.setRunOnHost(True)
    sync.setTimestampSource(dai.node.Sync.TimestampSource.DEVICE)
    sync.setSyncThreshold(timedelta(milliseconds=10))
    sync.setSyncAttempts(-1)
    for name, output in streams.items():
        output.link(sync.inputs[name])
    imu = pipeline.create(dai.node.IMU)
    imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_UNCALIBRATED, 100)
    imu.setBatchReportThreshold(10)
    imu.setMaxBatchReports(20)
    return (
        streams,
        sync.out.createOutputQueue(maxSize=2, blocking=False),
        imu.out.createOutputQueue(maxSize=4, blocking=False),
    )


def read_scene(group, generation):
    cloud, color, left, right = (
        group[name] for name in ("pointCloud", "color", "left", "right")
    )
    if any(
        reference_key(message) != reference_key(cloud)
        for message in (color, left, right)
    ):
        raise RuntimeError(
            "The cloud and images do not share a calibrated reference frame."
        )
    depth = group["depth"]
    if (depth.getWidth(), depth.getHeight()) != DEPTH_SIZE:
        raise RuntimeError(
            f"NeuralDepth returned {(depth.getWidth(), depth.getHeight())}, expected {DEPTH_SIZE}."
        )
    points = np.asarray(cloud.getPoints(), dtype=np.float32)
    if points.shape != (DEPTH_SIZE[0] * DEPTH_SIZE[1], 3):
        raise RuntimeError(
            f"Expected an organized {DEPTH_SIZE} point cloud, received {points.shape}."
        )
    return SceneFrame(
        cloud,
        color,
        left,
        right,
        color.getCvFrame(),
        points,
        CameraProjection.from_frame(color),
        generation,
    )


def parcel_boxes(batch, projection):
    parcels = []
    for item in batch.items:
        points = np.asarray(item.xyz_mm)
        bbox = projection.bounds(points)
        if bbox is not None:
            parcels.append(
                {
                    "candidate_id": item.candidate_id,
                    "bbox": bbox,
                    "center_mm": points.mean(axis=0).astype(float).tolist(),
                }
            )
    return parcels


def candidate_preview(frame, plane):
    valid = np.isfinite(frame.points).all(axis=1) & (
        np.linalg.norm(frame.points, axis=1) > 0
    )
    distance = np.abs(frame.points @ np.asarray(plane.normal) + plane.offset_mm)
    pixels, _ = frame.projection.project(frame.points[valid & (distance < 10)])
    pixels = np.rint(pixels).astype(np.int32)
    width, height = frame.projection.size
    pixels = pixels[
        (pixels[:, 0] >= 0)
        & (pixels[:, 0] < width)
        & (pixels[:, 1] >= 0)
        & (pixels[:, 1] < height)
    ]
    mask = np.zeros((height, width), dtype=np.uint8)
    if len(pixels):
        mask[pixels[:, 1], pixels[:, 0]] = 255
        mask = cv2.dilate(mask, np.ones((5, 5), np.uint8))
    image = frame.image.copy()
    chosen = mask != 0
    image[chosen] = (image[chosen] * 0.35 + np.array((100, 235, 70)) * 0.65).astype(
        np.uint8
    )
    return jpeg(image)


def annotated_image(image, parcels):
    result = image.copy()
    scale = max(0.45, image.shape[1] / 1400)
    for parcel in parcels:
        x1, y1, x2, y2 = map(round, parcel["bbox"])
        values = parcel["dimensions_mm"]
        dimensions = (
            " x ".join("?" if v is None else str(round(v)) for v in values) + " mm"
            if values
            else parcel["status"]
        )
        cv2.rectangle(
            result, (x1, y1), (x2, y2), (130, 230, 60), max(2, round(scale * 2))
        )
        cv2.putText(
            result,
            f"ID {parcel['track_id']} | {dimensions}",
            (max(0, x1), max(round(25 * scale), y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            (130, 230, 60),
            max(1, round(scale)),
            cv2.LINE_AA,
        )
    return result


def metadata_record(message):
    transformation = message.getTransformation()
    extrinsics = transformation.getExtrinsics()
    return {
        "size": list(transformation.getSize()),
        "intrinsics": transformation.getIntrinsicMatrix(),
        "distortion_model": str(transformation.getDistortionModel()),
        "distortion_coefficients": transformation.getDistortionCoefficients(),
        "pose_to_reference_mm": extrinsics.getTransformationMatrix(
            False, dai.LengthUnit.MILLIMETER
        ),
        "reference": [extrinsics.toDeviceId, extrinsics.toCameraSocket.name],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Measure parcels using public parcel nodes and the evaluated NeuralDepth capture profile."
    )
    parser.add_argument("-d", "--device", help="OAK4 IP or device ID")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8082)
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS)
    parser.add_argument("--inspect-port", type=int, default=8765)
    parser.add_argument(
        "--evidence",
        type=Path,
        help="Save selected plane, source metadata, RGB, overlay, and structured results locally",
    )
    args = parser.parse_args()
    if not 0 < args.fps <= 30:
        parser.error("--fps must be greater than zero and at most 30")
    server = BrowserServer(args.host, args.port)
    session, tracker = CalibrationSession(), ParcelTracker()
    candidates_ui = []
    frames = OrderedDict()
    pending_detections = {}
    waiting_measurement = None
    inflight = None
    last_frame = None
    error = None
    stopped = False
    detector = None
    config_dirty = False
    capture_samples, measurement_samples = deque(maxlen=60), deque(maxlen=30)
    rates = {"source_fps": None, "measurement_fps": None}
    profile = {
        "configured_fps": args.fps,
        "rgb": RGB_SIZE,
        "left": MONO_SIZE,
        "right": MONO_SIZE,
        "depth": DEPTH_SIZE,
        "depth_source": "NeuralDepth LARGE",
        "images": "unrectified",
    }

    def stop(*_):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    def state():
        return {
            "calibration": {
                "phase": session.phase.value,
                "generation": session.generation,
                "message": session.message,
                "selected": session.selected,
                "plane": session.plane.toJson() if session.plane else None,
                "candidates": candidates_ui,
            },
            "error": error,
            "frame_sequence": last_frame["sequence"] if last_frame else None,
            "capture": profile,
            "rates": rates,
        }

    def publish_frame(frame, parcels, message):
        nonlocal last_frame
        last_frame = {
            "sequence": frame.sequence,
            "width": frame.image.shape[1],
            "height": frame.image.shape[0],
            "jpeg": jpeg(frame.image),
            "parcels": parcels,
            "message": message,
        }
        server.publish(state(), last_frame)

    if args.evidence:
        args.evidence.mkdir(parents=True, exist_ok=True)
    server.publish(state())
    server.start()
    print(f"Parcel frontend at http://localhost:{args.port}", flush=True)
    remote = dai.RemoteConnection(
        address=args.host, serveFrontend=False, webSocketPort=args.inspect_port
    )
    try:
        device = (
            dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
        )
        if device.getPlatform() != dai.Platform.RVC4:
            device.close()
            raise RuntimeError("This capture profile requires an OAK4.")
        with device, dai.Pipeline(device) as capture, dai.Pipeline(False) as processing:
            streams, groups, imus = create_capture(capture, args.fps)
            calibration_source = capture.create(SceneSource)
            calibrator = capture.create(SupportPlaneCalibrator).build(
                streams["pointCloud"],
                calibration_source.outputs["imu"],
                DEPTH_SIZE,
                config=PlaneCalibrationConfig(max_calibration_attempts=12),
            )
            controls = calibrator.inputControl.createInputQueue()
            calibration_results = calibrator.out.createOutputQueue(
                maxSize=4, blocking=False
            )
            source = processing.create(SceneSource)
            outputs = source.outputs
            remote.addTopic("RGB", streams["color"])
            remote.addTopic("Depth", streams["depth"])
            remote.addTopic("Parcel overlay", outputs["overlay"])
            capture.start()
            remote.registerPipeline(capture)
            print("Pipeline started.", flush=True)
            print(json.dumps({"capture_profile": profile}), flush=True)
            first = True
            started = time.monotonic()
            latest_scene = None
            while (
                not stopped
                and capture.isRunning()
                and (detector is None or processing.isRunning())
            ):
                while not server.commands.empty():
                    action, data = server.commands.get_nowait()
                    try:
                        if action == "calibrate":
                            session.start()
                            tracker.clear()
                            candidates_ui = []
                            controls.send(SupportPlaneCalibrationControl.reset())
                            controls.send(SupportPlaneCalibrationControl.start())
                        elif action == "select":
                            session.select(data["generation"], data["index"])
                            if detector is None:
                                detector = processing.create(ParcelDetector).build(
                                    outputs["cloud"],
                                    outputs["color"],
                                    outputs["left"],
                                    outputs["right"],
                                    session.plane,
                                )
                                configs = detector.inputConfig.createInputQueue()
                                dimensioner = processing.create(
                                    ParcelDimensioner
                                ).build(detector.out)
                                detections = detector.out.createOutputQueue(
                                    maxSize=4, blocking=False
                                )
                                measurements = dimensioner.out.createOutputQueue(
                                    maxSize=4, blocking=False
                                )
                                processing.start()
                            else:
                                config_dirty = True
                            if args.evidence:
                                session.plane.toJsonFile(
                                    args.evidence / "support-plane.json"
                                )
                        error = None
                    except ValueError as exception:
                        error = str(exception)
                    server.publish(state())

                imu = imus.tryGet()
                while imu is not None:
                    if latest_scene is not None:
                        color_pose = np.linalg.inv(
                            latest_scene.projection.reference_to_camera
                        )
                        calibration_source.submit(
                            [("imu", transformed_imu(imu, color_pose[:3, :3]))]
                        )
                    imu = imus.tryGet()

                result = calibration_results.tryGet()
                if result is not None:
                    session.finish(result.candidates)
                    reference = frames.get(result.getSequenceNum()) or latest_scene
                    best = max((c.inlier_count for c in result.candidates), default=0)
                    candidates_ui = [
                        {
                            "index": index,
                            "plane": candidate.plane.toJson(),
                            "inlier_count": candidate.inlier_count,
                            "inlier_ratio": candidate.inlier_ratio,
                            "recommended": candidate.inlier_count == best,
                            "preview": candidate_preview(reference, candidate.plane)
                            if reference is not None
                            else None,
                        }
                        for index, candidate in enumerate(result.candidates)
                    ]
                    server.publish(state())
                    print(
                        json.dumps(
                            {
                                "calibration": session.phase.value,
                                "candidates": [
                                    {k: v for k, v in c.items() if k != "preview"}
                                    for c in candidates_ui
                                ],
                            }
                        ),
                        flush=True,
                    )

                if detector is not None:
                    batch = detections.tryGet()
                    while batch is not None:
                        pending_detections[batch.getSequenceNum()] = batch
                        batch = detections.tryGet()
                    if waiting_measurement is None:
                        waiting_measurement = measurements.tryGet()
                    if (
                        waiting_measurement is not None
                        and waiting_measurement.getSequenceNum() in pending_detections
                    ):
                        measured, waiting_measurement = waiting_measurement, None
                        seq = measured.getSequenceNum()
                        reference = (
                            inflight[2]
                            if inflight is not None and inflight[0] == seq
                            else frames.get(seq)
                        )
                        inflight = None
                        batch = pending_detections.pop(seq)
                        measurement_samples.append(time.monotonic())
                        if len(measurement_samples) > 1:
                            rates["measurement_fps"] = (
                                len(measurement_samples) - 1
                            ) / (measurement_samples[-1] - measurement_samples[0])
                        if (
                            reference is not None
                            and reference.generation == session.generation
                            and session.phase is CalibrationPhase.READY
                        ):
                            parcels = parcel_boxes(batch, reference.projection)
                            by_candidate = {
                                item.candidate_id: item for item in measured.items
                            }
                            for parcel in parcels:
                                item = by_candidate.get(parcel["candidate_id"])
                                parcel["status"] = (
                                    item.status.value
                                    if item is not None
                                    else "measurement_failed"
                                )
                                parcel["dimensions_mm"] = (
                                    [
                                        item.cuboid.length_mm,
                                        item.cuboid.width_mm,
                                        item.cuboid.height_mm,
                                    ]
                                    if item is not None and item.cuboid
                                    else None
                                )
                            parcels = tracker.update(parcels, time.monotonic())
                            if measured.outcome is ParcelMeasurements.Outcome.FAILED:
                                message = f"Frame failed: {measured.failure_code}. No measurement is available."
                            elif parcels:
                                complete = sum(
                                    p["status"] == "measured" for p in parcels
                                )
                                message = f"{len(parcels)} parcel{'s' if len(parcels) != 1 else ''} detected · {complete} with complete dimensions."
                            else:
                                message = "No eligible parcels in view. Keep each parcel fully visible and separated."
                            publish_frame(reference, parcels, message)
                            overlay = annotated_image(reference.image, parcels)
                            overlay_message = dai.ImgFrame()
                            overlay_message.setCvFrame(
                                overlay, dai.ImgFrame.Type.BGR888i
                            )
                            overlay_message.setTransformation(
                                reference.color.getTransformation()
                            )
                            source.submit(
                                [("overlay", stamp(overlay_message, reference.cloud))]
                            )
                            if args.evidence:
                                cv2.imwrite(
                                    str(args.evidence / "rgb.png"), reference.image
                                )
                                cv2.imwrite(str(args.evidence / "overlay.png"), overlay)
                                saved_state = state()
                                saved_state["calibration"] = {
                                    **saved_state["calibration"],
                                    "candidates": [
                                        {k: v for k, v in c.items() if k != "preview"}
                                        for c in candidates_ui
                                    ],
                                }
                                (args.evidence / "latest.json").write_text(
                                    json.dumps(
                                        {
                                            "state": saved_state,
                                            "frame": {
                                                k: v
                                                for k, v in last_frame.items()
                                                if k != "jpeg"
                                            },
                                            "outcome": measured.outcome.value,
                                            "failure_code": measured.failure_code,
                                            "measurement_plane": (
                                                measured.plane.toJson()
                                                if measured.plane is not None
                                                else None
                                            ),
                                            "algorithm_id": measured.algorithm_id,
                                        },
                                        indent=2,
                                    )
                                )

                group = groups.tryGet()
                if group is not None:
                    frame = read_scene(group, session.generation)
                    latest_scene = frame
                    frames[frame.sequence] = frame
                    while len(frames) > 24:
                        frames.popitem(last=False)
                    capture_samples.append(
                        (
                            frame.color.getSequenceNum(),
                            frame.color.getTimestampDevice().total_seconds(),
                        )
                    )
                    if len(capture_samples) > 1:
                        elapsed = capture_samples[-1][1] - capture_samples[0][1]
                        if elapsed > 0:
                            rates["source_fps"] = (
                                capture_samples[-1][0] - capture_samples[0][0]
                            ) / elapsed
                    if first:
                        first = False
                        if args.evidence:
                            (args.evidence / "camera-calibration.json").write_text(
                                json.dumps(
                                    {
                                        "capture_profile": profile,
                                        "streams": {
                                            name: metadata_record(group[name])
                                            for name in (
                                                "pointCloud",
                                                "color",
                                                "left",
                                                "right",
                                                "depth",
                                            )
                                        },
                                    },
                                    indent=2,
                                )
                            )
                    if session.phase is not CalibrationPhase.READY:
                        publish_frame(
                            frame,
                            [],
                            "Select a calibrated support plane to enable parcel measurements.",
                        )
                    elif inflight is None:
                        finite = frame.points[
                            np.isfinite(frame.points).all(axis=1)
                            & (np.linalg.norm(frame.points, axis=1) > 0)
                        ]
                        cloud = stamp(dai.PointCloudData(), frame.cloud)
                        cloud.setPoints(finite)
                        cloud.setTransformation(frame.cloud.getTransformation())
                        if config_dirty:
                            configs.send(
                                ParcelDetectorConfig(supportPlane=session.plane)
                            )
                            config_dirty = False
                        source.submit(
                            [
                                ("color", frame.color),
                                ("left", frame.left),
                                ("right", frame.right),
                                ("cloud", cloud),
                            ]
                        )
                        inflight = (frame.sequence, time.monotonic(), frame)
                elif first and time.monotonic() - started > 30:
                    raise RuntimeError(
                        "No synchronized RGB, mono, and NeuralDepth point cloud arrived within 30 seconds."
                    )
                if inflight is not None and time.monotonic() - inflight[1] > 30:
                    raise RuntimeError(
                        "Parcel processing did not return a result within 30 seconds."
                    )
                time.sleep(0.002)
            if detector is not None:
                processing.stop()
            capture.stop()
    finally:
        server.stop()


if __name__ == "__main__":
    main()
