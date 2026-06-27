import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Iterable

import cv2 as cv
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.patches import FancyArrowPatch
from mpl_toolkits.mplot3d import proj3d

from utils.depthai_path import configure_depthai_path

configure_depthai_path()

import depthai as dai


def format_socket(socket: dai.CameraBoardSocket) -> str:
    return str(socket).split(".")[-1]


@dataclass(frozen=True)
class StereoPair:
    left: dai.CameraBoardSocket
    right: dai.CameraBoardSocket

    def label(self) -> str:
        return f"{format_socket(self.left)} -> {format_socket(self.right)}"


class CoordinateFrameRenderer:
    def __init__(self, figsize=(12, 8), dpi=100):
        self.fig = plt.figure(figsize=figsize, dpi=dpi)
        self.canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111, projection="3d")

    @staticmethod
    def _camera_transform(
        calibration: dai.CalibrationHandler,
        socket: dai.CameraBoardSocket,
        reference_socket: dai.CameraBoardSocket,
    ) -> np.ndarray:
        if socket == reference_socket:
            return np.eye(4, dtype=np.float32)
        return np.array(
            calibration.getCameraExtrinsics(reference_socket, socket, False),
            dtype=np.float32,
        )

    @staticmethod
    def _plot_coords(point: np.ndarray) -> np.ndarray:
        return np.array([point[0], point[2], point[1]], dtype=np.float32)

    @staticmethod
    def _set_axes_equal(ax):
        limits = np.array([ax.get_xlim3d(), ax.get_ylim3d(), ax.get_zlim3d()])
        centers = limits.mean(axis=1)
        radius = (limits[:, 1] - limits[:, 0]).max() * 0.5

        ax.set_xlim3d([centers[0] - radius, centers[0] + radius])
        ax.set_ylim3d([centers[1] - radius, centers[1] + radius])
        ax.set_zlim3d([centers[2] - radius, centers[2] + radius])

    def _draw_camera_frame(
        self,
        ax,
        transform: np.ndarray,
        color,
        linestyle: str,
        axis_scale: float,
        highlight: bool = False,
    ):
        rotation = transform[:3, :3]
        translation = transform[:3, 3]
        origin = -rotation.T @ translation
        axes = rotation.T
        origin_plot = self._plot_coords(origin)
        axis_colors = ["r", "g", "b"]
        scatter_size = 120 if highlight else 80
        line_width = 4 if highlight else 3

        ax.scatter(
            origin_plot[0],
            origin_plot[1],
            origin_plot[2],
            color=color,
            edgecolors="black",
            linewidths=0.8,
            s=scatter_size,
            zorder=5,
        )

        for axis_idx, axis_color in enumerate(axis_colors):
            axis_end = origin + axes[:, axis_idx] * axis_scale
            axis_end_plot = self._plot_coords(axis_end)
            ax.plot(
                [origin_plot[0], axis_end_plot[0]],
                [origin_plot[1], axis_end_plot[1]],
                [origin_plot[2], axis_end_plot[2]],
                color=axis_color,
                linewidth=line_width,
                linestyle=linestyle,
            )

        frustum_depth = axis_scale * 1.4
        frustum_width = axis_scale * 0.9
        frustum_height = axis_scale * 0.6
        image_plane = [
            np.array([-frustum_width, -frustum_height, frustum_depth]),
            np.array([frustum_width, -frustum_height, frustum_depth]),
            np.array([frustum_width, frustum_height, frustum_depth]),
            np.array([-frustum_width, frustum_height, frustum_depth]),
        ]
        corners = [origin + axes @ corner for corner in image_plane]
        corners_plot = [self._plot_coords(corner) for corner in corners]

        for corner in corners_plot:
            ax.plot(
                [origin_plot[0], corner[0]],
                [origin_plot[1], corner[1]],
                [origin_plot[2], corner[2]],
                color=color,
                linewidth=1.8,
                linestyle=linestyle,
                alpha=0.95,
            )

        for start, end in zip(corners_plot, corners_plot[1:] + corners_plot[:1]):
            ax.plot(
                [start[0], end[0]],
                [start[1], end[1]],
                [start[2], end[2]],
                color=color,
                linewidth=1.8,
                linestyle=linestyle,
                alpha=0.95,
            )

    def render(
        self,
        calibration: dai.CalibrationHandler | None,
        sockets: list[dai.CameraBoardSocket],
        reference_socket: dai.CameraBoardSocket | None = None,
        selected_pair: StereoPair | None = None,
        title: str = "Camera Coordinate Frames",
        status_lines: list[str] | None = None,
    ) -> np.ndarray:
        self.ax.clear()
        for text in list(self.fig.texts):
            text.remove()

        if not sockets:
            self.ax.text2D(0.5, 0.5, "No cameras detected", transform=self.ax.transAxes)
            self.canvas.draw()
            return self._canvas_image()

        if reference_socket is None:
            reference_socket = sockets[0]

        if calibration is None:
            self.ax.text2D(
                0.5,
                0.5,
                "Calibration unavailable",
                transform=self.ax.transAxes,
                ha="center",
                va="center",
                fontsize=16,
                fontweight="bold",
            )
            if status_lines:
                panel_text = "\n".join(status_lines)
                self.fig.text(
                    0.02,
                    0.02,
                    panel_text,
                    ha="left",
                    va="bottom",
                    fontsize=10,
                    color="white",
                    bbox=dict(facecolor="black", alpha=0.65, pad=8),
                )
            self.canvas.draw()
            return self._canvas_image()

        colors = plt.get_cmap("tab10").colors
        transforms = [
            self._camera_transform(calibration, socket, reference_socket)
            for socket in sockets
        ]
        camera_centers = [
            -transform[:3, :3].T @ transform[:3, 3] for transform in transforms
        ]
        max_baseline = max(
            (np.linalg.norm(center) for center in camera_centers),
            default=1.0,
        )
        axis_scale = max(max_baseline * 0.15, 1.0)

        selected_sockets = set()
        if selected_pair is not None:
            selected_sockets = {selected_pair.left, selected_pair.right}

        for idx, socket in enumerate(sockets):
            color = colors[idx % len(colors)]
            self._draw_camera_frame(
                self.ax,
                transforms[idx],
                color,
                "-",
                axis_scale,
                highlight=socket in selected_sockets,
            )

        if selected_pair is not None and (
            selected_pair.left in sockets and selected_pair.right in sockets
        ):
            left_idx = sockets.index(selected_pair.left)
            right_idx = sockets.index(selected_pair.right)
            left_origin = -transforms[left_idx][:3, :3].T @ transforms[left_idx][:3, 3]
            right_origin = -transforms[right_idx][:3, :3].T @ transforms[right_idx][:3, 3]
            left_plot = self._plot_coords(left_origin)
            right_plot = self._plot_coords(right_origin)
            self.ax.plot(
                [left_plot[0], right_plot[0]],
                [left_plot[1], right_plot[1]],
                [left_plot[2], right_plot[2]],
                color="#c00000",
                linewidth=4.0,
                linestyle="-",
                alpha=0.95,
                zorder=20,
            )
            arrow = Arrow3D(
                [left_plot[0], right_plot[0]],
                [left_plot[1], right_plot[1]],
                [left_plot[2], right_plot[2]],
                mutation_scale=22,
                lw=3.5,
                arrowstyle="-|>",
                color="#c00000",
                alpha=0.98,
            )
            self.ax.add_artist(arrow)
            self.fig.text(
                0.50,
                0.965,
                f"{format_socket(selected_pair.left)}  --->  {format_socket(selected_pair.right)}",
                ha="center",
                va="top",
                fontsize=18,
                fontweight="bold",
                color="black",
                bbox=dict(facecolor="white", edgecolor="black", boxstyle="round,pad=0.35"),
            )
            self.fig.text(
                0.50,
                0.935,
                "selected stereo link",
                ha="center",
                va="top",
                fontsize=10,
                color="black",
            )

        legend_lines = []
        for idx, socket in enumerate(sockets):
            rgb = colors[idx % len(colors)][:3]
            hex_color = matplotlib.colors.to_hex(rgb)
            label = format_socket(socket)
            suffix = "  [selected]" if socket in selected_sockets else ""
            legend_lines.append((hex_color, f"{label}{suffix}"))

        legend_y = 0.965
        self.fig.text(
            0.02,
            legend_y,
            "Cameras",
            ha="left",
            va="top",
            fontsize=12,
            fontweight="bold",
            color="black",
            bbox=dict(facecolor="white", edgecolor="#cfd6df", boxstyle="round,pad=0.35"),
        )
        for idx, (hex_color, label) in enumerate(legend_lines, start=1):
            self.fig.text(
                0.03,
                legend_y - idx * 0.034,
                f"\u25A0 {label}",
                ha="left",
                va="top",
                fontsize=11,
                fontweight="bold",
                color=hex_color,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.88, pad=1.5),
            )

        self.ax.set_xlabel("X [cm]", fontsize=12, fontweight="bold", labelpad=12)
        self.ax.set_ylabel("Z forward [cm]", fontsize=12, fontweight="bold", labelpad=12)
        self.ax.set_zlabel("Y up [cm]", fontsize=12, fontweight="bold", labelpad=12)
        self.ax.set_title(title, fontsize=14, fontweight="bold", pad=18)
        self.ax.tick_params(axis="both", which="major", labelsize=10, width=1.2)
        self.ax.grid(True, linewidth=0.8, alpha=0.5)
        self.ax.view_init(elev=20, azim=-70)
        self._set_axes_equal(self.ax)

        if status_lines:
            panel_text = "\n".join(status_lines)
            self.fig.text(
                0.02,
                0.02,
                panel_text,
                ha="left",
                va="bottom",
                fontsize=10,
                color="white",
                bbox=dict(facecolor="black", alpha=0.65, pad=8),
            )

        self.fig.tight_layout()
        self.canvas.draw()
        return self._canvas_image()

    def _canvas_image(self) -> np.ndarray:
        rgba = np.asarray(self.canvas.buffer_rgba())
        return cv.cvtColor(rgba, cv.COLOR_RGBA2BGR)


