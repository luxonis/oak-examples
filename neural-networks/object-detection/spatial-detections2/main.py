import depthai as dai
from depthai_nodes.node import ApplyColormap

from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888p if platform == "RVC2" else dai.ImgFrame.Type.BGR888i
)

if args.fps_limit is None:
    args.fps_limit = 20 if platform == "RVC2" else 30
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

available_cameras = device.getConnectedCameras()
if len(available_cameras) < 3:
    raise ValueError(
        "Device must have 3 cameras (color, left and right) in order to run this example."
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # detection model
    det_model_description = dai.NNModelDescription.fromYamlFile(
        f"yolov6_nano_r2_coco.{platform}.yaml"
    )
    if det_model_description.model != args.model:
        det_model_description = dai.NNModelDescription(args.model, platform=platform)
    det_model_nn_archive = dai.NNArchive(dai.getModelFromZoo(det_model_description))
    classes = det_model_nn_archive.getConfig().model.heads[0].metadata.classes
    nn_size = det_model_nn_archive.getInputSize()

    # camera input
    cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    
    # Request higher resolution for video stream (1080p if available, otherwise 720p)
    rgb_resolution = (1920, 1080) if platform == "RVC4" else (1280, 720)
    print(f"RGB stream resolution: {rgb_resolution[0]}x{rgb_resolution[1]}")
    print(f"NN input resolution: {nn_size[0]}x{nn_size[1]}")
    
    # Request high-res output for video encoding
    cam_high_res = cam.requestOutput(rgb_resolution, fps=args.fps_limit)

    left_cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    right_cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
    
    # Request stereo outputs for both traditional and neural depth
    left_out = left_cam.requestOutput(nn_size, fps=args.fps_limit)
    right_out = right_cam.requestOutput(nn_size, fps=args.fps_limit)
    
    stereo = pipeline.create(dai.node.StereoDepth).build(
        left=left_out,
        right=right_out,
        presetMode=dai.node.StereoDepth.PresetMode.HIGH_DETAIL,
    )
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    if platform == "RVC2":
        stereo.setOutputSize(*nn_size)
    stereo.setLeftRightCheck(True)
    stereo.setRectification(True)
    
    # Neural depth network (optional)
    neural_depth_network = None
    neural_depth_colormap = None
    neural_depth_encoder = None
    if args.neural_depth_model:
        print(f"Loading neural depth model: {args.neural_depth_model}")
        try:
            neural_model_description = dai.NNModelDescription(args.neural_depth_model, platform=platform)
            neural_model_archive = dai.NNArchive(dai.getModelFromZoo(neural_model_description))
            neural_input_size = neural_model_archive.getInputSize()
            
            # Request stereo outputs at neural model input size
            neural_left_out = left_cam.requestOutput(neural_input_size, fps=args.fps_limit)
            neural_right_out = right_cam.requestOutput(neural_input_size, fps=args.fps_limit)
            
            neural_depth_network = pipeline.create(dai.node.NeuralNetwork).build(
                nnArchive=neural_model_archive
            )
            neural_left_out.link(neural_depth_network.inputs["left"])
            neural_right_out.link(neural_depth_network.inputs["right"])
            
            # Apply colormap to neural depth
            neural_depth_colormap = pipeline.create(ApplyColormap).build(neural_depth_network.out)
            
            # Encode neural depth for visualization
            neural_depth_encoder_manip = pipeline.create(dai.node.ImageManip)
            neural_depth_encoder_manip.setMaxOutputFrameSize(neural_input_size[0] * neural_input_size[1] * 3)
            neural_depth_encoder_manip.initialConfig.setOutputSize(*neural_input_size)
            neural_depth_encoder_manip.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
            neural_depth_colormap.out.link(neural_depth_encoder_manip.inputImage)
            
            neural_depth_encoder = pipeline.create(dai.node.VideoEncoder)
            neural_depth_encoder.setMaxOutputFrameSize(neural_input_size[0] * neural_input_size[1] * 3)
            neural_depth_encoder.setDefaultProfilePreset(
                args.fps_limit, dai.VideoEncoderProperties.Profile.H264_MAIN
            )
            neural_depth_encoder_manip.out.link(neural_depth_encoder.input)
            
            print(f"Neural depth model loaded successfully. Input size: {neural_input_size[0]}x{neural_input_size[1]}")
        except Exception as e:
            print(f"Warning: Failed to load neural depth model: {e}")
            print("Continuing without neural depth stream.")
            args.neural_depth_model = None

    # SpatialDetectionNetwork will configure cam to output at NN size
    nn = pipeline.create(dai.node.SpatialDetectionNetwork).build(
        input=cam,
        stereo=stereo,
        nnArchive=det_model_nn_archive,
        fps=float(args.fps_limit),
    )
    if platform == "RVC2":
        nn.setNNArchive(
            det_model_nn_archive, numShaves=7
        )  # TODO: change to numShaves=4 if running on OAK-D Lite
    nn.setBoundingBoxScaleFactor(0.7)

    # annotation
    annotation_node = pipeline.create(AnnotationNode).build(
        input_detections=nn.out, depth=stereo.depth, labels=classes
    )

    apply_colormap = pipeline.create(ApplyColormap).build(stereo.depth)

    # video encoding - use high resolution stream
    # Convert high-res RGB to NV12 for encoding
    rgb_to_nv12 = pipeline.create(dai.node.ImageManip)
    rgb_to_nv12.initialConfig.setOutputSize(*rgb_resolution)
    rgb_to_nv12.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    rgb_to_nv12.setMaxOutputFrameSize(rgb_resolution[0] * rgb_resolution[1] * 3 // 2)
    cam_high_res.link(rgb_to_nv12.inputImage)
    
    video_encoder = pipeline.create(dai.node.VideoEncoder)
    video_encoder.setMaxOutputFrameSize(rgb_resolution[0] * rgb_resolution[1] * 3 // 2)
    video_encoder.setDefaultProfilePreset(
        args.fps_limit, dai.VideoEncoderProperties.Profile.H264_MAIN
    )
    rgb_to_nv12.out.link(video_encoder.input)

    # depth colormap encoding
    depth_encoder_manip = pipeline.create(dai.node.ImageManip)
    depth_encoder_manip.setMaxOutputFrameSize(nn_size[0] * nn_size[1] * 3)
    depth_encoder_manip.initialConfig.setOutputSize(*nn_size)
    depth_encoder_manip.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    apply_colormap.out.link(depth_encoder_manip.inputImage)

    depth_encoder = pipeline.create(dai.node.VideoEncoder)
    depth_encoder.setMaxOutputFrameSize(nn_size[0] * nn_size[1] * 3)
    depth_encoder.setDefaultProfilePreset(
        args.fps_limit, dai.VideoEncoderProperties.Profile.H264_MAIN
    )
    depth_encoder_manip.out.link(depth_encoder.input)

    # visualization
    visualizer.addTopic("Camera", video_encoder.out)
    visualizer.addTopic("Detections", annotation_node.out_annotations)
    visualizer.addTopic("Depth", depth_encoder.out)
    if neural_depth_encoder:
        visualizer.addTopic("Neural Depth", neural_depth_encoder.out)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
