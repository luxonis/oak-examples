"""Calibrate several OAK devices and compose their cameras into one panorama with the Stitching node."""

from datetime import timedelta

import depthai as dai

from utils.arguments import initialize_argparser
from utils.calibration import load_or_calibrate, select_devices

HTTP_PORT = 8082
VIEW_SIZE = (1280, 800)  # Camera view sent to the host for stitching
MAX_PANORAMA_SIZE = (3200, 1600)


def main():
    _, args = initialize_argparser()
    device_infos = select_devices(args.devices, args.include_ip, args.max_devices)
    if len(device_infos) < 2:
        print("At least two devices are required for this example.")
        return

    calibration = load_or_calibrate(args, device_infos)

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

            camera = pipeline.create(dai.node.Camera, device).build(
                dai.CameraBoardSocket.CAM_A, sensorFps=args.fps_limit
            )
            # Calibrated composition needs undistorted inputs.
            view = camera.requestOutput(
                VIEW_SIZE,
                type=dai.ImgFrame.Type.NV12,
                fps=args.fps_limit,
                enableUndistortion=True,
            )
            views.append(view)
            visualizer.addTopic(f"Input - {device_id}", view, group="Inputs")

        stitching = pipeline.create(dai.node.Stitching).build(views)
        stitching.setMode(dai.node.Stitching.Mode.PANORAMA)
        # Compose from the calibrated camera poses instead of matching image features.
        stitching.setUseInputCalibration(True)
        stitching.setCameraModel(getattr(dai.CameraModel, args.projection))
        stitching.setSeamFinder(
            dai.node.Stitching.SeamFinder.NONE
            if args.no_blend
            else dai.node.Stitching.SeamFinder.GRAPHCUT_COLOR
        )
        stitching.setMaxPanoramaSize(*MAX_PANORAMA_SIZE)
        # The devices are not hardware-synchronized; accept frames within one frame period.
        stitching.setSyncThreshold(timedelta(seconds=1 / args.fps_limit))

        visualizer.addTopic("Panorama", stitching.out, group="Panorama")

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
