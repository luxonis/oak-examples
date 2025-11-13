from pathlib import Path
import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork

from utils.arguments import initialize_argparser
from utils.crop_face import CropFace

REQ_WIDTH = 3840
REQ_HEIGHT = 2880

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform()
print(f"Platform: {platform.name}")

fps = args.fps_limit
if fps is None:
    fps = 30 if platform == dai.Platform.RVC4 else 5

frame_type = (
    dai.ImgFrame.Type.BGR888i
    if platform == dai.Platform.RVC4
    else dai.ImgFrame.Type.BGR888p
)

model_description = dai.NNModelDescription.fromYamlFile(f"yunet.{platform.name}.yaml")
nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))
model_width = nn_archive.getInputWidth()
model_height = nn_archive.getInputHeight()

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(dai.ImgFrame.Type.NV12)
        replay.setLoop(True)
        replay.setFps(fps)
        cam_out = replay.out
    else:
        cam = pipeline.create(dai.node.Camera).build()
        cam_out = cam.requestOutput(
            (REQ_WIDTH, REQ_HEIGHT), dai.ImgFrame.Type.NV12, fps=fps
        )

    image_manip = pipeline.create(dai.node.ImageManip)
    image_manip.setMaxOutputFrameSize(model_width * model_height * 3)
    image_manip.initialConfig.setOutputSize(model_width, model_height)
    image_manip.initialConfig.setFrameType(frame_type)
    cam_out.link(image_manip.inputImage)

    nn_with_parser: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        image_manip.out, nn_archive
    )

    crop_face = pipeline.create(CropFace).build(
        nn_with_parser.out,
        source_size=(REQ_WIDTH, REQ_HEIGHT),
        target_size=(1920, 1088),
    )

    crop_manip = pipeline.create(dai.node.ImageManip)
    crop_manip.inputConfig.setReusePreviousMessage(False)

    crop_manip.setMaxOutputFrameSize(1920 * 1088 * 3)
    crop_face.config_output.link(crop_manip.inputConfig)
    cam_out.link(crop_manip.inputImage)

    crop_encoder = pipeline.create(dai.node.VideoEncoder)
    crop_encoder.setMaxOutputFrameSize(1920 * 1088 * 3)
    crop_encoder.setDefaultProfilePreset(
        fps, dai.VideoEncoderProperties.Profile.H264_MAIN
    )
    crop_manip.out.link(crop_encoder.input)

    video_encode_manip = pipeline.create(dai.node.ImageManip)
    video_encode_manip.setMaxOutputFrameSize(model_width * model_height * 3)
    video_encode_manip.initialConfig.setOutputSize(model_width, model_height)
    video_encode_manip.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    nn_with_parser.passthrough.link(video_encode_manip.inputImage)

    video_encoder = pipeline.create(dai.node.VideoEncoder)
    video_encoder.setMaxOutputFrameSize(model_width * model_height * 3)
    video_encoder.setDefaultProfilePreset(
        fps, dai.VideoEncoderProperties.Profile.H264_MAIN
    )
    video_encode_manip.out.link(video_encoder.input)

    visualizer.addTopic("Video", video_encoder.out, "images")
    visualizer.addTopic("Visualizations", nn_with_parser.out, "images")
    visualizer.addTopic("Cropped Face", crop_encoder.out, "crop")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
