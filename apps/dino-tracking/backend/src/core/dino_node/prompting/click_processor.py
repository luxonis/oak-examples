import cv2
import numpy as np
import depthai as dai
from .selection_processor import SelectionProcessor
from .frame_cache import FrameCache
from .click_state import ClickState


class ClickProcessor:
    """
    High-level click/selection pipeline.
    """

    def __init__(self):
        self._frame_cache = FrameCache()
        self._click_state = ClickState()
        self._selection = SelectionProcessor()

    def queue_click(self, x_norm: float, y_norm: float) -> None:
        self._click_state.set_click(x_norm, y_norm)

    def clear(self) -> None:
        self._click_state.clear()
        self._selection.clear()

    def update_cache(self, frame_full: np.ndarray, seg_fs: np.ndarray, seg_full: np.ndarray) -> None:
        self._frame_cache.update(frame_full, seg_fs, seg_full)

    def process_pending_click(self, logger=None) -> bool:
        click = self._click_state.consume_click()
        if click is None:
            return False

        x_norm, y_norm = click

        seg_full = self._frame_cache.get_last_seg_full()
        seg_fs = self._frame_cache.get_last_seg_fs()

        if seg_full is None or seg_fs is None:
            if logger:
                logger.info("ClickProcessor: no cached segmentation for click; ignoring")
            return False

        if logger:
            logger.info(
                f"ClickProcessor: processing pending click at normalized coords "
                f"({x_norm}, {y_norm})"
            )

        changed = self._selection.set_from_click(
            x_norm=x_norm,
            y_norm=y_norm,
            seg_full=seg_full,
            seg_fs=seg_fs,
            logger=logger,
        )

        return changed

    def update_cache_from_msgs(
            self,
            frame_msg: dai.ImgFrame,
            seg_msg,
    ) -> tuple[int, int]:
        frame_full = frame_msg.getCvFrame()
        H_full, W_full = frame_full.shape[:2]

        seg_fs = seg_msg.mask.astype(np.int32)
        seg_full = cv2.resize(
            seg_fs,
            (W_full, H_full),
            interpolation=cv2.INTER_NEAREST,
        )

        self._frame_cache.update(frame_full, seg_fs, seg_full)
        return H_full, W_full

    def has_object(self) -> bool:
        return self._selection.has_object()

    def get_selection_mask(self) -> np.ndarray | None:
        return self._selection.get_mask()
