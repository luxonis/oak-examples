from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, GatherData, ImgDetectionsBridge
from depthai_nodes.node.utils import generate_script_content

from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode

REQ_WIDTH, REQ_HEIGHT = (
    1024,
    768,
)  # we are requesting larger input size than required because we want to keep some resolution for the second stage model

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888i if platform == "RVC4" else dai.ImgFrame.Type.BGR888p
)

if args.fps_limit is None:
    args.fps_limit = 14 if platform == "RVC2" else 30
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # face detection model
    det_model_description = dai.NNModelDescription.fromYamlFile(
        f"yunet.{platform}.yaml"
    )
    det_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))
    det_model_w, det_model_h = det_model_nn_archive.getInputSize()

    # age-gender recognition model
    rec_model_description = dai.NNModelDescription.fromYamlFile(
        f"age_gender_recognition.{platform}.yaml"
    )
    rec_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(rec_model_description))

    # media/camera input
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(frame_type)
        replay.setLoop(True)
        if args.fps_limit:
            replay.setFps(args.fps_limit)
        replay.setSize(REQ_WIDTH, REQ_HEIGHT)
    else:
        cam = pipeline.create(dai.node.Camera).build()
        cam_out = cam.requestOutput(
            size=(REQ_WIDTH, REQ_HEIGHT), type=frame_type, fps=args.fps_limit
        )
    input_node_out = replay.out if args.media_path else cam_out

    # resize to det model input size
    resize_node = pipeline.create(dai.node.ImageManip)
    resize_node.initialConfig.setOutputSize(det_model_w, det_model_h)
    resize_node.initialConfig.setReusePreviousImage(False)
    resize_node.inputImage.setBlocking(True)
    input_node_out.link(resize_node.inputImage)

    det_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        resize_node.out, det_model_nn_archive
    )
    det_nn.getParser(0).conf_threshold = 0.9  # for more stable detections

    # detection processing
    det_bridge = pipeline.create(ImgDetectionsBridge).build(
        det_nn.out
    )  # TODO: remove once we have it working with ImgDetectionsExtended
    script_node = pipeline.create(dai.node.Script)
    det_bridge.out.link(script_node.inputs["det_in"])
    input_node_out.link(script_node.inputs["preview"])
    script_content = generate_script_content(
        resize_width=rec_model_nn_archive.getInputWidth(),
        resize_height=rec_model_nn_archive.getInputHeight(),
    )
    script_node.setScript(script_content)

    crop_node = pipeline.create(dai.node.ImageManip)
    crop_node.initialConfig.setOutputSize(
        rec_model_nn_archive.getInputWidth(), rec_model_nn_archive.getInputHeight()
    )
    crop_node.inputConfig.setWaitForMessage(True)

    script_node.outputs["manip_cfg"].link(crop_node.inputConfig)
    script_node.outputs["manip_img"].link(crop_node.inputImage)

    rec_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        crop_node.out, rec_model_nn_archive
    )

    # detections and recognitions sync
    gather_data_node = pipeline.create(GatherData).build(args.fps_limit)
    rec_nn.outputs.link(gather_data_node.input_data)
    det_nn.out.link(gather_data_node.input_reference)

    # annotation
    annotation_node = pipeline.create(AnnotationNode).build(gather_data_node.out)

    # video encoding
    video_encode_manip = pipeline.create(dai.node.ImageManip)
    video_encode_manip.setMaxOutputFrameSize(REQ_WIDTH * REQ_HEIGHT * 3)
    video_encode_manip.initialConfig.setOutputSize(REQ_WIDTH, REQ_HEIGHT)
    video_encode_manip.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    input_node_out.link(video_encode_manip.inputImage)

    video_encoder = pipeline.create(dai.node.VideoEncoder)
    video_encoder.setMaxOutputFrameSize(REQ_WIDTH * REQ_HEIGHT * 3)
    video_encoder.setDefaultProfilePreset(
        args.fps_limit, dai.VideoEncoderProperties.Profile.H264_MAIN
    )
    video_encode_manip.out.link(video_encoder.input)

    # visualization
    visualizer.addTopic("Video", video_encoder.out, "images")
    visualizer.addTopic("AgeGender", annotation_node.out, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
