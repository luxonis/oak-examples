"""Calibrate several OAK devices and merge their depth into one colored point cloud."""

from datetime import timedelta

import depthai as dai

from utils.arguments import initialize_argparser
from utils.calibration import check_calibrated, load_or_calibrate, select_devices

HTTP_PORT = 8082
SIZE = (640, 400)  # Depth and color size per device


def main():
    _, args = initialize_argparser()
    device_infos = select_devices(args.devices, args.include_ip, args.max_devices)
    if len(device_infos) < 2:
        print("At least two devices are required for this example.")
        return

    calibration = load_or_calibrate(args, device_infos)

    # One pipeline spans all devices; every node is created on the device it runs on.
    with dai.Pipeline(createImplicitDevice=False) as pipeline:
        # The calibration graph puts the camera transformations of all devices into one
        # coordinate system, which is what lets a single node merge their depth.
        pipeline.setMultiDeviceCalibration(calibration.getGraph())
        visualizer = dai.RemoteConnection(httpPort=HTTP_PORT)

        # One host PointCloud node takes a depth and a color stream per device.
        point_cloud = pipeline.create(dai.node.PointCloud)
        point_cloud.initialConfig.setLengthUnit(dai.LengthUnit.METER)
        # The devices are not hardware-synchronized; accept streams within one frame period.
        point_cloud.sync.setSyncThreshold(timedelta(seconds=1 / args.fps_limit))

        for info in device_infos:
            device = pipeline.addDevice(info)
            device_id = device.getDeviceId()
            check_calibrated(calibration, device_id)
            print(f"=== Connected to device: {device_id}")

            color = pipeline.create(dai.node.Camera, device).build(
                dai.CameraBoardSocket.CAM_A, sensorFps=args.fps_limit
            )
            color_out = color.requestOutput(
                SIZE,
                type=dai.ImgFrame.Type.RGB888i,
                fps=args.fps_limit,
                resizeMode=dai.ImgResizeMode.CROP,
                enableUndistortion=True,
            )

            depth = pipeline.create(dai.node.Depth, device).build(
                dai.node.Depth.Algorithm.AUTO, args.fps_limit, SIZE
            )
            depth.setAlignTo(color_out)

            # Streams are named by device ID; the node pairs each depth with its color.
            depth.depth.link(point_cloud.getDepthInput(device_id))
            color_out.link(point_cloud.getColorInput(device_id))

            visualizer.addTopic(f"Color - {device_id}", color_out, group=device_id)

        visualizer.addTopic("Merged point cloud", point_cloud.outputPointCloud, "3d")

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
