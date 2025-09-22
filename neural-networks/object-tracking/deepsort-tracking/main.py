from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork, GatherData
from depthai_nodes.node.utils import generate_script_content

from utils.arguments import initialize_argparser
from utils.deepsort_tracking import DeepsortTracking

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
    args.fps_limit = 5 if platform == "RVC2" else 30
    print(
        f"FPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag."
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # detection model
    det_model_description = dai.NNModelDescription.fromYamlFile(
        f"yolov6_nano_r2_coco.{platform}.yaml"
    )
    det_model_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))
    det_model_w, det_model_h = det_model_archive.getInputSize()

    # embeddings model
    embeddings_model_description = dai.NNModelDescription.fromYamlFile(
        f"osnet_imagenet.{platform}.yaml"
    )
    embeddings_model_nn_archive = dai.NNArchive(
        dai.getModelFromZoo(embeddings_model_description)
    )
    embeddings_model_w, embeddings_model_h = embeddings_model_nn_archive.getInputSize()

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
    resize_node.setMaxOutputFrameSize(det_model_w * det_model_h * 3)
    resize_node.initialConfig.setOutputSize(
        det_model_w,
        det_model_h,
        dai.ImageManipConfig.ResizeMode.STRETCH,
    )
    resize_node.initialConfig.setFrameType(frame_type)
    input_node_out.link(resize_node.inputImage)

    det_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        resize_node.out, det_model_archive
    )

    # detection processing
    script = pipeline.create(dai.node.Script)
    det_nn.out.link(script.inputs["det_in"])
    det_nn.passthrough.link(script.inputs["preview"])
    script_content = generate_script_content(
        resize_width=embeddings_model_w,
        resize_height=embeddings_model_h,
        padding=0,
    )
    script.setScript(script_content)

    crop_node = pipeline.create(dai.node.ImageManip)
    crop_node.initialConfig.setOutputSize(embeddings_model_w, embeddings_model_h)

    script.outputs["manip_cfg"].link(crop_node.inputConfig)
    script.outputs["manip_img"].link(crop_node.inputImage)

    embeddings_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        crop_node.out, embeddings_model_nn_archive
    )

    # detections and embeddings sync
    gather_data = pipeline.create(GatherData).build(camera_fps=args.fps_limit)
    det_nn.out.link(gather_data.input_reference)
    embeddings_nn.out.link(gather_data.input_data)

    # tracking
    deepsort_tracking = pipeline.create(DeepsortTracking).build(
        img_frame=resize_node.out,
        gathered_data=gather_data.out,
        labels=det_model_archive.getConfigV1().model.heads[0].metadata.classes,
    )

    # visualization
    visualizer.addTopic("Video", input_node_out, "images")
    visualizer.addTopic("Detections", deepsort_tracking.out, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