class Arrow3D(FancyArrowPatch):
    def __init__(self, xs, ys, zs, *args, **kwargs):
        super().__init__((0, 0), (0, 0), *args, **kwargs)
        self._verts3d = xs, ys, zs

    def do_3d_projection(self, renderer=None):
        xs3d, ys3d, zs3d = self._verts3d
        xs, ys, zs = proj3d.proj_transform(xs3d, ys3d, zs3d, self.axes.M)
        self.set_positions((xs[0], ys[0]), (xs[1], ys[1]))
        return np.min(zs)


class CalibrationDashboardNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self._renderer = CoordinateFrameRenderer(figsize=(8.8, 5.4), dpi=100)
        self._mode = "menu"
        self._title = "FFC Calibration"
        self._status_lines: list[str] = []
        self._calibration: dai.CalibrationHandler | None = None
        self._sockets: list[dai.CameraBoardSocket] = []
        self._pairs: list[StereoPair] = []
        self._selected_pair_idx: int = 0
        self._progress_pct: float | None = None
        self._progress_label = ""
        self._entered_baselines: dict[tuple[dai.CameraBoardSocket, dai.CameraBoardSocket], float] = {}
        self._cached_plot: np.ndarray | None = None
        self._cached_dashboard: np.ndarray | None = None
        self._last_emit_monotonic = 0.0
        self._min_emit_interval = 0.5
        self.dashboard = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )

    def build(
        self,
        preview: dai.Node.Output,
        calibration: dai.CalibrationHandler | None = None,
        sockets: list[dai.CameraBoardSocket] | None = None,
        pairs: list[StereoPair] | None = None,
    ) -> "CalibrationDashboardNode":
        self.link_args(preview)
        self._calibration = calibration
        self._sockets = list(sockets or [])
        self._pairs = list(pairs or [])
        return self

    def set_state(
        self,
        mode: str,
        title: str | None = None,
        status_lines: list[str] | None = None,
        calibration: dai.CalibrationHandler | None = None,
        pairs: list[StereoPair] | None = None,
        selected_pair_idx: int | None = None,
        entered_baselines: dict[tuple[dai.CameraBoardSocket, dai.CameraBoardSocket], float] | None = None,
    ) -> None:
        self._mode = mode
        if title is not None:
            self._title = title
        if status_lines is not None:
            self._status_lines = list(status_lines)
        if calibration is not None:
            self._calibration = calibration
        if pairs is not None:
            self._pairs = list(pairs)
        if selected_pair_idx is not None:
            self._selected_pair_idx = selected_pair_idx
        if entered_baselines is not None:
            self._entered_baselines = dict(entered_baselines)
        self._invalidate_cache()

    def set_progress(self, pct: float | None, label: str = "") -> None:
        next_pct = None if pct is None else float(np.clip(pct, 0.0, 100.0))
        if self._progress_pct != next_pct or self._progress_label != label:
            self._progress_pct = next_pct
            self._progress_label = label
            self._cached_dashboard = None

    def _invalidate_cache(self) -> None:
        self._cached_plot = None
        self._cached_dashboard = None

    def _make_canvas(self, width: int = 1280, height: int = 720) -> np.ndarray:
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
        canvas[:] = (18, 20, 26)
        return canvas

    def _draw_text_block(
        self,
        canvas: np.ndarray,
        lines: list[str],
        origin: tuple[int, int],
        font_scale: float = 0.72,
        color: tuple[int, int, int] = (235, 235, 235),
        line_step: int = 34,
        thickness: int = 2,
    ) -> None:
        x, y = origin
        for idx, line in enumerate(lines):
            cv.putText(
                canvas,
                line,
                (x, y + idx * line_step),
                cv.FONT_HERSHEY_SIMPLEX,
                font_scale,
                color,
                thickness,
                cv.LINE_AA,
            )

    def _draw_progress_bar(self, canvas: np.ndarray, pct: float, label: str) -> None:
        panel_w, panel_h = 720, 120
        x_panel = (canvas.shape[1] - panel_w) // 2
        y_panel = (canvas.shape[0] - panel_h) // 2
        overlay = canvas.copy()
        cv.rectangle(
            overlay,
            (x_panel, y_panel),
            (x_panel + panel_w, y_panel + panel_h),
            (18, 22, 30),
            -1,
        )
        cv.addWeighted(overlay, 0.78, canvas, 0.22, 0.0, dst=canvas)
        cv.rectangle(
            canvas,
            (x_panel, y_panel),
            (x_panel + panel_w, y_panel + panel_h),
            (84, 92, 108),
            2,
        )

        x0, y0 = x_panel + 36, y_panel + 70
        width, height = panel_w - 72, 28
        filled = int(width * np.clip(pct, 0.0, 100.0) / 100.0)
        cv.putText(
            canvas,
            f"{label or 'Capturing calibration frames'}  {pct:5.1f}%",
            (x0, y0 - 18),
            cv.FONT_HERSHEY_SIMPLEX,
            0.74,
            (245, 245, 245),
            2,
            cv.LINE_AA,
        )
        cv.rectangle(canvas, (x0, y0), (x0 + width, y0 + height), (70, 75, 88), 2)
        if filled > 0:
            cv.rectangle(canvas, (x0 + 3, y0 + 3), (x0 + filled - 3, y0 + height - 3), (76, 188, 131), -1)

    def process(self, frame: dai.ImgFrame) -> None:
        now = time.monotonic()
        if now - self._last_emit_monotonic < self._min_emit_interval:
            return
        self._last_emit_monotonic = now

        if self._cached_dashboard is None:
            render_start = time.monotonic()
            canvas = self._make_canvas()
            if self._sockets and self._calibration is not None:
                if self._cached_plot is None:
                    selected_pair = None
                    if self._pairs:
                        selected_pair = self._pairs[self._selected_pair_idx]
                    plot = self._renderer.render(
                        self._calibration,
                        self._sockets,
                        reference_socket=self._sockets[0],
                        selected_pair=selected_pair,
                        title="Camera Coordinate Frames",
                        status_lines=[],
                    )
                    self._cached_plot = cv.resize(plot, (1280, 720), interpolation=cv.INTER_AREA)
                plot = self._cached_plot
                y0, x0 = 0, 0
                canvas[y0 : y0 + plot.shape[0], x0 : x0 + plot.shape[1]] = plot

            if self._progress_pct is not None:
                self._draw_progress_bar(canvas, self._progress_pct, self._progress_label)
            self._cached_dashboard = canvas
            render_ms = (time.monotonic() - render_start) * 1000.0
            print(f"[dashboard] rebuilt cached frame in {render_ms:.1f} ms", flush=True)

        canvas = self._cached_dashboard

        out_frame = dai.ImgFrame()
        out_frame.setCvFrame(canvas, dai.ImgFrame.Type.BGR888p)
        out_frame.setTimestamp(frame.getTimestamp())
        out_frame.setSequenceNum(frame.getSequenceNum())
        out_frame.setTimestampDevice(frame.getTimestampDevice())
        try:
            self.dashboard.send(out_frame)
        except Exception:
            # The visualizer queue can be closed when the UI is shut down or
            # the calibration stage transitions away. Treat that as a normal
            # shutdown path instead of aborting the host node thread.
            return


class CoverageOverlayNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self._coverage_cells: np.ndarray | None = None
        self._progress_pct = 0.0
        self._label = "Capturing calibration frames"
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )

    def build(self, preview: dai.Node.Output) -> "CoverageOverlayNode":
        self.link_args(preview)
        return self

    def set_coverage(
        self,
        coverage_cells,
        progress_pct: float,
        label: str = "Capturing calibration frames",
    ) -> None:
        cells = None
        if coverage_cells is not None:
            arr = np.asarray(coverage_cells, dtype=np.float32)
            if arr.size > 0:
                if arr.ndim == 1:
                    side = int(round(np.sqrt(arr.size)))
                    if side * side == arr.size:
                        arr = arr.reshape(side, side)
                if arr.ndim == 2:
                    cells = np.clip(arr, 0.0, 1.0)
        self._coverage_cells = cells
        self._progress_pct = float(np.clip(progress_pct, 0.0, 100.0))
        self._label = label

    def _overlay_coverage(self, image: np.ndarray) -> np.ndarray:
        if len(image.shape) != 3:
            color_image = cv.cvtColor(image, cv.COLOR_GRAY2BGR)
        else:
            color_image = image.copy()

        cells = self._coverage_cells
        if cells is not None and cells.ndim == 2 and cells.shape[0] > 0 and cells.shape[1] > 0:
            rows, cols = cells.shape
            cell_width = max(1, color_image.shape[1] // cols)
            cell_height = max(1, color_image.shape[0] // rows)
            overlay = color_image.copy()
            for y in range(rows):
                for x in range(cols):
                    coverage = float(cells[y, x])
                    if coverage <= 0.0:
                        continue
                    alpha = 0.55 * coverage
                    x0 = x * cell_width
                    y0 = y * cell_height
                    x1 = color_image.shape[1] if x == cols - 1 else (x0 + cell_width)
                    y1 = color_image.shape[0] if y == rows - 1 else (y0 + cell_height)
                    cv.rectangle(overlay, (x0, y0), (x1, y1), (0, 220, 0), thickness=cv.FILLED)
                    color_image[y0:y1, x0:x1] = cv.addWeighted(
                        overlay[y0:y1, x0:x1], alpha, color_image[y0:y1, x0:x1], 1.0 - alpha, 0
                    )

        self._draw_progress(color_image)
        return color_image

    def _draw_progress(self, image: np.ndarray) -> None:
        text = f"{self._label}  {self._progress_pct:5.1f}%"
        x0 = 18
        y0 = image.shape[0] - 38
        width = max(120, image.shape[1] - 36)
        height = 18
        filled = int(width * self._progress_pct / 100.0)
        overlay = image.copy()
        cv.rectangle(overlay, (12, y0 - 34), (image.shape[1] - 12, image.shape[0] - 12), (15, 18, 24), -1)
        cv.addWeighted(overlay, 0.42, image, 0.58, 0.0, dst=image)
        cv.putText(image, text, (x0, y0 - 10), cv.FONT_HERSHEY_SIMPLEX, 0.58, (245, 245, 245), 2, cv.LINE_AA)
        cv.rectangle(image, (x0, y0), (x0 + width, y0 + height), (80, 88, 102), 2)
        if filled > 0:
            cv.rectangle(image, (x0 + 2, y0 + 2), (x0 + filled - 2, y0 + height - 2), (92, 208, 116), -1)

    def process(self, frame: dai.ImgFrame) -> None:
        image = frame.getCvFrame()
        output = self._overlay_coverage(image)
        out_frame = dai.ImgFrame()
        out_frame.setCvFrame(output, dai.ImgFrame.Type.BGR888p)
        out_frame.setTimestamp(frame.getTimestamp())
        out_frame.setSequenceNum(frame.getSequenceNum())
        out_frame.setTimestampDevice(frame.getTimestampDevice())
        try:
            self.output.send(out_frame)
        except Exception:
            return


class DepthPreviewNode(dai.node.HostNode):
    def __init__(self) -> None:
        super().__init__()
        self._max_distance_mm = 5000
        self._min_distance_mm = 300
        self._state: dict | None = None
        self.output = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)
            ]
        )

    def build(
        self,
        preview: dai.Node.Output,
        min_distance_mm: int = 300,
        max_distance_mm: int = 5000,
        state: dict | None = None,
    ) -> "DepthPreviewNode":
        self.link_args(preview)
        self._min_distance_mm = int(min_distance_mm)
        self._max_distance_mm = int(max_distance_mm)
        self._state = state
        return self

    def process(self, frame: dai.ImgFrame) -> None:
        depth_frame = frame.getCvFrame()
        min_distance_mm = self._min_distance_mm
        max_distance_mm = self._max_distance_mm
        hover_x = None
        hover_y = None
        if self._state is not None:
            lock = self._state["lock"]
            with lock:
                min_distance_mm = int(self._state["min_distance_mm"])
                max_distance_mm = int(self._state["max_distance_mm"])
                hover_x = self._state["hover_x"]
                hover_y = self._state["hover_y"]
        depth_color = FfcCalibrationApp._render_depth(
            depth_frame,
            min_distance=min_distance_mm,
            max_distance=max_distance_mm,
            colormap=cv.COLORMAP_TURBO,
        )
        label = (
            f"Depth range: {min_distance_mm / 1000.0:.1f}m"
            f" - {max_distance_mm / 1000.0:.1f}m"
        )
        cv.putText(
            depth_color,
            label,
            (18, 30),
            cv.FONT_HERSHEY_SIMPLEX,
            0.72,
            (255, 255, 255),
            2,
            cv.LINE_AA,
        )
        if hover_x is not None and hover_y is not None:
            x = int(np.clip(hover_x, 0, depth_frame.shape[1] - 1))
            y = int(np.clip(hover_y, 0, depth_frame.shape[0] - 1))
            x0 = max(0, x - 1)
            x1 = min(depth_frame.shape[1], x + 2)
            y0 = max(0, y - 1)
            y1 = min(depth_frame.shape[0], y + 2)
            roi = depth_frame[y0:y1, x0:x1]
            valid = roi[roi > 0]
            avg_mm = float(np.mean(valid)) if valid.size > 0 else None
            annotated = depth_color.copy()
            cv.rectangle(annotated, (x0, y0), (x1 - 1, y1 - 1), (255, 255, 255), 1)
            cv.drawMarker(annotated, (x, y), (255, 255, 255), cv.MARKER_CROSS, 10, 1, cv.LINE_AA)
            probe_label = f"3x3 ROI: invalid @ ({x}, {y})"
            if avg_mm is not None:
                probe_label = f"3x3 ROI: {avg_mm / 1000.0:.3f} m ({avg_mm:.0f} mm) @ ({x}, {y})"
            cv.putText(
                annotated,
                probe_label,
                (18, 58),
                cv.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
                cv.LINE_AA,
            )
            depth_color = annotated
            if self._state is not None:
                lock = self._state["lock"]
                with lock:
                    self._state["probe_mm"] = avg_mm
                    self._state["frame_width"] = int(depth_frame.shape[1])
                    self._state["frame_height"] = int(depth_frame.shape[0])
        out_frame = dai.ImgFrame()
        out_frame.setCvFrame(depth_color, dai.ImgFrame.Type.BGR888p)
        out_frame.setTimestamp(frame.getTimestamp())
        out_frame.setSequenceNum(frame.getSequenceNum())
        out_frame.setTimestampDevice(frame.getTimestampDevice())
        try:
            self.output.send(out_frame)
        except Exception:
            return


