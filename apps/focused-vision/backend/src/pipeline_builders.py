import depthai as dai
import host_nodes

from depthai_nodes.node.extended_neural_network import ExtendedNeuralNetwork
from depthai_nodes.node.stage_2_neural_network import Stage2NeuralNetwork
from depthai_nodes.node.utils import generate_script_content


def create_manip(
    pipeline: dai.Pipeline,
    frame_type: dai.ImgFrame.Type,
    width,
    height,
    mode: dai.ImageManipConfig.ResizeMode = dai.ImageManipConfig.ResizeMode.LETTERBOX,
):
    manip = pipeline.create(dai.node.ImageManip)
    manip.setMaxOutputFrameSize(width * height * 3)
    manip.initialConfig.setOutputSize(width, height, mode=mode)
    manip.initialConfig.setFrameType(frame_type)
    return manip


def convert_to_nv12(
    pipeline: dai.Pipeline, original: dai.Node.Output, width: int, height: int
) -> dai.Node:
    """
    ImageManip to convert to NV12 at given size, returns the ImageManip node (use .out)
    """
    manip = pipeline.create(dai.node.ImageManip)
    manip.initialConfig.setOutputSize(width, height)
    manip.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    manip.setMaxOutputFrameSize(int(width * height * 3))
    original.link(manip.inputImage)
    return manip


def build_h264_stream(
    pipeline: dai.Pipeline,
    *,
    src: dai.Node.Output,
    size: tuple[int, int],
    fps: int,
    profile: dai.VideoEncoderProperties.Profile,
    assume_nv12: bool = False,
    vbr: bool = False,
) -> dai.Node.Output:
    """
    Generic encoder builder
    - If assume_nv12=True: links src directly to encoder (expects NV12 at 'size')
    - Else: inserts NV12 converter+resize to 'size' before encoder
    Returns encoder.out (bitstream)
    """
    if assume_nv12:
        enc_in = src
    else:
        nv12_node = convert_to_nv12(pipeline, src, size[0], size[1])
        enc_in = nv12_node.out

    enc = pipeline.create(dai.node.VideoEncoder)
    enc.setDefaultProfilePreset(fps=fps, profile=profile)
    if vbr:
        enc.setRateControlMode(dai.VideoEncoderProperties.RateControlMode.VBR)
    enc_in.link(enc.input)
    return enc.out


def build_roi_cropper(
    pipeline: dai.Pipeline,
    *,
    preview_stream: dai.Node.Output,
    det_stream: dai.Node.Output,
    out_size: tuple[int, int],
    frame_type: dai.ImgFrame.Type,
    padding: float = 0.05,
    pool_size: int = 7,
    cfg_queue_size: int = 7,
) -> dai.Node.Output:
    """
    Build: Script(det_in+preview) -> ImageManip(crop+resize to out_size, frame_type) -> out
    Returns cropper.out (frames of size out_size)
    """
    resize_w, resize_h = out_size
    script = pipeline.create(dai.node.Script)
    script.setScript(
        generate_script_content(
            resize_width=resize_w,
            resize_height=resize_h,
            resize_mode="LETTERBOX",
            padding=padding,
        )
    )
    det_stream.link(script.inputs["det_in"])
    preview_stream.link(script.inputs["preview"])

    manip = pipeline.create(dai.node.ImageManip)
    manip.setMaxOutputFrameSize(resize_w * resize_h * 3)
    manip.initialConfig.setOutputSize(resize_w, resize_h)
    manip.initialConfig.setFrameType(frame_type)
    manip.inputConfig.setMaxSize(cfg_queue_size)
    manip.inputImage.setMaxSize(cfg_queue_size)
    manip.setNumFramesPool(pool_size)
    manip.inputConfig.setWaitForMessage(True)

    script.outputs["manip_cfg"].link(manip.inputConfig)
    script.outputs["manip_img"].link(manip.inputImage)

    return manip.out


def build_rgb(
    pipeline: dai.Pipeline,
    high_res: tuple[int, int],
    low_res: tuple[int, int],
    fps: int,
    frame_type: dai.ImgFrame.Type = dai.ImgFrame.Type.BGR888i,
) -> tuple[dai.Node.Output, dai.Node.Output]:
    rgb = pipeline.create(dai.node.Camera).build()
    # rgb.initialControl.setManualExposure(30_000, 105)
    if high_res[0] > 4000 or high_res[1] > 3000:
        high_res_out = rgb.requestOutput(size=high_res, type=frame_type, fps=fps)
        manip = pipeline.create(dai.node.ImageManip)
        manip.initialConfig.setOutputSize(
            *low_res, mode=dai.ImageManipConfig.ResizeMode.LETTERBOX
        )
        manip.setMaxOutputFrameSize(low_res[0] * low_res[1] * 3)
        high_res_out.link(manip.inputImage)
        low_res_out = manip.out
    else:
        high_res_out = rgb.requestOutput(size=high_res, type=frame_type, fps=fps)
        low_res_out = rgb.requestOutput(size=low_res, type=frame_type, fps=fps)
    return low_res_out, high_res_out


