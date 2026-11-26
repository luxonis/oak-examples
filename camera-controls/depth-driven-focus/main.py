from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, ApplyDepthColormap
from utils.arguments import initialize_argparser
from utils.depth_driven_focus import DepthDrivenFocus

_DEPTH_LOWER_THRESHOLD_MM = 200
_DEPTH_UPPER_THRESHOLD_MM = 30000
_KEYPOINT_RADIUS_PX = 5

_, args = initialize_argparser()
MODEL_DIR = Path(__file__).resolve().parent / "depthai_models"


def create_spatial_calculator(pipeline: dai.Pipeline, shrinking_factor: float):
    calculator = pipeline.create(dai.node.SpatialLocationCalculator)
    calculator.initialConfig.setDepthThresholds(
        _DEPTH_LOWER_THRESHOLD_MM, _DEPTH_UPPER_THRESHOLD_MM
    )
    calculator.initialConfig.setCalculationAlgorithm(
        dai.SpatialLocationCalculatorAlgorithm.AVERAGE
    )
    calculator.initialConfig.setStepSize(1)
    calculator.initialConfig.setBoundingBoxScaleFactor(1.0 - 2.0 * shrinking_factor)
    calculator.initialConfig.setCalculateSpatialKeypoints(True)
    calculator.initialConfig.setKeypointRadius(_KEYPOINT_RADIUS_PX)
    calculator.initialConfig.setUseSegmentation(False)
    # Set to blocking to avoid dropping and mismatching frames
    calculator.inputDetections.setBlocking(True)
    calculator.inputDetections.setMaxSize(2)
    calculator.inputDepth.setBlocking(True)
    calculator.inputDepth.setMaxSize(1)
    calculator.setRunOnHost(False)
    return calculator


def detector_frame_type(
    nn_archive: dai.NNArchive, platform: dai.Platform
) -> dai.ImgFrame.Type:
    """Frame type NeuralNetwork.build would request for this archive."""
    preprocessing = nn_archive.getConfigV1().model.inputs[0].preprocessing
    if preprocessing.daiType:
        return getattr(dai.ImgFrame.Type, preprocessing.daiType)
    if platform in (dai.Platform.RVC2, dai.Platform.RVC3):
        return dai.ImgFrame.Type.BGR888p
    return dai.ImgFrame.Type.BGR888i


visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()


with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    platform = device.getPlatform()

    model_description = dai.NNModelDescription.fromYamlFile(
        str(MODEL_DIR / f"yunet.{platform.name}.yaml")
    )
    nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))

    cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    resize_mode = nn_archive.getInputResizeMode() or dai.ImgResizeMode.CROP
    color_out = cam.requestOutput(
        nn_archive.getInputSize(),
        type=detector_frame_type(nn_archive, platform),
        resizeMode=resize_mode,
        fps=args.fps_limit,
        enableUndistortion=True,
    )

    depth = pipeline.create(dai.node.Depth)
    depth.build(
        dai.node.Depth.Algorithm.AUTO,
        fps=args.fps_limit,
        size=nn_archive.getInputSize(),
    )
    depth.setAlignTo(color_out)

    face_det_nn = pipeline.create(ParsingNeuralNetwork).build(color_out, nn_archive)
    if platform == dai.Platform.RVC2:
        face_det_nn.setNNArchive(nn_archive, numShaves=7)
    spatial_calculator = create_spatial_calculator(pipeline, shrinking_factor=0.0)
    face_det_nn.out.link(spatial_calculator.inputDetections)
    depth.depth.link(spatial_calculator.inputDepth)

    depth_color_transform = pipeline.create(ApplyDepthColormap).build(depth.depth)

    depth_driven_focus = pipeline.create(DepthDrivenFocus).build(
        control_queue=cam.inputControl.createInputQueue(),
        face_detection=spatial_calculator.outputDetections,
    )

    visualizer.addTopic("Video", color_out, "images")
    visualizer.addTopic("Visualizations", face_det_nn.out, "images")
    visualizer.addTopic("Depth", depth_color_transform.out, "images")
    visualizer.addTopic("Focus distance", depth_driven_focus.output, "images")

    print("Pipeline created.")
    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
