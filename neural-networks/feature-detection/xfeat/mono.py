import depthai as dai
from depthai_nodes.node import ParserGenerator, XFeatMonoParser
from utils.custom_visualizer import MonoVersionVisualizer


def mono_mode(
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

        cam = pipeline.create(dai.node.Camera).build()

        nn = pipeline.create(dai.node.NeuralNetwork).build(
            cam.requestOutput(
                nn_archive.getInputSize(), type=img_frame_type, fps=fps_limit
            ),
            nn_archive,
        )

        parser: XFeatMonoParser = pipeline.create(ParserGenerator).build(nn_archive)[0]
        parser.setMaxKeypoints(1024)
        nn.out.link(parser.input)

        custom_visualizer: MonoVersionVisualizer = pipeline.create(
            MonoVersionVisualizer
        ).build(
            target_frame_input=nn.passthrough,
            tracked_features=parser.out,
        )

        visualizer.addTopic("Matches", custom_visualizer.output, "images")

        print("Pipeline created.")
        print("\nPress 's' to set the reference frame.\n")

        pipeline.start()
        visualizer.registerPipeline(pipeline)

        while pipeline.isRunning():
            key_pressed = visualizer.waitKey(1)
            if key_pressed == ord("s"):
                parser.setTrigger()
                custom_visualizer.setReferenceFrame()
            elif key_pressed == ord("q"):
                pipeline.stop()
                break
