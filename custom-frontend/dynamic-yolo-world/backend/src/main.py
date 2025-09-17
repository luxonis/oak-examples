from pathlib import Path
import numpy as np

import depthai as dai
from depthai_nodes.node import (
    ParsingNeuralNetwork,
    ImgDetectionsFilter,
    ImgFrameOverlay,
    ApplyColormap,
)

from utils.helper_functions import (
    extract_text_embeddings,
    extract_image_prompt_embeddings,
    base64_to_cv2_image,
)
from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode
from utils.frame_cache_node import FrameCacheNode

_, args = initialize_argparser()

IP = args.ip or "localhost"
PORT = args.port or 8080

CLASS_NAMES = ["person", "chair", "TV"]
MAX_NUM_CLASSES = 80
CONFIDENCE_THRESHOLD = 0.1
VISUALIZATION_RESOLUTION = (1080, 1080)

visualizer = dai.RemoteConnection(serveFrontend=False)
device = dai.Device()
platform = device.getPlatformAsString()

if platform != "RVC4":
    raise ValueError("This example is supported only on RVC4 platform")

frame_type = dai.ImgFrame.Type.BGR888i
# choose initial features: text for yolo-world/yoloe, visual for yoloe-image
if args.model == "yoloe-image":
    placeholder = np.zeros((224, 224, 3), dtype=np.uint8)
    text_features = extract_image_prompt_embeddings(
        placeholder,
        max_num_classes=MAX_NUM_CLASSES,
        model_name=args.model,
        precision=args.precision,
    )
    CLASS_NAMES = ["image_prompt"]
else:
    text_features = extract_text_embeddings(
        class_names=CLASS_NAMES,
        max_num_classes=MAX_NUM_CLASSES,
        model_name=args.model,
        precision=args.precision,
    )

