import logging
import signal
import threading

import depthai as dai

from controller import TrackingController
from publisher import TrackingPublisher

log = logging.getLogger("track-anything")


def main():
    """Start the camera pipeline, frontend services, and inference worker."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    controller = TrackingController()
    signal.signal(signal.SIGTERM, lambda *_: controller.stop.set())
    signal.signal(signal.SIGINT, lambda *_: controller.stop.set())

    remote = dai.RemoteConnection(httpPort=8082)
    remote.registerService("Track State", controller.state)
    remote.registerService("Track Action", controller.action)
    controller.detections = remote.addTopic(
        "Target", group="tracking", maxSize=2, useVisualizationIfAvailable=False
    )
    controller.segmentation = remote.addTopic(
        "_Mask", group="diagnostics", maxSize=2, useVisualizationIfAvailable=False
    )
    controller.annotations = remote.addTopic(
        "Outline and trail", group="tracking", maxSize=2
    )
    topics = ["Target", "_Mask", "Outline and trail"]

    try:
        with dai.Pipeline() as pipeline:
            features = pipeline.getDefaultDevice().getConnectedCameraFeatures()
            log.info("Connected cameras: %s", features)
            color = [
                f for f in features if dai.CameraSensorType.COLOR in f.supportedTypes
            ]
            if not color:
                raise RuntimeError("Track Anything requires a connected color camera")

            socket = next(
                (f.socket for f in color if f.socket == dai.CameraBoardSocket.CAM_A),
                color[0].socket,
            )

            camera = pipeline.create(dai.node.Camera).build(socket)
            frames = camera.requestOutput(
                (1280, 720), type=dai.ImgFrame.Type.NV12, fps=20
            )
            output = frames.createOutputQueue(maxSize=1, blocking=False)

            # Encode matched frames from the publisher, not unsynchronized camera output.
            publisher = pipeline.create(TrackingPublisher)
            publisher.controller = controller
            encoder = pipeline.create(dai.node.VideoEncoder).build(
                publisher.video,
                frameRate=20,
                profile=dai.VideoEncoderProperties.Profile.H264_MAIN,
            )

            remote.addTopic("Video", encoder.out, "tracking")
            topics.append("Video")

            pipeline.start()
            log.info("Pipeline started.")

            remote.registerPipeline(pipeline)

            workers = [
                threading.Thread(
                    target=controller.capture, args=(output,), name="capture"
                ),
                threading.Thread(target=controller.worker, name="inference"),
            ]
            for worker in workers:
                worker.start()

            try:
                while pipeline.isRunning() and not controller.stop.is_set():
                    pipeline.processTasks()
                    if remote.waitKey(1) == ord("q"):
                        log.info("Received q. Stopping the app...")
                        break

            finally:
                controller.stop.set()
                for worker in workers:
                    worker.join()
    finally:
        controller.stop.set()
        for topic in topics:
            remote.removeTopic(topic)

    log.info("Application stopped.")


if __name__ == "__main__":
    main()
