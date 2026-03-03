import depthai as dai

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device()

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)

    # Two high-resolution raw outputs to push bandwidth
    raw_1 = cam.requestOutput((1440, 1080), type=dai.ImgFrame.Type.NV12)
    # Lag in H246 stream
    raw_2 = cam.requestOutput((1280, 720), type=dai.ImgFrame.Type.BGR888i)
    # No lag in H246 stream
    # raw_2 = cam.requestOutput((640, 480), type=dai.ImgFrame.Type.BGR888i)

    encoder = pipeline.create(dai.node.VideoEncoder)
    encoder.setDefaultProfilePreset(15, dai.VideoEncoderProperties.Profile.H264_MAIN)
    raw_1.link(encoder.input)

    visualizer.addTopic("Raw NV12", raw_1)
    visualizer.addTopic("Raw BGR", raw_2)
    visualizer.addTopic("H264", encoder.out)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
