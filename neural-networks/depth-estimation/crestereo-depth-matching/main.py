from datetime import timedelta

import cv2
import depthai as dai
from depthai_nodes.node import ApplyDepthColormap, ParsingNeuralNetwork
from utils.arguments import initialize_argparser
from utils.disparity_to_depth import DisparityToDepth
from utils.rectified_color import RectifiedColor

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatformAsString()
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888i if platform == "RVC4" else dai.ImgFrame.Type.BGR888p
)

supported_models = {
    "RVC2": ["luxonis/crestereo:iter2-160x120", "luxonis/crestereo:iter2-320x240"],
    "RVC4": ["luxonis/crestereo:iter4-640x360"],
}
if args.model is None:
    args.model = supported_models[platform][-1]
elif args.model not in supported_models[platform]:
    raise ValueError(f"Model {args.model} is not supported on {platform} platform.")

if args.fps_limit is None:
    args.fps_limit = 2 if platform == "RVC2" else 5
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # crestereo model
    cre_model_description = dai.NNModelDescription.fromYamlFile(
        f"crestereo.{platform}.yaml"
    )
    if cre_model_description.model != args.model:
        cre_model_description = dai.NNModelDescription(args.model, platform=platform)

    cre_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(cre_model_description))
    model_input_shape = cre_model_nn_archive.getInputSize()

    # stereo camera input
    left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)

    raw_left = left.requestOutput(
        model_input_shape, type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )
    raw_right = right.requestOutput(
        model_input_shape, type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )
    stereo = pipeline.create(dai.node.StereoDepth).build(
        left=raw_left,
        right=raw_right,
        presetMode=dai.node.StereoDepth.PresetMode.DEFAULT,
    )
    # Keep the baseline at the neural input resolution (no post-depth decimation).
    stereo.initialConfig.postProcessing.decimationFilter.decimationFactor = 1
    stereo.enableDistortionCorrection(True)
    stereo.setRectificationUseSpecTranslation(False)
    stereo.setRectifyEdgeFillColor(0)
    rect_left, rect_right = stereo.rectifiedLeft, stereo.rectifiedRight
    stereo.setDisparityToDepthUseSpecTranslation(False)
    stereo.setDepthAlign(
        dai.StereoDepthConfig.AlgorithmControl.DepthAlign.RECTIFIED_LEFT
    )

    lr_sync = pipeline.create(dai.node.Sync)
    lr_sync.setSyncThreshold(timedelta(milliseconds=5))
    lr_sync.setSyncAttempts(-1)
    for name, output in (("left", rect_left), ("right", rect_right)):
        color = pipeline.create(RectifiedColor).build(output, frame_type)
        color.output.link(lr_sync.inputs[name])

    demux = pipeline.create(dai.node.MessageDemux)
    lr_sync.out.link(demux.input)

    nn = pipeline.create(ParsingNeuralNetwork)
    if platform == "RVC4":
        nn.setNNArchive(cre_model_nn_archive)
        nn.setBackend("snpe")
        nn.setBackendProperties(
            {
                "runtime": "dsp",
                "performance_profile": "default",
            }
        )
    elif platform == "RVC2":
        nn.setNNArchive(cre_model_nn_archive, numShaves=7)

    demux.outputs["left"].link(nn.inputs["left"])
    demux.outputs["right"].link(nn.inputs["right"])

    # color classical stereo depth
    depth_coloring = pipeline.create(ApplyDepthColormap).build(stereo.depth)
    depth_coloring.setColormap(cv2.COLORMAP_PLASMA)

    calibration = device.readCalibration()
    baseline_mm = (
        calibration.getBaselineDistance(
            dai.CameraBoardSocket.CAM_B, dai.CameraBoardSocket.CAM_C, False
        )
        * 10
    )
    nn_depth = pipeline.create(DisparityToDepth).build(
        disparity=nn.out,
        rectified=nn.passthroughs["left"],
        baseline_mm=baseline_mm,
    )

    # color CREStereo output converted from disparity to depth
    nn_coloring = pipeline.create(ApplyDepthColormap).build(nn_depth.output)
    nn_coloring.setColormap(cv2.COLORMAP_PLASMA)

    # visualization
    visualizer.addTopic("Rectified Left", rect_left)
    visualizer.addTopic("Rectified Right", rect_right)
    visualizer.addTopic("Depth", depth_coloring.out)
    visualizer.addTopic("CREStereo Depth", nn_coloring.out)

    print("Pipeline created.")
    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
