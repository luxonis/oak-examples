import depthai as dai

from depthai_nodes.node import ParsingNeuralNetwork, ImgDetectionsFilter

from utils.helper_functions import extract_text_embeddings, read_intrinsics

from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode
from utils.measurement_node import MeasurementNode

_, args = initialize_argparser()

IP = args.ip or "localhost"
PORT = args.port or 8080

CLASS_NAMES = ["person", "chair", "TV"]
MAX_NUM_CLASSES = 80
CONFIDENCE_THRESHOLD = 0.15

visualizer = dai.RemoteConnection(serveFrontend=False)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()

platform = device.getPlatformAsString()

if platform != "RVC4":
    raise ValueError("This example is supported only on RVC4 platform")

device.setIrLaserDotProjectorIntensity(1.0)
device.setIrFloodLightIntensity(1)

frame_type = dai.ImgFrame.Type.BGR888i
text_features = extract_text_embeddings(
    class_names=CLASS_NAMES, max_num_classes=MAX_NUM_CLASSES
)

if args.fps_limit is None:
    args.fps_limit = 8
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    model_description = dai.NNModelDescription.fromYamlFile(
        f"yoloe_v8_l.{platform}.yaml"
    )
    model_description.platform = platform
    model_nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))
    model_w, model_h = model_nn_archive.getInputSize()

    cam = pipeline.create(dai.node.Camera).build(
        boardSocket=dai.CameraBoardSocket.CAM_A
    )
    cam_out = cam.requestOutput(
        size=(640, 400), type=dai.ImgFrame.Type.RGB888i, fps=args.fps_limit
    )

    left = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    right = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
    left_out = left.requestOutput(
        (640, 400), type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )
    right_out = right.requestOutput(
        (640, 400), type=dai.ImgFrame.Type.NV12, fps=args.fps_limit
    )

    stereo = pipeline.create(dai.node.StereoDepth).build(
        left=left_out,
        right=right_out,
        presetMode=dai.node.StereoDepth.PresetMode.DEFAULT,
    )

    imu = pipeline.create(dai.node.IMU)
    imu.enableIMUSensor(dai.IMUSensor.ACCELEROMETER_RAW, 100)
    imu.setBatchReportThreshold(10)
    imu.setMaxBatchReports(10)

    manip = pipeline.create(dai.node.ImageManip)
    manip.initialConfig.setOutputSize(
        model_w, model_h, dai.ImageManipConfig.ResizeMode.LETTERBOX
    )
    manip.initialConfig.setFrameType(frame_type)
    manip.setMaxOutputFrameSize(model_w * model_h * 3)

    align = pipeline.create(dai.node.ImageAlign)

    stereo.depth.link(align.input)
    cam_out.link(align.inputAlignTo)
    cam_out.link(manip.inputImage)

    input_node = manip.out

    nn_with_parser = pipeline.create(ParsingNeuralNetwork)
    nn_with_parser.setNNArchive(model_nn_archive)
    nn_with_parser.setBackend("snpe")
    nn_with_parser.setBackendProperties(
        {"runtime": "dsp", "performance_profile": "default"}
    )
    nn_with_parser.setNumInferenceThreads(1)
    nn_with_parser.getParser(0).setConfidenceThreshold(CONFIDENCE_THRESHOLD)

    input_node.link(nn_with_parser.inputs["images"])

    textInputQueue = nn_with_parser.inputs["texts"].createInputQueue()
    nn_with_parser.inputs["texts"].setReusePreviousMessage(True)

    det_process_filter = pipeline.create(ImgDetectionsFilter).build(nn_with_parser.out)
    det_process_filter.setLabels(labels=[i for i in range(len(CLASS_NAMES))], keep=True)

    # Annotation node
    annotation_node = pipeline.create(AnnotationNode).build(
        det_process_filter.out,
        cam_out,
        align.outputAligned,
        label_encoding={k: v for k, v in enumerate(CLASS_NAMES)},
    )

    # RGBD node for the segmented PCL
    rgbd_seg = pipeline.create(dai.node.RGBD).build()
    annotation_node.out_segm.link(rgbd_seg.inColor)
    annotation_node.out_segm_depth.link(rgbd_seg.inDepth)

    # Measurement node
    measurement_node = pipeline.create(MeasurementNode).build(
        rgbd_seg.pcl, annotation_node.out_selection, imu.out
    )
    measurement_node.out_result.link(annotation_node.in_meas_result)

    fx, fy, cx, cy = read_intrinsics(device, 640, 400)
    measurement_node.setIntrinsics(fx, fy, cx, cy, imgW=640, imgH=400)
    measurement_node.an_node = annotation_node

    # Service functions for all functionalities of the frontend
    def class_update_service(new_classes: list[str]):
        """Changes classes to detect based on the user input"""
        if len(new_classes) == 0:
            print("List of new classes empty, skipping.")
            return
        if len(new_classes) > MAX_NUM_CLASSES:
            print(
                f"Number of new classes ({len(new_classes)}) exceeds maximum number of classes ({MAX_NUM_CLASSES}), skipping."
            )
            return
        CLASS_NAMES = new_classes

        text_features = extract_text_embeddings(
            class_names=CLASS_NAMES,
            max_num_classes=MAX_NUM_CLASSES,
        )
        inputNNData = dai.NNData()
        inputNNData.addTensor(
            "texts", text_features, dataType=dai.TensorInfo.DataType.FP16
        )
        textInputQueue.send(inputNNData)

        det_process_filter.setLabels(
            labels=[i for i in range(len(CLASS_NAMES))], keep=True
        )
        annotation_node.setLabelEncoding({k: v for k, v in enumerate(CLASS_NAMES)})
        print(f"Classes set to: {CLASS_NAMES}")

    def conf_threshold_update_service(new_conf_threshold: float):
        """Changes confidence threshold based on the user input"""
        CONFIDENCE_THRESHOLD = max(0, min(1, new_conf_threshold))
        nn_with_parser.getParser(0).setConfidenceThreshold(CONFIDENCE_THRESHOLD)
        print(f"Confidence threshold set to: {CONFIDENCE_THRESHOLD}:")

    def selection_service(clicks: dict):
        """Changes selected object based on the user click"""
        if clicks.get("clear"):
            annotation_node.clearSelection()
            return {"ok": True, "cleared": True}
        try:
            x = float(clicks["x"])
            y = float(clicks["y"])
        except Exception as e:
            return {"ok": False, "error": f"bad payload: {e}"}

        annotation_node.setSelectionPoint(x, y)
        annotation_node.setKeepTopOnly(True)

        measurement_node.reset_measurements()
        annotation_node.clearCachedMeasurements()
        print(f"Selection point set to ({x:.3f}, {y:.3f})")
        return {"ok": True}

    def measurement_method_service(payload: dict):
        """
        Changes measurement method based on the user input
        Expects: {"method": "obb"|"heightgrid"}
        """
        method = str(payload.get("method", "")).lower()
        if method not in ("obb", "heightgrid"):
            return {"ok": False, "error": f"unknown method '{method}'"}
        measurement_node.measurement_mode = method
        if method == "heightgrid":
            annotation_node.requestPlaneCapture(True)
        else:
            annotation_node.requestPlaneCapture(False)
        measurement_node.reset_measurements()
        print("Selected method: ", method)
        return {"ok": True, "method": method, "have_plane": measurement_node.have_plane}

    # Connect the services in the frontend to functions in the backend
    visualizer.registerService("Selection Service", selection_service)
    visualizer.registerService("Class Update Service", class_update_service)
    visualizer.registerService(
        "Threshold Update Service", conf_threshold_update_service
    )
    visualizer.registerService("Measurement Method Service", measurement_method_service)

    visualizer.addTopic("Video", cam_out, "images")
    visualizer.addTopic("Detections", annotation_node.out_ann, "images")
    visualizer.addTopic("Pointclouds", rgbd_seg.pcl, "point_clouds")
    visualizer.addTopic("Measurement Overlay", measurement_node.out_ann, "images")
    visualizer.addTopic("Plane Status", measurement_node.out_plane_status, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    inputNNData = dai.NNData()
    inputNNData.addTensor("texts", text_features, dataType=dai.TensorInfo.DataType.FP16)
    textInputQueue.send(inputNNData)

    print("Press 'q' to stop")

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
