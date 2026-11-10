"""Hardware-free U01 checks. Run with the examples' depthai/depthai-nodes versions."""

from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import ast
import importlib.util
import math
from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import depthai as dai
from depthai_nodes import GatheredData
from depthai_nodes.node.utils.message_remapping import remap_message
import numpy as np


class CoordinateMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.modules = {}
        for name, directory, filename in (
            ("human", "neural-networks/pose-estimation/human-pose", "annotation_node"),
            (
                "animal",
                "neural-networks/pose-estimation/animal-pose",
                "annotation_node",
            ),
            ("objectron", "neural-networks/detection-3d/objectron", "annotation_node"),
            ("hand_configs", "neural-networks/pose-estimation/hand-pose", "process"),
            ("zoom", "camera-controls/lossless-zooming", "crop_face"),
            (
                "depth_crop",
                "neural-networks/segmentation/depth-crop",
                "annotation_node",
            ),
            ("qr", "tutorials/qr-with-tiling", "merge_img_detections"),
            (
                "stitch",
                "tutorials/multiple-devices/multiple-device-stitch-nn",
                "merge_img_detections",
            ),
            (
                "gaze",
                "neural-networks/face-detection/gaze-estimation",
                "process_keypoints",
            ),
            (
                "calibration",
                "tutorials/multiple-devices/multi-cam-calibration",
                "calibration_node",
            ),
        ):
            spec = importlib.util.spec_from_file_location(
                name, root / directory / "utils" / f"{filename}.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.modules[name] = module
        sys.path.insert(0, str(root / "neural-networks/pose-estimation/hand-pose"))
        spec = importlib.util.spec_from_file_location(
            "hand",
            root / "neural-networks/pose-estimation/hand-pose/utils/annotation_node.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.path.pop(0)
        cls.modules["hand"] = module
        qr_utils = ModuleType("utils")
        qr_utils.__path__ = [str(root / "tutorials/qr-with-tiling/utils")]
        spec = importlib.util.spec_from_file_location(
            "qr_scanner", Path(qr_utils.__path__[0]) / "host_qr_scanner.py"
        )
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"utils": qr_utils}):
            spec.loader.exec_module(module)
        cls.modules["qr_scanner"] = module
        package = ModuleType("volume")
        package.__path__ = [
            str(root / "apps/object-volume-measurement-3d/backend/src/utils")
        ]
        sys.modules["volume"] = package
        spec = importlib.util.spec_from_file_location(
            "volume.annotation_node", Path(package.__path__[0]) / "annotation_node.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.modules["volume"] = module
        spec = importlib.util.spec_from_file_location(
            "grid", root / "apps/qr-tiling/backend/src/tiling/tile_grid_overlay.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.modules["grid"] = module
        spec = importlib.util.spec_from_file_location(
            "outlines",
            root
            / "apps/dino-tracking/backend/src/annotations/outlines_overlay_node.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.modules["outlines"] = module

    @staticmethod
    def configure_nodes(path, names, namespace):
        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / path).read_text())
        setup = []
        for statement in ast.walk(tree):
            if isinstance(statement, ast.Assign):
                if any(
                    isinstance(t, ast.Name) and t.id in names for t in statement.targets
                ):
                    setup.append(ast.unparse(statement))
            elif isinstance(statement, ast.Expr) and isinstance(
                statement.value, ast.Call
            ):
                call = statement.value
                if isinstance(call.func, ast.Attribute) and call.func.attr.startswith(
                    "set"
                ):
                    if any(
                        ast.unparse(call.func).startswith(name + ".") for name in names
                    ):
                        setup.append(ast.unparse(statement))
        exec("\n".join(setup), namespace)
        return namespace

    def test_tiling_align_preserves_bursts_with_one_target(self):
        for path, name in (
            ("apps/qr-tiling/backend/src/main.py", "detections_in_display_space"),
            ("apps/focused-vision/backend/src/main.py", "face_det_coordinates_mapper"),
            (
                "apps/focused-vision/backend/src/main.py",
                "face_detection_tiling_remapper",
            ),
        ):
            with (
                self.subTest(node=name),
                ThreadPoolExecutor(max_workers=1) as sender,
                dai.Pipeline(False) as pipeline,
            ):
                namespace = self.configure_nodes(
                    path, {name}, {"pipeline": pipeline, "dai": dai}
                )
                align = namespace[name]
                align.setRunOnHost(True)
                source = align.input
                target = align.inputAlignTo.createInputQueue()
                tile_count = 8
                capacity = align.input.getMaxSize()
                self.assertLess(capacity, tile_count)
                output = align.outputAligned.createOutputQueue(
                    maxSize=tile_count, blocking=True
                )
                frame = dai.ImgFrame()
                frame.setCvFrame(
                    np.zeros((48, 64, 3), np.uint8), dai.ImgFrame.Type.BGR888i
                )
                transform = dai.ImgTransformation(64, 48)
                transform.setExtrinsics(
                    dai.Extrinsics(
                        np.eye(3).tolist(),
                        dai.Point3f(0, 0, 0),
                        dai.CameraBoardSocket.CAM_A,
                    )
                )
                frame.setTransformation(transform)
                target.send(frame)
                messages = []
                for i in range(tile_count):
                    message = dai.ImgDetections()
                    crop = frame.getTransformation().addCrop(
                        (i % 4) * 16, (i // 4) * 24, 16, 24
                    )
                    message.setTransformation(crop)
                    message.setSequenceNum(42)
                    det = dai.ImgDetection()
                    det.xmin, det.ymin, det.xmax, det.ymax = 0.25, 0.25, 0.75, 0.75
                    det.label = i
                    message.detections = [det]
                    messages.append(message)
                for message in messages[:capacity]:
                    source.send(message)
                pending = sender.submit(source.send, messages[capacity])
                with self.assertRaises(
                    TimeoutError,
                    msg="A full queue must block the producer rather than drop a tile",
                ):
                    pending.result(timeout=0.05)
                pipeline.start()
                pending.result(timeout=1)
                for message in messages[capacity + 1 :]:
                    source.send(message)
                for i in range(tile_count):
                    result = output.get(timedelta(seconds=1))
                    self.assertIsNotNone(
                        result, "Every tile must emit without another target frame"
                    )
                    self.assertEqual(result.detections[0].label, i)
                    self.assertEqual(result.getSequenceNum(), 42)

    def test_volume_sync_and_rgbd_share_tolerance_and_clock(self):
        with dai.Pipeline(False) as pipeline:
            namespace = self.configure_nodes(
                "apps/object-volume-measurement-3d/backend/src/main.py",
                {"sync", "rgbd_seg", "rgbd_sync"},
                {
                    "pipeline": pipeline,
                    "dai": dai,
                    "timedelta": timedelta,
                    "args": SimpleNamespace(fps_limit=8),
                },
            )
            sync = namespace["sync"]
            inner = namespace["rgbd_seg"].inColor.getParent()
            self.assertEqual(inner.getSyncThreshold(), sync.getSyncThreshold())
            self.assertEqual(inner.getTimestampSource(), sync.getTimestampSource())
            self.assertEqual(
                inner.getTimestampSource(), dai.node.Sync.TimestampSource.DEVICE
            )
            threshold, clock = inner.getSyncThreshold(), inner.getTimestampSource()
        with dai.Pipeline(False) as pipeline:
            sync = pipeline.create(dai.node.Sync)
            sync.setRunOnHost(True)
            sync.setSyncThreshold(threshold)
            sync.setTimestampSource(clock)
            rgb = sync.inputs["rgb"].createInputQueue()
            depth = sync.inputs["depth"].createInputQueue()
            output = sync.out.createOutputQueue()
            pipeline.start()
            for i in range(3):
                a, b = dai.Buffer(), dai.Buffer()
                a.setSequenceNum(i)
                b.setSequenceNum(i)
                a.setTimestamp(timedelta(seconds=100 + i * 0.125))
                b.setTimestamp(timedelta(seconds=101 + i * 0.125))
                a.setTimestampDevice(timedelta(seconds=1 + i * 0.125))
                b.setTimestampDevice(timedelta(seconds=1 + i * 0.125, milliseconds=20))
                rgb.send(a)
                depth.send(b)
                group = output.get(timedelta(seconds=1))
                self.assertIsNotNone(
                    group, "A 20 ms pair accepted upstream must also pass RGBD sync"
                )
                self.assertEqual(
                    group["rgb"].getSequenceNum(), group["depth"].getSequenceNum()
                )

    def test_dino_requests_an_undistorted_shared_preview(self):
        camera = Mock()
        self.configure_nodes(
            "apps/dino-tracking/backend/src/main.py",
            {"rgb_sensor"},
            {
                "camera": camera,
                "dai": dai,
                "constants": SimpleNamespace(
                    camera=SimpleNamespace(resolution=(1280, 720), fps=20)
                ),
            },
        )
        self.assertTrue(camera.requestOutput.call_args.kwargs["enableUndistortion"])

    def test_pose_overlays_follow_crop_padding_rotation_and_sensor_size(self):
        for scale in (1, 2):
            target = dai.ImgTransformation(640 * scale, 480 * scale)
            for mode in ("offset", "letterbox", "rotation", "clipped"):
                crop = dai.ImgTransformation(640 * scale, 480 * scale)
                crop.addCrop(100 * scale, 50 * scale, 320 * scale, 200 * scale)
                point = (0.25, 0.5)
                expected = (180 / 640, 150 / 480)
                if mode == "letterbox":
                    crop.addScale(0.5, 0.5).addPadding(30 * scale, 30 * scale, 0, 0)
                elif mode == "rotation":
                    crop.addRotation(90, dai.Point2f(0.5, 0.5, True))
                    point = (0.5, 0.25)
                    expected = (210 / 640, 150 / 480)
                elif mode == "clipped":
                    crop = dai.ImgTransformation(640 * scale, 480 * scale)
                    crop.addCrop(-100 * scale, -50 * scale, 320 * scale, 200 * scale)
                    expected = (-20 / 640, 50 / 480)
                keypoints = dai.beta.Keypoints()
                keypoints.setTransformation(crop)
                keypoints.setKeypoints(
                    [
                        dai.Keypoint(dai.Point2f(*point, True), 0.9),
                        dai.Keypoint(dai.Point2f(0.6, 0.6, True), 0.9),
                    ]
                )
                reference = dai.ImgDetections()
                reference.setTransformation(target)
                reference.setTimestamp(timedelta(seconds=3))
                reference.setTimestampDevice(timedelta(seconds=2))
                reference.setSequenceNum(42)
                detection = dai.ImgDetection()
                detection.xmin, detection.ymin = 0.1, 0.1
                detection.xmax, detection.ymax = 0.9, 0.9
                reference.detections = [detection]
                gathered = GatheredData(reference_data=reference, items=[keypoints])
                for name in ("human", "animal", "objectron"):
                    with self.subTest(example=name, mode=mode, scale=scale):
                        sink = Mock()
                        node = SimpleNamespace(
                            connection_pairs=[[0, 1]],
                            keypoint_conf_threshold=0.5,
                            out_pose_annotations=sink,
                            out_detections=Mock(),
                        )
                        self.modules[name].AnnotationNode.process(node, gathered)
                        annotations = sink.send.call_args.args[0]
                        points = [
                            (p.x, p.y)
                            for ann in annotations.annotations
                            for shape in ann.points
                            for p in shape.points
                        ]
                        self.assertTrue(any(np.allclose(p, expected) for p in points))
                        self.assertEqual(annotations.getSequenceNum(), 42)
                        self.assertEqual(
                            annotations.getTimestampDevice(),
                            reference.getTimestampDevice(),
                        )
                        self.assertTrue(
                            annotations.getTransformation().isEqualTransformation(
                                target
                            )
                        )
                        self.assertTrue(
                            keypoints.getTransformation().isEqualTransformation(crop)
                        )

    def test_zoom_uses_actual_source_geometry(self):
        module = self.modules["zoom"]
        source = dai.ImgFrame()
        source.setCvFrame(np.zeros((720, 1280, 3), np.uint8), dai.ImgFrame.Type.BGR888i)
        source.setTransformation(dai.ImgTransformation(1280, 720))
        detections = dai.ImgDetections()
        letterbox = (
            source.getTransformation().addScale(0.5, 0.5).addPadding(140, 140, 0, 0)
        )
        detections.setTransformation(letterbox)
        det = dai.ImgDetection()
        det.xmin, det.xmax, det.ymin, det.ymax = 0.70, 0.80, 0.45, 0.55
        detections.detections = [det]
        for size, expected in (
            ((320, 180), (0.75, 0.5, 0.25, 0.25)),
            ((1920, 1088), (0.5, 0.5, 1, 1)),
        ):
            with self.subTest(target_size=size):
                node = SimpleNamespace(
                    target_size=size,
                    resize_mode=dai.ImageManipConfig.ResizeMode.CENTER_CROP,
                    _average_filter=lambda x, y: (x, y),
                    config_output=Mock(),
                )
                with patch.object(module.dai, "ImageManipConfig") as config:
                    module.CropFace.process(node, detections, source)
                    rect = config.return_value.addCropRotatedRect.call_args.args[0]
                np.testing.assert_allclose(
                    (rect.center.x, rect.center.y, rect.size.width, rect.size.height),
                    expected,
                    atol=1e-6,
                )

    def test_merge_remaps_each_tile_and_preserves_reference(self):
        reference = dai.ImgFrame()
        reference.setTransformation(dai.ImgTransformation(640, 480))
        reference.setSequenceNum(42)
        reference.setTimestamp(timedelta(seconds=3))
        reference.setTimestampDevice(timedelta(seconds=2))
        items = []
        for offset, label in ((0, 11), (320, 22)):
            message = dai.ImgDetections()
            message.setTransformation(
                dai.ImgTransformation(640, 480).addCrop(offset, 120, 320, 240)
            )
            message.setBufferMetadataFrom(reference)
            det = dai.ImgDetection()
            det.label = label
            det.xmin, det.ymin, det.xmax, det.ymax = 0.25, 0.25, 0.75, 0.75
            message.detections = [det]
            items.append(message)
        for name in ("qr", "stitch"):
            for leaves in (items, []):
                with self.subTest(example=name, count=len(leaves)):
                    grouped = GatheredData(reference_data=reference, items=leaves)
                    node = SimpleNamespace(out=Mock())
                    self.modules[name].MergeImgDetections.process(node, grouped)
                    result = node.out.send.call_args.args[0]
                    self.assertEqual(
                        [d.label for d in result.detections], [11, 22] if leaves else []
                    )
                    for det, center in zip(result.detections, (0.25, 0.75)):
                        self.assertAlmostEqual(det.getBoundingBox().center.x, center)
                        self.assertAlmostEqual(det.getBoundingBox().center.y, 0.5)
                    self.assertIs(grouped.reference_data, reference)
                    self.assertEqual(
                        result.getSequenceNum(), reference.getSequenceNum()
                    )
                    self.assertEqual(result.getTimestamp(), reference.getTimestamp())
                    self.assertEqual(
                        result.getTimestampDevice(), reference.getTimestampDevice()
                    )
                    self.assertTrue(
                        result.getTransformation().isEqualTransformation(
                            reference.getTransformation()
                        )
                    )

    def test_qr_outputs_preserve_source_metadata(self):
        module = self.modules["qr_scanner"]
        with dai.Pipeline(False) as pipeline, patch.object(module, "DECODE", False):
            frame = dai.ImgFrame()
            frame.setCvFrame(np.zeros((48, 64, 3), np.uint8), dai.ImgFrame.Type.BGR888i)
            frame.setTransformation(dai.ImgTransformation(64, 48))
            frame.setTimestamp(timedelta(seconds=3))
            frame.setTimestampDevice(timedelta(seconds=2))
            frame.setSequenceNum(42)
            detections = dai.ImgDetections()
            detections.setBufferMetadataFrom(frame)
            node = pipeline.create(module.QRScanner)
            node._out, node._out_grid = Mock(), Mock()
            node.tile_positions = [(0, 0, 32, 24)]
            node.process(frame, detections)
            qr = node.out.send.call_args.args[0]
            grid = node.out_grid.send.call_args.args[0]
            for message in (qr, grid, qr.getVisualizationMessage()):
                self.assertEqual(message.getTimestamp(), frame.getTimestamp())
                self.assertEqual(
                    message.getTimestampDevice(), frame.getTimestampDevice()
                )
                self.assertEqual(message.getSequenceNum(), 42)
            self.assertTrue(
                grid.getTransformation().isEqualTransformation(
                    frame.getTransformation()
                )
            )

    def test_hand_crop_configs_preserve_source_metadata(self):
        detections = dai.ImgDetections()
        detections.setTimestamp(timedelta(seconds=3))
        detections.setTimestampDevice(timedelta(seconds=2))
        detections.setSequenceNum(42)
        detection = dai.ImgDetection()
        detection.xmin, detection.ymin, detection.xmax, detection.ymax = (
            0.2,
            0.2,
            0.6,
            0.6,
        )
        detections.detections = [detection]
        node = SimpleNamespace(
            padding=0.1, _target_w=224, _target_h=224, config_output=Mock()
        )
        self.modules["hand_configs"].ProcessDetections.process(node, detections)
        group = node.config_output.send.call_args.args[0]
        for message in (group, group["cfg_0"]):
            self.assertEqual(message.getTimestamp(), detections.getTimestamp())
            self.assertEqual(
                message.getTimestampDevice(), detections.getTimestampDevice()
            )
            self.assertEqual(message.getSequenceNum(), 42)

    def test_hand_landmarks_gestures_and_crop_box_use_rotated_geometry(self):
        module = self.modules["hand"]
        with dai.Pipeline(False) as pipeline:
            node = pipeline.create(module.AnnotationNode)
            node.out_detections, node.out_pose_annotations = Mock(), Mock()
            node.connection_pairs = [[0, 1]]
            frame = dai.ImgFrame()
            frame.setTransformation(
                dai.ImgTransformation(640, 480)
                .addScale(1.2, 1.2)
                .addPadding(96, 96, 0, 0)
            )
            detections = dai.ImgDetections()
            detections.setTransformation(dai.ImgTransformation(640, 480))
            detections.setSequenceNum(42)
            detections.setTimestampDevice(timedelta(seconds=2))
            palm = dai.ImgDetection()
            palm.xmin, palm.ymin, palm.xmax, palm.ymax = 0.1, 0.1, 0.9, 0.9
            detections.detections = [palm]
            keypoints = dai.beta.Keypoints()
            keypoints.setTransformation(
                dai.ImgTransformation(640, 480)
                .addCrop(100, 50, 320, 200)
                .addRotation(90, dai.Point2f(0.5, 0.5, True))
            )
            keypoints.setKeypoints(
                [dai.Keypoint(dai.Point2f(0.5, 0.25, True), 0.9)] * 21
            )
            prediction = dai.beta.Prediction()
            prediction.prediction = 0.9
            confidence = dai.beta.Predictions()
            confidence.predictions = [prediction]
            outputs = dai.MessageGroup()
            outputs["0"], outputs["1"], outputs["2"] = keypoints, confidence, confidence
            gathered = GatheredData(reference_data=detections, items=[outputs])
            with patch.object(
                module, "recognize_gesture", return_value="FIVE"
            ) as gesture:
                node.process(gathered, frame)
                np.testing.assert_allclose(
                    gesture.call_args.args[0][0], (252 / 768, 276 / 768)
                )
            result = node.out_detections.send.call_args.args[0]
            rect = result.detections[0].getBoundingBox()
            np.testing.assert_allclose(
                (rect.center.x, rect.center.y), (312 / 768, 276 / 768)
            )
            self.assertEqual(result.getSequenceNum(), 42)
            self.assertEqual(
                node.out_pose_annotations.send.call_args.args[0].getTimestampDevice(),
                detections.getTimestampDevice(),
            )

    def test_gaze_crops_and_calibration_axes_follow_offset_frames(self):
        with dai.Pipeline(False) as pipeline:
            frame = dai.ImgFrame()
            frame.setCvFrame(
                np.zeros((480, 640, 3), np.uint8), dai.ImgFrame.Type.BGR888i
            )
            frame.setTransformation(dai.ImgTransformation(640, 480))
            frame.setSequenceNum(42)
            detections = dai.ImgDetections()
            detections.setTransformation(
                dai.ImgTransformation(640, 480).addCrop(100, 50, 320, 200)
            )
            det = dai.ImgDetection()
            det.xmin, det.ymin, det.xmax, det.ymax = 0.1, 0.1, 0.9, 0.9
            det.setKeypoints(
                [
                    dai.Keypoint(dai.Point2f(0.25, 0.5, True)),
                    dai.Keypoint(dai.Point2f(0.75, 0.5, True)),
                ]
            )
            detections.detections = [det]
            detections.setBufferMetadataFrom(frame)
            node = pipeline.create(self.modules["gaze"].LandmarksProcessing)
            node.create_crop_cfg = Mock(wraps=node.create_crop_cfg)
            (
                node.left_config_output,
                node.right_config_output,
                node.face_config_output,
            ) = Mock(), Mock(), Mock()
            node.process(detections, frame)
            rect = node.create_crop_cfg.call_args_list[0].args[0]
            np.testing.assert_allclose((rect.center.x, rect.center.y), (180, 150))
            self.assertEqual(
                node.face_config_output.send.call_args.args[0].getSequenceNum(), 42
            )
            calibration = pipeline.create(self.modules["calibration"].CalibrationNode)
            calibration.calib = True
            calibration.rot_vec, calibration.trans_vec = (
                np.zeros(3),
                np.array([0.0, 0.0, 10.0]),
            )
            calibration.intrinsic_mat_still = np.array(
                [[100.0, 0.0, 160.0], [0.0, 100.0, 100.0], [0.0, 0.0, 1.0]]
            )
            calibration.still_transformation = detections.getTransformation()
            calibration.annotation_out = Mock()
            calibration.process(frame)
            annotations = calibration.annotation_out.send.call_args.args[0]
            origin = annotations.annotations[0].points[0].points[0]
            np.testing.assert_allclose((origin.x, origin.y), (260 / 640, 150 / 480))

    def test_license_plate_script_uses_the_actual_inference_transform(self):
        root = Path(__file__).resolve().parents[1]
        frame = dai.ImgFrame()
        frame.setCvFrame(np.zeros((480, 640, 3), np.uint8), dai.ImgFrame.Type.BGR888i)
        frame.setTransformation(dai.ImgTransformation(640, 480))
        reference = dai.ImgDetections()
        reference.detections = [dai.ImgDetection()]
        reference.setSequenceNum(42)
        reference.setTimestampDevice(timedelta(seconds=2))
        plate = dai.ImgDetections()
        plate.setTransformation(
            dai.ImgTransformation(640, 480)
            .addCrop(100, 50, 320, 200)
            .addScale(2, 2)
            .addPadding(120, 120, 0, 0)
        )
        det = dai.ImgDetection()
        det.setOuterBoundingBox(0.25, 0.4, 0.75, 0.6)
        det.confidence = 0.9
        plate.detections = [det]
        node = SimpleNamespace(
            inputs={
                name: Mock()
                for name in (
                    "frame_input",
                    "detections_input",
                    "license_plate_detections",
                )
            },
            outputs={
                name: Mock()
                for name in (
                    "lp_crop_config",
                    "lp_crop_frame",
                    "output_valid_crops",
                    "output_valid_detections",
                )
            },
            warn=Mock(),
        )
        node.inputs["frame_input"].get.side_effect = [frame, StopIteration()]
        node.inputs["detections_input"].get.return_value = reference
        node.inputs["license_plate_detections"].get.return_value = plate
        runpy.run_path(
            str(
                root
                / "neural-networks/ocr/license-plate-recognition/utils/license_plate_sender_script.py"
            ),
            init_globals={
                "node": node,
                "ImageManipConfig": dai.ImageManipConfig,
                "ImgDetections": dai.ImgDetections,
            },
        )
        result = node.outputs["output_valid_crops"].send.call_args.args[0]
        crop = result.detections[0]
        np.testing.assert_allclose(
            (crop.xmin, crop.ymin, crop.xmax, crop.ymax),
            (0.28375, 0.253833333, 0.52375, 0.367166667),
            atol=1e-6,
        )
        self.assertEqual(result.getSequenceNum(), 42)
        self.assertEqual(result.getTimestampDevice(), reference.getTimestampDevice())

    def test_mask_remapping_handles_crop_letterbox_and_rotation(self):
        for width, height in ((64, 48), (128, 96)):
            target = dai.ImgTransformation(width, height)
            for angle in (None, 0, 30, 90):
                frame = dai.ImgFrame()
                frame.setTransformation(target)
                source = frame.getTransformation()
                if angle is None:
                    source.addCrop(width // 4, height // 4, width // 2, height // 2)
                    source.addScale(0.5, 0.5).addPadding(height // 8, height // 8, 0, 0)
                    sw, sh = source.getSize()
                    pixels = np.full((sh, sw), 7, np.uint8)
                    pixels[:, : sw // 2] = 0
                    expected = (width * 5 // 8, height // 2)
                else:
                    source.addRotation(angle, dai.Point2f(0.5, 0.5, True))
                    pixels = np.full((height, width), 255, np.uint8)
                    x, y = width // 4, height // 4
                    pixels[y - 2 : y + 3, x - 2 : x + 3] = 7
                    pixels[
                        height // 2 - 2 : height // 2 + 3,
                        width * 5 // 8 - 2 : width * 5 // 8 + 3,
                    ] = 0
                    radians = math.radians(angle)
                    dx, dy = -width / 4, -height / 4
                    expected = (
                        width / 2 + math.cos(radians) * dx + math.sin(radians) * dy,
                        height / 2 - math.sin(radians) * dx + math.cos(radians) * dy,
                    )
                mask = dai.SegmentationMask()
                mask.setCvMask(pixels)
                mask.setTransformation(source)
                mask.setLabels(["zero", "seven"])
                mask.setTimestamp(timedelta(seconds=3))
                mask.setTimestampDevice(timedelta(seconds=2))
                mask.setSequenceNum(42)
                detections = dai.ImgDetections()
                detections.setTransformation(source)
                detections.setBufferMetadataFrom(mask)
                detections.setSegmentationMask(mask.getFrame())
                detection = dai.ImgDetection()
                detection.setBoundingBox(
                    dai.RotatedRect(
                        dai.Point2f(
                            0.75 if angle is None else 0.25,
                            0.5 if angle is None else 0.25,
                            True,
                        ),
                        dai.Size2f(0.1, 0.1, True),
                        0,
                    )
                )
                detections.detections = [detection]
                for message in (mask, detections):
                    with self.subTest(
                        size=(width, height), angle=angle, type=type(message).__name__
                    ):
                        result = remap_message(message, source, target)
                        aligned = (
                            result.getCvMask()
                            if isinstance(result, dai.SegmentationMask)
                            else result.getCvSegmentationMask()
                        )
                        self.assertEqual(aligned.shape, (height, width))
                        self.assertEqual(set(np.unique(aligned)), {0, 7, 255})
                        ex, ey = (round(v) for v in expected)
                        self.assertEqual(aligned[ey, ex], 7)
                        if angle is not None:
                            ys, xs = np.where(aligned == 7)
                            np.testing.assert_allclose(
                                (xs.mean(), ys.mean()), expected, atol=0.5
                            )
                        self.assertEqual(result.getTimestamp(), message.getTimestamp())
                        self.assertEqual(
                            result.getTimestampDevice(), message.getTimestampDevice()
                        )
                        self.assertEqual(result.getSequenceNum(), 42)
                        if isinstance(result, dai.ImgDetections):
                            center = result.detections[0].getBoundingBox().center
                            np.testing.assert_allclose(
                                (center.x * width, center.y * height),
                                expected,
                                atol=1e-4,
                            )
                        original = (
                            message.getCvMask()
                            if isinstance(message, dai.SegmentationMask)
                            else message.getCvSegmentationMask()
                        )
                        np.testing.assert_array_equal(original, pixels)

    def test_rotated_semantic_mask_cuts_out_the_matching_depth_pixels(self):
        preview, depth = dai.ImgFrame(), dai.ImgFrame()
        preview.setCvFrame(np.zeros((48, 64, 3), np.uint8), dai.ImgFrame.Type.BGR888i)
        preview.setTransformation(dai.ImgTransformation(64, 48))
        preview.setSequenceNum(42)
        depth.setCvFrame(np.full((48, 64, 3), 100, np.uint8), dai.ImgFrame.Type.BGR888i)
        mask = dai.SegmentationMask()
        pixels = np.full((48, 64), 255, np.uint8)
        pixels[10:15, 14:19] = 15
        mask.setCvMask(pixels)
        mask.setTransformation(
            preview.getTransformation().addRotation(90, dai.Point2f(0.5, 0.5, True))
        )
        node = SimpleNamespace(
            output_segmentation=Mock(),
            output_cutout=Mock(),
            output_depth=Mock(),
            person_class=15,
        )
        self.modules["depth_crop"].AnnotationNode.process(node, preview, depth, mask)
        cutout = node.output_cutout.send.call_args.args[0]
        result = cutout.getCvFrame()
        self.assertTrue((result[40, 20] > 90).all())
        self.assertFalse(result[12, 16].any())
        self.assertEqual(cutout.getSequenceNum(), 42)

    def test_volume_selection_preserves_rgb_metadata_and_ignores_background(self):
        module = self.modules["volume"]
        for angle, click_x, expected_mode in (
            (0, 0.25, 1),
            (0, 0.75, 0),
            (90, 0.25, 1),
            (90, 0.75, 0),
        ):
            with self.subTest(angle=angle, click_x=click_x), dai.Pipeline(
                False
            ) as pipeline:
                node = pipeline.create(module.AnnotationNode)
                node.isRunning = Mock(side_effect=[True, False])
                node.in_meas_result = Mock()
                node.in_meas_result.tryGet.return_value = None
                for name in ("out_ann", "out_selection", "out_segm", "out_segm_depth"):
                    setattr(node, name, Mock())
                rgb = dai.ImgFrame()
                rgb.setCvFrame(
                    np.zeros((48, 64, 3), np.uint8), dai.ImgFrame.Type.RGB888i
                )
                rgb.setTransformation(dai.ImgTransformation(64, 48))
                rgb.setTimestamp(timedelta(seconds=3))
                rgb.setTimestampDevice(timedelta(seconds=2))
                rgb.setSequenceNum(42)
                depth = dai.ImgFrame()
                depth.setFrame(np.full((48, 64), 1000, np.uint16))
                depth.setType(dai.ImgFrame.Type.RAW16)
                depth.setWidth(64)
                depth.setHeight(48)
                depth.setTransformation(rgb.getTransformation())
                depth.setTimestamp(timedelta(seconds=3, milliseconds=2))
                depth.setSequenceNum(43)
                mask = dai.ImgFrame()
                pixels = np.full((48, 64), 255, np.uint8)
                pixels[:, :32] = 0
                expected_pixels = pixels
                source = rgb.getTransformation()
                if angle:
                    source.addRotation(angle, dai.Point2f(0.5, 0.5, True))
                    pixels = np.full((48, 64), 255, np.uint8)
                    pixels[:24, :] = 0
                    expected_pixels = np.full((48, 64), 255, np.uint8)
                    expected_pixels[:, 8:32] = 0
                mask.setCvFrame(pixels, dai.ImgFrame.Type.GRAY8)
                mask.setTransformation(source)
                detections = dai.ImgDetections()
                detections.setTransformation(source)
                detections.setBufferMetadataFrom(rgb)
                detections.setSegmentationMask(mask)
                det = dai.ImgDetection()
                det.xmin, det.ymin, det.xmax, det.ymax = 0.1, 0.1, 0.9, 0.9
                detections.detections = [det]
                group = dai.MessageGroup()
                group["detections"], group["rgb"], group["depth"] = (
                    detections,
                    rgb,
                    depth,
                )
                node.in_sync = Mock()
                node.in_sync.get.return_value = group
                node.setSelectionPoint(click_x, 0.5)
                node.run()
                mode = node.out_selection.send.call_args.args[0]
                self.assertEqual(bytes(mode.getData())[0], expected_mode)
                self.assertEqual(mode.getSequenceNum(), 42)
                self.assertEqual(mode.getTimestampDevice(), rgb.getTimestampDevice())
                self.assertIs(node.out_segm.send.call_args.args[0], rgb)
                output_depth = node.out_segm_depth.send.call_args.args[0]
                if expected_mode == 1:
                    np.testing.assert_array_equal(
                        output_depth.getFrame(), np.where(expected_pixels == 0, 1000, 0)
                    )
                    self.assertEqual(output_depth.getSequenceNum(), 43)
                else:
                    self.assertIs(output_depth, depth)

    def test_volume_rotated_boxes_use_pixel_geometry(self):
        module = self.modules["volume"]
        target = dai.ImgTransformation(640, 400)
        source = (
            dai.ImgTransformation(640, 400)
            .addCrop(80, 40, 400, 240)
            .addRotation(30, dai.Point2f(0.5, 0.5, True))
        )
        detections = dai.ImgDetections()
        detections.setTransformation(source)
        detection = dai.ImgDetection()
        detection.setOuterBoundingBox(0.25, 0.25, 0.75, 0.75)
        detections.detections = [detection]
        detection = detections.transformTo(target).detections[0]
        with dai.Pipeline(False) as pipeline:
            node = pipeline.create(module.AnnotationNode)
            node._dst_size = (640, 400)
            with self.subTest(consumer="selection"):
                self.assertTrue(node._contains_point(detection, 325 / 640, 100 / 400))
            with self.subTest(consumer="drawing"), patch.object(module, "draw_label"):
                helper = Mock()
                node._draw_rotrect_and_label(helper, detection, "selected")
                actual = np.array(helper.draw_polyline.call_args.args[0]) * (640, 400)
                expected = np.array(
                    [
                        (163.39746, 158.03848),
                        (336.60254, 58.03848),
                        (396.60254, 161.96152),
                        (223.39746, 261.96152),
                    ]
                )
                distances = np.linalg.norm(actual[:, None] - expected[None], axis=2)
                self.assertLess(
                    max(distances.min(0).max(), distances.min(1).max()), 0.001
                )

    def test_outlines_keep_instance_zero_and_follow_rotation(self):
        for angle, edge, center in ((0, (12, 14), (12, 16)), (90, (40, 18), (40, 20))):
            with self.subTest(angle=angle):
                frame = dai.ImgFrame()
                frame.setCvFrame(
                    np.zeros((48, 64, 3), np.uint8), dai.ImgFrame.Type.BGR888i
                )
                frame.setTransformation(dai.ImgTransformation(64, 48))
                pixels = np.full((48, 64), 255, np.uint8)
                pixels[10:15, 14:19] = 0
                mask = dai.SegmentationMask()
                mask.setCvMask(pixels)
                mask.setTransformation(
                    frame.getTransformation().addRotation(
                        angle, dai.Point2f(0.5, 0.5, True)
                    )
                )
                node = SimpleNamespace(
                    _is_active=True, _kernel=np.ones((3, 3), np.uint8), _send=Mock()
                )
                self.modules["outlines"].OutlinesOverlay.process(node, frame, mask)
                result = node._send.call_args.args[0]
                self.assertGreater(result[edge][1], 0)
                self.assertFalse(result[center].any())

    def test_crop_control_sync_uses_device_clock(self):
        for name, cls, detection_input, output_name in (
            (
                "zoom",
                self.modules["zoom"].CropFace,
                "detection_message",
                "config_output",
            ),
            (
                "gaze",
                self.modules["gaze"].LandmarksProcessing,
                "img_detections",
                "face_config_output",
            ),
        ):
            with self.subTest(node=name), dai.Pipeline(False) as pipeline:
                node = pipeline.create(cls)
                detections = node.inputs[detection_input].createInputQueue()
                source = node.inputs["source"].createInputQueue()
                output = getattr(node, output_name).createOutputQueue()
                pipeline.start()
                for sequence in range(3):
                    frame = dai.ImgFrame(0)
                    frame.setWidth(640)
                    frame.setHeight(480)
                    frame.setTransformation(dai.ImgTransformation(640, 480))
                    frame.setTimestamp(timedelta(seconds=2 + sequence))
                    frame.setTimestampDevice(frame.getTimestamp())
                    frame.setSequenceNum(sequence)
                    message = dai.ImgDetections()
                    message.setTransformation(frame.getTransformation())
                    message.setTimestamp(timedelta(seconds=100 + sequence))
                    message.setTimestampDevice(frame.getTimestampDevice())
                    message.setSequenceNum(sequence)
                    detections.send(message)
                    source.send(frame)
                    result = output.get(timedelta(seconds=1))
                    self.assertIsNotNone(
                        result, "RVC2 metadata must sync on device time"
                    )
                    self.assertEqual(result.getSequenceNum(), sequence)
                    self.assertEqual(result.getTimestamp(), message.getTimestamp())
                    self.assertEqual(
                        result.getTimestampDevice(), message.getTimestampDevice()
                    )

    def test_source_metadata_scripts_and_rotated_tile_grid(self):
        root = Path(__file__).resolve().parents[1]
        source = dai.ImgFrame()
        source.setCvFrame(np.zeros((480, 640, 3), np.uint8), dai.ImgFrame.Type.BGR888i)
        source.setTransformation(dai.ImgTransformation(640, 480))
        source.setTimestamp(timedelta(seconds=3))
        source.setTimestampDevice(timedelta(seconds=2))
        source.setSequenceNum(42)
        for directory in (
            "camera-controls/lossless-zooming",
            "neural-networks/face-detection/gaze-estimation",
        ):
            tree = ast.parse((root / directory / "main.py").read_text())
            script = next(
                call.args[0].value
                for call in ast.walk(tree)
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "setScript"
                and isinstance(call.args[0], ast.Constant)
            )
            node = SimpleNamespace(
                inputs={"source": Mock()}, outputs={"metadata": Mock()}
            )
            node.inputs["source"].get.side_effect = [source, StopIteration()]
            with self.assertRaises(StopIteration):
                # RVC2 Script bindings require an explicit payload size.
                exec(
                    script, {"node": node, "ImgFrame": lambda size: dai.ImgFrame(size)}
                )
            metadata = node.outputs["metadata"].send.call_args.args[0]
            self.assertEqual(len(metadata.getData()), 0)
            self.assertEqual((metadata.getWidth(), metadata.getHeight()), (640, 480))
            self.assertEqual(metadata.getTimestamp(), source.getTimestamp())
            self.assertEqual(metadata.getTimestampDevice(), source.getTimestampDevice())
            self.assertEqual(metadata.getSequenceNum(), 42)
            self.assertTrue(
                metadata.getTransformation().isEqualTransformation(
                    source.getTransformation()
                )
            )
        node = SimpleNamespace(_regenerate_colors_if_needed=Mock())
        node._get_tile_positions = lambda: [(160, 120, 480, 360)]
        preview = dai.ImgFrame()
        preview.setCvFrame(np.zeros((200, 320, 3), np.uint8), dai.ImgFrame.Type.BGR888i)
        preview.setTransformation(
            dai.ImgTransformation(640, 480)
            .addCrop(100, 50, 320, 200)
            .addRotation(90, dai.Point2f(0.5, 0.5, True))
        )
        preview.setBufferMetadataFrom(source)
        node._draw_grid = Mock(return_value=preview.getCvFrame())
        node.out = Mock()
        self.modules["grid"].TileGridOverlay.process(node, preview, source)
        polygon = node._draw_grid.call_args.args[1][0]
        np.testing.assert_allclose(
            polygon, [(190, 0), (190, 320), (-50, 320), (-50, 0)], atol=1
        )
        self.assertTrue(
            node.out.send.call_args.args[0]
            .getTransformation()
            .isEqualTransformation(preview.getTransformation())
        )


if __name__ == "__main__":
    unittest.main()
