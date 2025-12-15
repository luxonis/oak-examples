import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork
from typing import Tuple
from utils.host_triangulation import Triangulation
from utils.arguments import initialize_argparser


_, args = initialize_argparser()


# Creates and connects nodes, once for the left camera and once for the right camera
def populate_pipeline(
    p: dai.Pipeline, left: bool, archive: dai.NNArchive
) -> Tuple[dai.Node.Output, dai.Node.Output]:
    socket = dai.CameraBoardSocket.CAM_B if left else dai.CameraBoardSocket.CAM_C
    cam = p.create(dai.node.Camera).build(socket)
    fps = 30
    cam_output = cam.requestOutput(
        archive.getInputSize(), type=dai.ImgFrame.Type.NV12, fps=fps
    )

    face_nn = p.create(ParsingNeuralNetwork).build(cam, faceDet_nnarchive, fps)

    return cam_output, face_nn.out


def create_video_encoder(p: dai.Pipeline, input_node: dai.Node, fps: float, size: int):
    video_encoder = p.create(dai.node.VideoEncoder)
    video_encoder.setMaxOutputFrameSize(size)
    video_encoder.setDefaultProfilePreset(
        fps, dai.VideoEncoderProperties.Profile.H264_MAIN
    )
    input_node.link(video_encoder.input)
    return video_encoder.out


visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")
    device_platform = device.getPlatform()
    rvc2 = device_platform == dai.Platform.RVC2

    faceDet_modelDescription = dai.NNModelDescription.fromYamlFile(
        f"yunet.{device_platform.name}.yaml"
    )
    faceDet_nnarchive = dai.NNArchive(dai.getModelFromZoo(faceDet_modelDescription))
    model_dimension = (
        faceDet_nnarchive.getInputWidth(),
        faceDet_nnarchive.getInputHeight(),
    )

    face_left, face_nn_left = populate_pipeline(pipeline, True, faceDet_nnarchive)
    face_right, face_nn_right = populate_pipeline(pipeline, False, faceDet_nnarchive)

    triangulation = pipeline.create(Triangulation).build(
        face_left=face_left,
        face_right=face_right,
        face_nn_left=face_nn_left,
        face_nn_right=face_nn_right,
        device=device,
        resolution_number=model_dimension,
    )

    face_left_encoded = create_video_encoder(
        p=pipeline,
        input_node=face_left,
        fps=30,
        size=model_dimension[0] * model_dimension[1],
    )
    visualizer.addTopic("Face Left", face_left_encoded, "left")
    visualizer.addTopic("Left Detections", triangulation.bbox_left, "left")
    visualizer.addTopic("Left Keypoints", triangulation.keypoints_left, "left")

    face_right_encoded = create_video_encoder(
        p=pipeline,
        input_node=face_right,
        fps=30,
        size=model_dimension[0] * model_dimension[1],
    )
    visualizer.addTopic("Face Right", face_right_encoded, "right")
    visualizer.addTopic("Right Detections", triangulation.bbox_right, "right")
    visualizer.addTopic("Right Keypoints", triangulation.keypoints_right, "right")

    combined_encoded = create_video_encoder(
        p=pipeline,
        input_node=triangulation.combined_frame,
        fps=30,
        size=model_dimension[0] * model_dimension[1],
    )
    visualizer.addTopic("Combined", combined_encoded, "combined")
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
