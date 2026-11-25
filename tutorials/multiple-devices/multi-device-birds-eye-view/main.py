"""Calibrate several OAK devices, find the ground plane with the AutoSupportPlane node
and project all cameras onto that plane with the Stitching node (bird's-eye view)."""

from datetime import timedelta

import depthai as dai
import numpy as np
from depthai_nodes.node import (
    AutoSupportPlane,
    AutoSupportPlaneConfig,
    PlaneCalibrationConfig,
)

from utils.arguments import initialize_argparser
from utils.calibration import check_calibrated, load_or_calibrate, select_devices

HTTP_PORT = 8082
DEPTH_SIZE = (640, 400)
SOCKET = dai.CameraBoardSocket.CAM_B  # Left stereo camera, projected onto the ground
MAX_VIEW_SIZE = (1280, 1280)
MAX_PLANE_CLOUDS = 50  # Point clouds fitted before the ground search gives up


def find_origin(calibration):
    """Return the device ID and camera socket of the common calibration origin."""
    device_id = calibration.getGraph()[0].fromDeviceId
    to_origin = calibration.getExtrinsicsToOrigin(
        device_id, calibration.getDeviceSocket(device_id)
    )
    origin_id = to_origin.toDeviceId
    return origin_id, calibration.getDeviceSocket(origin_id)


def estimate_ground_plane(device_infos, origin_id, origin_socket, fps):
    """Find the ground in the origin device's point cloud, checked against its IMU gravity.

    The cloud is expressed in the origin camera, the frame the Stitching plane uses.
    """
    with dai.Pipeline(createImplicitDevice=False) as pipeline:
        # A DeviceInfo given by IP has no device ID yet, so connect until the origin is found.
        for info in device_infos:
            device = pipeline.addDevice(info)
            if device.getDeviceId() == origin_id:
                break
        else:
            raise RuntimeError(f"Calibration origin device {origin_id} is not selected")

        # The calibrator needs an organized cloud of a known size; the Depth node picks
        # its own size per device, so StereoDepth runs without decimation instead.
        stereo = pipeline.create(dai.node.StereoDepth, device).build(
            autoCreateCameras=True, size=DEPTH_SIZE, fps=fps
        )
        stereo.initialConfig.postProcessing.decimationFilter.decimationFactor = 1
        point_cloud = pipeline.create(dai.node.PointCloud)
        point_cloud.initialConfig.setOrganized(True)
        point_cloud.initialConfig.setLengthUnit(dai.LengthUnit.MILLIMETER)
        point_cloud.setTargetCoordinateSystem(origin_socket)
        stereo.depth.link(point_cloud.inputDepth)

        imu = pipeline.create(dai.node.IMU, device)
        imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 100)
        imu.setBatchReportThreshold(10)
        imu.setMaxBatchReports(10)

        support_plane = pipeline.create(AutoSupportPlane).build(
            point_cloud.outputPointCloud,
            imu.out,
            DEPTH_SIZE,
            AutoSupportPlaneConfig(
                calibration=PlaneCalibrationConfig(
                    max_calibration_attempts=MAX_PLANE_CLOUDS
                )
            ),
        )
        results = support_plane.out.createOutputQueue()
        pipeline.start()
        print("Searching for the ground plane...")
        result = results.get(timedelta(seconds=60))

    if result is None:
        raise RuntimeError(
            "No ground plane result. Check that the origin device has a working IMU."
        )
    if not result.passed:
        raise RuntimeError(
            "No ground plane found. The origin device must see the floor."
        )
    down = np.asarray(result.plane.normal)
    height = -result.plane.offset_mm / 1000
    up = -down
    print(
        f"Ground plane: origin camera {height:.2f} m above it, "
        f"normal [{up[0]:.2f}, {up[1]:.2f}, {up[2]:.2f}]"
    )
    # The point on the floor right below the camera and the normal pointing up to it.
    return height * down, up


def main():
    _, args = initialize_argparser()
    device_infos = select_devices(args.devices, args.include_ip, args.max_devices)
    if len(device_infos) < 2:
        print("At least two devices are required for this example.")
        return

    calibration = load_or_calibrate(args, device_infos)
    origin_id, origin_socket = find_origin(calibration)
    point, normal = estimate_ground_plane(
        device_infos, origin_id, origin_socket, args.fps_limit
    )

    # One pipeline spans all devices; every node is created on the device it runs on.
    with dai.Pipeline(createImplicitDevice=False) as pipeline:
        # Every camera transformation must be expressed in one coordinate system before start.
        pipeline.setMultiDeviceCalibration(calibration.getGraph())
        visualizer = dai.RemoteConnection(httpPort=HTTP_PORT)

        views = []
        for info in device_infos:
            device = pipeline.addDevice(info)
            device_id = device.getDeviceId()
            check_calibrated(calibration, device_id)
            print(f"=== Connected to device: {device_id}")

            # The projection needs an undistorted frame at the sensor's native size:
            # on depthai 3.12 a resized output makes the node reject most of the image.
            features = next(
                (f for f in device.getConnectedCameraFeatures() if f.socket == SOCKET),
                None,
            )
            if features is None:
                raise RuntimeError(f"Device {device_id} has no {SOCKET.name} camera")
            camera = pipeline.create(dai.node.Camera, device).build(
                SOCKET, sensorFps=args.fps_limit
            )
            view = camera.requestOutput(
                (features.width, features.height),
                type=dai.ImgFrame.Type.NV12,
                fps=args.fps_limit,
                enableUndistortion=True,
            )
            views.append(view)
            visualizer.addTopic(f"Input - {device_id}", view, group="Inputs")

        stitching = pipeline.create(dai.node.Stitching).build(views)
        stitching.setMode(dai.node.Stitching.Mode.PLANAR_PROJECTION)
        # The fitted plane is in the common calibration origin, like the point cloud it came from.
        stitching.setPlane(
            dai.Point3f(*point), dai.Point3f(*normal), dai.LengthUnit.METER
        )
        stitching.setMaxRange(args.max_range, dai.LengthUnit.METER)
        stitching.setMaxViewSize(*MAX_VIEW_SIZE)
        # The devices are not hardware-synchronized; accept frames within one frame period.
        stitching.setSyncThreshold(timedelta(seconds=1 / args.fps_limit))

        visualizer.addTopic("Birds-eye view", stitching.out, group="Birds-eye view")

        pipeline.start()
        visualizer.registerPipeline(pipeline)
        print(f"Pipeline started with {len(device_infos)} devices.")

        while pipeline.isRunning():
            pipeline.processTasks()
            key = visualizer.waitKey(1)
            if key == ord("q"):
                print("Got 'q' key from the remote connection! Shutting down.")
                break


if __name__ == "__main__":
    main()
