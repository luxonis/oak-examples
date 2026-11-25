import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, DepthMerger

from utils.host_bird_eye_view import BirdsEyeView
from utils.measure_object_distance import MeasureObjectDistance
from utils.host_distance_annotations import DistanceAnnotations
from utils.arguments import initialize_argparser

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888i if platform == "RVC4" else dai.ImgFrame.Type.BGR888p
)

if args.fps_limit is None:
    args.fps_limit = 10 if platform == "RVC2" else 10
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # Detect people before adding depth and measuring their distances.
    det_model_description = dai.NNModelDescription.fromYamlFile(
        f"scrfd_person_detection_25g.{platform}.yaml"
    )
    det_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))

    # camera input
    cam = pipeline.create(dai.node.Camera).build(
        boardSocket=dai.CameraBoardSocket.CAM_A
    )
    rgb = cam.requestOutput(
        size=det_model_nn_archive.getInputSize(),
        type=frame_type,
        fps=args.fps_limit,
        enableUndistortion=True,
    )

    depth = pipeline.create(dai.node.Depth).build(
        dai.node.Depth.Algorithm.AUTO, fps=args.fps_limit
    )
    depth.setAlignTo(rgb)

    nn_parser: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        input=rgb,
        nnSource=det_model_nn_archive,
    )
    if platform == "RVC2":
        nn_parser.setNNArchive(det_model_nn_archive, numShaves=7)

    # produce spatial detections
    depth_merger = pipeline.create(DepthMerger).build(
        output2d=nn_parser.out,
        outputDepth=depth.depth,
        calibData=device.readCalibration2(),
        depthAlignmentSocket=dai.CameraBoardSocket.CAM_A,
        shrinkingFactor=0.1,
    )

    # Measure all detected person pairs once, then show the distances in both views.
    measure_obj_dist = pipeline.create(MeasureObjectDistance).build(depth_merger.output)
    bird_eye_view = pipeline.create(BirdsEyeView).build(measure_obj_dist.output)
    distance_annotations = pipeline.create(DistanceAnnotations).build(
        measure_obj_dist.output
    )

    # visualization
    visualizer.addTopic("Video", rgb, "images")
    visualizer.addTopic("Detections", nn_parser.out, "images")
    visualizer.addTopic("Pairwise distances", distance_annotations.output, "images")
    visualizer.addTopic("Bird's-eye view", bird_eye_view.output, "bird-eye")

    print("Pipeline created.")
    pipeline.start()
    print("Pipeline started.")
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
