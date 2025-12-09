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
    QUANT_VALUES,
    generate_high_contrast_colormap,
)
from utils.arguments import initialize_argparser
from utils.annotation_node import AnnotationNode
from utils.frame_cache_node import FrameCacheNode

import logging as log

log.basicConfig(level=log.INFO)

_, args = initialize_argparser()

IP = args.ip or "localhost"
PORT = args.port or 8080

CLASS_NAMES = ["person", "chair", "TV"]
# For unified YOLOE, 0-79 are text classes, 80-159 are image-prompt classes
CLASS_OFFSET = 0
MAX_NUM_CLASSES = 80
CONFIDENCE_THRESHOLD = 0.1
VISUALIZATION_RESOLUTION = (1280, 960)

MAX_IMAGE_PROMPTS = 5
IMAGE_PROMPT_VECTORS: list[np.ndarray] = []  # each vector shape: (512,)
IMAGE_PROMPT_LABELS: list[str] = []
LAST_TEXT_CLASSES: list[str] = CLASS_NAMES.copy()

visualizer = dai.RemoteConnection(serveFrontend=False)
device = dai.Device()
platform = device.getPlatformAsString()

if platform != "RVC4":
    raise ValueError("This example is supported only on RVC4 platform")

frame_type = dai.ImgFrame.Type.BGR888i


def make_dummy_features(max_num_classes: int, model_name: str, precision: str):
    if precision == "fp16":
        return np.zeros((1, 512, max_num_classes), dtype=np.float16)
    qzp = int(round(QUANT_VALUES.get(model_name, {}).get("quant_zero_point", 0)))
    return np.full((1, 512, max_num_classes), qzp, dtype=np.uint8)


# choose initial features: text for yolo-world/yoloe
text_features = extract_text_embeddings(
    class_names=CLASS_NAMES,
    max_num_classes=MAX_NUM_CLASSES,
    model_name=args.model if args.model != "yolo-world" else "yolo-world",
    precision=args.precision,
)
image_prompt_features = None
if args.model == "yoloe":
    # send dummy image-prompts initially
    image_prompt_features = make_dummy_features(
        MAX_NUM_CLASSES, model_name="yoloe", precision=args.precision
    )

