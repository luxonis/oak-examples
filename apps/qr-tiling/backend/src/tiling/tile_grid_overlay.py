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
        self._tile_size: Tuple[int, int] | None = None
        self._colors: List[Tuple[int, int, int]] = []
        self._last_tile_count: int = 0

    def build(
        self,
        input_frame: dai.Node.Output,
        get_tile_positions: Callable[[], List[Tuple[int, int, int, int]]],
        tile_size: Tuple[int, int] | None = None,
    ) -> "TileGridOverlay":
        self.link_args(input_frame)
        self._get_tile_positions = get_tile_positions
        self._tile_size = tile_size
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

    def process(self, input_frame: dai.Buffer) -> None:
        assert isinstance(
            input_frame, dai.ImgFrame
        ), f"Expected dai.ImgFrame, got {type(input_frame)}"
        frame = input_frame.getCvFrame()
        tile_positions = self._get_tile_positions()
        self._regenerate_colors_if_needed(tile_positions)
        frame_with_grid = self._draw_grid(frame, tile_positions)

        out_frame = dai.ImgFrame()
        out_frame.setCvFrame(frame_with_grid, dai.ImgFrame.Type.BGR888p)
        out_frame.setTimestamp(input_frame.getTimestamp())
        out_frame.setSequenceNum(input_frame.getSequenceNum())
        out_frame.setTimestampDevice(input_frame.getTimestampDevice())

        self.out.send(out_frame)

    def _scale_positions(
        self,
        tile_positions: List[Tuple[int, int, int, int]],
        frame_size: Tuple[int, int],
    ) -> List[Tuple[int, int, int, int]]:
        """Scale tile positions from source size to frame size."""
        if not self._tile_size:
            return tile_positions

        src_w, src_h = self._tile_size
        dst_w, dst_h = frame_size

        scale_x = dst_w / src_w
        scale_y = dst_h / src_h

        return [
            (
                int(x1 * scale_x),
                int(y1 * scale_y),
                int(x2 * scale_x),
                int(y2 * scale_y),
            )
            for x1, y1, x2, y2 in tile_positions
        ]

    def _draw_grid(
        self,
        frame: np.ndarray,
        tile_positions: List[Tuple[int, int, int, int]],
    ) -> np.ndarray:
        """Draw tile grid overlay on the frame."""
        frame_h, frame_w = frame.shape[:2]
        scaled_positions = self._scale_positions(tile_positions, (frame_w, frame_h))

        overlay = frame.copy()

        for idx, (x1, y1, x2, y2) in enumerate(scaled_positions):
            color = self._colors[idx % len(self._colors)]

            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        frame = cv2.addWeighted(overlay, 0.3, frame, 0.7, 0)

        text = f"Tiles: {len(tile_positions)}"
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
