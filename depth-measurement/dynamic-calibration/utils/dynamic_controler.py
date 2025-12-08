from typing import Optional, Tuple
from collections import deque
import numpy as np
import time

import depthai as dai


class DynamicCalibrationControler(dai.node.HostNode):
    def __init__(self):
        super().__init__()
        # queues you set after pipeline.start()
        self._cmd_q = None
        self._quality_q = None

        # extra input for raw depth/disparity frames
        self.in_depth = self.createInput(
            types=[dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgFrame, True)],
            queueSize=1,
            blocking=False,
            waitForMessage=False,
        )

        self._device: Optional[dai.Device] = None  # for flash operations

        # state
        self.calibration: Optional[dai.CalibrationHandler] = None
        self.new_calibration: Optional[dai.CalibrationHandler] = None
        self.old_calibration: Optional[dai.CalibrationHandler] = None
        self.last_quality = None
        self.wants_quit = False
        self._show_help = True

        self._calib_q = None  # queue for dyn_calib.calibrationOutput
        self._last_calib_diff = None  # latest calibrationDifference
        self.auto_apply_new = True  # set False if you prefer pressing 'n'

        self._coverage_q = None
        self._coverage_vec = (
            None  # flattened coveragePerCellA (0..1 or 0..100 per cell)
        )
        self._coverage_pct = 0.0  # mean coverage in %
        self._data_acquired = 0.0  # dataAcquired from device (0..1 or 0..100)
        self._collecting = False  # are we currently collecting frames?
        self._collecting_until = 0.0

        # transient status banner (2s)
        self._status_text = None
        self._status_expire_ts = 0.0

        # modal overlays (centered), auto-hide or dismiss on key
        self._modal_kind = None  # None | "recalib" | "quality"
        self._modal_expire_ts = 0.0
        self._modal_payload = {}

        # depth HUD state
        self._last_depth = None  # np.ndarray (uint16 depth mm or disparity)
        self._depth_is_mm = True  # set False if you link disparity
        self._cursor_xy = None  # (x,y) in depth pixels
        self._roi_half = 10  # radius in depth pixels (=> (2h+1)^2 window)
        self._hud_on = True  # toggle with 'g'

        self._avg_len = 10
        self._roi_mean_hist = deque(maxlen=self._avg_len)
        self._center_hist = deque(maxlen=self._avg_len)
        self._hist_cursor_xy = None

        self.out_annotations = self.createOutput(
            possibleDatatypes=[
                dai.Node.DatatypeHierarchy(dai.DatatypeEnum.ImgAnnotations, True)
            ]
        )

    def set_device(self, device: dai.Device):
        """Provide a device so we can flash calibrations from keypresses."""
        self._device = device

    # ---- external wiring ----
    def set_command_input(self, q):
        self._cmd_q = q

    def set_quality_output(self, q):
        self._quality_q = q

    def set_coverage_output(self, q):
        """Pass dyn_calib.coverageOutput.createOutputQueue(...) here."""
        self._coverage_q = q

    # If you want to use disparity instead of depth (units in “levels”):
    def set_depth_units_is_mm(self, is_mm: bool):
        self._depth_is_mm = is_mm

    def set_calibration_output(self, q):
        """Pass dyn_calib.calibrationOutput.createOutputQueue(...) here."""
        self._calib_q = q

    def _flash_status(self, text: str, seconds: float = 2.0):
        self._status_text = text
        self._status_expire_ts = time.time() + seconds

    def set_auto_apply_new(self, enable: bool):
        self.auto_apply_new = bool(enable)

    def build(self, preview: dai.Node.Output, depth: dai.Node.Output = None):
        # 'preview' is the stream we time-stamp overlays against (e.g., your colormapped depth)
        self.link_args(preview)
        if depth is not None:
            depth.link(self.in_depth)
        return self

    # ---- helpers ----
    def _send_cmd(self, cmd):
        if self._cmd_q is None:
            raise RuntimeError(
                "Command queue not set. Call set_command_input(...) after pipeline.start()"
            )
        self._cmd_q.send(dai.DynamicCalibrationControl(cmd))

    def _coverage_bar_text(self, pct: float, width_chars: int = 36) -> str:
        pct = float(np.clip(pct, 0.0, 100.0))
        filled = int(round((pct / 100.0) * width_chars))
        return "█" * filled + "░" * (width_chars - filled)

    def _draw_depth_hud(self, hud: dai.ImgAnnotation, preview_w: int, preview_h: int):
        if self._last_depth is None or not self._hud_on:
            return

        H, W = self._last_depth.shape[:2]
        # init cursor at center the first time
        if self._cursor_xy is None:
            self._cursor_xy = (W // 2, H // 2)

        cx, cy = self._cursor_xy
        cx = int(np.clip(cx, 0, W - 1))
        cy = int(np.clip(cy, 0, H - 1))

        # ROI bounds
        h = int(max(1, self._roi_half))
        x0, x1 = max(0, cx - h), min(W, cx + h + 1)
        y0, y1 = max(0, cy - h), min(H, cy + h + 1)
        roi = self._last_depth[y0:y1, x0:x1]

        # stats (ignore zeros if depth)
        if self._hist_cursor_xy != (cx, cy):
            self._roi_mean_hist.clear()
            self._center_hist.clear()
            self._hist_cursor_xy = (cx, cy)

        if self._depth_is_mm:
            valid = roi > 0

            # center (mm)
            center_mm = float(self._last_depth[cy, cx])
            if center_mm > 0:
                self._center_hist.append(center_mm)

            # roi mean (mm)
            if np.any(valid):
                roi_mean_mm = float(roi[valid].mean())
                self._roi_mean_hist.append(roi_mean_mm)

            # aggregated (m)
            if len(self._center_hist) > 0:
                center_val = float(np.mean(self._center_hist)) / 1000.0
            else:
                center_val = float("nan")

            if len(self._roi_mean_hist) > 0:
                mean_val = float(np.mean(self._roi_mean_hist)) / 1000.0
            else:
                mean_val = float("nan")

            val_text = (
                f"Depth: {center_val:.2f} m, "
                f"ROI mean: {mean_val:.2f} m "
                f"(avg {len(self._roi_mean_hist)}/{self._avg_len})"
            )
        else:
            # disparity path (no zero filtering)
            center_disp = float(self._last_depth[cy, cx])
            roi_mean_disp = float(roi.mean())

            self._center_hist.append(center_disp)
            self._roi_mean_hist.append(roi_mean_disp)

            center_val = float(np.mean(self._center_hist))
            mean_val = float(np.mean(self._roi_mean_hist))

            val_text = (
                f"Disp: {center_val:.1f}, "
                f"ROI mean: {mean_val:.1f} "
                f"(avg {len(self._roi_mean_hist)}/{self._avg_len})"
            )

        # normalized positions relative to preview (assume 1:1 mapping depth→preview)
        u = (cx + 0.5) / W
        v = (cy + 0.5) / H

        # place readout slightly offset
        hud.texts.append(
            self._create_text_annot(
                val_text, (min(u + 0.02, 0.95), min(v + 0.02, 0.95))
            )
        )

        # "tiny box" corners using text markers (no special rect types needed)
        corner = "□"
        u0, v0 = x0 / W, y0 / H
        u1, v1 = x1 / W, y1 / H
        hud.texts.append(self._create_text_annot(corner, (u0, v0), bg=(0, 0, 0, 0)))
        hud.texts.append(self._create_text_annot(corner, (u1, v0), bg=(0, 0, 0, 0)))
        hud.texts.append(self._create_text_annot(corner, (u0, v1), bg=(0, 0, 0, 0)))
        hud.texts.append(self._create_text_annot(corner, (u1, v1), bg=(0, 0, 0, 0)))

    # --- styling helpers (white on translucent black) ---
    def _create_text_annot(
        self,
        text: str,
        pos: Tuple[float, float],
        size=14,
        bg=(0, 0, 0, 0.55),
        fg=(1, 1, 1, 1),
    ):
        t = dai.TextAnnotation()
        t.fontSize = size
        t.backgroundColor = dai.Color(*bg)
        t.textColor = dai.Color(*fg)
        t.position = dai.Point2f(*pos)  # normalized [0..1]
        t.text = text
        return t

    # --- centered panels / modals ---
    def _push_center_panel(
        self,
        img_annots: dai.ImgAnnotations,
        lines,
        *,
        y_center=0.50,
        width=0.74,
        line_size=20,
        line_gap=0.035,
        accent_idx=None,
        accent_colors=None,
    ):
        """
        Draws a centered panel with a single translucent background slab and multiple lines.
        `accent_idx`: set of indices to color differently (e.g., titles/warnings).
        `accent_colors`: dict idx->(r,g,b,a) for text, e.g. (1,0,0,1) for red.
        """
        if not lines:
            return
        x0 = (1.0 - width) / 2.0
        x_text = x0 + 0.15
        n = len(lines)
        total_h = n * line_gap
        y0 = y_center - total_h / 2

        # foreground text
        hud = dai.ImgAnnotation()
        for i, line in enumerate(lines):
            fg = (1, 1, 1, 1)
            if accent_idx and i in accent_idx and accent_colors and i in accent_colors:
                fg = accent_colors[i]
            hud.texts.append(
                self._create_text_annot(
                    line,
                    (x_text, y0 + i * line_gap),
                    size=line_size,
                    bg=(0, 0, 0, 0),
                    fg=fg,
                )
            )
        img_annots.annotations.append(hud)

    def _bar_string(self, length_chars, char="█"):
        return char * max(0, int(length_chars))

    def _push_quality_bar_modal(
        self, img_annots: dai.ImgAnnotations, values, rotation, display_text=""
    ):
        """
        Big centered quality modal:
          - Title: 'Calibration Quality: {GOOD | COULD BE IMPROVED | NEEDS RECALIBRATION}'
          - 3 contiguous colored bar segments (green/yellow/red) packed closer together
          - Downward pointer (▼) placed ABOVE the bar (pointing down at it)
          - No text rendered below the bar
        """
        if rotation is None or len(rotation) == 0:
            self._push_center_panel(
                img_annots,
                [
                    "Data is missing — please load more images with 'l'.",
                    "Press any key to continue …",
                ],
                y_center=0.42,
                width=0.84,
                line_size=20,
                line_gap=0.04,
            )
            return

        rot_max = float(np.max(np.abs(rotation)))
        # thresholds (deg)
        t1, t2 = 0.07, 0.15

        # status text + title color
        if rot_max <= t1:
            status = "GOOD"
            title_color = (0, 1, 0, 1)
        elif rot_max <= t2:
            status = "COULD BE IMPROVED"
            title_color = (1, 1, 0, 1)
        else:
            status = "NEEDS RECALIBRATION"
            title_color = (1, 0, 0, 1)

        # Centered title (use a narrower panel so it looks centered)
        title = f"Calibration Quality: {status}"
        self._push_center_panel(
            img_annots,
            [title],
            y_center=0.42,
            width=0.60,
            line_size=24,
            line_gap=0.04,
            accent_idx={0},
            accent_colors={0: title_color},
        )

        # Optional summary ABOVE the bar (never below)
        if values is not None and len(values) >= 4:
            summary = (
                f"Depth error @1m:{values[0]:.2f}%, 2m:{values[1]:.2f}%, "
                f"5m:{values[2]:.2f}%, 10m:{values[3]:.2f}%"
            )
            self._push_center_panel(
                img_annots,
                [summary],
                y_center=0.62,
                width=0.90,
                line_size=18,
                line_gap=0.035,
            )

        # Bar geometry (packed closer together)
        x0, x1 = 0.20, 0.80  # tighter horizontal span
        y_bar = 0.52  # bar vertical position
        w = x1 - x0
        total_chars = 45
        seg_chars = total_chars // 3

        good = self._bar_string(seg_chars)
        mid = self._bar_string(seg_chars)
        bad = self._bar_string(total_chars - 2 * seg_chars)

        # contiguous segments (minimal padding between thirds)
        seg_dx = w / 3.0
        lefts = [x0 + 0.01, x0 + seg_dx + 0.005, x0 + 2 * seg_dx + 0.005]

        def _slice(x, y, s, color):
            ann = dai.ImgAnnotation()
            ann.texts.append(
                self._create_text_annot(s, (x, y), size=26, bg=(0, 0, 0, 0), fg=color)
            )
            img_annots.annotations.append(ann)

        _slice(lefts[0], y_bar, good, (0, 1, 0, 1))  # green
        _slice(lefts[1], y_bar, mid, (1, 1, 0, 1))  # yellow
        _slice(lefts[2], y_bar, bad, (1, 0, 0, 1))  # red

        # Downward pointer '▼' placed ABOVE the bar (pointing down at it)
        if rot_max <= t1:
            frac = (rot_max / t1) * (1.0 / 3.0)
        elif rot_max <= t2:
            frac = (1.0 / 3.0) + ((rot_max - t1) / (t2 - t1)) * (1.0 / 3.0)
        else:
            cap = max(t2, min(rot_max, 2.0 * t2))
            frac = (2.0 / 3.0) + ((cap - t2) / t2) * (1.0 / 3.0)
            frac = min(frac, 0.999)

        x_ptr = x0 + frac * w
        arrow = dai.ImgAnnotation()
        arrow.texts.append(
            self._create_text_annot(
                "▼", (x_ptr, y_bar - 0.045), size=24, bg=(0, 0, 0, 0), fg=(1, 1, 1, 1)
            )
        )
        img_annots.annotations.append(arrow)

        # NOTE: No labels or tail text are rendered under the bar.

    def _push_recalibration_modal(self, img_annots: dai.ImgAnnotations, values, angles):
        """
        Recreates your draw_recalibration_message.
        """
        lines = []
        accents = {}
        if values is None or len(values) == 0 or angles is None or len(angles) < 3:
            lines = [
                "Data is missing — please load more images with 'l'.",
                "Press any key to continue …",
            ]
            self._push_center_panel(
                img_annots,
                lines,
                y_center=0.42,
                width=0.84,
                line_size=20,
                line_gap=0.04,
            )
            return

        threshold = 0.075
        abs_ang = np.abs(np.asarray(angles))
        over = np.where(abs_ang > threshold)[0].tolist()
        axis_names = ["Roll", "Pitch", "Yaw"]
        lines.append("Recalibration complete")
        accents[0] = (0, 1, 0, 1)  # green title

        if over:
            axes = ", ".join(axis_names[i] for i in over)
            lines.append(f"Significant change in rotation! {axes}")
            accents[1] = (1, 0, 0, 1)  # red warning
            lines.append("To permanently flash new calibration, press 's'!")
        else:
            lines.append("No significant change detected")

        lines.append(
            f"Euler angles (deg): Roll={angles[0]:.2f}, "
            f"Pitch={angles[1]:.2f}, Yaw={angles[2]:.2f}"
        )
        if values is not None and len(values) >= 4:
            lines.append(
                f"Depth error @1m:{values[0]:.2f}%, 2m:{values[1]:.2f}%, "
                f"5m:{values[2]:.2f}%, 10m:{values[3]:.2f}%"
            )
        lines.append("Press any key to continue …")

        self._push_center_panel(
            img_annots,
            lines,
            y_center=0.55,
            width=0.80,
            line_size=20,
            line_gap=0.04,
            accent_idx=set(accents.keys()),
            accent_colors=accents,
        )

    # --- help panel ---
    def _push_help_panel(self, img_annots: dai.ImgAnnotations, frame: dai.ImgFrame):
        """
        Draws a compact help list without per-line background (keeps it readable).
        """
        lines = [
            "DynamicCalibration — Key commands",
            "[c] Calibration quality check",
            "[r] Recalibrate",
            "[C] Force calibration check",
            "[R] Force recalibrate",
            "[l] Load image",
            "[n] Apply new calibration",
            "[o] Apply old/previous",
            "[p] Flash new calibration",
            "[k] Flash old calibration",
            "[f] Flash factory calibration",
            "[g] Toggle depth HUD    [h] Toggle help",
            "[w]/[a]/[s] Move ROI    [z]/[x] ROI size",
            "",
            "[h] Show/Hide Help Display",
            "[q] Quit",
        ]

        # Layout (smaller font, tighter spacing)
        size = 18
        x = 0.04  # left
        y0 = 0.075  # top
        dy = 0.025  # line spacing (tight)

        hud = dai.ImgAnnotation()
        # Title slightly larger
        hud.texts.append(
            self._create_text_annot(
                lines[0], (x, y0), size=16, bg=(0, 0, 0, 0), fg=(1, 1, 1, 1)
            )
        )
        y = y0 + dy * 1.2
        for line in lines[1:]:
            hud.texts.append(
                self._create_text_annot(
                    line, (x, y), size=size, bg=(0, 0, 0, 0), fg=(1, 1, 1, 1)
                )
            )
            y += dy

        img_annots.annotations.append(hud)
        img_annots.setTimestamp(frame.getTimestamp())

    def _push_center_banner(
        self,
        img_annots: dai.ImgAnnotations,
        text: str,
        x0=0.25,
        x1=0.75,
        y_center=0.50,
        band_h=0.14,
        size=20,
    ):
        # Background slab built from spacer rows
        slab = dai.ImgAnnotation()
        rows = 12
        for i in range(rows):
            y = y_center - band_h / 2 + i * (band_h / (rows - 1))
            slab.texts.append(
                self._create_text_annot(
                    " ", (x0, y), size=size, bg=(0, 0, 0, 0.55), fg=(0, 0, 0, 0)
                )
            )
        img_annots.annotations.append(slab)

        # Foreground text (center-left aligned with a small left margin)
        txt = dai.ImgAnnotation()
        txt.texts.append(
            self._create_text_annot(
                text,
                (x0 + 0.02, y_center - 0.01),
                size=size,
                bg=(0, 0, 0, 0),
                fg=(1, 1, 1, 1),
            )
        )
        img_annots.annotations.append(txt)

    # --- existing HUD, but styled to match (no green) ---
    def _push_status_overlay(self, img_annots: dai.ImgAnnotations, frame: dai.ImgFrame):
        hud = dai.ImgAnnotation()
        y, dy, x = 0.05, 0.04, 0.05

        if self.old_calibration:
            hud.texts.append(
                self._create_text_annot("PREVIOUS calibration: available", (x, y))
            )
            y += dy

        if self.last_quality and getattr(self.last_quality, "qualityData", None):
            q = self.last_quality.qualityData
            rotmag = float(
                np.sqrt(
                    q.rotationChange[0] ** 2
                    + q.rotationChange[1] ** 2
                    + q.rotationChange[2] ** 2
                )
            )
            hud.texts.append(
                self._create_text_annot(f"Δrot = {rotmag:.3f}°", (0.55, 0.05))
            )
            hud.texts.append(
                self._create_text_annot(
                    f"Sampson mean: new={q.sampsonErrorNew:.3f}px  current={q.sampsonErrorCurrent:.3f}px",
                    (0.55, 0.09),
                )
            )

        # Small hint to show help
        hud.texts.append(
            self._create_text_annot(
                "[h] Help", (0.05, 0.92), size=14, bg=(0, 0, 0, 0.35)
            )
        )
        img_annots.annotations.append(hud)
        img_annots.setTimestamp(frame.getTimestamp())

    def _push_overlay(self, frame: dai.ImgFrame):
        img_annots = dai.ImgAnnotations()

        # Always show help panel
        if self._show_help:
            self._push_help_panel(img_annots, frame)

        now = time.time()

        # If 'l' timer elapsed, stop timed collecting
        if (
            self._collecting
            and self._collecting_until > 0.0
            and now >= self._collecting_until
        ):
            self._collecting = False
            self._collecting_until = 0.0

        # Coverage bar: show while collecting (respecting timer) or when partial progress exists
        show_cov = (
            self._collecting
            and (self._collecting_until == 0.0 or now < self._collecting_until)
        ) or (self._coverage_vec is not None and 0.0 < self._coverage_pct < 100.0)

        # Flash banner (2s) if any
        if self._status_text:
            if now < self._status_expire_ts:
                self._push_center_banner(img_annots, self._status_text, size=22)
            else:
                self._status_text = None
                self._status_expire_ts = 0.0

        elif show_cov:
            # Centered, bold coverage bar (no background slab)
            x0, x1 = 0.24, 0.67
            y_center = 0.51

            bar = self._coverage_bar_text(self._coverage_pct, width_chars=36)
            txt = f"Collecting frames  {self._coverage_pct:5.1f}%  {bar}"

            banner = dai.ImgAnnotation()
            banner.texts.append(
                self._create_text_annot(
                    txt,
                    (x0 + 0.02, y_center - 0.02),
                    size=22,
                    bg=(0, 0, 0, 0),
                    fg=(1, 1, 1, 1),
                )
            )
            img_annots.annotations.append(banner)

        # When no banner, no coverage bar, and no modal → draw the depth HUD
        no_banner = not (self._status_text and now < self._status_expire_ts)
        no_modal = not (self._modal_kind and now < self._modal_expire_ts)
        if no_banner and not show_cov and no_modal:
            hud = dai.ImgAnnotation()
            try:
                self._draw_depth_hud(hud, frame.getWidth(), frame.getHeight())
            except Exception:
                pass
            if len(hud.texts) > 0:
                img_annots.annotations.append(hud)

        # Small metrics (top-right) only when no modal is up
        if not (self._modal_kind and time.time() < self._modal_expire_ts):
            if self.last_quality and getattr(self.last_quality, "qualityData", None):
                qhud = dai.ImgAnnotation()
                q = self.last_quality.qualityData
                rotmag = float(
                    np.sqrt(
                        q.rotationChange[0] ** 2
                        + q.rotationChange[1] ** 2
                        + q.rotationChange[2] ** 2
                    )
                )
                qhud.texts.append(
                    self._create_text_annot(
                        f"Δrot = {rotmag:.3f}°",
                        (0.62, 0.06),
                        size=16,
                        bg=(0, 0, 0, 0.35),
                    )
                )
                qhud.texts.append(
                    self._create_text_annot(
                        f"Sampson mean: new={q.sampsonErrorNew:.3f}px  current={q.sampsonErrorCurrent:.3f}px",
                        (0.62, 0.10),
                        size=16,
                        bg=(0, 0, 0, 0.35),
                    )
                )
                img_annots.annotations.append(qhud)

            elif self._last_calib_diff is not None:
                q = self._last_calib_diff
                rotmag = float(
                    np.sqrt(
                        q.rotationChange[0] ** 2
                        + q.rotationChange[1] ** 2
                        + q.rotationChange[2] ** 2
                    )
                )
                hud_metrics = dai.ImgAnnotation()
                hud_metrics.texts.append(
                    self._create_text_annot(
                        f"Δrot(new vs current) = {rotmag:.3f}°",
                        (0.62, 0.06),
                        size=16,
                        bg=(0, 0, 0, 0.35),
                    )
                )
                hud_metrics.texts.append(
                    self._create_text_annot(
                        f"Sampson: new={q.sampsonErrorNew:.3f}px  current={q.sampsonErrorCurrent:.3f}px",
                        (0.62, 0.10),
                        size=16,
                        bg=(0, 0, 0, 0.35),
                    )
                )
                d = getattr(q, "depthErrorDifference", None)
                if d and len(d) >= 4:
                    hud_metrics.texts.append(
                        self._create_text_annot(
                            f"Depth Δ @1/2/5/10m: {d[0]:.2f}% / {d[1]:.2f}% / {d[2]:.2f}% / {d[3]:.2f}%",
                            (0.62, 0.14),
                            size=16,
                            bg=(0, 0, 0, 0.35),
                        )
                    )
                img_annots.annotations.append(hud_metrics)

        # Modals (centered, large) — drawn last so they’re on top
        now = time.time()
        if self._modal_kind and now < self._modal_expire_ts:
            if self._modal_kind == "recalib":
                self._push_recalibration_modal(
                    img_annots,
                    self._modal_payload.get("values"),
                    self._modal_payload.get("angles"),
                )
            elif self._modal_kind == "quality":
                self._push_quality_bar_modal(
                    img_annots,
                    self._modal_payload.get("values"),
                    self._modal_payload.get("rotation"),
                    self._modal_payload.get("text", ""),
                )
        elif self._modal_kind and now >= self._modal_expire_ts:
            self._modal_kind = None
            self._modal_expire_ts = 0.0
            self._modal_payload = {}

        self.out_annotations.send(img_annots)

    def process(self, frame: dai.ImgFrame):
        # 0) drain depth/disparity input so HUD has up-to-date pixels
        if self.in_depth is not None:
            while True:
                dmsg = self.in_depth.tryGet()
                if dmsg is None:
                    break
                try:
                    # store raw array (uint16 depth in mm, or disparity)
                    self._last_depth = dmsg.getFrame()
                except Exception:
                    pass

        # 1) drain quality queue
        if self._quality_q is not None:
            while True:
                msg = self._quality_q.tryGet()
                if msg is None:
                    break

                info = getattr(msg, "info", None)
                if info:
                    print(f"Dynamic calibration status: {info}")

                qd = getattr(msg, "qualityData", None)
                if qd:
                    self.last_quality = msg
                    self._status_text = None
                    self._status_expire_ts = 0.0
                    # Show quality modal (health bar)
                    self._modal_kind = "quality"
                    self._modal_payload = {
                        "values": getattr(qd, "depthErrorDifference", None),
                        "rotation": getattr(qd, "rotationChange", None),
                        "text": "",
                    }
                    self._modal_expire_ts = time.time() + 3.5
                else:
                    self._status_text = (
                        "Data is missing — please load more images with 'l'."
                    )
                    self._status_expire_ts = time.time() + 2.5

        # 2) drain calibrationOutput queue
        if self._calib_q is not None:
            while True:
                msg = self._calib_q.tryGet()
                if msg is None:
                    break
                cd = getattr(msg, "calibrationData", None)
                if not cd:
                    continue

                # stop collecting when calibration finishes
                self._collecting = False

                # store new calibration + diff
                self.new_calibration = getattr(cd, "newCalibration", None)
                self._last_calib_diff = getattr(cd, "calibrationDifference", None)

                # console messages
                print("Successfully calibrated")
                if self.new_calibration is not None:
                    print(f"New calibration: {self.new_calibration}")

                # auto-apply if enabled
                if self.auto_apply_new and self.new_calibration is not None:
                    try:
                        self._send_cmd(
                            dai.DynamicCalibrationControl.Commands.ApplyCalibration(
                                self.new_calibration
                            )
                        )
                        self.old_calibration, self.calibration = (
                            self.calibration,
                            self.new_calibration,
                        )
                        self.new_calibration = None
                    except Exception as e:
                        print(f"Failed to apply new calibration: {e}")
                    # after applying, you may want to reset device-side buffers
                    self._send_cmd(dai.DynamicCalibrationControl.Commands.ResetData())

                # pretty print the difference metrics (if available)
                q = self._last_calib_diff
                if q is not None:
                    rotmag = float(
                        np.sqrt(
                            q.rotationChange[0] ** 2
                            + q.rotationChange[1] ** 2
                            + q.rotationChange[2] ** 2
                        )
                    )
                    print(
                        f"Rotation difference: || r_current - r_new || = {rotmag} deg"
                    )
                    print(f"Mean Sampson error achievable = {q.sampsonErrorNew} px ")
                    print(f"Mean Sampson error current    = {q.sampsonErrorCurrent} px")
                    d = getattr(q, "depthErrorDifference", None)
                    if d and len(d) >= 4:
                        print(
                            "Theoretical Depth Error Difference "
                            f"@1m:{d[0]:.2f}%, 2m:{d[1]:.2f}%, 5m:{d[2]:.2f}%, 10m:{d[3]:.2f}%"
                        )

                    # Show recalibration modal with values + Euler angles
                    self._modal_kind = "recalib"
                    self._modal_payload = {
                        "values": getattr(q, "depthErrorDifference", None),
                        "angles": getattr(q, "rotationChange", None),
                    }
                    self._modal_expire_ts = time.time() + 3.5

        # 3) drain coverage (device -> host)
        if self._coverage_q is not None:
            while True:
                msg = self._coverage_q.tryGet()
                if msg is None:
                    break

                # coveragePerCellA: list/array of cell coverages in [0..1] or [0..100]
                cvec = getattr(msg, "coveragePerCellA", None)
                if cvec is not None:
                    try:
                        arr = np.asarray(cvec, dtype=np.float32).ravel()
                        if arr.size > 0:
                            self._coverage_vec = arr
                            # auto-detect units
                            mx = float(np.nanmax(arr))
                            pct_from_cells = float(
                                np.nanmean(arr) * (100.0 if mx <= 1.01 else 1.0)
                            )
                            self._coverage_pct = pct_from_cells
                    except Exception:
                        pass

                # optional: dataAcquired (0..1 or 0..100)
                da = getattr(msg, "dataAcquired", None)
                if da is not None:
                    try:
                        val = float(da)
                        self._data_acquired = val
                        if 0.0 <= val <= 1.0:
                            pct_from_da = val * 100.0
                        else:
                            pct_from_da = val
                        # take the max so bar never goes backwards
                        self._coverage_pct = max(self._coverage_pct, pct_from_da)
                    except Exception:
                        pass

        # 4) normal HUD push
        self._push_overlay(frame)

    # ---- public helpers ----
    def set_current_calibration(self, calib: Optional[dai.CalibrationHandler]):
        self.calibration = calib

    def on_new_calibration(self, calib: dai.CalibrationHandler):
        self.new_calibration = calib

    # ---- key handling ----
    def handle_key_press(self, key: int):
        # dismiss modal on any key
        if self._modal_kind is not None:
            self._modal_kind = None
            self._modal_expire_ts = 0.0
            self._modal_payload = {}

        # commands
        if key == ord("q"):
            self.wants_quit = True
            return

        if key == ord("r"):
            self._collecting_until = 0.0
            self._collecting = True
            self._coverage_vec = None
            self._coverage_pct = 0.0
            self._data_acquired = 0.0
            self._last_calib_diff = None
            self.last_quality = None
            self._send_cmd(dai.DynamicCalibrationControl.Commands.StartCalibration())
            return

        if key == ord("R"):
            self._collecting = False
            self._coverage_vec = None
            self._coverage_pct = 0.0
            self._data_acquired = 0.0
            self._last_calib_diff = None
            self.last_quality = None
            self._send_cmd(dai.DynamicCalibrationControl.Commands.Calibrate(force=True))
            return

        if key == ord("l"):
            self._collecting_until = time.time() + 2.0  # show bar only for 2s
            self._collecting = False
            self._coverage_vec = None
            self._coverage_pct = 0.0
            self._data_acquired = 0.0
            self._last_calib_diff = None
            self.last_quality = None
            self._flash_status("Loading images… move the rig to collect frames.", 2.0)
            self._send_cmd(dai.DynamicCalibrationControl.Commands.LoadImage())
            return

        if key == ord("n") and self.new_calibration:
            self._send_cmd(
                dai.DynamicCalibrationControl.Commands.ApplyCalibration(
                    self.new_calibration
                )
            )
            self.old_calibration, self.calibration = (
                self.calibration,
                self.new_calibration,
            )
            self.new_calibration = None
            self._flash_status("Applying NEW calibration…", 2.0)
            return

        if key == ord("o") and self.old_calibration:
            self._send_cmd(
                dai.DynamicCalibrationControl.Commands.ApplyCalibration(
                    self.old_calibration
                )
            )
            self.new_calibration, self.calibration, self.old_calibration = (
                self.calibration,
                self.old_calibration,
                None,
            )
            self._flash_status("Reverting to PREVIOUS calibration…", 2.0)
            return

        if key == ord("c"):
            self._collecting = False
            self._coverage_vec = None
            self._coverage_pct = 0.0
            self._data_acquired = 0.0
            self._last_calib_diff = None
            self.last_quality = None
            self._send_cmd(dai.DynamicCalibrationControl.Commands.CalibrationQuality())
            return

        if key == ord("C"):
            self._collecting = False
            self._coverage_vec = None
            self._coverage_pct = 0.0
            self._data_acquired = 0.0
            self._last_calib_diff = None
            self.last_quality = None
            self._send_cmd(
                dai.DynamicCalibrationControl.Commands.CalibrationQuality(force=True)
            )
            return

        if key == ord("h"):
            self._show_help = not self._show_help
            return

        # depth HUD controls
        if key in (ord("g"), ord("G")):
            self._hud_on = not self._hud_on
            return

        if self._last_depth is not None:
            step = max(1, int(0.01 * self._last_depth.shape[1]))  # ~1% width per tap
            cx, cy = (
                self._cursor_xy
                if self._cursor_xy is not None
                else (self._last_depth.shape[1] // 2, self._last_depth.shape[0] // 2)
            )
            if key in (ord("a"), ord("A")):
                cx -= step
            if key in (ord("d"), ord("D")):
                cx += step
            if key in (ord("w"), ord("W")):
                cy -= step
            if key in (ord("s"), ord("S")):
                cy += step
            if key in (ord("z"), ord("Z")):
                self._roi_half = max(1, self._roi_half - 1)
            if key in (ord("x"), ord("X")):
                self._roi_half += 1
            H, W = self._last_depth.shape[:2]
            self._cursor_xy = (int(np.clip(cx, 0, W - 1)), int(np.clip(cy, 0, H - 1)))

        # --- FLASH to EEPROM ---
        if key == ord("p"):
            # Flash NEW (or current) calibration
            if self._device is None:
                self._flash_status("No device bound — cannot flash.", 2.0)
                return
            calib_to_flash = self.new_calibration or self.calibration
            if calib_to_flash is None:
                self._flash_status("No NEW/current calibration to flash.", 2.0)
                return
            try:
                self._device.flashCalibration(calib_to_flash)
                self._flash_status("Flashed NEW/current calibration to EEPROM.", 2.0)
            except Exception as e:
                self._flash_status(f"Flash failed: {e}", 2.5)
            return

        if key == ord("k"):
            # Flash PREVIOUS calibration
            if self._device is None:
                self._flash_status("No device bound — cannot flash.", 2.0)
                return
            if self.old_calibration is None:
                self._flash_status("No PREVIOUS calibration to flash.", 2.0)
                return
            try:
                self._device.flashCalibration(self.old_calibration)
                self._flash_status("Flashed PREVIOUS calibration to EEPROM.", 2.0)
            except Exception as e:
                self._flash_status(f"Flash failed: {e}", 2.5)
            return

        if key == ord("f"):
            # Flash FACTORY calibration
            if self._device is None:
                self._flash_status("No device bound — cannot flash.", 2.0)
                return
            try:
                factory = self._device.readFactoryCalibration()
                self._device.flashCalibration(factory)
                self._flash_status("Flashed FACTORY calibration to EEPROM.", 2.0)
            except Exception as e:
                self._flash_status(f"Flash failed: {e}", 2.5)
            return
