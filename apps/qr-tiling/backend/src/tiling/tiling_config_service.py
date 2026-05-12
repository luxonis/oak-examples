from collections.abc import Callable

from .tiling import Tiling
import depthai as dai
from pydantic import BaseModel, Field

from base_service import BaseService


class TilingConfigPayload(BaseModel):
    rows: int = Field(..., ge=1, le=8)
    cols: int = Field(..., ge=1, le=8)
    overlap: float = Field(0.2, ge=0.0, lt=1.0)
    global_detection: bool = False
    grid_matrix: list[list[int]] | None = None


class TilingConfigService(BaseService[TilingConfigPayload]):
    NAME = "Tiling Config Service"
    PAYLOAD_MODEL = TilingConfigPayload

    def __init__(
        self,
        tiling: Tiling,
        canvas_shape: tuple[int, int],
        resize_shape: tuple[int, int],
        resize_mode: dai.ImageManipConfig.ResizeMode,
        adjust_fps_from_tile_count: Callable[[int], None],
        initial_params: dict,
    ):
        self._tiling = tiling
        self._canvas_shape = canvas_shape
        self._resize_shape = resize_shape
        self._resize_mode = resize_mode
        self._adjust_fps_from_tile_count = adjust_fps_from_tile_count
        self._old_tile_count = tiling.tileCount
        self._current_params = initial_params.copy()

    def handle_typed(self, payload: TilingConfigPayload) -> dict:
        grid_size = (payload.cols, payload.rows)

        self._tiling.updateTilingConfig(
            overlap=payload.overlap,
            gridSize=grid_size,
            canvasShape=self._canvas_shape,
            resizeShape=self._resize_shape,
            resizeMode=self._resize_mode,
            globalDetection=payload.global_detection,
            gridMatrix=payload.grid_matrix,
        )
        self._current_params = {
            "rows": payload.rows,
            "cols": payload.cols,
            "overlap": payload.overlap,
            "global_detection": payload.global_detection,
            "grid_matrix": payload.grid_matrix,
        }

        new_tile_count = self._tiling.tileCount
        if new_tile_count != self._old_tile_count:
            self._adjust_fps_from_tile_count(new_tile_count)
            self._old_tile_count = new_tile_count

        return {"ok": True}

    @property
    def current_params(self) -> dict:
        return self._current_params.copy()

    def get_tile_positions(self) -> list[tuple[int, int, int, int]]:
        return self._tiling.tilePositions