def build_naive_approach(
    pipeline: dai.Pipeline,
    rgb_low_res_out: dai.Node.Output,
    face_detection_model_name: str,
    frame_type: dai.ImgFrame.Type,
):
    face_detection_naive = pipeline.create(ExtendedNeuralNetwork)
    face_detection_naive.build(
        input=rgb_low_res_out,
        input_resize_mode=dai.ImageManipConfig.ResizeMode.LETTERBOX,
        nn_source=face_detection_model_name,
        enable_detection_filtering=True,
    )
    largest_face_detection_naive = host_nodes.PickLargestBbox().build(
        face_detection_naive.out
    )
    face_detection_naive_as_img_det = (
        host_nodes.SafeImgDetectionsExtendedBridge().build(
            largest_face_detection_naive.out, ignore_angle=True
        )
    )
    switch_naive = host_nodes.Switch().build(
        face_detection_naive_as_img_det.out, rgb_low_res_out
    )
    face_cropper_naive = build_roi_cropper(
        pipeline=pipeline,
        preview_stream=switch_naive.rgb,
        det_stream=switch_naive.has_detections,
        out_size=(320, 320),
        frame_type=frame_type,
        padding=0.02,
        pool_size=5,
        cfg_queue_size=5,
    )
    black_image_generator_naive = host_nodes.BlackFrame().build(
        switch_naive.no_detections
    )
    face_crops_naive = host_nodes.Passthrough().build(
        face_cropper_naive, black_image_generator_naive.out
    )
    return face_crops_naive, face_crops_naive


def transform_ymin(detection: dai.ImgDetection):
    return max(0.0, detection.ymin - 0.03)


def transform_ymax(detection: dai.ImgDetection):
    return min(1.0, detection.ymin + ((detection.ymax - detection.ymin) * 0.15))


def build_2_stage_face_detection(
    pipeline: dai.Pipeline,
    rgb_low_res_out: dai.Node.Output,
    rgb_high_res_out: dai.Node.Output,
    people_detection_model_name: str,
    face_detection_model_name: str,
    frame_type: dai.ImgFrame.Type,
    fps_limit: int,
):
    people_detection = pipeline.create(ExtendedNeuralNetwork)
    people_detection.build(
        input=rgb_low_res_out,
        input_resize_mode=dai.ImageManipConfig.ResizeMode.LETTERBOX,
        nn_source=people_detection_model_name,
        enable_detection_filtering=True,
    )
    largest_people_detection = host_nodes.PickLargestBbox().build(people_detection.out)
    largest_people_detection_as_img_detection = (
        host_nodes.SafeImgDetectionsExtendedBridge().build(
            largest_people_detection.out, ignore_angle=True
        )
    )
    largest_people_detection_cropped = host_nodes.CropPersonDetectionWaistDown(
        ymin_transformer=transform_ymin,
        ymax_transformer=transform_ymax,
    ).build(largest_people_detection_as_img_detection.out)
    face_people_gathered = pipeline.create(Stage2NeuralNetwork).build(
        img_frame=rgb_high_res_out,
        stage_1_nn=largest_people_detection_cropped.out,
        nn_source=face_detection_model_name,
        input_resize_mode=dai.ImageManipConfig.ResizeMode.LETTERBOX,
        fps=fps_limit,
        remap_detections=True,
    )
    face_detection_2_stage = host_nodes.FaceDetectionFromGatheredData().build(
        node_out=face_people_gathered.out
    )
    face_detection_2_stage_as_img_detection = (
        host_nodes.SafeImgDetectionsExtendedBridge().build(
            face_detection_2_stage.out, ignore_angle=True
        )
    )
    switch_2_stage = host_nodes.Switch().build(
        face_detection_2_stage_as_img_detection.out, rgb_high_res_out
    )
    face_cropper_2_stage = build_roi_cropper(
        pipeline=pipeline,
        preview_stream=switch_2_stage.rgb,
        det_stream=switch_2_stage.has_detections,
        out_size=(320, 320),
        frame_type=frame_type,
        padding=0.02,
        pool_size=7,
        cfg_queue_size=5,
    )
    black_image_generator_2_stage = host_nodes.BlackFrame().build(
        switch_2_stage.no_detections
    )
    face_crops_2_stage = host_nodes.Passthrough().build(
        face_cropper_2_stage, black_image_generator_2_stage.out
    )
    return face_crops_2_stage


def build_1_stage_with_tiling(
    pipeline: dai.Pipeline,
    rgb_high_res_out: dai.Node.Output,
    high_res_width: int,
    high_res_height: int,
    face_detection_model_name: str,
    frame_type: dai.ImgFrame.Type,
):
    face_detection_with_tiling_nn = pipeline.create(ExtendedNeuralNetwork)
    face_detection_with_tiling_nn.build(
        input=rgb_high_res_out,
        input_resize_mode=dai.ImageManipConfig.ResizeMode.LETTERBOX,
        nn_source=face_detection_model_name,
        enable_detection_filtering=True,
        enable_tiling=True,
        input_size=(high_res_width, high_res_height),
    )
    face_detection_with_tiling_nn.setConfidenceThreshold(0.8)
    face_detection_with_tiling_nn.setTilingGridSize((4, 4))
    largest_face_detection_tiling = host_nodes.PickLargestBbox().build(
        face_detection_with_tiling_nn.out
    )
    face_detection_tiling_as_img_det = (
        host_nodes.SafeImgDetectionsExtendedBridge().build(
            largest_face_detection_tiling.out, ignore_angle=True
        )
    )
    switch_tiling = host_nodes.Switch().build(
        face_detection_tiling_as_img_det.out, rgb_high_res_out
    )
    head_cropper_tiling = build_roi_cropper(
        pipeline=pipeline,
        preview_stream=switch_tiling.rgb,
        det_stream=switch_tiling.has_detections,
        out_size=(320, 320),
        frame_type=frame_type,
        padding=0.02,
        pool_size=5,
        cfg_queue_size=5,
    )
    black_image_generator_tiling = host_nodes.BlackFrame().build(
        switch_tiling.no_detections
    )
    face_crops_tiling = host_nodes.Passthrough().build(
        head_cropper_tiling, black_image_generator_tiling.out
    )
    return face_crops_tiling
