import argparse
import json
import logging
import os
from pathlib import Path
import signal
import threading

import cv2
import depthai as dai

from util.network import frontend_urls
from util.frontend_server import FrontendServer
from measurement.history import MeasurementStore
from depthai_pipeline.init_pipeline import DEFAULT_FPS, init_pipeline


logger = logging.getLogger(__name__)
EXAMPLE_ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description="Measure anything with an OAK4.")
    parser.add_argument("-d", "--device", help="OAK4 IP or device ID")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--no-frontend",
        action="store_true",
        help="Run the backend without serving the local frontend",
    )
    parser.add_argument("--frontend-port", type=int, default=8082)
    parser.add_argument(
        "--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO"
    )
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS)
    parser.add_argument("--inspect-port", type=int, default=8765)
    parser.add_argument("--evidence", type=Path, help="Save local validation artifacts")
    parser.add_argument(
        "--storage",
        type=Path,
        default=Path(os.environ.get("OAKAGENT_STORAGE_APP", str(EXAMPLE_ROOT / "data")))
        / "measure-anything.sqlite3",
        help="Persistent measurement history database",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    if not 0 < args.fps <= 30:
        parser.error("--fps must be greater than zero and at most 30")
    if (
        not args.no_frontend
        and not os.environ.get("OAKAPP_STATIC_FRONTEND_PATH")
        and not (EXAMPLE_ROOT / "frontend" / "dist" / "index.html").is_file()
    ):
        parser.error(
            "Frontend build missing. Run npm --prefix frontend ci and npm --prefix frontend run build, "
            "or pass --no-frontend for backend-only operation."
        )
    cv2.setNumThreads(1)

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

    frontend = None
    with device, dai.Pipeline(device) as pipeline:
        try:
            if device.getIrDrivers():
                if device.setIrLaserDotProjectorIntensity(1.0):
                    logger.info(
                        "IR laser dot projector enabled at full intensity (1.0)."
                    )
                else:
                    logger.warning("Failed to enable IR laser dot projector.")
            else:
                logger.info("No IR driver detected; skipping the dot projector.")
            store = MeasurementStore(args.storage)
            controller = init_pipeline(
                pipeline, fps=args.fps, evidence=args.evidence, store=store
            )
            for name, output in (
                ("Color stream", controller.encoded_video),
                ("Object annotations", controller.annotations),
            ):
                remote.addTopic(name, output, "preview")
                topics.append(name)
            for name, handler in (
                ("getMeasurementState", controller.get_state),
                ("calibrateSupportPlane", controller.calibrate),
                ("selectSupportPlane", controller.select),
                ("getSupportPlanePreview", controller.preview),
                ("getMeasurements", controller.get_measurements),
                ("getMeasurement", controller.get_measurement),
                ("getMeasurementPreview", controller.get_measurement_preview),
                ("requestMeasurementUpdate", controller.update_measurement),
                ("setPreviewOptions", controller.set_preview_options),
            ):
                remote.registerService(name, handler)

            pipeline.start()
            logger.info("Pipeline started.")
            remote.registerPipeline(pipeline)
            logger.info(
                "%s",
                json.dumps({"capture_profile": controller.get_state({})["capture"]}),
            )
            if os.environ.get("OAKAPP_STATIC_FRONTEND_PATH"):
                port = int(os.environ.get("OAKAPP_STATIC_FRONTEND_PORT", "8000"))
                urls = frontend_urls(args.host, port)
                for url in urls:
                    logger.info("Measure anything frontend at %s", url)
                if not urls:
                    logger.info("Open the OAK4's HTTPS address on port %s.", port)
            elif not args.no_frontend:
                frontend = FrontendServer(
                    args.host, args.frontend_port, EXAMPLE_ROOT / "frontend" / "dist"
                )
                frontend.start()
                logger.info(
                    "Measure anything frontend at %s", frontend.url(args.inspect_port)
                )

            while pipeline.isRunning() and not stopped.is_set():
                pipeline.processTasks()
                if remote.waitKey(50) == ord("q"):
                    break
        finally:
            if frontend is not None:
                frontend.stop()
            if pipeline.isRunning():
                pipeline.stop()
                pipeline.wait()
            for name in topics:
                remote.removeTopic(name)


if __name__ == "__main__":
    main()
