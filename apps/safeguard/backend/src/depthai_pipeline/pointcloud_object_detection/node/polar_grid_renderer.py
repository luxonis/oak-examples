import cv2
import numpy as np

from settings.settings import SpatialZone


class PolarGridRenderer:
    """
    Renders a polar occupancy grid visualization.
    Takes sector distances and rectangular zones, produces a BGR image.
    """

    # BGR colors
    COL_BG = (250, 250, 250)
    COL_FOV = (236, 236, 236)
    COL_BLIND = (228, 228, 228)
    COL_BLIND_HATCH = (208, 208, 208)
    COL_DANGER = (50, 50, 230)
    COL_WARNING = (0, 140, 250)
    COL_SAFE = (60, 160, 60)
    COL_SECTOR_LINE = (245, 245, 245)
    COL_RANGE_CELL = (222, 222, 222)
    COL_RANGE_ARC = (140, 140, 140)
    COL_TEXT = (50, 50, 50)
    _CODE_COLORS = (COL_SAFE, COL_WARNING, COL_DANGER)
    TOP_MARGIN_PX = 30
    BOTTOM_MARGIN_PX = 30
    ZONE_FILL_ALPHA = 0.2
    ZONE_OUTLINE_THICKNESS = 1

    def __init__(
        self,
        hfov_deg: float,
        max_range: float,
        min_visible_range: float,
        range_res: float,
        n_sectors: int,
        sector_angle_edges: np.ndarray,
        danger_zone: SpatialZone,
        warning_zone: SpatialZone,
        min_z_mm: float,
        img_w: int = 640,
        img_h: int = 480,
        render_scale: int = 2,
    ):
        self._hfov_deg = hfov_deg
        self._max_range = max_range
        self._min_visible_range = min_visible_range
        self._range_res = range_res
        self._n_sectors = n_sectors
        self._img_w = img_w
        self._img_h = img_h
        self._render_scale = render_scale

        self._danger_zone = danger_zone
        self._warning_zone = warning_zone
        self._min_z_mm = min_z_mm

        # Render geometry
        self._render_w = img_w * render_scale
        self._render_h = img_h * render_scale
        self._cx = self._render_w // 2
        self._cy = self._render_h - (self.BOTTOM_MARGIN_PX * render_scale)
        self._center = (self._cx, self._cy)
        self._scale = (
            self._render_h
            - ((self.TOP_MARGIN_PX + self.BOTTOM_MARGIN_PX) * render_scale)
        ) / max_range
        self._min_r = int(min_visible_range * self._scale)
        self._max_r = int(max_range * self._scale)
        self._fov_s = 270 - hfov_deg / 2
        self._fov_e = 270 + hfov_deg / 2
        self._label_angle = np.radians(hfov_deg / 2 + 4)

        # Pre-compute sector arc geometry
        self._sector_arc_sin = []
        self._sector_arc_cos = []
        self._sector_arc_sin_rev = []
        self._sector_arc_cos_rev = []
        self._sector_poly_buffers = []
        for idx in range(n_sectors):
            arc_angles = np.linspace(
                np.radians(sector_angle_edges[idx]),
                np.radians(sector_angle_edges[idx + 1]),
                12,
            )
            sins = np.sin(arc_angles)
            coss = np.cos(arc_angles)
            self._sector_arc_sin.append(sins)
            self._sector_arc_cos.append(coss)
            self._sector_arc_sin_rev.append(sins[::-1].copy())
            self._sector_arc_cos_rev.append(coss[::-1].copy())
            self._sector_poly_buffers.append(
                np.empty((2 * sins.shape[0], 2), dtype=np.int32)
            )

        self._sector_center_rad = np.radians(
            (sector_angle_edges[:-1] + sector_angle_edges[1:]) / 2.0
        )
        self._sector_center_sin = np.sin(self._sector_center_rad)
        self._sector_center_cos = np.cos(self._sector_center_rad)

        # Sector line endpoints
        sector_angles_rad = np.radians(sector_angle_edges)
        self._sector_endpoints = np.column_stack(
            [
                self._cx + self._max_r * np.sin(sector_angles_rad),
                self._cy - self._max_r * np.cos(sector_angles_rad),
            ]
        ).astype(np.int32)
        self._sector_inner_endpoints = np.column_stack(
            [
                self._cx + self._min_r * np.sin(sector_angles_rad),
                self._cy - self._min_r * np.cos(sector_angles_rad),
            ]
        ).astype(np.int32)

        self._precompute_zone_polygons()
        self._static_layer = self._build_static_layer()

    def render(self, sector_nearest: np.ndarray) -> np.ndarray:
        """Draw obstacle bands on the pre-rendered static layer. Returns BGR image."""

        if sector_nearest.shape[0] != self._n_sectors:
            raise ValueError(
                f"Expected sector_nearest with {self._n_sectors} entries, got {sector_nearest.shape}"
            )

        img = self._static_layer.copy()

        codes = self._zone_codes(sector_nearest)
        draw = np.flatnonzero(codes >= 0)
        band_mm = self._range_res
        for s in draw:
            code = int(codes[s])
            color = self._CODE_COLORS[code]
            d = float(sector_nearest[s])
            r_inner = max(self._min_visible_range, d - band_mm) * self._scale
            r_outer = min(self._max_range, d + band_mm) * self._scale
            sins = self._sector_arc_sin[s]
            coss = self._sector_arc_cos[s]
            n_arc = sins.shape[0]

            poly = self._sector_poly_buffers[s]
            poly[:n_arc, 0] = self._cx + r_outer * sins
            poly[:n_arc, 1] = self._cy - r_outer * coss
            poly[n_arc:, 0] = self._cx + r_inner * self._sector_arc_sin_rev[s]
            poly[n_arc:, 1] = self._cy - r_inner * self._sector_arc_cos_rev[s]

            cv2.fillPoly(img, [poly], color, cv2.LINE_AA)

        if self._render_scale > 1:
            img = cv2.resize(
                img, (self._img_w, self._img_h), interpolation=cv2.INTER_AREA
            )
        return img

    def _xz_to_render_pixel(self, x_mm: float, z_mm: float) -> tuple[int, int] | None:
        """Map ground-plane (x, z) in millimeters to supersampled render-space pixels."""
        if z_mm <= 1e-6:
            return None

        u = int(round(self._cx + self._scale * x_mm))
        v = int(round(self._cy - self._scale * z_mm))
        return (u, v)

    def _precompute_zone_polygons(self) -> None:
        """Cache zone rectangle polygons in supersampled render-space coordinates."""
        self._warning_polygon = self._build_zone_polygon(
            x_min_mm=self._warning_zone.x_min_mm,
            x_max_mm=self._warning_zone.x_max_mm,
            z_min_mm=self._min_z_mm,
            z_max_mm=self._warning_zone.distance_mm,
        )
        self._danger_polygon = self._build_zone_polygon(
            x_min_mm=self._danger_zone.x_min_mm,
            x_max_mm=self._danger_zone.x_max_mm,
            z_min_mm=self._min_z_mm,
            z_max_mm=self._danger_zone.distance_mm,
        )

    def _draw_zone_polygons(self, img: np.ndarray) -> None:
        if self._warning_polygon is not None:
            self._draw_polygon(
                img=img,
                polygon=self._warning_polygon,
                color_bgr=self.COL_WARNING,
                fill_alpha=self.ZONE_FILL_ALPHA,
                outline_thickness=self.ZONE_OUTLINE_THICKNESS,
            )
        if self._danger_polygon is not None:
            self._draw_polygon(
                img=img,
                polygon=self._danger_polygon,
                color_bgr=self.COL_DANGER,
                fill_alpha=self.ZONE_FILL_ALPHA,
                outline_thickness=self.ZONE_OUTLINE_THICKNESS,
            )

    def _build_zone_polygon(
        self,
        x_min_mm: float,
        x_max_mm: float,
        z_min_mm: float,
        z_max_mm: float,
    ) -> np.ndarray | None:
        """Clip a rectangular zone to the field of view in render pixels."""
        rect_xz = [
            (x_min_mm, z_min_mm),
            (x_max_mm, z_min_mm),
            (x_max_mm, z_max_mm),
            (x_min_mm, z_max_mm),
        ]
        poly_xz = self._clip_polygon_xz_to_fov(rect_xz)
        if len(poly_xz) < 3:
            return None

        pts: list[tuple[int, int]] = []
        for x_mm, z_mm in poly_xz:
            pt = self._xz_to_render_pixel(float(x_mm), float(z_mm))
            if pt is not None:
                pts.append(pt)
        if len(pts) < 3:
            return None
        return np.asarray(pts, dtype=np.int32)

    def _clip_polygon_xz_to_fov(
        self,
        polygon_xz: list[tuple[float, float]],
    ) -> list[tuple[float, float]]:
        if not polygon_xz:
            return []

        half_hfov_rad = np.deg2rad(self._hfov_deg / 2.0)
        slope = float(np.tan(half_hfov_rad))

        clipped = self._clip_polygon_halfplane(
            polygon_xz,
            a=1.0,
            b=-slope,
            c=0.0,
        )  # x <= z*tan(hfov/2)
        clipped = self._clip_polygon_halfplane(
            clipped,
            a=-1.0,
            b=-slope,
            c=0.0,
        )  # x >= -z*tan(hfov/2)
        return clipped

    @staticmethod
    def _clip_polygon_halfplane(
        polygon_xz: list[tuple[float, float]],
        a: float,
        b: float,
        c: float,
    ) -> list[tuple[float, float]]:
        """Keep polygon points satisfying ``a*x + b*z + c <= 0``."""
        if not polygon_xz:
            return []

        def value(point: tuple[float, float]) -> float:
            return a * point[0] + b * point[1] + c

        def inside(point: tuple[float, float]) -> bool:
            return value(point) <= 1e-6

        def intersect(
            p1: tuple[float, float],
            p2: tuple[float, float],
        ) -> tuple[float, float] | None:
            f1 = value(p1)
            f2 = value(p2)
            denom = f1 - f2
            if abs(denom) <= 1e-9:
                return None
            t = f1 / denom
            if t < 0.0 or t > 1.0:
                return None
            x = p1[0] + t * (p2[0] - p1[0])
            z = p1[1] + t * (p2[1] - p1[1])
            return (float(x), float(z))

        output: list[tuple[float, float]] = []
        for idx, curr in enumerate(polygon_xz):
            prev = polygon_xz[idx - 1]
            curr_in = inside(curr)
            prev_in = inside(prev)

            if curr_in:
                if not prev_in:
                    cross = intersect(prev, curr)
                    if cross is not None:
                        output.append(cross)
                output.append(curr)
            elif prev_in:
                cross = intersect(prev, curr)
                if cross is not None:
                    output.append(cross)

        return output

    @staticmethod
    def _draw_polygon(
        img: np.ndarray,
        polygon: np.ndarray,
        color_bgr: tuple[int, int, int],
        fill_alpha: float,
        outline_thickness: int,
    ) -> None:
        overlay = img.copy()
        cv2.fillPoly(overlay, [polygon], color_bgr, lineType=cv2.LINE_AA)
        cv2.addWeighted(overlay, fill_alpha, img, 1.0 - fill_alpha, 0.0, dst=img)
        cv2.polylines(
            img,
            [polygon],
            isClosed=True,
            color=color_bgr,
            thickness=outline_thickness,
            lineType=cv2.LINE_AA,
        )

    def _zone_codes(self, sector_nearest: np.ndarray) -> np.ndarray:
        """Vectorized per-sector zone classification.

        Returns an int8 array of per-sector codes:
            -1 = do not draw
             0 = safe
             1 = warning
             2 = danger
        """
        finite = np.isfinite(sector_nearest)
        dist = np.where(finite, sector_nearest, 0.0).astype(np.float32)
        x = dist * self._sector_center_sin
        z = dist * self._sector_center_cos

        visible = finite & (z >= self._min_z_mm)

        in_warning = (
            visible
            & (z <= self._warning_zone.distance_mm)
            & (x >= self._warning_zone.x_min_mm)
            & (x <= self._warning_zone.x_max_mm)
        )
        in_danger = (
            visible
            & (z <= self._danger_zone.distance_mm)
            & (x >= self._danger_zone.x_min_mm)
            & (x <= self._danger_zone.x_max_mm)
        )

        codes = np.full(self._n_sectors, -1, dtype=np.int8)
        codes[visible] = 0
        codes[in_warning] = 1
        codes[in_danger] = 2  # danger overrides warning where they overlap
        return codes

    def _build_static_layer(self) -> np.ndarray:
        """Build the cached static polar-grid background."""
        img = np.full((self._render_h, self._render_w, 3), self.COL_BG, dtype=np.uint8)

        fov_angles = np.linspace(
            -np.radians(self._hfov_deg / 2),
            np.radians(self._hfov_deg / 2),
            181,
        )
        outer_arc = np.column_stack(
            [
                self._cx + self._max_r * np.sin(fov_angles),
                self._cy - self._max_r * np.cos(fov_angles),
            ]
        ).astype(np.int32)
        inner_arc = np.column_stack(
            [
                self._cx + self._min_r * np.sin(fov_angles[::-1]),
                self._cy - self._min_r * np.cos(fov_angles[::-1]),
            ]
        ).astype(np.int32)
        fov_poly = np.vstack([outer_arc, inner_arc])
        cv2.fillPoly(img, [fov_poly], self.COL_FOV, cv2.LINE_AA)

        # Blind-zone wedge
        if self._min_r > 0:
            blind_mask = np.zeros((self._render_h, self._render_w), dtype=np.uint8)
            cv2.ellipse(
                blind_mask,
                self._center,
                (self._min_r, self._min_r),
                0,
                self._fov_s,
                self._fov_e,
                (255,),
                -1,
            )
            img[blind_mask > 0] = self.COL_BLIND

            hatch_layer = np.zeros_like(img)
            hatch_step = max(14, 16 * self._render_scale)
            for x0 in range(-self._render_h, self._render_w, hatch_step):
                cv2.line(
                    hatch_layer,
                    (x0, 0),
                    (x0 + self._render_h, self._render_h),
                    self.COL_BLIND_HATCH,
                    1,
                    cv2.LINE_AA,
                )
            hatch_mask = (blind_mask > 0) & (np.any(hatch_layer > 0, axis=2))
            img[hatch_mask] = hatch_layer[hatch_mask]

        # Ring outlines
        cv2.polylines(img, [outer_arc], False, self.COL_RANGE_ARC, 1, cv2.LINE_AA)
        cv2.polylines(img, [inner_arc[::-1]], False, self.COL_RANGE_ARC, 1, cv2.LINE_AA)
        cv2.line(
            img,
            (int(outer_arc[0, 0]), int(outer_arc[0, 1])),
            (int(inner_arc[-1, 0]), int(inner_arc[-1, 1])),
            self.COL_RANGE_ARC,
            1,
            cv2.LINE_AA,
        )
        cv2.line(
            img,
            (int(outer_arc[-1, 0]), int(outer_arc[-1, 1])),
            (int(inner_arc[0, 0]), int(inner_arc[0, 1])),
            self.COL_RANGE_ARC,
            1,
            cv2.LINE_AA,
        )

        # Sector lines
        for inner_ep, outer_ep in zip(
            self._sector_inner_endpoints, self._sector_endpoints
        ):
            cv2.line(
                img,
                (int(inner_ep[0]), int(inner_ep[1])),
                (int(outer_ep[0]), int(outer_ep[1])),
                self.COL_SECTOR_LINE,
                1,
                cv2.LINE_AA,
            )

        # Cell-resolution arcs
        for dist_mm in range(
            int(self._range_res), int(self._max_range) + 1, int(self._range_res)
        ):
            r = int(dist_mm * self._scale)
            if self._min_r < r <= self._max_r:
                cv2.ellipse(
                    img,
                    self._center,
                    (r, r),
                    0,
                    self._fov_s,
                    self._fov_e,
                    self.COL_RANGE_CELL,
                    1,
                    cv2.LINE_AA,
                )

        # Range arcs (every 1m) with labels
        for dist_mm in range(1000, int(self._max_range) + 1, 1000):
            r = int(dist_mm * self._scale)
            if self._min_r < r <= self._max_r:
                cv2.ellipse(
                    img,
                    self._center,
                    (r, r),
                    0,
                    self._fov_s,
                    self._fov_e,
                    self.COL_RANGE_ARC,
                    1,
                    cv2.LINE_AA,
                )
                lx = int(self._cx + r * np.sin(self._label_angle))
                ly = int(self._cy - r * np.cos(self._label_angle))
                cv2.putText(
                    img,
                    f"{dist_mm // 1000} m",
                    (lx, ly),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.35 * self._render_scale,
                    self.COL_TEXT,
                    max(1, self._render_scale - 1),
                    cv2.LINE_AA,
                )

        # Zone polygons are static context; runtime obstacle sectors are drawn over this layer.
        self._draw_zone_polygons(img)

        return img
