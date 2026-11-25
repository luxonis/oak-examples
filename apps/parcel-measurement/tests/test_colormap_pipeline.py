from datetime import timedelta
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import depthai as dai
from depthai_nodes.node import ApplyDepthColormap
import numpy as np

from test_preview import PreviewRendererNode, PreviewRequest, scene


class ColormapPipelineTests(unittest.TestCase):
    def test_public_colormap_is_blended_with_matching_rgb_and_invalid_depth_is_clear(
        self,
    ):
        cv2.setNumThreads(1)
        device = SimpleNamespace(getPlatform=lambda: dai.Platform.RVC4)
        with patch.object(
            dai.Pipeline, "getDefaultDevice", return_value=device
        ), dai.Pipeline(False) as pipeline:
            renderer = pipeline.create(PreviewRendererNode)
            colormap = pipeline.create(ApplyDepthColormap).build(
                renderer.depthToColorize
            )
            colormap.out.link(renderer.inputColoredDepth)
            inputs = renderer.inputFrames.createInputQueue()
            videos = renderer.out.createOutputQueue()
            colors = colormap.out.createOutputQueue()
            frame = scene(sequence=47)
            values = np.tile(np.arange(32, dtype=np.uint16) * 50 + 300, (24, 1))
            values[:, :2] = 0
            values[:, -2:] = 65535
            frame.depth.setCvFrame(values, dai.ImgFrame.Type.RAW16)
            frame.depth.setSequenceNum(91)
            frame.depth.setTimestampDevice(timedelta(seconds=2))
            pipeline.start()
            try:
                inputs.send(PreviewRequest(frame, depth=True))
                video = videos.get(timedelta(seconds=3))
                colored = colors.get(timedelta(seconds=3))
                self.assertIsNotNone(video)
                self.assertIsNotNone(colored)
                self.assertEqual(video.getSequenceNum(), 47)
                self.assertEqual(colored.getSequenceNum(), 91)
                texture = colored.getCvFrame()
                np.testing.assert_array_equal(texture[:, :2], 0)
                np.testing.assert_array_equal(texture[:, -2:], 0)
                rgb = video.getCvFrame()
                np.testing.assert_allclose(rgb[24, 0], (100, 100, 100), atol=3)
                np.testing.assert_allclose(rgb[24, 60], (100, 100, 100), atol=3)
                # Interior patches avoid NV12 chroma subsampling at mask boundaries.
                expected = 0.5 * np.array((100, 100, 100)) + 0.5 * texture[12, 16]
                np.testing.assert_allclose(rgb[24, 32], expected, atol=12)
            finally:
                pipeline.stop()