if args.fps_limit is None:
    args.fps_limit = 5
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # Model selection with precision-aware YAMLs for YOLOE variants
    if args.model == "yolo-world":
        model_description = dai.NNModelDescription.fromYamlFile(
            f"yolo_world_l.{platform}.yaml"
        )
    elif args.model == "yoloe":
        yaml_base = "yoloe_v8_l_fp16" if args.precision == "fp16" else "yoloe_v8_l"
        model_description = dai.NNModelDescription.fromYamlFile(
            f"{yaml_base}.{platform}.yaml"
        )
    elif args.model == "yoloe-image":
        yaml_base = (
            "yoloe_v8_l_image_fp16" if args.precision == "fp16" else "yoloe_v8_l_image"
        )
        model_description = dai.NNModelDescription.fromYamlFile(
            f"{yaml_base}.{platform}.yaml"
        )
    model_description.platform = platform
    model_nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))
    model_w, model_h = model_nn_archive.getInputSize()

    # media/camera input at high resolution for visualization
    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(dai.ImgFrame.Type.NV12)
        replay.setLoop(True)
        if args.fps_limit:
            replay.setFps(args.fps_limit)
        replay.setSize(VISUALIZATION_RESOLUTION[0], VISUALIZATION_RESOLUTION[1])
        video_src_out = replay.out
    else:
        cam = pipeline.create(dai.node.Camera).build(
            boardSocket=dai.CameraBoardSocket.CAM_A
        )
        # Request high-res NV12 frames for visualization/encoding
        video_src_out = cam.requestOutput(
            size=VISUALIZATION_RESOLUTION,
            type=dai.ImgFrame.Type.NV12,
            fps=args.fps_limit,
        )

    image_manip = pipeline.create(dai.node.ImageManip)
    image_manip.setMaxOutputFrameSize(model_w * model_h * 3)
    image_manip.initialConfig.setOutputSize(model_w, model_h)
    image_manip.initialConfig.setFrameType(frame_type)
    video_src_out.link(image_manip.inputImage)

    video_enc = pipeline.create(dai.node.VideoEncoder)
    video_enc.setDefaultProfilePreset(
        fps=args.fps_limit, profile=dai.VideoEncoderProperties.Profile.H264_MAIN
    )
    video_src_out.link(video_enc.input)

    input_node = image_manip.out

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

    # filter and rename detection labels
    det_process_filter = pipeline.create(ImgDetectionsFilter).build(nn_with_parser.out)
    det_process_filter.setLabels(labels=[i for i in range(len(CLASS_NAMES))], keep=True)
    annotation_node = pipeline.create(AnnotationNode).build(
        det_process_filter.out,
        video_src_out,
        label_encoding={k: v for k, v in enumerate(CLASS_NAMES)},
    )
    # Cache last frame for services that need full frame content
    frame_cache = pipeline.create(FrameCacheNode).build(video_src_out)

    if args.model == "yolo-world":
        visualizer.addTopic("Video", video_enc.out, "images")
    elif args.model in ("yoloe", "yoloe-image"):
        apply_colormap_node = pipeline.create(ApplyColormap).build(nn_with_parser.out)
        overlay_frames_node = pipeline.create(ImgFrameOverlay).build(
            video_src_out,
            apply_colormap_node.out,
        )
        overlay_to_nv12 = pipeline.create(dai.node.ImageManip)
        overlay_to_nv12.setMaxOutputFrameSize(
            VISUALIZATION_RESOLUTION[0] * VISUALIZATION_RESOLUTION[1] * 3
        )
        overlay_to_nv12.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
        overlay_frames_node.out.link(overlay_to_nv12.inputImage)

        overlay_enc = pipeline.create(dai.node.VideoEncoder)
        overlay_enc.setDefaultProfilePreset(
            fps=args.fps_limit, profile=dai.VideoEncoderProperties.Profile.H264_MAIN
        )
        overlay_to_nv12.out.link(overlay_enc.input)

        visualizer.addTopic("Video", overlay_enc.out, "images")

    visualizer.addTopic("Detections", annotation_node.out)

    def class_update_service(new_classes: list[str]):
        """Changes classes to detect based on the user input"""
        if args.model == "yoloe-image":
            print(
                "Class update is disabled in yoloe-image mode. Upload a new image prompt instead."
            )
            return
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
            model_name=args.model,
            precision=args.precision,
        )
        inputNNData = dai.NNData()
        inputNNData.addTensor(
            "texts",
            text_features,
            dataType=(
                dai.TensorInfo.DataType.FP16
                if args.model in ("yoloe", "yoloe-image") and args.precision == "fp16"
                else dai.TensorInfo.DataType.U8F
            ),
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

    def image_upload_service(image_data):
        image = base64_to_cv2_image(image_data["data"])
        image_features = extract_image_prompt_embeddings(
            image, model_name=args.model, precision=args.precision
        )
        print("Image features extracted, sending to model...")
        inputNNData = dai.NNData()
        inputNNData.addTensor(
            "texts",
            image_features,
            dataType=(
                dai.TensorInfo.DataType.FP16
                if args.model in ("yoloe", "yoloe-image") and args.precision == "fp16"
                else dai.TensorInfo.DataType.U8F
            ),
        )
        textInputQueue.send(inputNNData)

        filename = image_data["filename"]
        CLASS_NAMES = [filename.split(".")[0]]

        det_process_filter.setLabels(
            labels=[i for i in range(len(CLASS_NAMES))], keep=True
        )
        annotation_node.setLabelEncoding({k: v for k, v in enumerate(CLASS_NAMES)})
        print(f"Classes set to: {CLASS_NAMES}")

    def bbox_prompt_service(payload):
        """
        Accepts a full-frame PNG (base64) plus a normalized bbox {x,y,width,height} in viewport space.
        - For yolo-world: crops the bbox region and extracts image prompt features from the crop.
        - For yoloe-image: builds a binary mask from the bbox over the full frame and extracts features with mask_prompt.
        """
        print("[BBox] Service payload keys:", list(payload.keys()))
        # Try FE-provided image first, else fall back to cached live frame
        image = base64_to_cv2_image(payload["data"]) if payload.get("data") else None
        if image is None:
            image = frame_cache.get_last_frame()
            if image is None:
                print("[BBox] No image data and no cached frame available")
                return {"ok": False, "reason": "no_image"}
        if image is None:
            print("[BBox] Decoded image is None")
            return {"ok": False, "reason": "decode_failed"}
        if (image == 0).all():
            print("[BBox] Warning: decoded image is all zeros")
        # print image stats
        print(f"[BBox] Image shape: {image.shape}")
        print(f"[BBox] Image dtype: {image.dtype}")
        print(f"[BBox] Image min: {image.min()}")
        print(f"[BBox] Image max: {image.max()}")
        print(f"[BBox] Image mean: {image.mean()}")
        print(f"[BBox] Image std: {image.std()}")

        bbox = payload.get("bbox", {})
        bx = float(bbox.get("x", 0.0))
        by = float(bbox.get("y", 0.0))
        bw = float(bbox.get("width", 0.0))
        bh = float(bbox.get("height", 0.0))

        H, W = image.shape[:2]
        is_pixel = payload.get("bboxType", "normalized") == "pixel"
        if is_pixel:
            x0 = int(round(bx))
            y0 = int(round(by))
            x1 = int(round(bx + bw))
            y1 = int(round(by + bh))
        else:
            # bbox is normalized in source frame space
            x0 = int(round(bx * W))
            y0 = int(round(by * H))
            x1 = int(round((bx + bw) * W))
            y1 = int(round((by + bh) * H))

        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        print(f"[BBox] Image size: {W}x{H}, bbox(px): x0={x0}, y0={y0}, x1={x1}, y1={y1}")

        if x1 <= x0 or y1 <= y0:
            print("Invalid bbox, ignoring bbox prompt request.")
            return {"ok": False, "reason": "invalid_bbox"}

        if args.model == "yolo-world":
            crop = image[y0:y1, x0:x1]
            print(f"[BBox] YOLO-World crop shape: {crop.shape if crop is not None else None}")
            image_features = extract_image_prompt_embeddings(
                crop, model_name=args.model, precision=args.precision
            )
        elif args.model == "yoloe-image":
            mask = np.zeros((H, W), dtype=np.float32)
            mask[y0:y1, x0:x1] = 1.0
            print(f"[BBox] YOLOE-Image mask sum: {float(mask.sum())}")
            image_features = extract_image_prompt_embeddings(
                image,
                model_name=args.model,
                mask_prompt=mask,
                precision=args.precision,
            )
        else:
            print(f"Unsupported model for bbox prompt: {args.model}")
            return {"ok": False, "reason": "unsupported_model"}

        inputNNData = dai.NNData()
        inputNNData.addTensor(
            "texts",
            image_features,
            dataType=(
                dai.TensorInfo.DataType.FP16
                if args.model in ("yoloe", "yoloe-image") and args.precision == "fp16"
                else dai.TensorInfo.DataType.U8F
            ),
        )
        textInputQueue.send(inputNNData)

        label = payload.get("label", "object")
        CLASS_NAMES = [label]
        det_process_filter.setLabels(
            labels=[i for i in range(len(CLASS_NAMES))], keep=True
        )
        annotation_node.setLabelEncoding({k: v for k, v in enumerate(CLASS_NAMES)})
        print(f"BBox prompt applied. Classes set to: {CLASS_NAMES}")
        return {"ok": True, "bbox": {"x0": x0, "y0": y0, "x1": x1, "y1": y1}}

    visualizer.registerService("Class Update Service", class_update_service)
    visualizer.registerService(
        "Threshold Update Service", conf_threshold_update_service
    )
    if args.model == "yolo-world":
        visualizer.registerService("Image Upload Service", image_upload_service)
    elif args.model == "yoloe-image":
        visualizer.registerService("Image Upload Service", image_upload_service)
    visualizer.registerService("BBox Prompt Service", bbox_prompt_service)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    inputNNData = dai.NNData()
    inputNNData.addTensor(
        "texts",
        text_features,
        dataType=(
            dai.TensorInfo.DataType.FP16
            if args.model in ("yoloe", "yoloe-image") and args.precision == "fp16"
            else dai.TensorInfo.DataType.U8F
        ),
    )
    textInputQueue.send(inputNNData)

    print("Press 'q' to stop")

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
