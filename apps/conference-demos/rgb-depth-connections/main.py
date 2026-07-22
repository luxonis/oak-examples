import logging
import signal

import depthai as dai

from utils.host_bird_eye_view import BirdsEyeView
from utils.host_rgb_conference_node import CombineOutputs
from utils.arguments import initialize_argparser

logger = logging.getLogger(__name__)
shutdown_requested = False


def _handle_shutdown_signal(_signum, _frame):
    global shutdown_requested
    logger.info("Application received a stop signal. Stopping the app...")
    shutdown_requested = True


signal.signal(signal.SIGINT, _handle_shutdown_signal)
signal.signal(signal.SIGTERM, _handle_shutdown_signal)

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()

OUTPUT_SHAPE = (512, 288)

if not device.setIrLaserDotProjectorIntensity(1):
    print(
        "Failed to set IR laser projector intensity. Maybe your device does not support this feature."
    )

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    platform = device.getPlatform()
    FPS = 10 if platform == dai.Platform.RVC2 else 30

    cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)

    cam.initialControl.setManualFocus(130)
    cam_output = cam.requestOutput(OUTPUT_SHAPE, type=dai.ImgFrame.Type.NV12, fps=FPS)

    depth = pipeline.create(dai.node.Depth)
    depth.build(dai.node.Depth.Algorithm.AUTO, fps=FPS, size=OUTPUT_SHAPE)

    model_description = dai.NNModelDescription.fromYamlFile(
        f"yolov6_nano_r2_coco.{platform.name}.yaml"
    )
    nn_archive = dai.NNArchive(dai.getModelFromZoo(modelDescription=model_description))

    spatialDetectionNetwork = pipeline.create(dai.node.SpatialDetectionNetwork).build(
        cam,
        depth,
        nn_archive,
        fps=FPS,
    )
    spatialDetectionNetwork.setConfidenceThreshold(0.5)
    spatialDetectionNetwork.setBoundingBoxScaleFactor(0.5)
    spatialDetectionNetwork.setDepthLowerThreshold(300)
    spatialDetectionNetwork.setDepthUpperThreshold(35000)
    spatialDetectionNetwork.input.setMaxSize(1)
    spatialDetectionNetwork.input.setBlocking(False)
    spatialDetectionNetwork.inputDepth.setMaxSize(1)
    spatialDetectionNetwork.inputDepth.setBlocking(False)

    # In order to not loose synced messages (on low bandwidth), do all syncing on device
    sync = pipeline.create(dai.node.Sync)
    sync.setRunOnHost(False)
    sync_color_input = sync.inputs["color"]
    sync_color_input.setBlocking(True)
    cam_output.link(sync_color_input)
    sync_depth_input = sync.inputs["depth"]
    sync_depth_input.setBlocking(False)
    spatialDetectionNetwork.passthroughDepth.link(sync_depth_input)
    sync_detections_input = sync.inputs["detections"]
    sync_detections_input.setMaxSize(1)
    sync_detections_input.setBlocking(False)
    spatialDetectionNetwork.out.link(sync_detections_input)

    demux = pipeline.create(dai.node.MessageDemux)
    sync.out.link(demux.input)

    bird_eye = pipeline.create(BirdsEyeView).build(demux.outputs["detections"])

    combined = pipeline.create(CombineOutputs).build(
        color=demux.outputs["color"],
        depth=demux.outputs["depth"],
        birdseye=bird_eye.output,
        detections=demux.outputs["detections"],
        label_map=nn_archive.getConfigV1().model.heads[0].metadata.classes,
    )

    visualizer.addTopic("Combined View", combined.output, "images")
    visualizer.addTopic("Detections", combined.detections_output, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        if shutdown_requested:
            pipeline.stop()
            break
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
