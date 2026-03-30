#!/usr/bin/env python3

from depthai_nodes.node import (
    CoordinatesMapper,
    FrameCropper,
    GatherData,
    ImgDetectionsFilter,
    ParsingNeuralNetwork,
    Tiling,
)
from utils.arguments import initialize_argparser
from utils.merge_img_detections import MergeImgDetections
from utils.stitch import Stitch
import contextlib
import depthai as dai
import time

_, args = initialize_argparser()

IMG_SIZES = {
    "2160p": (3840, 2160),
    "1080p": (1920, 1080),
    "720p": (1280, 720),
    "480p": (640, 480),
    "360p": (640, 360),
}
# Nr of seconds in float to wait before autofocus is turned off after program start and after homography recalculation.
AF_MSG_DELAY_S = 5.0
IMG_SHAPE = IMG_SIZES[args.input_size]
AF_MODE_NAMES = {
    dai.CameraControl.AutoFocusMode.OFF: "OFF",
    dai.CameraControl.AutoFocusMode.AUTO: "AUTO",
}


def createPipeline(pipeline):
    camRgb = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    output = camRgb.requestOutput(
        IMG_SHAPE, dai.ImgFrame.Type.NV12, dai.ImgResizeMode.CROP, fps=args.fps_limit
    )
    input = camRgb.inputControl.createInputQueue()
    return pipeline, input, output


def send_af_mode(inputs, mode):
    ctrl = dai.CameraControl()
    ctrl.setAutoFocusMode(mode)
    print(f"Setting autofocus mode to {AF_MODE_NAMES[mode]} for {len(inputs)} cameras.")
    for input in inputs:
        input.send(ctrl)


with contextlib.ExitStack() as stack:
    visualizer = dai.RemoteConnection(httpPort=8082)
    deviceInfos = dai.Device.getAllAvailableDevices()
    print("=== Found devices: ", deviceInfos)
    inputs = []
    outputs = []
    pipelines = []

    for deviceInfo in deviceInfos:
        pipeline = stack.enter_context(dai.Pipeline())
        device = pipeline.getDefaultDevice()

        print("===Connected to ", deviceInfo.getDeviceId())
        mxId = device.getDeviceId()
        cameras = device.getConnectedCameras()
        usbSpeed = device.getUsbSpeed()
        eepromData = device.readCalibration2().getEepromData()
        print("   >>> Device ID:", mxId)
        print("   >>> Num of cameras:", len(cameras))
        if eepromData.boardName != "":
            print("   >>> Board name:", eepromData.boardName)
        if eepromData.productName != "":
            print("   >>> Product name:", eepromData.productName)

        pipeline, input, output = createPipeline(pipeline)
        pipelines.append(pipeline)
        outputs.append(output)
        inputs.append(input)

    platform = device.getPlatform()
    # Get model based on platform type from yaml file
    model_description = dai.NNModelDescription.fromYamlFile(
        f"yolov6_nano.{platform.name}.yaml"
    )
    nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))

    # Determine stitched output resolution x = nn y size + (nn_y_size//2)*nr of cameras,
    #                                      y = y size of nn model
    out_stitch_res = (
        nn_archive.getInputSize()[0]
        + (nn_archive.getInputSize()[0] // 2) * len(outputs),
        nn_archive.getInputSize()[1],
    )
    # Create threaded node pipeline with Stitch class, setting nr on inputs and output resolution
    # set to NN input resolution
    stitch_pl = pipeline.create(
        Stitch, nr_inputs=len(outputs), output_resolution=out_stitch_res
    )
    for i, output in enumerate(outputs):
        # Link each output of a camera to stitching inputs
        output.link(stitch_pl.inputs[i])
        # Do not block stream if image queue gets full - less delay in output detection stream
        stitch_pl.inputs[i].setBlocking(False)

    grid_size = (len(outputs), 1)

    tile_manager = pipeline.create(Tiling).build(
        trigger=stitch_pl.out,
        canvasShape=out_stitch_res,
        overlap=0.5,
        gridSize=grid_size,
        gridMatrix=None,
        globalDetection=False,
        resizeShape=nn_archive.getInputSize(),
    )

    tiling_cropper = (
        pipeline.create(FrameCropper)
        .fromManipConfigs(tile_manager.out)
        .build(
            inputImage=stitch_pl.out,
            outputSize=nn_archive.getInputSize(),
            resizeMode=dai.ImageManipConfig.ResizeMode.STRETCH,
        )
    )

    nn = pipeline.create(ParsingNeuralNetwork).build(
        input=tiling_cropper.out, nnSource=nn_archive
    )

    detections_in_stitched_space = pipeline.create(CoordinatesMapper).build(
        toTransformationInput=stitch_pl.out,
        fromTransformationInput=nn.out,
    )

    gathered_detections = pipeline.create(GatherData).build(
        inputData=detections_in_stitched_space.out,
        inputReference=stitch_pl.out,
        cameraFps=args.fps_limit,
        waitCountFn=lambda _: tile_manager.tileCount,
    )

    merged_detections = pipeline.create(MergeImgDetections).build(
        input=gathered_detections.out
    )

    filtered_detections = (
        pipeline.create(ImgDetectionsFilter)
        .useNms(
            confThresh=0.1,
            iouThresh=0.2,
        )
        .build(input=merged_detections.out)
    )

    # Show stitched image on visualizer overlayed with nn detections
    visualizer.addTopic("Stitched", stitch_pl.out_full_res)
    visualizer.addTopic("Patcher", filtered_detections.out)

    for i, p in enumerate(pipelines):
        p.start()

    # Register visualizer with the first pipeline
    visualizer.registerPipeline(pipelines[0])

    print("Press 'r' in visualizer to recalculate homography.")
    print(f"Autofocus will be tuned OFF after {AF_MSG_DELAY_S} seconds")
    af_start_time = time.time()
    af_on = True
    while pipeline.isRunning():
        pipeline.processTasks()  # run processTasks in every loop since .start() doesn't do it
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
        if key == ord("r"):
            print(
                f"Got r key from the remote connection, recalculating homography. Autofocus will be turned to AUTO for {AF_MSG_DELAY_S}s."
            )
            send_af_mode(inputs, dai.CameraControl.AutoFocusMode.AUTO)
            af_on = True
            stitch_pl.recalculate_homography()
            af_start_time = time.time()
        if af_on and (time.time() - af_start_time > AF_MSG_DELAY_S):
            # After AF_MSG_DELAY_S seconds send the autofocus off message to all cams to avoid flickering
            send_af_mode(inputs, dai.CameraControl.AutoFocusMode.OFF)
            af_on = False
