import depthai as dai
from utils.arguments import initialize_argparser

_, args = initialize_argparser()

IMG_SHAPE = (640, 400)

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
if not device.setIrLaserDotProjectorIntensity(1):
    print(
        "Failed to set IR laser projector intensity. Maybe your device does not support this feature."
    )
with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    rgbd = pipeline.create(dai.node.RGBD).build()

    if args.mono:
        cam_node = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
    else:
        cam_node = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)

    cam_out = cam_node.requestOutput(
        IMG_SHAPE, type=dai.ImgFrame.Type.RGB888i, enableUndistortion=True
    )
    cam_out.link(rgbd.inColor)

    depth = pipeline.create(dai.node.Depth)
    depth.build(dai.node.Depth.Algorithm.AUTO, size=IMG_SHAPE)
    depth.setAlignTo(cam_out)
    depth.depth.link(rgbd.inDepth)

    visualizer.addTopic("preview", cam_out)
    visualizer.addTopic("pointcloud", rgbd.pcl)

    print("Pipeline created.")
    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
