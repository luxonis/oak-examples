import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork
from utils.arguments import initialize_argparser
from utils.translate_cropped_detections import TranslateCroppedDetections

_, args = initialize_argparser()


device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()

visualizer = dai.RemoteConnection(httpPort=8082)

with dai.Pipeline(device) as pipeline:
    platform = device.getPlatform()

    model_description = dai.NNModelDescription(
        "luxonis/yolov6-nano:r2-coco-512x288", platform=platform.name
    )
    archive_path = dai.getModelFromZoo(model_description)
    nn_archive = dai.NNArchive(archivePath=archive_path)

    cam = pipeline.create(dai.node.Camera).build()
    cam_out = cam.requestOutput(
        (640, 480),
        fps=args.fps_limit,
        type=dai.ImgFrame.Type.BGR888i
        if platform == dai.Platform.RVC4
        else dai.ImgFrame.Type.BGR888p,
    )

    crop_manip = pipeline.create(dai.node.ImageManip)
    crop_manip.initialConfig.addCrop(0, 0, 512, 288)
    cam_out.link(crop_manip.inputImage)

    nn = pipeline.create(ParsingNeuralNetwork).build(crop_manip.out, nn_archive)
    translate_cropped_dets = pipeline.create(TranslateCroppedDetections).build(
        nn.out, (640, 480), (512, 288)
    )

    visualizer.addTopic("Full cam FOV (4:3)", cam_out, "full")
    visualizer.addTopic("Translated Detections", translate_cropped_dets.out, "full")
    visualizer.addTopic("Cropped (16:9)", crop_manip.out, "cropped")
    visualizer.addTopic("Original Detections", nn.out, "cropped")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
