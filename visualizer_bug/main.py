import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork


visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device()

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    platform = device.getPlatform()
    nn_archive = dai.NNArchive(
        dai.getModelFromZoo(
            dai.NNModelDescription(
                model="luxonis/yunet:640x360",
                platform=platform.name,
            )
        )
    )

    cam = pipeline.create(dai.node.Camera).build()
    cam_out = cam.requestOutput(
        (nn_archive.getInputWidth(), nn_archive.getInputHeight()),
        type=dai.ImgFrame.Type.NV12,
    )

    interleaved_manip = pipeline.create(dai.node.ImageManip)
    interleaved_manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888i)
    interleaved_manip.setMaxOutputFrameSize(
        nn_archive.getInputHeight() * nn_archive.getInputWidth() * 3
    )
    cam_out.link(interleaved_manip.inputImage)

    nn_input = interleaved_manip.out

    nn = pipeline.create(ParsingNeuralNetwork).build(
        input=nn_input, nn_source=nn_archive
    )

    nn_archive_2 = dai.NNArchive(
        dai.getModelFromZoo(
            dai.NNModelDescription(
                model="luxonis/mediapipe-palm-detection:192x192",
                platform=platform.name,
            )
        )
    )

    cam_out2 = cam.requestOutput(
        (nn_archive_2.getInputWidth(), nn_archive_2.getInputHeight()),
        type=dai.ImgFrame.Type.BGR888i,
    )

    nn_2_input = cam_out2

    nn2 = pipeline.create(ParsingNeuralNetwork).build(
        input=nn_2_input, nn_source=nn_archive_2
    )

    visualizer.addTopic("Video", cam_out, "images")
    visualizer.addTopic("Faces", nn.out, "images")
    visualizer.addTopic("Hands", nn2.out, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
