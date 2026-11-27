import depthai as dai
import numpy as np
import rerun as rr
import rerun.blueprint as rrb

TIMELINE = "device_time"

STEREO_CAMERA_NAMES = {
    dai.CameraBoardSocket.CAM_B: "left",
    dai.CameraBoardSocket.CAM_C: "right",
}
IMU_SENSORS = [
    dai.IMUSensor.ACCELEROMETER_CALIBRATED,
    dai.IMUSensor.GYROSCOPE_CALIBRATED,
]
IMU_UNITS = {"accel": "m/s²", "gyro": "rad/s"}

MM_PER_M = 1000.0
DETECTION_RADIUS_M = 0.03
ACCEL_ARROW_M_PER_MPS2 = 0.01
EYE_POSITION_IN_DEVICE = [0.3, -0.4, -0.7]
EYE_LOOK_TARGET_IN_DEVICE = [0.0, 0.0, 1.0]
EYE_UP_IN_DEVICE = [0.0, -1.0, 0.0]


def camera_name(camera: dai.CameraFeatures) -> str:
    if dai.CameraSensorType.THERMAL in camera.supportedTypes:
        return "thermal"
    if dai.CameraSensorType.TOF in camera.supportedTypes:
        return "tof"
    if (
        camera.socket == dai.CameraBoardSocket.CAM_A
        and dai.CameraSensorType.COLOR in camera.supportedTypes
    ):
        return "rgb"
    return STEREO_CAMERA_NAMES.get(camera.socket, camera.socket.name.lower())


def _set_time(msg: dai.Buffer) -> None:
    rr.set_time(TIMELINE, duration=msg.getTimestampDevice())


def _pinhole(transformation: dai.ImgTransformation) -> rr.Pinhole:
    width, height = transformation.getSize()
    return rr.Pinhole(
        image_from_camera=transformation.getIntrinsicMatrix(),
        resolution=[width, height],
    )


def log_video_codec(camera_name: str) -> None:
    rr.log(
        f"oak/{camera_name}/video",
        rr.VideoStream(codec=rr.VideoCodec.H264),
        static=True,
    )


def log_imu_static() -> None:
    for name, unit in IMU_UNITS.items():
        rr.log(
            f"imu/{name}",
            rr.Measurements.from_fields(units=[unit] * 3, names=["x", "y", "z"]),
            static=True,
        )


def log_annotation_context(class_names: list[str]) -> None:
    rr.log("/", rr.AnnotationContext(list(enumerate(class_names))), static=True)


def log_video(camera_name: str, frame: dai.EncodedFrame) -> None:
    _set_time(frame)
    rr.log(
        f"oak/{camera_name}/video",
        _pinhole(frame.getTransformation()),
        rr.VideoStream.from_fields(sample=frame.getData()),
    )


def log_depth(camera_name: str, frame: dai.ImgFrame) -> None:
    _set_time(frame)
    rr.log(
        f"oak/{camera_name}/depth",
        _pinhole(frame.getTransformation()),
        rr.DepthImage(frame.getFrame(), meter=MM_PER_M),
    )


def log_detections(
    camera_name: str,
    video_size: tuple[int, int],
    class_names: list[str],
    detections: dai.ImgDetections | dai.SpatialImgDetections,
) -> None:
    _set_time(detections)
    dets = detections.detections
    class_ids = [d.label for d in dets]
    labels = [f"{class_names[d.label]} {d.confidence:.2f}" for d in dets]
    width, height = video_size
    rr.log(
        f"oak/{camera_name}/video/detections",
        rr.Boxes2D(
            array=[
                [d.xmin * width, d.ymin * height, d.xmax * width, d.ymax * height]
                for d in dets
            ],
            array_format=rr.Box2DFormat.XYXY,
            class_ids=class_ids,
            labels=labels,
        ),
    )
    if not isinstance(detections, dai.SpatialImgDetections):
        return
    centroids_mm = [
        [d.spatialCoordinates.x, d.spatialCoordinates.y, d.spatialCoordinates.z]
        for d in dets
    ]
    rr.log(
        f"oak/{camera_name}/detections",
        rr.Points3D(
            np.array(centroids_mm).reshape(-1, 3) / MM_PER_M,
            radii=DETECTION_RADIUS_M,
            class_ids=class_ids,
            labels=labels,
            show_labels=True,
        ),
    )


