import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork
from utils.arguments import initialize_argparser
from utils.host_triangulation import Triangulation
from utils.rectified_color import RectifiedColor

_, args = initialize_argparser()


def populate_pipeline(
    p: dai.Pipeline, rectified: dai.Node.Output, archive: dai.NNArchive
):
    platform = p.getDefaultDevice().getPlatform()
    frame_type = (
        dai.ImgFrame.Type.BGR888i
        if platform == dai.Platform.RVC4
        else dai.ImgFrame.Type.BGR888p
    )
    color = p.create(RectifiedColor).build(rectified, frame_type)
    face_nn = p.create(ParsingNeuralNetwork)
    if platform == dai.Platform.RVC2:
        # Leave room for stereo rectification and both networks in CMX.
        face_nn.setNNArchive(archive, numShaves=6)
    else:
        face_nn.setNNArchive(archive)
    color.output.link(face_nn.input)
    face_nn.setNumInferenceThreads(1)
    return face_nn.passthrough, face_nn.out


visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")
    device_platform = device.getPlatform()

    faceDet_modelDescription = dai.NNModelDescription.fromYamlFile(
        f"yunet.{device_platform.name}.yaml"
    )
    faceDet_nnarchive = dai.NNArchive(dai.getModelFromZoo(faceDet_modelDescription))
    model_dimension = (
        faceDet_nnarchive.getInputWidth(),
        faceDet_nnarchive.getInputHeight(),
    )

    left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
    raw_left = left.requestOutput(model_dimension, type=dai.ImgFrame.Type.NV12, fps=30)
    raw_right = right.requestOutput(
        model_dimension, type=dai.ImgFrame.Type.NV12, fps=30
    )
    stereo = pipeline.create(dai.node.StereoDepth).build(left=raw_left, right=raw_right)
    stereo.enableDistortionCorrection(True)
    stereo.setRectificationUseSpecTranslation(False)
    stereo.setRectifyEdgeFillColor(0)
    rect_left, rect_right = stereo.rectifiedLeft, stereo.rectifiedRight
    face_left, face_nn_left = populate_pipeline(pipeline, rect_left, faceDet_nnarchive)
    face_right, face_nn_right = populate_pipeline(
        pipeline, rect_right, faceDet_nnarchive
    )

    triangulation = pipeline.create(Triangulation).build(
        face_left=face_left,
        face_right=face_right,
        face_nn_left=face_nn_left,
        face_nn_right=face_nn_right,
        device=device,
    )

    visualizer.addTopic("Face Left", face_left, "left")
    visualizer.addTopic("Left Detections", triangulation.bbox_left, "left")
    visualizer.addTopic("Left Keypoints", triangulation.keypoints_left, "left")

    visualizer.addTopic("Face Right", face_right, "right")
    visualizer.addTopic("Right Detections", triangulation.bbox_right, "right")
    visualizer.addTopic("Right Keypoints", triangulation.keypoints_right, "right")

    visualizer.addTopic("Combined", triangulation.combined_frame, "combined")
    visualizer.addTopic("Left Face Detections", triangulation.bbox_left, "combined")
    visualizer.addTopic("Right Face Detections", triangulation.bbox_right, "combined")
    visualizer.addTopic(
        "Left Keypoints Combined", triangulation.keypoints_left, "combined"
    )
    visualizer.addTopic(
        "Right Keypoints Combined", triangulation.keypoints_right, "combined"
    )
    visualizer.addTopic("Disparity line", triangulation.disparity_line, "combined")
    visualizer.addTopic(
        "Measurements Info", triangulation.measurements_info, "combined"
    )

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
