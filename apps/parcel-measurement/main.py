import argparse
import json
import os
from pathlib import Path
import signal
import threading

import depthai as dai

from network import frontend_urls
from pipeline import DEFAULT_FPS, init_pipeline


def main():
    parser = argparse.ArgumentParser(description="Measure parcels with an OAK4.")
    parser.add_argument("-d", "--device", help="OAK4 IP or device ID")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS)
    parser.add_argument("--inspect-port", type=int, default=8765)
    parser.add_argument("--evidence", type=Path, help="Save local validation artifacts")
    args = parser.parse_args()
    if not 0 < args.fps <= 30:
        parser.error("--fps must be greater than zero and at most 30")

    stopped = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    remote = dai.RemoteConnection(
        address=args.host, webSocketPort=args.inspect_port, serveFrontend=False
    )
    topics = []
    device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
    if device.getPlatform() != dai.Platform.RVC4:
        device.close()
        raise RuntimeError("This example requires an OAK4.")

    with device, dai.Pipeline(device) as pipeline:
        try:
            controller = init_pipeline(pipeline, fps=args.fps, evidence=args.evidence)
            for name, output in (
                ("Color stream", controller.encoded_video),
                ("Parcel annotations", controller.annotations),
            ):
                remote.addTopic(name, output, "preview")
                topics.append(name)
            for name, handler in (
                ("getParcelState", controller.get_state),
                ("calibrateSupportPlane", controller.calibrate),
                ("selectSupportPlane", controller.select),
                ("getSupportPlanePreview", controller.preview),
            ):
                remote.registerService(name, handler)

            pipeline.start()
            print("Pipeline started.", flush=True)
            remote.registerPipeline(pipeline)
            print(
                json.dumps({"capture_profile": controller.get_state({})["capture"]}),
                flush=True,
            )
            if os.environ.get("OAKAPP_STATIC_FRONTEND_PATH"):
                port = int(os.environ.get("OAKAPP_STATIC_FRONTEND_PORT", "8000"))
                urls = frontend_urls(args.host, port)
                for url in urls:
                    print(f"Parcel frontend at {url}", flush=True)
                if not urls:
                    print(f"Open the OAK4's HTTPS address on port {port}.", flush=True)
            else:
                print(
                    "Start the frontend with npm --prefix frontend run dev.", flush=True
                )

            while pipeline.isRunning() and not stopped.is_set():
                pipeline.processTasks()
                if remote.waitKey(50) == ord("q"):
                    break
        finally:
            if pipeline.isRunning():
                pipeline.stop()
                pipeline.wait()
            for name in topics:
                remote.removeTopic(name)


if __name__ == "__main__":
    main()
