import depthai as dai
from depthai_nodes.node import ParserGenerator, XFeatStereoParser
from utils.custom_visualizer import StereoVersionVisualizer


def stereo_mode(
    device: dai.Device,
    nn_archive: dai.NNArchive,
    visualizer: dai.RemoteConnection,
    fps_limit: int,
):
    with dai.Pipeline(device) as pipeline:
        print("Creating pipeline...")

        platform = device.getPlatform().name

        img_frame_type = (
            dai.ImgFrame.Type.BGR888p
            if platform == "RVC2"
            else dai.ImgFrame.Type.BGR888i
        )

        available_cameras = [
            camera.name for camera in device.getConnectedCameraFeatures()
        ]

        if len(available_cameras) < 2:
            raise RuntimeError(
                f"Expected at least 2 cameras, but found {len(available_cameras)} cameras: {available_cameras}. You need at least 2 cameras (left and right) to run this example in stereo mode."
            )

        try:
            left_cam = pipeline.create(dai.node.Camera).build(
                dai.CameraBoardSocket.CAM_B
            )
            right_cam = pipeline.create(dai.node.Camera).build(
                dai.CameraBoardSocket.CAM_C
            )
        except ValueError as e:
            raise RuntimeError("Could not build left and right cameras.") from e

        left_network = pipeline.create(dai.node.NeuralNetwork).build(
            left_cam.requestOutput(
                nn_archive.getInputSize(), type=img_frame_type, fps=fps_limit
            ),
            nn_archive,
        )
        left_network.setNumInferenceThreads(2)

        right_network = pipeline.create(dai.node.NeuralNetwork).build(
            right_cam.requestOutput(
                nn_archive.getInputSize(), type=img_frame_type, fps=fps_limit
            ),
            nn_archive,
        )
        right_network.setNumInferenceThreads(2)

        parser: XFeatStereoParser = pipeline.create(ParserGenerator).build(nn_archive)[
            0
        ]
        parser.setMaxKeypoints(512)
        left_network.out.link(parser.reference_input)
        right_network.out.link(parser.target_input)

        custom_visualizer = pipeline.create(StereoVersionVisualizer).build(
            left_frame_input=left_network.passthrough,
            right_frame_input=right_network.passthrough,
            tracked_features=parser.out,
        )

        visualizer.addTopic("Left Camera", left_network.passthrough, "images")
        visualizer.addTopic("Right Camera", right_network.passthrough, "images")
        visualizer.addTopic("Matches", custom_visualizer.output, "images")

        print("Pipeline created.")

        pipeline.start()
        visualizer.registerPipeline(pipeline)

        while pipeline.isRunning():
            key_pressed = visualizer.waitKey(1)
            if key_pressed == ord("q"):
                pipeline.stop()
                break
