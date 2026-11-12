"""Device-bound nodes explain themselves in a pipeline without a device.

This module deliberately does not patch the depthai-nodes device lookup.
"""

import unittest

import depthai as dai

from solutions_sdk.box_measurement import BoxDetector, BoxMeasurer


class NodesWithoutDeviceTests(unittest.TestCase):
    def test_device_bound_nodes_require_an_rvc4_device(self):
        for node in (BoxDetector, BoxMeasurer):
            with (
                self.subTest(node=node.__name__),
                self.assertRaisesRegex(ValueError, "requires an RVC4 device"),
            ):
                dai.Pipeline(False).create(node)


if __name__ == "__main__":
    unittest.main()
