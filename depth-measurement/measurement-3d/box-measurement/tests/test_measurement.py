import sys
import time
import unittest
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import open3d as o3d
from depthai_nodes.utils import AnnotationHelper
import depthai as dai

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.box_processing_node import BoxProcessingNode
from utils.cuboid_fitter import CuboidFitter
from utils.helper_functions import reverse_resize_and_pad


class MeasurementTests(unittest.TestCase):
    def test_sync_discards_stale_cloud_and_publishes_matching_preview(self):
        points = np.zeros((400 * 640, 3), dtype=np.float32)
        colors = np.zeros((400 * 640, 4), dtype=np.uint8)
        stale_cloud = dai.PointCloudData()
        stale_cloud.setPointsRGB(points, colors)
        stale_cloud.setTimestamp(timedelta(seconds=0.5))
        stale_cloud.setSequenceNum(1)
        cloud = dai.PointCloudData()
        cloud.setPointsRGB(points, colors)
        cloud.setTimestamp(timedelta(seconds=1, microseconds=200))
        cloud.setSequenceNum(2)
        rgb = dai.ImgFrame()
        rgb.setType(dai.ImgFrame.Type.RGB888i)
        rgb.setWidth(640)
        rgb.setHeight(400)
        rgb.setData(np.zeros(400 * 640 * 3, dtype=np.uint8))
        rgb.setTimestamp(timedelta(seconds=1))
        rgb.setSequenceNum(2)
        detection = dai.ImgDetection()
        detection.setBoundingBox(
            dai.RotatedRect(dai.Point2f(0.5, 0.5), dai.Size2f(0.4, 0.4), 0)
        )
        detections = dai.ImgDetections()
        detections.detections = [detection]
        detections.setCvSegmentationMask(np.zeros((320, 512), dtype=np.uint8))
        detections.setTimestamp(timedelta(seconds=1))
        detections.setSequenceNum(2)

        class Source(dai.node.ThreadedHostNode):
            def __init__(self):
                super().__init__()
                self.pcl = self.createOutput()
                self.rgb = self.createOutput()
                self.detections = self.createOutput()

            def run(self):
                self.pcl.send(stale_cloud)
                self.rgb.send(rgb)
                self.detections.send(detections)
                self.pcl.send(cloud)

        with dai.Pipeline(False) as pipeline:
            source = pipeline.create(Source)
            sync = pipeline.create(dai.node.Sync)
            sync.setRunOnHost(True)
            sync.setSyncThreshold(timedelta(milliseconds=50))
            sync.setSyncAttempts(-1)
            source.pcl.link(sync.inputs["pcl"])
            source.rgb.link(sync.inputs["rgb"])
            source.detections.link(sync.inputs["detections"])
            processing = pipeline.create(BoxProcessingNode)
            sync.out.link(processing.inputSynced)
            annotations = processing.outputANN.createOutputQueue()
            previews = processing.outputRGB.createOutputQueue()

            pipeline.start()
            deadline = time.monotonic() + 5
            annotation = preview = None
            while time.monotonic() < deadline and (
                annotation is None or preview is None
            ):
                if annotation is None:
                    annotation = annotations.tryGet()
                if preview is None:
                    preview = previews.tryGet()
                time.sleep(0.01)

            self.assertIsNotNone(annotation)
            self.assertIsNotNone(preview)
            self.assertEqual(annotation.getSequenceNum(), 2)
            self.assertEqual(preview.getSequenceNum(), 2)
            self.assertEqual(annotation.getTimestamp(), preview.getTimestamp())
            texts = [
                text.text for layer in annotation.annotations for text in layer.texts
            ]
            self.assertIn("Not enough valid depth points", texts)

    def test_parallel_residual_does_not_hide_perpendicular_faces(self):
        rng = np.random.default_rng(42)
        top = np.column_stack(
            (rng.uniform(0, 30, 600), rng.uniform(0, 20, 600), np.full(600, 100))
        )
        parallel = np.column_stack(
            (rng.uniform(0, 30, 400), rng.uniform(0, 20, 400), np.full(400, 104))
        )
        left = np.column_stack(
            (np.zeros(200), rng.uniform(0, 20, 200), rng.uniform(100, 110, 200))
        )
        front = np.column_stack(
            (rng.uniform(0, 30, 180), np.zeros(180), rng.uniform(100, 110, 180))
        )
        fitter = CuboidFitter(distance_threshold=0.1)
        fitter.update_point_cloud(np.vstack((top, parallel, left, front)))
        o3d.utility.random.seed(42)

        self.assertTrue(fitter.fit_orthogonal_planes())
        self.assertEqual(len(fitter.planes), 3)

    def test_one_face_does_not_produce_a_measurement(self):
        x, y = np.meshgrid(np.arange(10), np.arange(10))
        fitter = CuboidFitter()
        fitter.update_point_cloud(
            np.column_stack((x.ravel(), y.ravel(), np.full(x.size, 100)))
        )

        self.assertFalse(fitter.fit_orthogonal_planes())
        self.assertEqual(len(fitter.planes), 1)

    def test_invalid_depth_clears_previous_success_and_explains_failure(self):
        state = SimpleNamespace(fit=True, fitter=CuboidFitter())
        points = np.zeros((400 * 640, 3))
        points[0] = np.nan
        colors = np.zeros((400, 640, 3), dtype=np.uint8)
        mask = np.zeros((400, 640), dtype=np.int16)

        BoxProcessingNode._fit_cuboid(state, 0, mask, points, colors)

        self.assertFalse(state.fit)
        self.assertEqual(state.fit_failure, "Not enough valid depth points")

    def test_failure_reason_is_in_the_detection_overlay(self):
        state = SimpleNamespace(
            fit=False,
            fit_failure="Could fit only 1 of 3 perpendicular faces",
            helper_det=AnnotationHelper(),
        )
        detection = dai.ImgDetection()
        detection.confidence = 0.97
        detection.setBoundingBox(
            dai.RotatedRect(dai.Point2f(0.5, 0.5), dai.Size2f(0.4, 0.4), 0)
        )

        BoxProcessingNode._draw_box_and_label(state, detection)

        texts = [text.text for text in state.helper_det.annotation.texts]
        self.assertIn("measurement unavailable", texts[0])
        self.assertEqual(texts[1], state.fit_failure)

    def test_resizing_instance_ids_does_not_invent_another_instance(self):
        mask = np.array([[-1, 2], [2, -1]], dtype=np.int16)

        resized = reverse_resize_and_pad(mask, (8, 8), (2, 2))

        self.assertEqual(set(np.unique(resized)), {-1, 2})


if __name__ == "__main__":
    unittest.main()
