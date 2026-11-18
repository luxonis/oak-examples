from typing import Callable, List, Tuple

import cv2
import depthai as dai
import numpy as np

from depthai_nodes.node import BaseHostNode


class TileGridOverlay(BaseHostNode):
    """Draws tile grid overlay directly on frames."""

    def __init__(self) -> None:
        super().__init__()
        self._get_tile_positions: Callable[[], List[Tuple[int, int, int, int]]] = (
            lambda: []
        )
        self._colors: List[Tuple[int, int, int]] = []
        self._last_tile_count: int = 0

    def build(
        self,
        input_frame: dai.Node.Output,
        get_tile_positions: Callable[[], List[Tuple[int, int, int, int]]],
        source_frame: dai.Node.Output,
    ) -> "TileGridOverlay":
        self.link_args(input_frame, source_frame)
        self._get_tile_positions = get_tile_positions
        self._regenerate_colors_if_needed(get_tile_positions())
        return self

    def _regenerate_colors_if_needed(
        self, tile_positions: List[Tuple[int, int, int, int]]
    ) -> None:
        """Regenerate colors only when tile count changes."""
        count = len(tile_positions)
        if count == self._last_tile_count:
            return
        self._last_tile_count = count
        np.random.seed(432)
        self._colors = [
            (
                int(np.random.random() * 255),
                int(np.random.random() * 255),
                int(np.random.random() * 255),
            )
            for _ in range(max(count, 1))
        ]

    def process(self, input_frame: dai.ImgFrame, source_frame: dai.ImgFrame) -> None:
        assert isinstance(
            input_frame, dai.ImgFrame
        ), f"Expected dai.ImgFrame, got {type(input_frame)}"
        frame = input_frame.getCvFrame()
        tile_positions = self._get_tile_positions()
        self._regenerate_colors_if_needed(tile_positions)
        source = source_frame.getTransformation()
        target = input_frame.getTransformation()
        polygons = []
        for x1, y1, x2, y2 in tile_positions:
            points = [
                source.remapPointTo(target, dai.Point2f(x, y, False))
                for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2))
            ]
            polygons.append(np.array([(p.x, p.y) for p in points], dtype=np.int32))
        frame_with_grid = self._draw_grid(frame, polygons)

        out_frame = dai.ImgFrame()
        out_frame.setCvFrame(frame_with_grid, dai.ImgFrame.Type.BGR888p)
        out_frame.setBufferMetadataFrom(input_frame)
        out_frame.setTransformation(target)

        self.out.send(out_frame)

    def _draw_grid(
        self,
        frame: np.ndarray,
        polygons: List[np.ndarray],
    ) -> np.ndarray:
        """Draw tile grid overlay on the frame."""
        overlay = frame.copy()
        for idx, points in enumerate(polygons):
            color = self._colors[idx % len(self._colors)]
            cv2.fillConvexPoly(overlay, points, color)
            cv2.polylines(frame, [points], True, color, 2)

        frame = cv2.addWeighted(overlay, 0.3, frame, 0.7, 0)
        text = f"Tiles: {len(polygons)}"
        cv2.putText(
            frame,
            text,
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        return frame
