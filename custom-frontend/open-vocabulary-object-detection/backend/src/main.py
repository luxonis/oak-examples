from dotenv import load_dotenv
import os
os.environ.setdefault("DEPTHAI_LEVEL", "INFO")
import depthai as dai

from depthai_nodes.node import ParsingNeuralNetwork
from utils.arguments import initialize_argparser
from utils.input import create_input_node

from utils.outlines_overlay_node import OutlinesOverlayNode
from utils.segmentation_selection_service import SegmentationSelectionService
from utils.dino_seg_tracker_node import DinoSegTrackerNode
from utils.dino_annotation_node import DinoAnnotationNode   # NEW


load_dotenv(override=True)
_, args = initialize_argparser()

# ----- VISUALIZER -----
visualizer = dai.RemoteConnection(httpPort=8082)

device = dai.Device()
platform = device.getPlatformAsString()
print(f"Platform: {platform}")

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    # ------------------------------------------------------------
    # 1) CAMERA / VIDEO INPUT — FULL RESOLUTION FOR FE & OVERLAY
    # ------------------------------------------------------------
    input_node = create_input_node(
        pipeline,
        platform,
        args.media_path,
    )

    video_full = input_node.requestOutput(
        size=(1280, 720),      # Full resolution for FE
        type=dai.ImgFrame.Type.BGR888i,
        fps=args.fps_limit,
    )

    # ------------------------------------------------------------
    # 2) FASTSAM INPUT (RESIZED)
    # ------------------------------------------------------------
    fs_model = dai.NNModelDescription("luxonis/fastsam-x:640x352")
    fs_model.platform = platform
    fs_archive = dai.NNArchive(dai.getModelFromZoo(fs_model))

    fastsam_manip = pipeline.create(dai.node.ImageManip)
    fastsam_manip.initialConfig.setOutputSize(
        fs_archive.getInputWidth(),
        fs_archive.getInputHeight(),
    )
    fastsam_manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888i)
    fastsam_manip.setMaxOutputFrameSize(
        fs_archive.getInputWidth() * fs_archive.getInputHeight() * 3
    )

    video_full.link(fastsam_manip.inputImage)

    fastsam_nn = pipeline.create(ParsingNeuralNetwork).build(
        fastsam_manip.out,
        fs_archive,
        fps=args.fps_limit,
    )

    seg_out = fastsam_nn.out

    # ------------------------------------------------------------
    # 3) DINO INPUT (RESIZED)
    # ------------------------------------------------------------
    dino_model = dai.NNModelDescription("luxonis/dinov3-backbone:convnext-small-640x480")
    dino_model.platform = platform
    dino_archive = dai.NNArchive(dai.getModelFromZoo(dino_model))

    dino_manip = pipeline.create(dai.node.ImageManip)
    dino_manip.initialConfig.setOutputSize(*dino_archive.getInputSize())
    dino_manip.initialConfig.setFrameType(dai.ImgFrame.Type.BGR888i)
    dino_manip.setMaxOutputFrameSize(
        dino_archive.getInputWidth() * dino_archive.getInputHeight() * 3
    )

    video_full.link(dino_manip.inputImage)

    dino_nn = pipeline.create(dai.node.NeuralNetwork).build(
        dino_manip.out,
        dino_archive,
    )

    # ------------------------------------------------------------
    # 4) OUTLINES NODE – only draws FastSAM outlines
    # ------------------------------------------------------------
    outlines_node = pipeline.create(OutlinesOverlayNode).build(
        video_full,
        seg_out,
    )

    # ------------------------------------------------------------
    # 5) DINO TRACKER – computes reference + HEATMAP ONLY
    # ------------------------------------------------------------
    tracker = pipeline.create(DinoSegTrackerNode).build(
        video_full,
        seg_out,
        dino_nn.out,
        fs_size=(fs_archive.getInputWidth(), fs_archive.getInputHeight()),
        dino_size=dino_archive.getInputSize(),
    )

    # ------------------------------------------------------------
    # 6) ANNOTATION NODE – gets outlined video + seg + heatmap
    #    and fills ONLY the segment containing the hottest pixel
    # ------------------------------------------------------------
    annot_node = pipeline.create(DinoAnnotationNode).build(
        outlines_node.out,   # outlined video
        seg_out,             # FastSAM segmentation
        tracker.out,         # heatmap from tracker
    )

    im = pipeline.create(dai.node.ImageManip)
    im.initialConfig.setOutputSize(1280, 720)
    im.initialConfig.setFrameType(dai.ImgFrame.Type.NV12)
    im.setMaxOutputFrameSize(int(1280 * 720 * 3))
    annot_node.out.link(im.inputImage)

    video_enc = pipeline.create(dai.node.VideoEncoder)

    video_enc.setDefaultProfilePreset(
        30,
        dai.VideoEncoderProperties.Profile.H264_MAIN,
    )

    # Feed annotated frames into encoder
    im.out.link(video_enc.input)

    # ------------------------------------------------------------
    # 7) SELECTION SERVICE (clicks from FE → tracker)
    # ------------------------------------------------------------
    selection_service = SegmentationSelectionService(tracker)

    visualizer.addTopic("Video", video_enc.out, "images")
    visualizer.registerService(selection_service.NAME, selection_service.process)
    visualizer.registerService("Clear Selection Service", selection_service.clear)
    visualizer.registerService("Threshold Update Service", tracker.set_confidence)
    visualizer.registerService("Annotation Mode Service", annot_node.set_mode)
    visualizer.registerService("Outlines Mode Service", outlines_node.set_mode)

    print("Pipeline created.")

    # ------------------------------------------------------------
    # START PIPELINE
    # ------------------------------------------------------------
    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Received q. Exiting...")
            break
