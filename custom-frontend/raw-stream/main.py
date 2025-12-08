import os
import depthai as dai
from pathlib import Path
from frontend_server import FrontendServer
from utils.arguments import initialize_argparser

_, args = initialize_argparser()

FRONTEND_DIRECTORY = Path(os.environ["OAKAPP_STATIC_FRONTEND_PATH"])
IP = args.ip or "localhost"
PORT = args.port or 8082

frontend_server = FrontendServer(IP, PORT, FRONTEND_DIRECTORY)
print(f"Serving frontend at http://{IP}:{PORT}")
frontend_server.start()

device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
visualizer = dai.RemoteConnection(serveFrontend=False)

with dai.Pipeline(device) as pipeline:
    cam = pipeline.create(dai.node.Camera).build()
    raw_stream = cam.requestOutput(
        (640, 400), dai.ImgFrame.Type.NV12, fps=30 or args.fps_limit
    )
    visualizer.addTopic("Raw Stream", raw_stream)

    def custom_service(message):
        print("Received message:", message)

    visualizer.registerService("Custom Service", custom_service)
    pipeline.start()
    print("Running pipeline...")

    while pipeline.isRunning():
        key_pressed = visualizer.waitKey(1)
        if key_pressed == ord("q"):
            break

    pipeline.stop()
