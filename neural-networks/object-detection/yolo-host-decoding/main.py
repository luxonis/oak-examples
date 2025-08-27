from pathlib import Path

import depthai as dai

from utils.arguments import initialize_argparser
from utils.host_decoding import HostDecoding

REQ_WIDTH, REQ_HEIGHT = (
    1280,
    720,
)  # we are requesting larger input size than required because we want to keep some resolution for the second stage model

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888p if platform == "RVC2" else dai.ImgFrame.Type.BGR888i
)

if args.fps_limit is None:
    args.fps_limit = 10 if platform == "RVC2" else 30
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # detection model
    det_model_description = dai.NNModelDescription.fromYamlFile(
        f"yolov6_nano_r2_coco.{platform}.yaml"
    )
    det_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))

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
            (REQ_WIDTH, REQ_HEIGHT), frame_type, fps=args.fps_limit
        )
    input_node_out = replay.out if args.media_path else cam_out

    # resize to det model input size
    crop_node = pipeline.create(dai.node.ImageManip)
    crop_node.initialConfig.setOutputSize(*det_model_nn_archive.getInputSize())
    crop_node.initialConfig.setFrameType(frame_type)
    crop_node.setMaxOutputFrameSize(
        det_model_nn_archive.getInputWidth() * det_model_nn_archive.getInputHeight() * 3
    )
    input_node_out.link(crop_node.inputImage)

    nn = pipeline.create(dai.node.NeuralNetwork).build(
        crop_node.out, det_model_nn_archive
    )

    # host decoding
    host_decoding_node = pipeline.create(HostDecoding).build(nn=nn.out)
    host_decoding_node.set_nn_size(det_model_nn_archive.getInputSize())
    host_decoding_node.set_conf_thresh(args.confidence_thresh)
    host_decoding_node.set_iou_thresh(args.iou_thresh)

    # visualization
    visualizer.addTopic("Camera", input_node_out)
    visualizer.addTopic("Detections", host_decoding_node.output)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