if args.fps_limit is None:
    args.fps_limit = 10
    log.info(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    log.info("Creating pipeline...")

    # Model selection with precision-aware YAMLs for YOLOE variants
    models_dir = Path(__file__).parent / "depthai_models"
    if args.model == "yolo-world":
        yaml_base = "yolo_world_l_fp16" if args.precision == "fp16" else "yolo_world_l"
        yaml_filename = f"{yaml_base}.{platform}.yaml"
        yaml_path = models_dir / yaml_filename
        if not yaml_path.exists():
            raise SystemExit(
                f"Model YAML not found: {yaml_path}. Ensure the model config exists."
            )
        model_description = dai.NNModelDescription.fromYamlFile(str(yaml_path))
    elif args.model == "yoloe":
        yaml_base = "yoloe_v8_l_fp16" if args.precision == "fp16" else "yoloe_v8_l"
        yaml_filename = f"{yaml_base}.{platform}.yaml"
        yaml_path = models_dir / yaml_filename
        log.debug(f"YOLOE YAML path: {yaml_path}")
        if not yaml_path.exists():
            raise SystemExit(
                f"Model YAML not found for YOLOE with precision {args.precision}: {yaml_path}. "
                f"YOLOE int8 YAML is not available; run with --precision fp16."
            )
        model_description = dai.NNModelDescription.fromYamlFile(str(yaml_path))
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
    if args.model == "yoloe":
        imagePromptInputQueue = nn_with_parser.inputs[
            "image_prompts"
        ].createInputQueue()
        nn_with_parser.inputs["image_prompts"].setReusePreviousMessage(True)

    # filter and rename detection labels
    det_process_filter = pipeline.create(ImgDetectionsFilter).build(nn_with_parser.out)
    annotation_node = pipeline.create(AnnotationNode).build(
        det_process_filter.out,
        video_src_out,
    )

    def update_labels(label_names: list[str], offset: int = 0):
        det_process_filter.setLabels(
            labels=[i for i in range(offset, offset + len(label_names))], keep=True
        )
        annotation_node.setLabelEncoding(
            {offset + k: v for k, v in enumerate(label_names)}
        )

    # Cache last frame for services that need full frame content
    frame_cache = pipeline.create(FrameCacheNode).build(video_src_out)

    if args.model == "yolo-world":
        visualizer.addTopic("Video", video_enc.out, "images")
    elif args.model == "yoloe":
        apply_colormap_node = pipeline.create(ApplyColormap).build(nn_with_parser.out)
        apply_colormap_node.setColormap(generate_high_contrast_colormap())
        apply_colormap_node.setInstanceToSemanticMask(args.semantic_seg)
        overlay_frames_node = pipeline.create(ImgFrameOverlay).build(
            video_src_out,
            apply_colormap_node.out,
            preserve_background=True,
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

    def get_current_params_service(req) -> dict[str, any]:
        """Returns current parameters used"""
        out_data = {
            "confidence_threshold": CONFIDENCE_THRESHOLD,
            "class_names": CLASS_NAMES,
            "image_prompt_labels": IMAGE_PROMPT_LABELS,
        }
        log.info(f"Current params: {out_data}")
        return out_data

    def class_update_service(new_classes: list[str]):
        """Changes classes to detect based on the user input"""
        if len(new_classes) == 0:
            log.info("List of new classes empty, skipping.")
            return
        if len(new_classes) > MAX_NUM_CLASSES:
            log.info(
                f"Number of new classes ({len(new_classes)}) exceeds maximum number of classes ({MAX_NUM_CLASSES}), skipping."
            )
            return
        global CLASS_NAMES, LAST_TEXT_CLASSES
        CLASS_NAMES = new_classes
        LAST_TEXT_CLASSES = new_classes.copy()
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
                if args.precision == "fp16"
                else dai.TensorInfo.DataType.U8F
            ),
        )
        textInputQueue.send(inputNNData)
        # In unified YOLOE, ensure image_prompts are dummy when text prompts are active
        if args.model == "yoloe":
            dummy = make_dummy_features(
                MAX_NUM_CLASSES, model_name="yoloe", precision=args.precision
            )
            inputNNDataImg = dai.NNData()
            inputNNDataImg.addTensor(
                "image_prompts",
                dummy,
                dataType=(
                    dai.TensorInfo.DataType.FP16
                    if args.precision == "fp16"
                    else dai.TensorInfo.DataType.U8F
                ),
            )
            imagePromptInputQueue.send(inputNNDataImg)

        update_labels(CLASS_NAMES, offset=0)
        log.info(f"Classes set to: {CLASS_NAMES}")

        global IMAGE_PROMPT_VECTORS, IMAGE_PROMPT_LABELS
        IMAGE_PROMPT_VECTORS = []
        IMAGE_PROMPT_LABELS = []

    def conf_threshold_update_service(new_conf_threshold: float):
        """Changes confidence threshold based on the user input"""
        global CONFIDENCE_THRESHOLD
        CONFIDENCE_THRESHOLD = max(0.01, min(0.99, new_conf_threshold))
        nn_with_parser.getParser(0).setConfidenceThreshold(CONFIDENCE_THRESHOLD)
        log.info(f"Confidence threshold set to: {CONFIDENCE_THRESHOLD}:")

    def rename_image_prompt_service(payload):
        """Rename an accumulated image prompt label by index or old name.
        payload: { index?: int, oldLabel?: str, newLabel: str }
        Applies to both YOLO-World (texts) and YOLOE (image_prompts) accumulation paths.
        """
        global IMAGE_PROMPT_LABELS
        new_label = payload.get("newLabel")
        if not new_label or not isinstance(new_label, str):
            log.info("rename_image_prompt_service: invalid newLabel")
            return
        idx = payload.get("index")
        if isinstance(idx, int) and 0 <= idx < len(IMAGE_PROMPT_LABELS):
            IMAGE_PROMPT_LABELS[idx] = new_label
        else:
            old = payload.get("oldLabel")
            if isinstance(old, str) and old in IMAGE_PROMPT_LABELS:
                pos = IMAGE_PROMPT_LABELS.index(old)
                IMAGE_PROMPT_LABELS[pos] = new_label
            else:
                log.info("rename_image_prompt_service: index/oldLabel not found")
                return
        # Re-apply labels (offset depends on model)
        if args.model == "yoloe":
            update_labels(IMAGE_PROMPT_LABELS, offset=80)
        else:
            update_labels(IMAGE_PROMPT_LABELS, offset=0)
        log.info(f"Image prompt labels updated: {IMAGE_PROMPT_LABELS}")

    def delete_image_prompt_service(payload):
        """Delete an accumulated image prompt by index or label and update model inputs.
        payload: { index?: int, label?: str }
        """
        global IMAGE_PROMPT_VECTORS, IMAGE_PROMPT_LABELS, CLASS_NAMES
        idx = payload.get("index")
        if isinstance(idx, int) and 0 <= idx < len(IMAGE_PROMPT_VECTORS):
            del IMAGE_PROMPT_VECTORS[idx]
            del IMAGE_PROMPT_LABELS[idx]
        else:
            lbl = payload.get("label")
            if isinstance(lbl, str) and lbl in IMAGE_PROMPT_LABELS:
                pos = IMAGE_PROMPT_LABELS.index(lbl)
                del IMAGE_PROMPT_VECTORS[pos]
                del IMAGE_PROMPT_LABELS[pos]
            else:
                log.info("delete_image_prompt_service: index/label not found")
                return

        if len(IMAGE_PROMPT_VECTORS) > 0:
            # Rebuild combined features and apply
            if args.model == "yoloe":
                combined = make_dummy_features(
                    MAX_NUM_CLASSES, model_name="yoloe", precision=args.precision
                )
                for i, v in enumerate(IMAGE_PROMPT_VECTORS):
                    combined[0, :, i] = v
                inputNNDataImg = dai.NNData()
                inputNNDataImg.addTensor(
                    "image_prompts",
                    combined,
                    dataType=(
                        dai.TensorInfo.DataType.FP16
                        if args.precision == "fp16"
                        else dai.TensorInfo.DataType.U8F
                    ),
                )
                imagePromptInputQueue.send(inputNNDataImg)
                # ensure texts are dummy
                dummy = make_dummy_features(
                    MAX_NUM_CLASSES, model_name="yoloe", precision=args.precision
                )
                inputNNDataTxt = dai.NNData()
                inputNNDataTxt.addTensor(
                    "texts",
                    dummy,
                    dataType=(
                        dai.TensorInfo.DataType.FP16
                        if args.precision == "fp16"
                        else dai.TensorInfo.DataType.U8F
                    ),
                )
                textInputQueue.send(inputNNDataTxt)
                update_labels(IMAGE_PROMPT_LABELS, offset=80)
                log.info(
                    f"Deleted image prompt; remaining (yoloe) labels: {IMAGE_PROMPT_LABELS}"
                )
            else:  # yolo-world
                combined = make_dummy_features(
                    MAX_NUM_CLASSES, model_name="yolo-world", precision=args.precision
                )
                for i, v in enumerate(IMAGE_PROMPT_VECTORS):
                    combined[0, :, i] = v
                inputNNData = dai.NNData()
                inputNNData.addTensor(
                    "texts",
                    combined,
                    dataType=(
                        dai.TensorInfo.DataType.FP16
                        if args.precision == "fp16"
                        else dai.TensorInfo.DataType.U8F
                    ),
                )
                textInputQueue.send(inputNNData)
                update_labels(IMAGE_PROMPT_LABELS, offset=0)
                log.info(
                    f"Deleted image prompt; remaining (yolo-world) labels: {IMAGE_PROMPT_LABELS}"
                )
        else:
            # No image prompts left: revert to last text classes
            CLASS_NAMES = LAST_TEXT_CLASSES.copy()
            text_features = extract_text_embeddings(
                class_names=CLASS_NAMES,
                max_num_classes=MAX_NUM_CLASSES,
                model_name=args.model if args.model != "yolo-world" else "yolo-world",
                precision=args.precision,
            )
            inputNNData = dai.NNData()
            inputNNData.addTensor(
                "texts",
                text_features,
                dataType=(
                    dai.TensorInfo.DataType.FP16
                    if args.precision == "fp16"
                    else dai.TensorInfo.DataType.U8F
                ),
            )
            textInputQueue.send(inputNNData)
            if args.model == "yoloe":
                dummy = make_dummy_features(
                    MAX_NUM_CLASSES, model_name="yoloe", precision=args.precision
                )
                inputNNDataImg = dai.NNData()
                inputNNDataImg.addTensor(
                    "image_prompts",
                    dummy,
                    dataType=(
                        dai.TensorInfo.DataType.FP16
                        if args.precision == "fp16"
                        else dai.TensorInfo.DataType.U8F
                    ),
                )
                imagePromptInputQueue.send(inputNNDataImg)
            update_labels(CLASS_NAMES, offset=0)
            log.info(
                f"All image prompts deleted; reverted to text classes: {CLASS_NAMES}"
            )

    def image_upload_service(image_data):
        image = base64_to_cv2_image(image_data["data"])
        if args.model == "yolo-world":
            image_features = extract_image_prompt_embeddings(
                image, model_name=args.model, precision=args.precision
            )
            log.info(
                "Image features extracted (yolo-world), updating accumulated prompts as texts..."
            )

            # Extract single 512-d vector from padded features (column 0)
            vec = image_features[0, :, 0].copy()
            label = image_data.get("label") or image_data["filename"].split(".")[0]

            global \
                IMAGE_PROMPT_VECTORS, \
                IMAGE_PROMPT_LABELS, \
                MAX_IMAGE_PROMPTS, \
                MAX_NUM_CLASSES

            IMAGE_PROMPT_VECTORS.append(vec)
            IMAGE_PROMPT_LABELS.append(label)
            if len(IMAGE_PROMPT_VECTORS) > MAX_IMAGE_PROMPTS:
                del IMAGE_PROMPT_VECTORS[
                    0 : len(IMAGE_PROMPT_VECTORS) - MAX_IMAGE_PROMPTS
                ]
                del IMAGE_PROMPT_LABELS[
                    0 : len(IMAGE_PROMPT_LABELS) - MAX_IMAGE_PROMPTS
                ]

            combined = make_dummy_features(
                MAX_NUM_CLASSES, model_name="yolo-world", precision=args.precision
            )
            for i, v in enumerate(IMAGE_PROMPT_VECTORS):
                combined[0, :, i] = v

            inputNNData = dai.NNData()
            inputNNData.addTensor(
                "texts",
                combined,
                dataType=(
                    dai.TensorInfo.DataType.FP16
                    if args.precision == "fp16"
                    else dai.TensorInfo.DataType.U8F
                ),
            )
            textInputQueue.send(inputNNData)
            update_labels(IMAGE_PROMPT_LABELS, offset=0)
            log.info(
                f"Image prompts set as texts (yolo-world, n={len(IMAGE_PROMPT_LABELS)}): {IMAGE_PROMPT_LABELS}"
            )
        else:  # yoloe unified with image_prompts input (accumulate up to 5)
            image_features = extract_image_prompt_embeddings(
                image, model_name="yoloe", precision=args.precision
            )
            log.info("Image features extracted, updating accumulated image_prompts...")

            vec = image_features[0, :, 0].copy()
            label = image_data.get("label") or image_data["filename"].split(".")[0]

            IMAGE_PROMPT_VECTORS.append(vec)
            IMAGE_PROMPT_LABELS.append(label)
            if len(IMAGE_PROMPT_VECTORS) > MAX_IMAGE_PROMPTS:
                del IMAGE_PROMPT_VECTORS[
                    0 : len(IMAGE_PROMPT_VECTORS) - MAX_IMAGE_PROMPTS
                ]
                del IMAGE_PROMPT_LABELS[
                    0 : len(IMAGE_PROMPT_LABELS) - MAX_IMAGE_PROMPTS
                ]

            combined = make_dummy_features(
                MAX_NUM_CLASSES, model_name="yoloe", precision=args.precision
            )
            for i, v in enumerate(IMAGE_PROMPT_VECTORS):
                combined[0, :, i] = v

            inputNNDataImg = dai.NNData()
            inputNNDataImg.addTensor(
                "image_prompts",
                combined,
                dataType=(
                    dai.TensorInfo.DataType.FP16
                    if args.precision == "fp16"
                    else dai.TensorInfo.DataType.U8F
                ),
            )
            imagePromptInputQueue.send(inputNNDataImg)

            # Send dummy texts so only image prompts are considered
            dummy = make_dummy_features(
                MAX_NUM_CLASSES, model_name="yoloe", precision=args.precision
            )
            inputNNDataTxt = dai.NNData()
            inputNNDataTxt.addTensor(
                "texts",
                dummy,
                dataType=(
                    dai.TensorInfo.DataType.FP16
                    if args.precision == "fp16"
                    else dai.TensorInfo.DataType.U8F
                ),
            )
            textInputQueue.send(inputNNDataTxt)

            update_labels(IMAGE_PROMPT_LABELS, offset=80)
            log.info(
                f"Image prompts set (n={len(IMAGE_PROMPT_LABELS)} at offset 80): {IMAGE_PROMPT_LABELS}"
            )

    def bbox_prompt_service(payload):
        """
        Accepts a full-frame PNG (base64) plus a normalized bbox {x,y,width,height} in viewport space.
        - For yolo-world: crops the bbox region and extracts image prompt features from the crop.
        - For yoloe: builds a binary mask from the bbox over the full frame and extracts features with mask_prompt.
        """
        log.info(f"[BBox] Service payload keys: {list(payload.keys())}")
        # Try FE-provided image first, else fall back to cached live frame
        image = base64_to_cv2_image(payload["data"]) if payload.get("data") else None
        if image is None:
            image = frame_cache.get_last_frame()
            if image is None:
                log.info("[BBox] No image data and no cached frame available")
                return {"ok": False, "reason": "no_image"}
        if image is None:
            log.info("[BBox] Decoded image is None")
            return {"ok": False, "reason": "decode_failed"}
        if (image == 0).all():
            log.info("[BBox] Warning: decoded image is all zeros")
        # print image stats
        log.debug(f"[BBox] Image shape: {image.shape}")
        log.debug(f"[BBox] Image dtype: {image.dtype}")
        log.debug(f"[BBox] Image min: {image.min()}")
        log.debug(f"[BBox] Image max: {image.max()}")
        log.debug(f"[BBox] Image mean: {image.mean()}")
        log.debug(f"[BBox] Image std: {image.std()}")

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
        log.info(
            f"[BBox] Image size: {W}x{H}, bbox(px): x0={x0}, y0={y0}, x1={x1}, y1={y1}"
        )

        if x1 <= x0 or y1 <= y0:
            log.info("Invalid bbox, ignoring bbox prompt request.")
            return {"ok": False, "reason": "invalid_bbox"}

        if args.model == "yolo-world":
            crop = image[y0:y1, x0:x1]
            log.info(
                f"[BBox] YOLO-World crop shape: {crop.shape if crop is not None else None}"
            )
            image_features = extract_image_prompt_embeddings(
                crop, model_name=args.model, precision=args.precision
            )
        elif args.model == "yoloe":
            mask = np.zeros((H, W), dtype=np.float32)
            mask[y0:y1, x0:x1] = 1.0
            log.info(f"[BBox] YOLOE mask sum: {float(mask.sum())}")
            image_features = extract_image_prompt_embeddings(
                image,
                model_name="yoloe",
                mask_prompt=mask,
                precision=args.precision,
            )
        else:
            log.info(f"Unsupported model for bbox prompt: {args.model}")
            return {"ok": False, "reason": "unsupported_model"}

        global \
            IMAGE_PROMPT_VECTORS, \
            IMAGE_PROMPT_LABELS, \
            MAX_IMAGE_PROMPTS, \
            MAX_NUM_CLASSES

        if args.model == "yolo-world":
            vec = image_features[0, :, 0].copy()
            label = payload.get("label", "object")

            IMAGE_PROMPT_VECTORS.append(vec)
            IMAGE_PROMPT_LABELS.append(label)
            if len(IMAGE_PROMPT_VECTORS) > MAX_IMAGE_PROMPTS:
                del IMAGE_PROMPT_VECTORS[
                    0 : len(IMAGE_PROMPT_VECTORS) - MAX_IMAGE_PROMPTS
                ]
                del IMAGE_PROMPT_LABELS[
                    0 : len(IMAGE_PROMPT_LABELS) - MAX_IMAGE_PROMPTS
                ]

            combined = make_dummy_features(
                MAX_NUM_CLASSES, model_name="yolo-world", precision=args.precision
            )
            for i, v in enumerate(IMAGE_PROMPT_VECTORS):
                combined[0, :, i] = v

            inputNNData = dai.NNData()
            inputNNData.addTensor(
                "texts",
                combined,
                dataType=(
                    dai.TensorInfo.DataType.FP16
                    if args.precision == "fp16"
                    else dai.TensorInfo.DataType.U8F
                ),
            )
            textInputQueue.send(inputNNData)
            update_labels(IMAGE_PROMPT_LABELS, offset=0)
            log.info(
                f"BBox prompts set as texts (yolo-world, n={len(IMAGE_PROMPT_LABELS)}): {IMAGE_PROMPT_LABELS}"
            )
        else:
            vec = image_features[0, :, 0].copy()
            label = payload.get("label", "object")

            IMAGE_PROMPT_VECTORS.append(vec)
            IMAGE_PROMPT_LABELS.append(label)
            if len(IMAGE_PROMPT_VECTORS) > MAX_IMAGE_PROMPTS:
                del IMAGE_PROMPT_VECTORS[
                    0 : len(IMAGE_PROMPT_VECTORS) - MAX_IMAGE_PROMPTS
                ]
                del IMAGE_PROMPT_LABELS[
                    0 : len(IMAGE_PROMPT_LABELS) - MAX_IMAGE_PROMPTS
                ]

            combined = make_dummy_features(
                MAX_NUM_CLASSES, model_name="yoloe", precision=args.precision
            )
            for i, v in enumerate(IMAGE_PROMPT_VECTORS):
                combined[0, :, i] = v

            inputNNDataImg = dai.NNData()
            inputNNDataImg.addTensor(
                "image_prompts",
                combined,
                dataType=(
                    dai.TensorInfo.DataType.FP16
                    if args.precision == "fp16"
                    else dai.TensorInfo.DataType.U8F
                ),
            )
            imagePromptInputQueue.send(inputNNDataImg)
            # Send dummy texts so only image prompts are considered
            dummy = make_dummy_features(
                MAX_NUM_CLASSES, model_name="yoloe", precision=args.precision
            )
            inputNNDataTxt = dai.NNData()
            inputNNDataTxt.addTensor(
                "texts",
                dummy,
                dataType=(
                    dai.TensorInfo.DataType.FP16
                    if args.precision == "fp16"
                    else dai.TensorInfo.DataType.U8F
                ),
            )
            textInputQueue.send(inputNNDataTxt)
            update_labels(IMAGE_PROMPT_LABELS, offset=80)
            log.info(
                f"BBox prompts set (n={len(IMAGE_PROMPT_LABELS)} at offset 80): {IMAGE_PROMPT_LABELS}"
            )
        return {"ok": True, "bbox": {"x0": x0, "y0": y0, "x1": x1, "y1": y1}}

    visualizer.registerService("Get Current Params Service", get_current_params_service)
    visualizer.registerService("Class Update Service", class_update_service)
    visualizer.registerService(
        "Threshold Update Service", conf_threshold_update_service
    )
    if args.model in ("yolo-world", "yoloe"):
        visualizer.registerService("Image Upload Service", image_upload_service)
    visualizer.registerService("BBox Prompt Service", bbox_prompt_service)
    visualizer.registerService(
        "Rename Image Prompt Service", rename_image_prompt_service
    )
    visualizer.registerService(
        "Delete Image Prompt Service", delete_image_prompt_service
    )

    log.info("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    update_labels(CLASS_NAMES, offset=CLASS_OFFSET)

    inputNNData = dai.NNData()
    inputNNData.addTensor(
        "texts",
        text_features,
        dataType=(
            dai.TensorInfo.DataType.FP16
            if args.precision == "fp16"
            else dai.TensorInfo.DataType.U8F
        ),
    )
    textInputQueue.send(inputNNData)
    if args.model == "yoloe":
        inputNNDataImg = dai.NNData()
        inputNNDataImg.addTensor(
            "image_prompts",
            image_prompt_features,
            dataType=(
                dai.TensorInfo.DataType.FP16
                if args.precision == "fp16"
                else dai.TensorInfo.DataType.U8F
            ),
        )
        imagePromptInputQueue.send(inputNNDataImg)

    log.info("Press 'q' to stop")

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            log.info("Got q key. Exiting...")
            break
