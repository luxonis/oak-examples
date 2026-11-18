from pathlib import Path
import depthai as dai
from depthai_nodes.node import FrameCropper, ParsingNeuralNetwork

from utils.arguments import initialize_argparser
from utils.simple_barcode_overlay import SimpleBarcodeOverlay
from utils.barcode_decoder import BarcodeDecoder
from utils.barcode_regions import BarcodeRegions
from utils.gather_crops import GatherCrops

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

frame_type = (
    dai.ImgFrame.Type.BGR888i if platform == "RVC4" else dai.ImgFrame.Type.BGR888p
)

if not args.fps_limit:
    args.fps_limit = 10 if platform == "RVC2" else 30
    print(
        f"\nFPS limit set to {args.fps_limit} for {platform} platform. If you want to set a custom FPS limit, use the --fps_limit flag.\n"
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    model_description = dai.NNModelDescription.fromYamlFile(
        f"barcode-detection.{platform}.yaml"
    )
    nn_archive = dai.NNArchive(
        dai.getModelFromZoo(
            model_description,
        )
    )

    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(frame_type)
        replay.setLoop(True)
        if args.fps_limit:
            replay.setFps(args.fps_limit)
    else:
        cam = pipeline.create(dai.node.Camera).build()
        cam.initialControl.setManualExposure(3000, 200)

        cam_out = cam.requestOutput((2592, 1944), frame_type, fps=args.fps_limit)
    input_node = replay.out if args.media_path else cam_out

    resize_node = pipeline.create(dai.node.ImageManip)
    resize_node.setMaxOutputFrameSize(
        nn_archive.getInputWidth() * nn_archive.getInputHeight() * 3
    )
    resize_node.initialConfig.setOutputSize(
        nn_archive.getInputWidth(),
        nn_archive.getInputHeight(),
        mode=dai.ImageManipConfig.ResizeMode.STRETCH,
    )
    resize_node.initialConfig.setFrameType(frame_type)
    input_node.link(resize_node.inputImage)

    detection_nn: ParsingNeuralNetwork = pipeline.create(ParsingNeuralNetwork).build(
        resize_node.out, nn_archive
    )

    regions = pipeline.create(BarcodeRegions).build(detection_nn.out)
    crop_node = (
        pipeline.create(FrameCropper)
        .fromImgDetections(
            inputImgDetections=regions.out,
            outputSize=(640, 480),
            resizeMode=dai.ImageManipConfig.ResizeMode.LETTERBOX,
        )
        .build(inputImage=input_node)
    )
    decoder = pipeline.create(BarcodeDecoder).build(crop_node.out)
    decoded_barcodes = pipeline.create(GatherCrops).build(
        cameraFps=args.fps_limit,
        inputData=decoder.out,
        inputReference=detection_nn.out,
    )

    barcode_overlay = pipeline.create(SimpleBarcodeOverlay).build(
        decoded_barcodes.out, resize_node.out
    )

    visualizer.addTopic("Barcode Overlay", barcode_overlay.output)

    print("Pipeline created.")
    pipeline.start()
    print("Pipeline started.")

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            break
