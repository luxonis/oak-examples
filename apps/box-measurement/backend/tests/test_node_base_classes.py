"""Box nodes share depthai-nodes' host-node base classes, as solutions-sdk nodes do."""

import unittest

from depthai_nodes.node import BaseHostNode, BaseThreadedHostNode

from solutions_sdk.box_measurement import (
    BoxDetector,
    BoxDimensioner,
    BoxMeasurer,
    SupportPlaneCalibrator,
)


class NodeBaseClassTests(unittest.TestCase):
    def test_threaded_nodes_subclass_base_threaded_host_node(self):
        for node in (BoxDetector, BoxMeasurer, SupportPlaneCalibrator):
            with self.subTest(node=node.__name__):
                self.assertTrue(issubclass(node, BaseThreadedHostNode))

    def test_dimensioner_subclasses_base_host_node(self):
        self.assertTrue(issubclass(BoxDimensioner, BaseHostNode))


if __name__ == "__main__":
    unittest.main()
