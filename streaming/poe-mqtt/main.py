from pathlib import Path

import depthai as dai
from depthai_nodes.node import ParsingNeuralNetwork
from utils.arguments import initialize_argparser

_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()

with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")
    platform = pipeline.getDefaultDevice().getPlatform()

    model_description = dai.NNModelDescription.fromYamlFile(
        f"yolov6_nano_r2_coco.{platform.name}.yaml"
    )
    nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))

    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(
            dai.ImgFrame.Type.BGR888i
            if platform == dai.Platform.RVC4
            else dai.ImgFrame.Type.BGR888p
        )
        replay.setLoop(True)
        if args.fps_limit:
            replay.setFps(args.fps_limit)
            args.fps_limit = None  # only want to set it once
        replay.setSize(nn_archive.getInputWidth(), nn_archive.getInputHeight())

    input_node = (
        replay.out if args.media_path else pipeline.create(dai.node.Camera).build()
    )

    nn_with_parser = pipeline.create(ParsingNeuralNetwork).build(
        input_node, nn_archive, fps=args.fps_limit
    )

    script = pipeline.create(dai.node.Script)
    script.setProcessor(dai.ProcessorType.LEON_CSS)
    script.setLogLevel(dai.LogLevel.CRITICAL)

    nn_with_parser.out.link(script.inputs["detections"])
    script_text = f"""
    import time

    mqttc = Client()
    if "{args.username}" != "" and "{args.password}" != "":
        mqttc.username_pw_set("{args.username}", "{args.password}")
    node.warn('Connecting to MQTT broker {args.broker}:{args.port}...')
    success = mqttc.connect("{args.broker}", {args.port}, 60) 
    node.warn('Successfully connected to MQTT broker!')

    mqttc.loop_start()
    total = 0
    frame_count = 0
    last_msg = time.time()
    while True:
        dets = node.io['detections'].get()
        total += len(dets.detections)
        frame_count += 1
        if time.time() - last_msg > 10: # Send every 10 seconds
            last_msg = time.time()
            avrg = str(round(total / frame_count, 2))
            frame_count = 0
            total = 0
            node.warn('Sending ' + avrg)
            (ok, id) = mqttc.publish("{args.topic}", avrg, qos=2)
    """
    with open(Path(__file__).parent / "utils/paho-mqtt.py", "r") as f:
        paho_script = f.read()
        script.setScript(f"{paho_script}\n{script_text}")

    visualizer.addTopic("Video", nn_with_parser.passthrough, "images")
    visualizer.addTopic("Detections", nn_with_parser.out, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        pipeline.processTasks()
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
