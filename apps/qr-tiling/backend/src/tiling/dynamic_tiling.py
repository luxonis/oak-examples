from typing import List, Tuple, Union, Any

import depthai as dai
import numpy as np

from depthai_nodes.node import Tiling


class DynamicTiling(Tiling):
    """Extends Tiling node with runtime configuration updates."""

    SCRIPT_CONTENT = """
try:
    # Get initial configurations
    cfg_count_msg = node.inputs['cfg_count'].get()
    cfg_count = cfg_count_msg.getData()[0]
    configs = []
    for i in range(cfg_count):
        cfg = node.inputs['cfg'].get()
        configs.append(cfg)

    while True:
        # Check for config update (non-blocking)
        if node.inputs['cfg_count'].has():
            while node.inputs['cfg_count'].has():
                cfg_count_msg = node.inputs['cfg_count'].get()
            cfg_count = cfg_count_msg.getData()[0]

            configs = []
            for i in range(cfg_count):
                cfg = node.inputs['cfg'].get()
                configs.append(cfg)

        frame = node.inputs['preview'].get()
        for cfg in configs:
            node.outputs['manip_cfg'].send(cfg)
            node.outputs['manip_img'].send(frame)

except Exception as e:
    node.warn(str(e))
"""

    def __init__(self) -> None:
        super().__init__()
        self._script.setScript(self.SCRIPT_CONTENT)

        self._script.inputs["cfg"].setMaxSize(64)
        self._script.inputs["cfg"].setBlocking(False)
        self._script.inputs["cfg_count"].setMaxSize(2)
        self._script.inputs["cfg_count"].setBlocking(False)

        self._overlap: float | None = None
        self._grid_size: Tuple | None = None
        self._img_shape: Tuple | None = None
        self._nn_shape: Tuple[int, int] | None = None
        self._resize_mode: dai.ImageManipConfig.ResizeMode | None = None
        self._global_detection: bool | None = None
        self._grid_matrix: Union[np.ndarray, List, None] = None

    def build(
        self,
        img_output: dai.Node.Output,
        img_shape: Tuple,
        nn_shape: Tuple[int, int],
        resize_mode: dai.ImageManipConfig.ResizeMode,
        overlap: float = 0.2,
        grid_size: Tuple = (2, 2),
        global_detection: bool = False,
        grid_matrix: Union[np.ndarray, List, None] = None,
    ) -> "DynamicTiling":
        self._overlap = overlap
        self._grid_size = grid_size
        self._img_shape = img_shape
        self._nn_shape = nn_shape
        self._resize_mode = resize_mode
        self._global_detection = global_detection
        self._grid_matrix = grid_matrix

        super().build(
            overlap=overlap,
            img_output=img_output,
            grid_size=grid_size,
            img_shape=img_shape,
            nn_shape=nn_shape,
            resize_mode=resize_mode,
            global_detection=global_detection,
            grid_matrix=grid_matrix,
        )

        return self

    def run(self) -> None:
        """Send initial configuration to script node."""
        self._sendConfig()

    def updateConfig(
        self,
        overlap: float = None,
        grid_size: Tuple = None,
        global_detection: bool = None,
        grid_matrix: Union[np.ndarray, List, None] = None,
    ) -> None:
        """Update tiling configuration at runtime."""
        self._overlap = overlap if overlap is not None else self._overlap
        self._grid_size = grid_size if grid_size is not None else self._grid_size
        self._global_detection = (
            global_detection if global_detection is not None else self._global_detection
        )
        self._grid_matrix = (
            grid_matrix if grid_matrix is not None else self._grid_matrix
        )

        self._initCropConfigs(
            overlap=self._overlap,
            grid_size=self._grid_size,
            img_shape=self._img_shape,
            nn_shape=self._nn_shape,
            resize_mode=self._resize_mode,
            global_detection=self._global_detection,
            grid_matrix=self._grid_matrix,
        )

        self._sendConfig()

    def _sendConfig(self) -> None:
        """Send crop configs to script node."""
        for cfg in self._crop_configs:
            self._cfg_out.send(cfg)

        buff = dai.Buffer()
        buff.setData(np.array([self.tile_count]).astype(np.uint8))
        self._cfg_count.send(buff)

    @property
    def tile_positions(self) -> List[Tuple[int, int, int, int]]:
        """Get current tile positions for visualization."""
        return self._computeTilePositions(
            overlap=self._overlap,
            grid_size=self._grid_size,
            img_shape=self._img_shape,
            grid_matrix=self._grid_matrix,
            global_detection=self._global_detection,
        )

    @property
    def current_params(self) -> dict[str, Any]:
        return {
            "rows": self._grid_size[1],
            "cols": self._grid_size[0],
            "overlap": self._overlap,
            "global_detection": self._global_detection,
            "grid_matrix": self._grid_matrix,
        }

    def get_tile_positions(self):
        return self.tile_positions
