"""Calibrate several OAK devices, fit the ground plane to their merged point cloud and
project all cameras onto that plane with the Stitching node (bird's-eye view)."""

from datetime import timedelta

import depthai as dai
import numpy as np

from utils.arguments import initialize_argparser
from utils.calibration import load_or_calibrate, select_devices
from utils.plane import fit_ground_plane

HTTP_PORT = 8082
DEPTH_SIZE = (640, 400)
SOCKET = dai.CameraBoardSocket.CAM_B  # Left stereo camera, projected onto the ground
MAX_VIEW_SIZE = (1280, 1280)
WARMUP_CLOUDS = 10  # First clouds are skipped while exposure and depth settle
PLANE_CLOUDS = 3  # Merged point clouds accumulated for the plane fit


def estimate_ground_plane(device_infos, calibration, fps, max_range):
    """Merge the depth of all devices into one point cloud and fit the ground plane to it."""
    with dai.Pipeline(createImplicitDevice=False) as pipeline:
        pipeline.setMultiDeviceCalibration(calibration.getGraph())

        # One host PointCloud node merges the depth of every device. The cloud is
        # expressed in the common calibration origin, the frame the Stitching plane uses.
        point_cloud = pipeline.create(dai.node.PointCloud)
        point_cloud.initialConfig.setLengthUnit(dai.LengthUnit.METER)
        point_cloud.sync.setSyncThreshold(timedelta(seconds=1 / fps))

        for info in device_infos:
            device = pipeline.addDevice(info)
            depth = pipeline.create(dai.node.Depth, device).build(
                dai.node.Depth.Algorithm.AUTO, fps, DEPTH_SIZE
            )
            depth.depth.link(point_cloud.getDepthInput(device.getDeviceId()))

        queue = point_cloud.outputPointCloud.createOutputQueue(
            maxSize=2, blocking=False
        )
        pipeline.start()
        print("Fitting the ground plane to the merged point cloud...")

        clouds = []
        for index in range(WARMUP_CLOUDS + PLANE_CLOUDS):
            message = queue.get(timedelta(seconds=30))
            if message is None:
                raise RuntimeError("No merged point cloud received")
            if index >= WARMUP_CLOUDS:
                clouds.append(np.asarray(message.getPoints(), dtype=np.float64))

    points = np.concatenate(clouds)
    # Far depth is noisy and is not drawn anyway.
    points = points[np.linalg.norm(points, axis=1) < max_range]
    plane = fit_ground_plane(points)
    if plane is None:
        raise RuntimeError(
            "No ground plane found. The cameras must see the floor and be mounted roughly upright."
        )
    point, normal, inlier_ratio = plane
    print(
        f"Ground plane: {100 * inlier_ratio:.0f}% of the points, "
        f"origin camera {abs(normal @ point):.2f} m above it, "
        f"normal [{normal[0]:.2f}, {normal[1]:.2f}, {normal[2]:.2f}]"
    )
    return point, normal


def main():
    _, args = initialize_argparser()
    device_infos = select_devices(args.devices, args.include_ip, args.max_devices)
    if len(device_infos) < 2:
        print("At least two devices are required for this example.")
        return

    calibration = load_or_calibrate(args, device_infos)
    point, normal = estimate_ground_plane(
        device_infos, calibration, args.fps_limit, args.max_range
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
