import logging
import depthai as dai
from pathlib import Path
from depthai_nodes.runtime import serve_frontend
from utils.arguments import initialize_argparser

logging.basicConfig(level=logging.INFO)

_, args = initialize_argparser()

with serve_frontend(
    args.frontend_dir or Path(__file__).resolve().parent / "frontend" / "dist",
    host=args.ip or "127.0.0.1",
    port=args.port or 8082,
    enabled=not args.no_frontend,
):
    device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
    visualizer = dai.RemoteConnection(serveFrontend=False)

    with dai.Pipeline(device) as pipeline:
        cam = pipeline.create(dai.node.Camera).build()
        raw_stream = cam.requestOutput(
            (640, 400), dai.ImgFrame.Type.NV12, fps=args.fps_limit or 30
        )
        visualizer.addTopic("Raw Stream", raw_stream)

        def custom_service(message):
            print("Received message:", message)
            return {"response": "Message received"}

        visualizer.registerService("Message Service", custom_service)
        pipeline.start()
        print("Pipeline started.")
        print("Running pipeline...")

        while pipeline.isRunning():
            key_pressed = visualizer.waitKey(1)
            if key_pressed == ord("q"):
                break

        pipeline.stop()