def log_imu(imu_frame: str | None, imu: dai.IMUData) -> None:
    if not imu.packets:
        return
    reports = {
        "accel": [p.acceleroMeter for p in imu.packets],
        "gyro": [p.gyroscope for p in imu.packets],
    }
    for name, series in reports.items():
        rr.send_columns(
            f"imu/{name}",
            indexes=[
                rr.TimeColumn(
                    TIMELINE, duration=[r.getTimestampDevice() for r in series]
                )
            ],
            columns=rr.Measurements.columns(values=[[r.x, r.y, r.z] for r in series]),
        )
    if imu_frame is None:
        return
    latest = reports["accel"][-1]
    _set_time(latest)
    rr.log(
        f"{imu_frame}/accel",
        rr.Arrows3D(
            vectors=[np.array([latest.x, latest.y, latest.z]) * ACCEL_ARROW_M_PER_MPS2]
        ),
    )


def log_system(info: dai.SystemInformation | dai.SystemInformationRVC4) -> None:
    _set_time(info)
    rr.log(
        "device/temperature/chip",
        rr.Measurements([info.chipTemperature.average], units=["°C"]),
    )
    ddr = info.ddrMemoryUsage
    rr.log(
        "device/memory/ddr",
        rr.Measurements([100.0 * ddr.used / ddr.total], units=["%"]),
    )
    if isinstance(info, dai.SystemInformationRVC4):
        cpu = {"average": info.cpuAvgUsage.average}
    else:
        cpu = {
            "leon_css": info.leonCssCpuUsage.average,
            "leon_mss": info.leonMssCpuUsage.average,
        }
    for name, load in cpu.items():
        rr.log(f"device/cpu/{name}", rr.Measurements([100.0 * load], units=["%"]))


def blueprint(
    detection_camera: str | None,
    has_depth: bool,
    other_cameras: list[str],
    has_imu: bool,
) -> rrb.Blueprint:
    main_views = []
    if detection_camera is not None:
        main_views.append(
            rrb.Spatial2DView(
                name=detection_camera, origin=f"oak/{detection_camera}/video"
            )
        )
        if has_depth:
            main_views.append(
                rrb.Spatial2DView(name="depth", origin=f"oak/{detection_camera}/depth")
            )
    image_rows = []
    if main_views:
        image_rows.append(rrb.Tabs(*main_views))
    if other_cameras:
        image_rows.append(
            rrb.Horizontal(
                *[
                    rrb.Spatial2DView(name=name, origin=f"oak/{name}/video")
                    for name in other_cameras
                ]
            )
        )

    plots = []
    if has_imu:
        plots.append(
            rrb.Tabs(
                rrb.TimeSeriesView(name="Accel", origin="imu/accel"),
                rrb.TimeSeriesView(name="Gyro", origin="imu/gyro"),
            )
        )
    plots.append(
        rrb.Tabs(
            rrb.TimeSeriesView(name="Temp", origin="device/temperature"),
            rrb.TimeSeriesView(name="CPU", origin="device/cpu"),
            rrb.TimeSeriesView(name="Memory", origin="device/memory"),
        )
    )

    return rrb.Blueprint(
        rrb.Horizontal(
            rrb.Spatial3DView(
                name="3D",
                origin="oak",
                eye_controls=rrb.EyeControls3D(
                    position=EYE_POSITION_IN_DEVICE,
                    look_target=EYE_LOOK_TARGET_IN_DEVICE,
                    eye_up=EYE_UP_IN_DEVICE,
                ),
            ),
            rrb.Vertical(
                *image_rows, row_shares=[2, 1] if len(image_rows) == 2 else None
            ),
            rrb.Vertical(*plots),
            column_shares=[3, 2, 1],
        ),
        rrb.TimePanel(timeline=TIMELINE, state="collapsed"),
        collapse_panels=True,
    )
