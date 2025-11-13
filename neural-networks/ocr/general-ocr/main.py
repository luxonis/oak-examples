from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, GatherData

from utils.annotation_node import OCRAnnotationNode
from utils.arguments import initialize_argparser
from utils.host_process_detections import CropConfigsCreator

REQ_WIDTH, REQ_HEIGHT = (
    1152,
    640,
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
    args.fps_limit = 5 if platform == "RVC2" else 30
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # text detection model
    det_model_description = dai.NNModelDescription.fromYamlFile(
        f"paddle_text_detection.{platform}.yaml"
    )
    det_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))
    det_model_w, det_model_h = det_model_nn_archive.getInputSize()

    # text recognition model
    rec_model_description = dai.NNModelDescription.fromYamlFile(
        f"paddle_text_recognition.{platform}.yaml"
    )
    rec_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(rec_model_description))
    rec_model_w, rec_model_h = rec_model_nn_archive.getInputSize()

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
    input_node_out.link(resize_node.inputImage)

    det_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        resize_node.out, det_model_nn_archive
    )
    det_nn.setNumPoolFrames(30)

    # detection processing
    detection_process_node = pipeline.create(CropConfigsCreator)
    detection_process_node.build(
        det_nn.out, (REQ_WIDTH, REQ_HEIGHT), (rec_model_w, rec_model_h)
    )

    crop_node = pipeline.create(dai.node.ImageManip)
    crop_node.initialConfig.setReusePreviousImage(False)
    crop_node.inputConfig.setReusePreviousMessage(False)
    crop_node.inputImage.setReusePreviousMessage(True)
    crop_node.inputConfig.setMaxSize(30)
    crop_node.inputImage.setMaxSize(30)
    crop_node.setNumFramesPool(30)

    detection_process_node.config_output.link(crop_node.inputConfig)
    input_node_out.link(crop_node.inputImage)

    ocr_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        crop_node.out, rec_model_nn_archive
    )
    ocr_nn.setNumPoolFrames(30)
    ocr_nn.input.setMaxSize(30)

    # detections and recognitions sync
    gather_data_node = pipeline.create(GatherData).build(args.fps_limit)
    detection_process_node.detections_output.link(gather_data_node.input_reference)
    ocr_nn.out.link(gather_data_node.input_data)

    # annotation
    annotation_node = pipeline.create(OCRAnnotationNode)
    gather_data_node.out.link(annotation_node.input)
    det_nn.passthrough.link(annotation_node.passthrough)

    # video encoding
    video_encode_manip = pipeline.create(dai.node.ImageManip)
    video_encode_manip.setMaxOutputFrameSize(REQ_WIDTH * REQ_HEIGHT * 3)
    video_encode_manip.initialConfig.setOutputSize(REQ_WIDTH, REQ_HEIGHT)
    video_encode_manip.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    annotation_node.frame_output.link(video_encode_manip.inputImage)

    video_encoder = pipeline.create(dai.node.VideoEncoder)
    video_encoder.setMaxOutputFrameSize(REQ_WIDTH * REQ_HEIGHT * 3)
    video_encoder.setDefaultProfilePreset(
        args.fps_limit, dai.VideoEncoderProperties.Profile.H264_MAIN
    )
    video_encode_manip.out.link(video_encoder.input)

    # visualization
    visualizer.addTopic("Video", video_encoder.out)
    visualizer.addTopic("Text", annotation_node.text_annotations_output)

    print("Pipeline created.")
    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