class FfcCalibrationApp:
    def __init__(
        self,
        ip: str | None = None,
        resolution: tuple[int, int] = (1280, 800),
        fps: int = 30,
    ):
        self.ip = ip
        self.resolution = resolution
        self.fps = fps
        self._device_info = dai.DeviceInfo(ip) if ip else None
        self._renderer = CoordinateFrameRenderer()
        self.device: dai.Device | None = None

        with self._open_device() as device:
            self.deviceId = device.getDeviceId()
            self.camera_features = list(device.getConnectedCameraFeatures())
            self._camera_features_by_socket = {
                feature.socket: feature for feature in self.camera_features
            }
            self.all_sockets = [feature.socket for feature in self.camera_features]
            self.sockets = list(self.all_sockets)
            self.baseline_pairs = self._recommended_baseline_pairs(self.sockets)

        if len(self.sockets) < 2:
            raise RuntimeError(
                f"Dynamic calibration needs at least 2 connected cameras, got {len(self.sockets)}"
            )

    def _open_device(self):
        return dai.Device(self._device_info) if self._device_info is not None else dai.Device()

    def preview_resolution_for_socket(
        self, socket: dai.CameraBoardSocket
    ) -> tuple[int, int]:
        feature = self._camera_features_by_socket.get(socket)
        width = int(getattr(feature, "width", 0) or 0)
        height = int(getattr(feature, "height", 0) or 0)
        calibration_resolution = getattr(feature, "calibrationResolution", None)
        calib_width = int(getattr(calibration_resolution, "width", 0) or 0)
        calib_height = int(getattr(calibration_resolution, "height", 0) or 0)
        sensor_type = str(getattr(feature, "supportedTypes", "")).upper()

        if (width, height) == (3840, 2160) or (calib_width, calib_height) == (4056, 3040):
            return (1920, 1080)
        if "MONO" in sensor_type and (width, height) == (1280, 800):
            return (640, 400)
        return self.resolution

    def preview_resolution_for_pair(
        self,
        left_socket: dai.CameraBoardSocket,
        right_socket: dai.CameraBoardSocket,
    ) -> tuple[int, int]:
        left_resolution = self.preview_resolution_for_socket(left_socket)
        right_resolution = self.preview_resolution_for_socket(right_socket)
        return (
            min(left_resolution[0], right_resolution[0]),
            min(left_resolution[1], right_resolution[1]),
        )

    @contextmanager
    def open_device(self):
        if self.device is not None:
            yield self.device
            return

        with self._open_device() as device:
            self.device = device
            try:
                yield device
            finally:
                self.device = None

    def close(self):
        if self.device is not None:
            self.device.close()
            self.device = None

    def select_sockets(self, sockets: list[dai.CameraBoardSocket]) -> None:
        available = set(self.all_sockets)
        selected = [socket for socket in self.all_sockets if socket in sockets and socket in available]
        if len(selected) < 2:
            raise ValueError("Select at least two connected camera sockets")
        self.sockets = selected
        self.baseline_pairs = self._recommended_baseline_pairs(self.sockets)

    @staticmethod
    def _recommended_baseline_pairs(
        sockets: list[dai.CameraBoardSocket],
    ) -> list[tuple[dai.CameraBoardSocket, dai.CameraBoardSocket]]:
        return list(zip(sockets[:-1], sockets[1:]))

    def select_baseline_pairs(
        self,
        pairs: list[tuple[dai.CameraBoardSocket, dai.CameraBoardSocket]],
    ) -> None:
        selected = set(self.sockets)
        normalized: list[tuple[dai.CameraBoardSocket, dai.CameraBoardSocket]] = []
        seen: set[tuple[dai.CameraBoardSocket, dai.CameraBoardSocket]] = set()

        for src, dest in pairs:
            if src not in selected or dest not in selected:
                raise ValueError("Baseline links must use selected sockets")
            if src == dest:
                raise ValueError("Baseline link cannot use the same socket twice")
            key = (src, dest)
            reverse_key = (dest, src)
            if key in seen or reverse_key in seen:
                continue
            seen.add(key)
            normalized.append(key)

        if not normalized:
            raise ValueError("Select at least one baseline link")

        connected = {normalized[0][0], normalized[0][1]}
        changed = True
        while changed:
            changed = False
            for src, dest in normalized:
                if src in connected and dest not in connected:
                    connected.add(dest)
                    changed = True
                if dest in connected and src not in connected:
                    connected.add(src)
                    changed = True

        if connected != selected:
            raise ValueError("Baseline links must connect all selected sockets")

        self.baseline_pairs = normalized

    def get_all_stereo_pairs(
        self, calibration: dai.CalibrationHandler
    ) -> list[StereoPair]:
        pairs: list[StereoPair] = []
        for i in range(len(self.sockets)):
            for j in range(i + 1, len(self.sockets)):
                tvec = np.asarray(
                    calibration.getCameraTranslationVector(
                        self.sockets[i], self.sockets[j], False
                    )
                ).reshape(-1)
                if float(tvec[0]) < 0:
                    pairs.append(StereoPair(self.sockets[i], self.sockets[j]))
                else:
                    pairs.append(StereoPair(self.sockets[j], self.sockets[i]))
        return pairs

    @staticmethod
    def _render_depth(
        depth_frame: np.ndarray,
        min_distance: int = 500,
        max_distance: int = 8000,
        colormap=cv.COLORMAP_TURBO,
        use_log: bool = False,
    ) -> np.ndarray:
        depth_frame = depth_frame.astype(np.float32)
        valid_mask = depth_frame > 0

        if use_log:
            min_distance = np.log(min_distance + 1)
            max_distance = np.log(max_distance + 1)
            depth_frame = np.log(depth_frame + 1)

        depth_frame = np.clip(depth_frame, min_distance, max_distance)
        depth_frame = (
            (depth_frame - min_distance) / (max_distance - min_distance) * 255
        ).astype(np.uint8)
        depth_heatmap = cv.applyColorMap(depth_frame, colormap)
        depth_heatmap[~valid_mask] = (0, 0, 0)
        return depth_heatmap

    @staticmethod
    def _annotate_depth(
        depth_color: np.ndarray, depth_frame: np.ndarray, depth_pick: dict[str, int | None]
    ) -> np.ndarray:
        x = depth_pick["x"]
        y = depth_pick["y"]
        if x is None or y is None:
            return depth_color
        if y < 0 or y >= depth_frame.shape[0] or x < 0 or x >= depth_frame.shape[1]:
            return depth_color

        depth_mm = int(depth_frame[y, x])
        label = f"({x}, {y}) depth: invalid"
        if depth_mm > 0:
            label = f"({x}, {y}) depth: {depth_mm} mm / {depth_mm / 1000.0:.3f} m"

        annotated = depth_color.copy()
        cv.circle(annotated, (x, y), 5, (255, 255, 255), 1)
        cv.putText(
            annotated,
            label,
            (20, 30),
            cv.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            3,
            cv.LINE_AA,
        )
        cv.putText(
            annotated,
            label,
            (20, 30),
            cv.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 0),
            1,
            cv.LINE_AA,
        )
        return annotated

    def _apply_entered_baselines(
        self,
        calibration: dai.CalibrationHandler,
        entered_baselines_cm: dict[tuple[dai.CameraBoardSocket, dai.CameraBoardSocket], float],
    ) -> dai.CalibrationHandler:
        for (src, dest), baseline_cm in entered_baselines_cm.items():
            constrained_list = np.array([baseline_cm, 0, 0]).tolist()
            calibration.setCameraExtrinsics(
                src,
                dest,
                np.eye(3),
                constrained_list,
                constrained_list,
            )

        return calibration

    def _copy_calibration(
        self, calibration: dai.CalibrationHandler
    ) -> dai.CalibrationHandler:
        return dai.CalibrationHandler.fromJson(calibration.eepromToJson())

    def validate_entered_baselines(
        self,
        calibration: dai.CalibrationHandler,
        entered_baselines_cm: dict[tuple[dai.CameraBoardSocket, dai.CameraBoardSocket], float],
    ) -> None:
        if not entered_baselines_cm:
            return

        try:
            self._apply_entered_baselines(
                self._copy_calibration(calibration),
                entered_baselines_cm,
            )
        except RuntimeError as exc:
            raise ValueError(
                "Invalid baseline selection. The entered links create an inconsistent "
                f"calibration topology: {exc}"
            ) from exc

    def create_empty_handler(self, calibration: dai.CalibrationHandler):
        for src in self.all_sockets:
            calibration.setCameraExtrinsics(srcCameraId= src, destCameraId=dai.CameraBoardSocket.AUTO, rotationMatrix=np.eye(3), translation=[0,0,0], specTranslation=[0, 0, 0])


    def _log_entered_baseline_readback(
        self,
        calibration: dai.CalibrationHandler,
        entered_baselines_cm: dict[tuple[dai.CameraBoardSocket, dai.CameraBoardSocket], float],
        header: str = "Entered baseline readback",
    ) -> None:
        if not entered_baselines_cm:
            return

        print(f"\n{header}:")
        for (src, dest), entered_baseline_cm in entered_baselines_cm.items():
            tvec = np.asarray(
                calibration.getCameraTranslationVector(src, dest, False),
                dtype=np.float64,
            ).reshape(-1)
            print(
                f"  {format_socket(src)} -> {format_socket(dest)} "
                f"entered={entered_baseline_cm:.3f} cm "
                f"applied={np.round(tvec, 3).tolist()} "
                f"norm={float(np.linalg.norm(tvec)):.3f} cm"
            )

    def create_eeprom(self, use_device_calibration: bool = True) -> dai.CalibrationHandler:
        with self.open_device() as device:
            source_calibration = device.readCalibration()

            if use_device_calibration:
                entered = getattr(self, "entered_baselines_cm", {})
                if entered:
                    self.create_empty_handler(source_calibration)
                    self.validate_entered_baselines(source_calibration, entered)
                    constrained = self._apply_entered_baselines(source_calibration, entered)
                    self._log_entered_baseline_readback(
                        constrained,
                        entered,
                        header="Applied entered baselines to device calibration",
                    )
                    return constrained
                return source_calibration

            self.entered_baselines_cm = {}

            for src, dest in self.baseline_pairs:
                baseline_cm = float(
                    input(
                        f"Baseline distance between sockets {format_socket(src)} and {format_socket(dest)} (cm): "
                    )
                )
                self.entered_baselines_cm[(src, dest)] = baseline_cm

            self.validate_entered_baselines(
                source_calibration,
                self.entered_baselines_cm,
            )
            constrained = self._apply_entered_baselines(
                source_calibration,
                self.entered_baselines_cm,
            )
            self._log_entered_baseline_readback(
                constrained,
                self.entered_baselines_cm,
                header="Applied entered baselines to initial calibration",
            )
            return constrained

    def flash_calibration(self, calibration: dai.CalibrationHandler):
        if self.device is None:
            raise RuntimeError("flash_calibration requires an active device context")
        self.device.flashCalibration(calibration)
        print("Calibration flashed to device.")

    def visualize_cameras(
        self,
        calibration: dai.CalibrationHandler,
        save_path: Path | None = None,
        selected_pair: StereoPair | None = None,
    ):
        reference_socket = self.sockets[0]
        image = self._renderer.render(
            calibration,
            self.sockets,
            reference_socket=reference_socket,
            selected_pair=selected_pair,
            title=f"Camera Coordinate Frames relative to {format_socket(reference_socket)}",
            status_lines=[
                f"Detected cameras: {', '.join(format_socket(socket) for socket in self.sockets)}",
                "Press any key in the OpenCV window to close this preview.",
            ],
        )

        if save_path is not None:
            cv.imwrite(str(save_path), image)
            print(f"Saved coordinate-system plot to {save_path}")
            return

        window_name = "coordinate_frames"
        cv.namedWindow(window_name, cv.WINDOW_NORMAL)
        cv.imshow(window_name, image)
        while True:
            if cv.waitKey(30) != -1:
                break
        cv.destroyWindow(window_name)

    def calibrate(
        self,
        initial_calibration: dai.CalibrationHandler,
        status_label: str = "Dynamic calibration",
    ) -> dai.CalibrationHandler:
        with self.open_device() as device:
            with dai.Pipeline(device) as pipeline:
                pipeline.setAutoCalibrationMode(dai.Pipeline.AutoCalibrationMode.OFF)
                device.setCalibration(initial_calibration)
                dynamic_calibration = pipeline.create(dai.node.DynamicCalibration)
                dynamic_calibration.sync.setSyncThreshold(timedelta(milliseconds=20))

                preview_queues = {}
                preview_windows = {}
                for socket in self.sockets:
                    camera = pipeline.create(dai.node.Camera).build(socket)
                    output = camera.requestOutput(
                        self.preview_resolution_for_socket(socket), fps=self.fps
                    )
                    output.link(dynamic_calibration.inputs[f"input_{int(socket)}"])
                    preview_queues[socket] = output.createOutputQueue(
                        maxSize=1, blocking=False
                    )
                    preview_windows[socket] = f"preview_{format_socket(socket)}"
                    cv.namedWindow(preview_windows[socket], cv.WINDOW_NORMAL)

                calibration_input = dynamic_calibration.inputControl.createInputQueue()
                calibration_output = dynamic_calibration.calibrationOutput.createOutputQueue(
                    maxSize=1, blocking=False
                )

                status_window = "calibration_status"
                frames_window = "calibration_frames"
                cv.namedWindow(status_window, cv.WINDOW_NORMAL)
                cv.namedWindow(frames_window, cv.WINDOW_NORMAL)

                new_calibration = None
                print("Starting dynamic calibration...")

                pipeline.start()
                calibration_input.send(
                    dai.DynamicCalibrationControl.setPerformanceMode(
                        dai.DynamicCalibrationControl.PerformanceMode.SKIP_CHECKS
                    )
                )
                calibration_input.send(
                    dai.DynamicCalibrationControl.startCalibration(
                        loadImagePeriod=0.5,
                        calibrationPeriod=5.0,
                    )
                )

                while pipeline.isRunning():
                    status_frame = np.zeros((220, 760, 3), dtype=np.uint8)
                    lines = [
                        status_label,
                        "Collecting frames for calibration.",
                        "Press q to cancel.",
                    ]
                    for i, line in enumerate(lines):
                        cv.putText(
                            status_frame,
                            line,
                            (20, 45 + i * 42),
                            cv.FONT_HERSHEY_SIMPLEX,
                            0.9 if i == 0 else 0.7,
                            (255, 255, 255),
                            2,
                            cv.LINE_AA,
                        )

                    cv.imshow(status_window, status_frame)

                    current_calibration = device.getCalibration()
                    frame = self._renderer.render(
                        current_calibration,
                        self.sockets,
                        reference_socket=self.sockets[0],
                        title="Camera Coordinate Frames (live)",
                        status_lines=[
                            f"Calibration status: {status_label}",
                            "Frames stay visible while capture is running.",
                            "This plot always reflects the current calibration state.",
                        ],
                    )
                    cv.imshow(frames_window, frame)

                    for socket, queue in preview_queues.items():
                        preview = queue.tryGet()
                        if preview is not None:
                            image = preview.getCvFrame()
                            cv.putText(
                                image,
                                format_socket(socket),
                                (20, 30),
                                cv.FONT_HERSHEY_SIMPLEX,
                                0.8,
                                (255, 255, 255),
                                2,
                                cv.LINE_AA,
                            )
                            cv.imshow(preview_windows[socket], image)

                    result = calibration_output.tryGet()
                    if result is not None and result.calibrationData:
                        new_calibration = result.calibrationData.newCalibration
                        calibration_input.send(
                            dai.DynamicCalibrationControl.stopCalibration()
                        )
                        calibration_input.send(
                            dai.DynamicCalibrationControl(
                                dai.DynamicCalibrationControl.Commands.ApplyCalibration(
                                    new_calibration
                                )
                            )
                        )
                        break

                    if cv.waitKey(1) == ord("q"):
                        raise RuntimeError("Calibration cancelled by user")

                cv.destroyWindow(status_window)

                if new_calibration is None:
                    raise RuntimeError("DynamicCalibration did not return calibration data")

                print("Calibration complete.")
                return new_calibration

    def show_depth(
        self,
        left_socket: dai.CameraBoardSocket,
        right_socket: dai.CameraBoardSocket,
        calibration: dai.CalibrationHandler | None = None,
        live_renderer: CoordinateFrameRenderer | None = None,
    ):
        with self.open_device() as device:
            with dai.Pipeline(device) as pipeline:
                pipeline.setAutoCalibrationMode(dai.Pipeline.AutoCalibrationMode.OFF)
                stereo = pipeline.create(dai.node.StereoDepth)
                stereo.setRectification(True)
                stereo.setExtendedDisparity(True)
                stereo.setRectificationUseSpecTranslation(False)
                stereo.setDepthAlignmentUseSpecTranslation(False)
                stereo.setDisparityToDepthUseSpecTranslation(False)

                left_cam = pipeline.create(dai.node.Camera).build(left_socket)
                right_cam = pipeline.create(dai.node.Camera).build(right_socket)

                shared_resolution = self.preview_resolution_for_pair(
                    left_socket, right_socket
                )
                left_output = left_cam.requestOutput(shared_resolution, fps=self.fps)
                right_output = right_cam.requestOutput(shared_resolution, fps=self.fps)
                left_output.link(stereo.left)
                right_output.link(stereo.right)

                rectified_left_queue = stereo.rectifiedLeft.createOutputQueue()
                rectified_right_queue = stereo.rectifiedRight.createOutputQueue()
                depth_queue = stereo.depth.createOutputQueue()
                depth_window = "depth_heatmap"
                depth_pick = {"x": None, "y": None}
                device.setCalibration(calibration)

                def on_depth_mouse(event, x, y, flags, param):
                    if event == cv.EVENT_LBUTTONDOWN:
                        depth_pick["x"] = x
                        depth_pick["y"] = y

                cv.namedWindow(depth_window, cv.WINDOW_NORMAL)
                cv.setMouseCallback(depth_window, on_depth_mouse)

                if live_renderer is not None:
                    plot_window = "camera_frames"
                    cv.namedWindow(plot_window, cv.WINDOW_NORMAL)

                pipeline.start()
                active_pair_label = f"{format_socket(left_socket)} -> {format_socket(right_socket)}"
                while pipeline.isRunning():
                    left_rectified = rectified_left_queue.get()
                    right_rectified = rectified_right_queue.get()
                    depth = depth_queue.get()

                    cv.imshow("left_rectified", left_rectified.getCvFrame())
                    cv.imshow("right_rectified", right_rectified.getCvFrame())

                    depth_frame = depth.getFrame()
                    color_depth = self._render_depth(
                        depth_frame,
                        min_distance=500,
                        max_distance=8000,
                        colormap=cv.COLORMAP_TURBO,
                        use_log=False,
                    )
                    color_depth = self._annotate_depth(color_depth, depth_frame, depth_pick)
                    cv.imshow(depth_window, color_depth)

                    if live_renderer is not None:
                        plot = live_renderer.render(
                            calibration if calibration is not None else device.getCalibration(),
                            self.sockets,
                            reference_socket=self.sockets[0],
                            title=f"Camera Coordinate Frames (live) - {active_pair_label}",
                            status_lines=[
                                f"Currently displaying: {active_pair_label}",
                                "Press q to exit depth preview.",
                            ],
                        )
                        cv.imshow(plot_window, plot)

                    if cv.waitKey(1) == ord("q"):
                        break

        cv.destroyAllWindows()
