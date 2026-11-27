"""Application-owned live support-plane preview."""

import depthai as dai
import numpy as np

from services.support_plane_controller import SupportPlaneController, plane_equation
from util.plane_grid import build_plane_grid, move_plane_grid


class SupportPlanePreview(dai.node.HostNode):
    _COLOR_CONFIRMED = (0, 255, 0, 255)
    _COLOR_PENDING = (255, 140, 0, 255)
    _PREVIEW_DOWNSAMPLE = 3

    def __init__(self):
        super().__init__()
        self._preview_grid: np.ndarray | None = None
        self._preview_grid_key: bytes | None = None

    def build(
        self,
        point_cloud: dai.Node.Output,
        point_cloud_size: tuple[int, int],
        controller: SupportPlaneController,
    ) -> "SupportPlanePreview":
        self.link_args(point_cloud)
        self._size = point_cloud_size
        self._controller = controller
        return self

    def process(self, cloud: dai.Buffer) -> None:
        if not isinstance(cloud, dai.PointCloudData):
            return
        try:
            self._publish_plane_preview_pcl(cloud)
        except dai.MessageQueue.QueueException:
            return

    def _get_preview_data(self):
        _, plane, corrected, active = self._controller.preview_data()
        color = self._COLOR_CONFIRMED if active else self._COLOR_PENDING
        return (
            plane_equation(plane) if plane is not None else None,
            plane_equation(corrected) if corrected is not None else None,
            color,
        )

    def _publish_plane_preview_pcl(self, pcl_msg: dai.PointCloudData) -> None:
        preview_active, _, _, _ = self._controller.preview_data()
        if not preview_active:
            # Rebuild the grid on the next page visit from what is visible then
            self._preview_grid_key = None
            return

        if pcl_msg.isColor():
            points, colors = pcl_msg.getPointsRGB()
        else:
            points = np.asarray(pcl_msg.getPoints())
            colors = np.full((len(points), 4), 255, dtype=np.uint8)
        if len(points) == 0:
            return

        points, colors = self._downsample_preview_pcl(points, colors)

        valid = np.isfinite(points).all(axis=1) & (points[:, 2] > 1e-6)
        points = points[valid].astype(np.float32)
        colors = colors[valid].copy()

        plane, grid_plane, color = self._get_preview_data()

        if plane is not None and grid_plane is not None:
            grid = self._preview_grid_for(plane, points)
            if grid is not None:
                grid_points = move_plane_grid(grid, plane, grid_plane)
                grid_colors = np.full(
                    (grid_points.shape[0], 4), color, dtype=colors.dtype
                )
                points = np.concatenate([points, grid_points])
                colors = np.concatenate([colors, grid_colors])

        out = dai.PointCloudData()
        out.setPointsRGB(points, colors)  # type: ignore[arg-type]
        out.setTimestamp(pcl_msg.getTimestamp())
        out.setTimestampDevice(pcl_msg.getTimestampDevice())
        out.setSequenceNum(pcl_msg.getSequenceNum())
        self.out.send(out)

    def _downsample_preview_pcl(
        self, points: np.ndarray, colors: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        step = self._PREVIEW_DOWNSAMPLE
        if step <= 1:
            return points, colors

        pcl_width, pcl_height = self._size
        if points.shape[0] != self._size[0] * self._size[1]:
            return points, colors

        downsampled_points = points.reshape(pcl_height, pcl_width, -1)[::step, ::step]
        downsampled_colors = colors.reshape(pcl_height, pcl_width, -1)[::step, ::step]

        return (
            downsampled_points.reshape(-1, downsampled_points.shape[-1]),
            downsampled_colors.reshape(-1, downsampled_colors.shape[-1]),
        )

    def _preview_grid_for(
        self, plane: np.ndarray, points: np.ndarray
    ) -> np.ndarray | None:
        key = plane.tobytes()
        if key != self._preview_grid_key:
            on_plane = np.abs(points @ plane[:3] + plane[3]) < 10.0
            self._preview_grid = build_plane_grid(points[on_plane], plane)
            self._preview_grid_key = key if self._preview_grid is not None else None
        return self._preview_grid
