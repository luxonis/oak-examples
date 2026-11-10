"""Check live camera remapping and the production metadata Scripts."""

import argparse
from datetime import timedelta
import json
from pathlib import Path

import depthai as dai
import numpy as np

from test_coordinate_mapping import CoordinateMappingTests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", required=True, help="Camera DeviceID or IP")
    parser.add_argument("--output", type=Path, help="Optional JSON results file")
    args = parser.parse_args()
    results = []
    with dai.Device(dai.DeviceInfo(args.device)) as device, dai.Pipeline(
        device
    ) as pipeline:
        camera = pipeline.create(dai.node.Camera).build(
            dai.CameraBoardSocket.CAM_A, sensorFps=5
        )
        cases = []
        metadata_checks = []
        for size in ((640, 480), (1280, 960)):
            stream = camera.requestOutput(
                size, fps=5, type=dai.ImgFrame.Type.BGR888i, enableUndistortion=True
            )
            full_queue = stream.createOutputQueue()
            if size == (640, 480):
                metadata_reference = stream.createOutputQueue()
                for directory in (
                    "camera-controls/lossless-zooming",
                    "neural-networks/face-detection/gaze-estimation",
                ):
                    namespace = CoordinateMappingTests.configure_nodes(
                        f"{directory}/main.py",
                        {"source_metadata"},
                        {"pipeline": pipeline, "dai": dai},
                    )
                    metadata = namespace["source_metadata"]
                    stream.link(metadata.inputs["source"])
                    metadata_checks.append(
                        (directory, metadata.outputs["metadata"].createOutputQueue())
                    )
            for angle in (0, 30, 90):
                manip = pipeline.create(dai.node.ImageManip)
                manip.initialConfig.addCrop(
                    size[0] // 8, size[1] // 8, size[0] // 2, size[1] // 2
                )
                manip.initialConfig.addRotateDeg(angle)
                manip.initialConfig.setOutputSize(
                    320, 320, dai.ImageManipConfig.ResizeMode.LETTERBOX
                )
                manip.setMaxOutputFrameSize(320 * 320 * 3)
                stream.link(manip.inputImage)
                cases.append((size, angle, full_queue, manip.out.createOutputQueue()))

        remappers = []
        for path, name in (
            ("apps/qr-tiling/backend/src/main.py", "detections_in_display_space"),
            ("apps/focused-vision/backend/src/main.py", "face_det_coordinates_mapper"),
            (
                "apps/focused-vision/backend/src/main.py",
                "face_detection_tiling_remapper",
            ),
        ):
            namespace = CoordinateMappingTests.configure_nodes(
                path, {name}, {"pipeline": pipeline, "dai": dai}
            )
            align = namespace[name]
            remappers.append(
                (
                    name,
                    align,
                    align.input.createInputQueue(maxSize=64, blocking=True),
                    align.inputAlignTo.createInputQueue(maxSize=1, blocking=True),
                    align.outputAligned.createOutputQueue(maxSize=64, blocking=True),
                )
            )
        pipeline.start()
        print("Pipeline started.", flush=True)
        previous = None
        for _ in range(3):
            reference = metadata_reference.get(timedelta(seconds=5))
            assert reference is not None, "Metadata reference frame timed out"
            for directory, queue in metadata_checks:
                message = queue.get(timedelta(seconds=5))
                assert message is not None, (directory, "Metadata Script timed out")
                assert len(message.getData()) == 0
                assert (message.getWidth(), message.getHeight()) == (640, 480)
                assert message.getTransformation().isValid()
                assert message.getTransformation().getSize() == (640, 480)
                assert message.getSequenceNum() == reference.getSequenceNum()
                assert message.getTimestampDevice() == reference.getTimestampDevice()
                assert message.getTransformation().isEqualTransformation(
                    reference.getTransformation()
                )
                if previous is not None:
                    assert message.getSequenceNum() > previous.getSequenceNum()
                    assert message.getTimestampDevice() > previous.getTimestampDevice()
            previous = reference
        for directory, _ in metadata_checks:
            print(f"PASS: {directory} metadata Script", flush=True)
        for size, angle, full_queue, crop_queue in cases:
            frame = full_queue.get(timedelta(seconds=5))
            crop = crop_queue.get(timedelta(seconds=5))
            assert frame is not None and crop is not None, "Camera stream timed out"
            assert frame.validateTransformations() and crop.validateTransformations()
            for name, align, source, target, output in remappers:
                if device.getPlatform() == dai.Platform.RVC4:
                    assert not align.runOnHost(), "Expected RVC4 device Align"
                target.send(frame)
                expected = []
                for label in range(64):
                    message = dai.ImgDetections()
                    message.setTransformation(crop.getTransformation())
                    message.setBufferMetadataFrom(crop)
                    detection = dai.ImgDetection()
                    detection.xmin, detection.ymin = 0.2, 0.3
                    detection.xmax, detection.ymax = 0.7, 0.8
                    detection.label = label
                    message.detections = [detection]
                    expected.append(message.transformTo(frame.getTransformation()))
                    source.send(message)
                errors = []
                for label in range(64):
                    actual = output.get(timedelta(seconds=5))
                    assert actual is not None, (
                        name,
                        size,
                        angle,
                        label,
                        "Missing result",
                    )
                    assert actual.detections[0].label == label, "Crop order changed"
                    assert actual.getSequenceNum() == crop.getSequenceNum()
                    assert actual.getTimestampDevice() == crop.getTimestampDevice()
                    assert actual.getTimestamp() == crop.getTimestamp()
                    corners = [
                        np.array(
                            [
                                (p.x, p.y)
                                for p in msg.detections[0]
                                .getBoundingBox()
                                .denormalize(*size)
                                .getPoints()
                            ]
                        )
                        for msg in (actual, expected[label])
                    ]
                    distances = np.linalg.norm(
                        corners[0][:, None] - corners[1][None], axis=2
                    )
                    errors.append(
                        float(max(distances.min(0).max(), distances.min(1).max()))
                    )
                result = {
                    "node": name,
                    "size": size,
                    "rotation": angle,
                    "run_on_host": align.runOnHost(),
                    "delivered": 64,
                    "max_error_pixels": max(errors),
                }
                print(json.dumps(result), flush=True)
                assert max(errors) < 0.1, result
                results.append(result)
    if args.output:
        args.output.write_text(json.dumps(results, indent=2) + "\n")
    print(f"PASS: {len(results)} live-camera cases, 64 detections each.")


if __name__ == "__main__":
    main()
