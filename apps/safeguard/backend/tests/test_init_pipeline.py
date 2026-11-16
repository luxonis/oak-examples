"""The pipeline builder refuses devices SafeGuard does not support."""

import unittest
from unittest.mock import MagicMock, patch

import depthai as dai

from depthai_pipeline.init_pipeline import init_pipeline
from settings.settings import Settings


class NonRvc4DeviceTest(unittest.TestCase):
    def setUp(self):
        device = MagicMock()
        device.getPlatform.return_value = dai.Platform.RVC2
        lookup = patch.object(dai.Pipeline, "getDefaultDevice", return_value=device)
        lookup.start()
        self.addCleanup(lookup.stop)
        self.pipeline = dai.Pipeline(False)

    def test_refuses_before_creating_nodes(self):
        with self.assertRaisesRegex(RuntimeError, "requires an RVC4.*RVC2"):
            init_pipeline(self.pipeline, Settings(), MagicMock())

        self.assertEqual(self.pipeline.getAllNodes(), [])


if __name__ == "__main__":
    unittest.main()
