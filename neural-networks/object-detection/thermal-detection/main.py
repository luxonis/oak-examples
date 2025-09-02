from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork

from utils.arguments import initialize_argparser
from utils.yuv2bgr import YUV2BGR

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888i if platform == "RVC4" else dai.ImgFrame.Type.BGR888p
)

if args.fps_limit is None:
    args.fps_limit = 20
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # detection model
    det_model_description = dai.NNModelDescription.fromYamlFile(
        f"thermal_person_detection.{platform}.yaml"
    )
    if det_model_description.model != args.model:
        det_model_description = dai.NNModelDescription(args.model, platform=platform)
    det_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))
    det_model_w, det_model_h = det_model_nn_archive.getInputSize()

    # media/camera input
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(dai.ImgFrame.Type.NV12)
        replay.setLoop(True)
        imageManip = pipeline.create(dai.node.ImageManip)
        imageManip.setMaxOutputFrameSize(det_model_w * det_model_h * 3)
        imageManip.initialConfig.setOutputSize(det_model_w, det_model_h)
        imageManip.initialConfig.setFrameType(frame_type)
        replay.out.link(imageManip.inputImage)
        input_node = imageManip.out

    else:
        cam = pipeline.create(dai.node.Thermal).build()
        yuv2bgr = pipeline.create(YUV2BGR)  # Thermal output is YUV, model needs BGR
        cam.color.link(yuv2bgr.input)
        input_node = yuv2bgr.out

    nn_with_parser = pipeline.create(ParsingNeuralNetwork).build(
        input_node, det_model_nn_archive, fps=args.fps_limit
    )
    parser = nn_with_parser.getParser()
    parser.setConfidenceThreshold(0.6)  # NOTE: Adjust if needed

    # visualization
    visualizer.addTopic("Video", nn_with_parser.passthrough, "images")
    visualizer.addTopic("Visualizations", nn_with_parser.out, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
