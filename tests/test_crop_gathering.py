"""Exercise the real GatherData matching code without a pipeline or device."""

import importlib.util
import unittest
from datetime import timedelta
from pathlib import Path
from queue import PriorityQueue
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = {
    "barcode": "neural-networks/object-detection/barcode-detection-conveyor-belt/utils",
    "alpr": "neural-networks/ocr/license-plate-recognition/utils",
    "focused": "apps/focused-vision/backend/src",
    "demographics": "apps/people-demographics-and-sentiment-analysis/backend/src",
}


def load_module(path):
    spec = importlib.util.spec_from_file_location(path.parent.parent.name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CropGatheringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import depthai as dai
            from depthai_nodes.node import GatherData
        except ImportError as error:
            raise unittest.SkipTest(
                "Install an affected example's requirements"
            ) from error
        cls.dai = dai
        cls.modules = [
            load_module(ROOT / example / "gather_crops.py")
            for example in EXAMPLES.values()
        ]
        # Rebind SDK methods onto a plain object: C++ HostNode construction needs
        # a pipeline, but matching and buffering themselves are Python code.
        cls.sdk_methods = {
            name: value
            for name, value in vars(GatherData).items()
            if name.startswith("_") and not name.startswith("__")
        }
        cls.sdk_methods.update(
            FPS_TOLERANCE_DIVISOR=GatherData.FPS_TOLERANCE_DIVISOR,
            INPUT_CHECKS_PER_FPS=GatherData.INPUT_CHECKS_PER_FPS,
        )

    def reference(self, sequence, count):
        message = self.dai.ImgDetections()
        message.detections = [self.dai.ImgDetection() for _ in range(count)]
        message.setTimestamp(timedelta(seconds=sequence))
        message.setTimestampDevice(timedelta(seconds=sequence))
        message.setSequenceNum(sequence)
        return message

    def result(self, sequence, index=0):
        message = self.dai.Buffer()
        message.setTimestamp(timedelta(seconds=sequence))
        message.setTimestampDevice(timedelta(seconds=sequence))
        message.setSequenceNum(sequence)
        message.setData([index])
        return message

    def gather(self, references, data, ticks=None, wait_count_fn=None, **limits):
        nodes = []
        for module in self.modules:
            node_type = module.GatherCrops
            harness = type(
                "GatherHarness",
                (),
                dict(
                    self.sdk_methods,
                    run=node_type.run,
                    _send_ready_data=node_type._send_ready_data,
                    TIMEOUT_SECONDS=node_type.TIMEOUT_SECONDS,
                    MAX_PENDING_FRAMES=node_type.MAX_PENDING_FRAMES,
                ),
            )
            node = harness()
            node.__dict__.update(limits)
            node._camera_fps = 25
            node._reference_data = {}
            node._data_by_reference_ts = {}
            node._ready_timestamps = PriorityQueue()
            node._wait_count_fn = wait_count_fn or node._default_wait_count_fn
            node._logger = Mock()
            node.sent = []
            node.out = SimpleNamespace(send=node.sent.append)
            node._reference_input = SimpleNamespace(
                tryGet=lambda stream=iter(references): next(stream, None)
            )
            node._data_input = SimpleNamespace(
                tryGet=lambda stream=iter(data): next(stream, None)
            )
            iterations = ticks or max(len(references), len(data)) + 1
            node.isRunning = Mock(side_effect=[True] * iterations + [False])
            clock = iter(tick / 100 for tick in range(iterations + 1))
            now = 0

            def advance(_):
                nonlocal now
                now = next(clock)

            with patch.object(module, "monotonic", lambda: now), patch.object(
                module, "sleep", advance
            ):
                node.run()
            nodes.append(node)
        return nodes

    def test_zero_one_many_preserve_indices_and_metadata(self):
        references = [self.reference(1, 0), self.reference(2, 1), self.reference(3, 12)]
        data = [None, self.result(2)] + [self.result(3, i) for i in range(12)]
        for node in self.gather(references, data):
            self.assertEqual([group.getSequenceNum() for group in node.sent], [1, 2, 3])
            for group, reference in zip(node.sent, references):
                self.assertIs(group.reference_data, reference)
                self.assertEqual(
                    group.getTimestampDevice(), reference.getTimestampDevice()
                )
                self.assertEqual(len(group.items), len(reference.detections))
            self.assertEqual(
                [bytes(item.getData())[0] for item in node.sent[2].items],
                list(range(12)),
            )

    def test_empty_frame_waits_for_delayed_crop(self):
        for node in self.gather(
            [self.reference(1, 1), self.reference(2, 0)],
            [None, None, self.result(1)],
        ):
            self.assertEqual([group.getSequenceNum() for group in node.sent], [1, 2])
            self.assertFalse(node._unmatched_data)

    def test_results_can_arrive_before_reference(self):
        for node in self.gather(
            [None, None, self.reference(1, 2)],
            [self.result(1, 0), self.result(1, 1)],
        ):
            self.assertEqual(len(node.sent), 1)
            self.assertEqual(
                [bytes(item.getData())[0] for item in node.sent[0].items], [0, 1]
            )

    def test_missing_crop_expires_and_late_result_is_ignored(self):
        data = [self.result(1), self.result(2)] + [None] * 210 + [self.result(1, 1)]
        for node in self.gather([self.reference(1, 2), self.reference(2, 1)], data):
            self.assertEqual([group.getSequenceNum() for group in node.sent], [2])
            self.assertFalse(node._reference_data)
            self.assertFalse(node._data_by_reference_ts)
            self.assertFalse(node._unmatched_data)

    def test_final_incomplete_frame_expires_with_idle_inputs(self):
        for node in self.gather([self.reference(1, 2)], [self.result(1)], ticks=220):
            self.assertFalse(node.sent)
            self.assertFalse(node._reference_data)
            self.assertFalse(node._arrived_at)

    def test_pending_frame_limit_recovers_before_timeout(self):
        references = [self.reference(1, 1)] + [
            self.reference(i, 0) for i in range(2, 5)
        ]
        for node in self.gather(references, [], MAX_PENDING_FRAMES=3):
            self.assertEqual([group.getSequenceNum() for group in node.sent], [2, 3, 4])
            self.assertFalse(node._reference_data)

    def test_results_without_references_are_bounded(self):
        for node in self.gather([], [self.result(i) for i in range(100)]):
            self.assertEqual(len(node._unmatched_data), node.MAX_PENDING_FRAMES)

    def test_empty_decoder_result_still_counts_as_one_crop(self):
        result = self.dai.MessageGroup()
        result.setTimestamp(timedelta(seconds=1))
        result.setSequenceNum(1)
        for node in self.gather([self.reference(1, 1)], [result]):
            self.assertEqual(len(node.sent), 1)
            self.assertEqual(node.sent[0].items, [result])

    def test_multi_head_results_keep_face_order(self):
        results = []
        for index in range(2):
            result = self.dai.MessageGroup()
            result["age"] = self.result(1, index)
            result["gender"] = self.result(1, index + 10)
            result.setTimestamp(timedelta(seconds=1))
            result.setSequenceNum(1)
            results.append(result)
        for node in self.gather(
            [self.reference(1, 2), self.reference(2, 0)],
            [None, None] + results,
        ):
            self.assertEqual([group.getSequenceNum() for group in node.sent], [1, 2])
            self.assertEqual(node.sent[0].items, results)
            self.assertEqual(
                [bytes(item["gender"].getData())[0] for item in node.sent[0].items],
                [10, 11],
            )

    def test_missing_tile_recovers_with_frame_references(self):
        frames = []
        for sequence in (1, 2):
            frame = self.dai.ImgFrame()
            frame.setTimestamp(timedelta(seconds=sequence))
            frame.setSequenceNum(sequence)
            frames.append(frame)
        for node in self.gather(
            frames,
            [self.result(1)] + [self.result(2, index) for index in range(3)],
            ticks=220,
            wait_count_fn=lambda _: 3,
        ):
            self.assertEqual([group.getSequenceNum() for group in node.sent], [2])
            self.assertIs(node.sent[0].reference_data, frames[1])
            self.assertEqual(
                [bytes(item.getData())[0] for item in node.sent[0].items], [0, 1, 2]
            )

    def test_barcode_rotation_and_metadata_survive_roi_expansion(self):
        module = load_module(ROOT / EXAMPLES["barcode"] / "barcode_regions.py")
        reference = self.reference(1, 1)
        detection = self.dai.ImgDetection()
        detection.setBoundingBox(
            self.dai.RotatedRect(
                self.dai.Point2f(0.5, 0.5, True),
                self.dai.Size2f(0.2, 0.1, True),
                30,
            )
        )
        reference.detections = [detection]
        regions = module.BarcodeRegions.process(None, reference)
        rect = regions.detections[0].getBoundingBox()
        self.assertAlmostEqual(rect.angle, 30)
        self.assertAlmostEqual(rect.size.width, 0.23)
        self.assertAlmostEqual(rect.size.height, 0.115)
        self.assertEqual(regions.getTimestampDevice(), reference.getTimestampDevice())
        self.assertEqual(regions.getSequenceNum(), reference.getSequenceNum())

    def test_multiple_vehicles_keep_original_parent_indices(self):
        from depthai_nodes import GatheredData

        module = load_module(ROOT / EXAMPLES["alpr"] / "crop_regions.py")
        reference = self.reference(1, 0)
        reference.setTransformation(self.dai.ImgTransformation(640, 480))
        vehicles = []
        for label, xmin in [(2, 0.05), (0, 0), (5, 0.35), (7, 0.65)]:
            detection = self.dai.ImgDetection()
            detection.label, detection.confidence = label, 0.9
            detection.xmin, detection.xmax = xmin, xmin + 0.25
            detection.ymin, detection.ymax = 0.2, 0.8
            vehicles.append(detection)
        reference.detections = vehicles
        vehicle_node = SimpleNamespace(reference=Mock(), out=Mock())
        module.VehicleRegions.process(vehicle_node, reference)
        vehicle_reference = vehicle_node.reference.send.call_args.args[0]
        self.assertEqual(vehicle_reference.indices, [0, 2, 3])

        plate_results = []
        for index, vehicle in enumerate(vehicle_reference.detections):
            transform = reference.getTransformation()
            x, y = int(vehicle.xmin * 640), int(vehicle.ymin * 480)
            width = int((vehicle.xmax - vehicle.xmin) * 640)
            height = int((vehicle.ymax - vehicle.ymin) * 480)
            transform.addCrop(x, y, width, height)
            transform.addScale(640 / width, 640 / height)
            transform.setSize(640, 640)
            result = self.reference(1, 0)
            result.setTransformation(transform)
            plates = []
            for confidence in (
                [0.6, 0.9] if index == 0 else [] if index == 1 else [0.9, 0.6]
            ):
                plate = self.dai.ImgDetection()
                plate.confidence = confidence
                plate.xmin, plate.xmax = 0.2, 0.8
                plate.ymin, plate.ymax = 0.5, 0.8
                plates.append(plate)
            result.detections = plates
            plate_results.append(result)
        gathered = GatheredData(vehicle_reference, plate_results)
        plate_node = SimpleNamespace(
            _frame_size=(640, 480), reference=Mock(), out=Mock()
        )
        module.PlateRegions.process(plate_node, gathered)
        plates = plate_node.reference.send.call_args.args[0]
        self.assertIs(plates.source, gathered)
        self.assertEqual(plates.indices, [(0, 1), (2, 0)])
        self.assertEqual(
            [vehicle_reference.indices[index] for index, _ in plates.indices], [0, 3]
        )
        self.assertLess(plates.detections[0].xmin, plates.detections[1].xmin)
        self.assertEqual(plates.getSequenceNum(), reference.getSequenceNum())


if __name__ == "__main__":
    unittest.main()
