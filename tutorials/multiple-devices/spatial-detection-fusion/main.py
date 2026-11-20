"""Fuse spatial detections from several calibrated OAK devices into one bird's-eye view."""

from datetime import timedelta

import depthai as dai

from utils import config
from utils.arguments import initialize_argparser
from utils.birds_eye_view import BirdsEyeView
from utils.fusion import FusionManager


def main():
    _, args = initialize_argparser()

    if not args.calibration.exists():
        print(
            f"Calibration file {args.calibration} not found. "
            "Run the multi-device-calibration example first or pass --calibration."
        )
        return
    calibration = dai.beta.MultiDeviceCalibrationHandler(args.calibration)
    graph = calibration.getGraph()

    calibrated_ids = {edge.fromDeviceId for edge in graph}
    calibrated_ids |= {edge.extrinsics.toDeviceId for edge in graph}
    identifiers = args.devices or sorted(calibrated_ids)
    if len(identifiers) < 2:
        print("At least two calibrated devices are required.")
        return

    # One pipeline spans all devices; every node is created on the device it runs on.
    with dai.Pipeline(createImplicitDevice=False) as pipeline:
        # The calibration graph puts the camera transformations of all devices into one
        # coordinate system, so messages can be transformed between devices.
        pipeline.setMultiDeviceCalibration(graph)
        visualizer = dai.RemoteConnection(httpPort=config.HTTP_PORT)

        # Group one detection message per device by host timestamp.
        detection_sync = pipeline.create(dai.node.Sync)
        detection_sync.setRunOnHost(True)
        detection_sync.setSyncThreshold(timedelta(seconds=1 / args.fps_limit))

        device_ids = []
        for identifier in identifiers:
            device = pipeline.addDevice(dai.DeviceInfo(identifier))
            device_id = device.getDeviceId()
            if device_id not in calibrated_ids:
                raise RuntimeError(
                    f"Device {device_id} is not part of the calibration {args.calibration}"
                )
            print(f"=== Connected to device: {device_id}")
            print(f"    >>> Cameras: {[c.name for c in device.getConnectedCameras()]}")

            platform = device.getPlatformAsString()
            model_description = dai.NNModelDescription(
                config.NN_MODEL_SLUG, platform=platform
            )
            nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))

            cam = pipeline.create(dai.node.Camera, device).build(
                dai.CameraBoardSocket.CAM_A, sensorFps=args.fps_limit
            )

            depth = pipeline.create(dai.node.Depth, device)
            depth.build(
                dai.node.Depth.Algorithm.AUTO,
                fps=args.fps_limit,
                size=nn_archive.getInputSize(),
            )
            # SpatialDetectionNetwork handles depth alignment; no depth.setAlignTo(...) call is needed.

            detector = pipeline.create(dai.node.SpatialDetectionNetwork, device).build(
                input=cam, depthSource=depth, model=nn_archive
            )
            detector.setBoundingBoxScaleFactor(0.2)

            if platform == "RVC2":
                detector.setNNArchive(nn_archive, numShaves=7)

            detector.out.link(detection_sync.inputs[device_id])
            device_ids.append(device_id)

            visualizer.addTopic(f"{device_id}", detector.passthrough, group=device_id)
            visualizer.addTopic(
                f"{device_id} Detections", detector.out, group=device_id
            )

        fusion_manager = pipeline.create(FusionManager).build(
            synced_detections=detection_sync.out,
            device_ids=device_ids,
            distance_threshold=config.DISTANCE_THRESHOLD_M,
        )
        bev = pipeline.create(BirdsEyeView).build(detections=fusion_manager.output)

        visualizer.addTopic("BEV Canvas", bev.canvas, group="BEV")
        visualizer.addTopic("BEV Cameras", bev.cameras_pos, group="BEV")
        visualizer.addTopic("BEV History Trails", bev.history_trails, group="BEV")
        visualizer.addTopic("BEV Detections", bev.detections, group="BEV")

        pipeline.start()
        visualizer.registerPipeline(pipeline)
        print(f"Pipeline started with {len(device_ids)} devices.")

        while pipeline.isRunning():
            pipeline.processTasks()
            key = visualizer.waitKey(1)
            if key == ord("q"):
                print("Got 'q' key from the remote connection! Shutting down.")
                break


if __name__ == "__main__":
    main()
