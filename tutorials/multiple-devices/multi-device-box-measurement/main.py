"""Measure boxes seen by one or more OAK devices, with the support plane found automatically."""

import logging
from datetime import timedelta

import depthai as dai
from depthai_nodes.node import AutoSupportPlane, AutoSupportPlaneConfig, BoxMeasurer

from utils.arguments import initialize_argparser
from utils.box_overlay import BoxOverlay
from utils.calibration import (
    STEREO_SOCKETS,
    check_calibrated,
    load_or_calibrate,
    select_devices,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

HTTP_PORT = 8082
SIZE = (
    640,
    400,
)  # Color and depth size per device, in the aspect ratio of the box model


def create_camera(pipeline, device, socket, fps, ptp):
    """Create a camera that captures on the PTP clock when ptp is set."""
    camera = pipeline.create(dai.node.Camera, device).build(socket, sensorFps=fps)
    if ptp:
        camera.initialControl.setFrameSyncMode(dai.CameraControl.FrameSyncMode.TIME_PTP)
    return camera


def main():
    _, args = initialize_argparser()
    device_infos = select_devices(args.devices, args.include_ip, args.max_devices)
    if not device_infos:
        logger.error("No device found. Pass --devices or --include-ip.")
        return

    # One device measures in its own CAM_A frame; several devices need their poses.
    multi_device = len(device_infos) > 1
    if multi_device:
        calibration = load_or_calibrate(args, device_infos)
    else:
        calibration = None
        logger.info(
            "One device: no multi-device calibration is needed; "
            "--calibrate, --calibration and --ptp are ignored."
        )

    # Without PTP, the devices capture at unrelated times, so views are grouped
    # within half a frame period. With PTP, all devices capture at the same time
    # and the default sync threshold applies.
    ptp = multi_device and args.ptp
    sync_threshold = None
    if multi_device and not args.ptp:
        sync_threshold = timedelta(seconds=0.5 / args.fps_limit)
        logger.info(
            "Capturing without PTP: only static boxes are measured correctly. "
            "Pass --ptp to measure moving boxes."
        )

    # One pipeline spans all devices; every node is created on the device it runs on.
    with dai.Pipeline(createImplicitDevice=False) as pipeline:
        if calibration is not None:
            pipeline.setMultiDeviceCalibration(calibration.getGraph())
        visualizer = dai.RemoteConnection(httpPort=HTTP_PORT)

        # The support plane is found in the depth of all devices, merged in millimeters.
        scene_cloud = pipeline.create(dai.node.PointCloud)
        scene_cloud.initialConfig.setLengthUnit(dai.LengthUnit.MILLIMETER)
        if sync_threshold is not None:
            scene_cloud.sync.setSyncThreshold(sync_threshold)

        devices = []
        device_ids = []
        views = []  # One (color, aligned depth) pair per device
        for info in device_infos:
            device = pipeline.addDevice(info)
            device_id = device.getDeviceId()
            if calibration is not None:
                check_calibrated(calibration, device_id)
            logger.info(f"=== Connected to device: {device_id}")
            # The IR dot pattern gives plain box faces texture, so their depth is less noisy.
            device.setIrLaserDotProjectorIntensity(1)

            color = create_camera(
                pipeline,
                device,
                dai.CameraBoardSocket.CAM_A,
                args.fps_limit,
                ptp,
            )
            color_out = color.requestOutput(
                SIZE,
                type=dai.ImgFrame.Type.RGB888i,
                fps=args.fps_limit,
                resizeMode=dai.ImgResizeMode.CROP,
                enableUndistortion=True,
            )
            # The Depth node uses the stereo cameras that already exist on its device.
            for socket in STEREO_SOCKETS:
                create_camera(pipeline, device, socket, args.fps_limit, ptp)
            depth = pipeline.create(dai.node.Depth, device).build(
                dai.node.Depth.Algorithm.AUTO, args.fps_limit, SIZE
            )
            depth.setAlignTo(color_out)

            depth.depth.link(scene_cloud.getDepthInput(device_id))
            devices.append(device)
            device_ids.append(device_id)
            views.append((color_out, depth.depth))

        measurer = pipeline.create(BoxMeasurer).build(
            views, syncThreshold=sync_threshold
        )
        for view, (device_id, (color_out, _)) in enumerate(zip(device_ids, views)):
            overlay = pipeline.create(BoxOverlay).build(measurer.out, view)
            visualizer.addTopic(f"Color - {device_id}", color_out, group=device_id)
            visualizer.addTopic(f"Boxes - {device_id}", overlay.out, group=device_id)

        # Gravity from the first device's IMU tells the support plane apart from walls.
        imu = pipeline.create(dai.node.IMU, devices[0])
        imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 100)
        support_plane = pipeline.create(AutoSupportPlane).build(
            scene_cloud.outputPointCloud,
            imu.out,
            # Keep checking the plane and find it again when a device moves.
            AutoSupportPlaneConfig(mode=AutoSupportPlaneConfig.Mode.CONTINUOUS),
        )
        plane_results = support_plane.out.createOutputQueue()

        pipeline.start()
        visualizer.registerPipeline(pipeline)
        logger.info(f"Pipeline started with {len(device_infos)} devices.")
        logger.info("Searching for the support plane...")

        while pipeline.isRunning():
            pipeline.processTasks()
            for result in plane_results.tryGetAll():
                # Every passed check repeats the held plane; setting it again would
                # reset the aggregated box dimensions.
                if result.plane is None or result.plane == measurer.getSupportPlane():
                    continue
                measurer.setSupportPlane(result.plane)
                logger.info(
                    f"Support plane found {-result.plane.offset_mm / 1000:.2f} m "
                    "from the origin camera."
                )
            key = visualizer.waitKey(1)
            if key == ord("q"):
                logger.info("Got 'q' key from the remote connection! Shutting down.")
                break


if __name__ == "__main__":
    main()
