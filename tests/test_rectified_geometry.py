"""Hardware-independent metric geometry regression tests (run with unittest)."""

import importlib.util
import unittest
from pathlib import Path

try:
    import depthai  # noqa: F401
    import numpy as np
except ImportError as exc:
    raise unittest.SkipTest(
        "Install the examples’ DepthAI and NumPy requirements"
    ) from exc

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    spec = importlib.util.spec_from_file_location("geometry", ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


StereoInference = load(
    "depth-measurement/triangulation/utils/stereo_inference.py"
).StereoInference
convert = load(
    "neural-networks/depth-estimation/crestereo-depth-matching/utils/disparity_to_depth.py"
).disparity_to_depth


class RectifiedGeometryTests(unittest.TestCase):
    def test_known_metric_points_with_off_center_principal_point(self):
        baseline = 75.0
        k = np.array([[420.0, 0, 301.0], [0, 415.0, 189.0], [0, 0, 1]])
        model = StereoInference(baseline)
        for xyz in ((0, 0, 1000), (300, -200, 2000), (-400, 300, 5000)):
            x, y, z = xyz
            left = (420 * x / z + 301, 415 * y / z + 189)
            right = (420 * (x - baseline) / z + 301, left[1])
            np.testing.assert_allclose(model.triangulate(left, right, k), xyz)
            depth = convert(np.array([[left[0] - right[0]]]), baseline, k[0, 0])
            self.assertAlmostEqual(int(depth[0, 0]), z, delta=1)

    def test_rejects_invalid_correspondences(self):
        model = StereoInference(75)
        k = np.diag([400, 400, 1])
        for right in ((100, 50), (101, 50), (99.9, 50), (90, 60), (np.nan, 50)):
            self.assertIsNone(model.triangulate((100, 50), right, k))

    def test_depth_invalid_values_and_uint16_saturation(self):
        depth = convert([[0, -2, np.nan, np.inf, 0.001, 30, 0.02]], 75, 400)
        np.testing.assert_array_equal(depth, [[0, 0, 0, 0, 0, 1000, 65535]])
        self.assertEqual(depth.dtype, np.uint16)

    def test_vertical_noise_does_not_change_horizontal_disparity(self):
        model = StereoInference(75)
        k = np.diag([400, 400, 1])
        np.testing.assert_allclose(
            model.triangulate((100, 50), (70, 52), k), [250, 125, 1000]
        )

    def test_rejects_missing_baseline_and_focal_length(self):
        for baseline in (0, -1, np.nan):
            with self.assertRaises(ValueError):
                StereoInference(baseline)
            with self.assertRaises(ValueError):
                convert([1], baseline, 400)
        with self.assertRaises(ValueError):
            convert([1], 75, 0)


if __name__ == "__main__":
    unittest.main()
