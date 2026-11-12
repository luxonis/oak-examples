"""Host-only stand-in for the device lookup depthai-nodes base classes do.

``BaseHostNode`` and ``BaseThreadedHostNode`` read the pipeline's default
device when a node is created. Like solutions-sdk's barcode tests, replace
their ``__init__`` so nodes can be created without a device.

A test module that creates box nodes imports ``setUpModule`` and
``tearDownModule`` from here; unittest runs them around the module's tests.
"""

from contextlib import ExitStack
from unittest.mock import patch

import depthai as dai
from depthai_nodes.logging import get_logger
from depthai_nodes.node import BaseHostNode, BaseThreadedHostNode


def patch_device_lookup(stack: ExitStack, platform=dai.Platform.RVC4) -> None:
    """Create depthai-nodes host nodes as if on a ``platform`` device."""

    def initializer(native_base):
        def initialize(node) -> None:
            native_base.__init__(node)
            node._platform = platform
            node._img_frame_type = BaseHostNode.IMG_FRAME_TYPES[platform]
            node._logger = get_logger(type(node).__name__)

        return initialize

    stack.enter_context(
        patch.object(BaseHostNode, "__init__", initializer(dai.node.HostNode))
    )
    stack.enter_context(
        patch.object(
            BaseThreadedHostNode, "__init__", initializer(dai.node.ThreadedHostNode)
        )
    )


_module_stack = ExitStack()


def setUpModule() -> None:
    patch_device_lookup(_module_stack)


def tearDownModule() -> None:
    _module_stack.close()
