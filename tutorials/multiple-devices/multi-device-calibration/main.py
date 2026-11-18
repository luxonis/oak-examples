"""Calibrate the relative poses of several OAK devices with the MultiDeviceCalibration node."""

from datetime import timedelta

import depthai as dai

from utils.arguments import initialize_argparser
from utils.utility import select_devices

HTTP_PORT = 8082
PREVIEW_SIZE = (640, 400)
CALIBRATION_FPS = 5
STEREO_SOCKETS = (dai.CameraBoardSocket.CAM_B, dai.CameraBoardSocket.CAM_C)


def report(result: dai.beta.MultiDeviceCalibrationResult, output) -> None:
    if not result.passed or result.graph is None:
        print(f"Calibration failed: {result.info}")
        print("Aim the cameras at a shared textured scene and press 'c' to retry.")
        return

    handler = result.getHandler()
    if not handler.toJsonFile(output):
        print(f"Failed to save the calibration to {output}")
        return

    print(f"Calibration saved to {output}")
    print(
        f"Confidence: {result.dataConfidence:.3f}, Sampson error: {result.sampsonError:.4g}"
    )
    # Every device is expressed in the coordinate system of one automatically selected origin device.
    device_ids = {edge.fromDeviceId for edge in result.graph}
    device_ids |= {edge.extrinsics.toDeviceId for edge in result.graph}
    for device_id in sorted(device_ids):
        socket = handler.getDeviceSocket(device_id)
        to_origin = handler.getExtrinsicsToOrigin(device_id, socket)
        x, y, z = (100 * value for value in _translation(to_origin))
        print(
            f"  {device_id} {socket.name} -> origin {to_origin.toDeviceId}: "
            f"x={x:.1f} cm, y={y:.1f} cm, z={z:.1f} cm"
        )
    print("Press 'c' to calibrate again or 'q' to quit.")


def _translation(extrinsics: dai.Extrinsics):
    matrix = extrinsics.getTransformationMatrix(unit=dai.LengthUnit.METER)
    return matrix[0][3], matrix[1][3], matrix[2][3]


def main():
    _, args = initialize_argparser()
    device_infos = select_devices(args.devices, args.include_ip, args.max_devices)
    if len(device_infos) < 2:
        print("At least two devices are required for multi-device calibration.")
        return

    # One pipeline spans all devices; every node is created on the device it runs on.
    with dai.Pipeline(createImplicitDevice=False) as pipeline:
        visualizer = dai.RemoteConnection(httpPort=HTTP_PORT)

        calibration = pipeline.create(dai.beta.node.MultiDeviceCalibration)
        calibration.setSampleCount(args.sample_count)
        # The devices are free-running; a static scene tolerates capture offsets between them.
        calibration.sync.setSyncThreshold(timedelta(seconds=5))

        first_cameras = []
        has_stereo_pair = False
        for info in device_infos:
            device = pipeline.addDevice(info)
            device_id = device.getDeviceId()
            connected = device.getConnectedCameras()
            # A factory-calibrated stereo pair fixes the metric scale of the result.
            if all(socket in connected for socket in STEREO_SOCKETS):
                sockets = STEREO_SOCKETS
                has_stereo_pair = True
            elif dai.CameraBoardSocket.CAM_A in connected:
                sockets = (dai.CameraBoardSocket.CAM_A,)
            else:
                raise RuntimeError(
                    f"Device {device_id} needs CAM_A or CAM_B/CAM_C; connected: {connected}"
                )
            print(
                f"=== Device {device_id}: calibrating with {', '.join(s.name for s in sockets)}"
            )

            for socket in sockets:
                camera = pipeline.create(dai.node.Camera, device).build(
                    socket, sensorFps=CALIBRATION_FPS
                )
                calibration.addCamera(
                    camera.requestFullResolutionOutput(fps=CALIBRATION_FPS)
                )
                if socket == sockets[0]:
                    preview = camera.requestOutput(
                        PREVIEW_SIZE, dai.ImgFrame.Type.NV12, fps=CALIBRATION_FPS
                    )
                    visualizer.addTopic(f"{device_id} {socket.name}", preview)
            first_cameras.append((device_id, sockets[0]))

        if args.known_distance is not None:
            (id_a, socket_a), (id_b, socket_b) = first_cameras[:2]
            calibration.setKnownDistance(
                id_a,
                socket_a,
                id_b,
                socket_b,
                args.known_distance,
                dai.LengthUnit.CENTIMETER,
            )
        elif not has_stereo_pair:
            raise RuntimeError(
                "No device has a CAM_B/CAM_C stereo pair, so the scale is unknown. "
                "Pass --known-distance with the measured distance between the first two devices."
            )

        control_queue = calibration.inputControl.createInputQueue()
        result_queue = calibration.calibrationOutput.createOutputQueue()

        pipeline.start()
        visualizer.registerPipeline(pipeline)
        print(
            f"Open http://localhost:{HTTP_PORT}, aim all cameras at a shared textured scene "
            "and keep them still. Press 'c' to calibrate, 'q' to quit."
        )

        while pipeline.isRunning():
            pipeline.processTasks()
            result = result_queue.tryGet()
            if result is not None:
                report(result, args.output)

            key = visualizer.waitKey(1)
            if key == ord("q"):
                print("Got 'q' key from the remote connection! Shutting down.")
                break
            if key == ord("c"):
                print(f"Collecting {args.sample_count} synchronized samples...")
                control_queue.send(dai.beta.MultiDeviceCalibrationControl.start())


if __name__ == "__main__":
    main()
