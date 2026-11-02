import open3d as o3d
import numpy as np
from typing import List, Tuple, Optional
from scipy.spatial.transform import Rotation as R


class PointCloudMeasurement:
    """
    A class to measure volume and dimensions of object pointclouds
    """

    def __init__(self):
        # Note: parameters in millimeters
        self.distance_thr = 10
        self.sample_points = 3
        self.max_iterations = 500
        self.ransac_inlier_ratio_thr = 0.17

        self.voxel_size = 5
        self.points_buffer: np.ndarray = np.empty((0, 3), dtype=np.float64)
        self.points_buffer_plane: np.ndarray = np.empty((0, 3), dtype=np.float64)
        self.point_cloud: o3d.geometry.PointCloud = o3d.geometry.PointCloud()

        # For ground + HG
        self.point_cloud_tf: o3d.geometry.PointCloud = o3d.geometry.PointCloud()
        self.point_cloud_plane: o3d.geometry.PointCloud = o3d.geometry.PointCloud()
        self.cell = 5.0
        self.fill_iters = 1
        self.z_base = 5.0
        self.plane_eq = None
        self.center = None
        self.corners3d = None
        self.corners3d_table = None
        self.R_w2t = None
        self.t_w2t = None

        self.volume = None
        self.dimensions = None
        self.obb = None

        self.obb_pts = None
        self.obb_edges = None

        # Smoothing/filtering of bbox
        # OBB case
        self.prev_c = None
        self.prev_R = None
        self.prev_e = None

        # Smoothing parameters
        self.alpha_pos = 0.25
        self.alpha_rot = 0.20
        self.alpha_ext = 0.20

        # Robustness
        self.extent_delta_clamp = (
            20.0  # mm; max per-frame size change we allow in the filter
        )
        self.max_center_jump = (
            100.0  # mm; if raw center jumps more than this, reject update
        )

        # HG case
        self.hg_prev_center2 = None  # center of footprint in table XY frame
        self.hg_prev_yaw = None
        self.hg_prev_LW = None
        self.hg_prev_H = None

        self.extent_delta_clamp_hg = 20.0
        self.max_hg_center_jump = 100.0

        self.from_reset = False

        self.reinit_inlier_ratio = 0.70
        self.inlier_margin_mm = 10.0

    def _is_finite_like(self, x) -> bool:
        if x is None:
            return False
        try:
            arr = np.asarray(x, dtype=float)
        except Exception:
            return False
        return arr.size > 0 and np.all(np.isfinite(arr))

    def _need_init_state(self, *values) -> bool:
        """Return True if any of the provided values is missing/non-finite."""
        return not all(self._is_finite_like(v) for v in values)

    def reset_hg_filter(self):
        self.hg_prev_center2 = self.hg_prev_yaw = self.hg_prev_LW = self.hg_prev_H = (
            None
        )

    def reset_obb_filter(self):
        self.prev_c = self.prev_R = self.prev_e = None

    # ---- Small math helpers -----------------------------------------------------
    @staticmethod
    def _wrap_pi(a: float) -> float:
        """Wrap angle to (-pi, pi]."""
        a = (a + np.pi) % (2 * np.pi) - np.pi
        return float(a)

    @staticmethod
    def _yaw_vec(a: float) -> np.ndarray:
        """Unit vector [cos(a), sin(a)]."""
        return np.array([np.cos(a), np.sin(a)], float)

    @staticmethod
    def _yaw_from_vec(v: np.ndarray) -> float:
        return float(np.arctan2(v[1], v[0]))

    @staticmethod
    def _best_rect_candidate(
        yaw_raw: float, L: float, W: float, yaw_prev: float | None
    ):
        """
        Min-area rectangle has two equivalent orientations:
        (yaw, L,W)  or  (yaw+pi/2, W,L)
        Choose the one closest to yaw_prev (ignoring 180° flips).
        """
        if yaw_prev is None:
            return yaw_raw, np.array([L, W], float)

        u_prev = PointCloudMeasurement._yaw_vec(yaw_prev)

        # Candidate A
        a1 = yaw_raw
        u1 = PointCloudMeasurement._yaw_vec(a1)
        if np.dot(u1, u_prev) < 0:
            a1 += np.pi
            u1 = -u1
        s1 = np.dot(u1, u_prev)

        # Candidate B (swap L/W and rotate by 90°)
        a2 = yaw_raw + np.pi / 2.0
        u2 = PointCloudMeasurement._yaw_vec(a2)
        if np.dot(u2, u_prev) < 0:
            a2 += np.pi
            u2 = -u2
        s2 = np.dot(u2, u_prev)

        # Choose the candidate with the better alignment score
        if s2 > s1:
            return PointCloudMeasurement._wrap_pi(a2), np.array([W, L], float)
        else:
            return PointCloudMeasurement._wrap_pi(a1), np.array([L, W], float)

    @staticmethod
    def _rect_xy_from_params(
        center2: np.ndarray, yaw: float, L: float, W: float
    ) -> np.ndarray:
        """Return 4×2 CCW rectangle corners in table XY given center, yaw, L, W."""
        c = center2.astype(float)
        hx, hy = L * 0.5, W * 0.5
        R2 = np.array([[np.cos(yaw), -np.sin(yaw)], [np.sin(yaw), np.cos(yaw)]], float)
        local = np.array([[-hx, -hy], [hx, -hy], [hx, hy], [-hx, hy]], float)
        return c + local @ R2.T

    @staticmethod
    def _ensure_right_handed(R: np.ndarray) -> np.ndarray:
        """Make sure det(R)=+1 (proper rotation). If negative, flip Z axis."""
        if np.linalg.det(R) < 0:
            R = R.copy()
            R[:, 2] = -R[:, 2]
        return R

    @staticmethod
    def project_to_so3(M: np.ndarray) -> np.ndarray:
        """Return the closest proper rotation matrix to M (polar decomposition)."""
        U, _, Vt = np.linalg.svd(M)
        Rproj = U @ Vt
        if np.linalg.det(Rproj) < 0:  # enforce right-handedness
            U[:, -1] *= -1
            Rproj = U @ Vt
        return Rproj

    @staticmethod
    def _rot_to_quat(Rm: np.ndarray) -> np.ndarray:
        """Rotation matrix -> unit quaternion in [w,x,y,z]."""
        Rm = PointCloudMeasurement.project_to_so3(Rm)
        q_xyzw = R.from_matrix(Rm).as_quat()
        x, y, z, w = q_xyzw
        q_wxyz = np.array([w, x, y, z], float)
        return q_wxyz / (np.linalg.norm(q_wxyz) + 1e-12)

    @staticmethod
    def _quat_to_rot(q_wxyz: np.ndarray) -> np.ndarray:
        """Unit quaternion [w,x,y,z] -> rotation matrix"""
        w, x, y, z = q_wxyz
        q_xyzw = np.array([x, y, z, w], float)
        Rm = R.from_quat(q_xyzw).as_matrix()
        return Rm

    @staticmethod
    def _slerp(q0: np.ndarray, q1: np.ndarray, alpha: float) -> np.ndarray:
        """Spherical linear interpolation on unit quaternions"""
        if np.dot(q0, q1) < 0.0:
            q1 = -q1
        c = float(np.clip(np.dot(q0, q1), -1.0, 1.0))
        if c > 0.9995:
            q = (1.0 - alpha) * q0 + alpha * q1
            return q / (np.linalg.norm(q) + 1e-12)
        th = np.arccos(c)
        s0 = np.sin((1.0 - alpha) * th) / np.sin(th)
        s1 = np.sin(alpha * th) / np.sin(th)
        return s0 * q0 + s1 * q1

    @staticmethod
    def _align_axes_to_prev(
        R_new: np.ndarray, e_new: np.ndarray, R_ref: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Find permutation P and signs S so that R_new @ P @ S best aligns to R_ref.
        - R_new: 3x3 rotation (columns are OBB axes)
        - e_new: (3,) extents (mm)
        - R_ref: 3x3 previous rotation

        Returns:
            R_aligned (3x3): new rotation expressed with the same axis labeling as R_ref
            e_perm    (3,) : extents permuted to match those axes (always positive)
        """
        best = None
        for perm in ((0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0)):
            P = np.eye(3)[:, perm]
            Rp = R_new @ P
            M = R_ref.T @ Rp
            s = np.sign(np.diag(M))
            s[s == 0] = 1.0
            S = np.diag(s)
            Rps = Rp @ S
            score = float(np.trace(R_ref.T @ Rps))
            if (best is None) or (score > best[0]):
                best = (score, Rps, e_new[list(perm)])
        R_aligned = PointCloudMeasurement._ensure_right_handed(best[1])
        e_perm = best[2].astype(float)
        return R_aligned, e_perm

    @staticmethod
    def _build_corners(center: np.ndarray, R: np.ndarray, e: np.ndarray) -> np.ndarray:
        """
        Corner order (stable):
        0..3: bottom ring CCW, then 4..7: top ring CCW
        """
        hx, hy, hz = e / 2.0
        local = np.array(
            [
                [-hx, -hy, -hz],
                [hx, -hy, -hz],
                [hx, hy, -hz],
                [-hx, hy, -hz],
                [-hx, -hy, hz],
                [hx, -hy, hz],
                [hx, hy, hz],
                [-hx, hy, hz],
            ],
            dtype=float,
        )
        return center + local @ R.T

    @staticmethod
    def ratio_inside_box(
        points: np.ndarray, C: np.ndarray, R: np.ndarray, E: np.ndarray, margin=10.0
    ):
        """
        Returns ratio of points inside a box defined with:
        C: (3,) box center
        R: (3,3) box rotation
        E: (3,) box extents (mm)
        """
        H = E * 0.5 + margin
        Q = (points - C) @ R
        inside = (np.abs(Q) <= H + 1e-6).all(axis=1)
        return float(np.mean(inside))

    @staticmethod
    def box_from_corners(corners: np.ndarray):
        """
        Recovers box pose (C, R, E) from 8 corners (sorted bottom CCW then top CCW)
        """
        C = corners.mean(axis=0)
        ex = corners[1] - corners[0]
        ey = corners[3] - corners[0]
        ez = corners[4] - corners[0]
        Ex, Ey, Ez = np.linalg.norm(ex), np.linalg.norm(ey), np.linalg.norm(ez)
        X = ex / (Ex + 1e-12)
        Y = ey - np.dot(ey, X) * X
        Y /= np.linalg.norm(Y) + 1e-12
        Z = np.cross(X, Y)
        Z /= np.linalg.norm(Z) + 1e-12
        R = np.column_stack([X, Y, Z])
        E = np.array([Ex, Ey, Ez], float)
        return C, R, E

    def update_point_cloud(self, points: np.ndarray):
        """
        Updates the Open3D point cloud data using an internal buffer, which makes execution faster.

        Args:
            points (np.ndarray): A NumPy array of 3D points.
        """
        if points.shape[0] > self.points_buffer.shape[0]:
            self.points_buffer = np.empty((points.shape[0], 3), dtype=np.float64)

        np.copyto(self.points_buffer[: points.shape[0]], points)
        self.point_cloud.points = o3d.utility.Vector3dVector(
            self.points_buffer[: points.shape[0]]
        )

    def update_point_cloud_plane(self, points: np.ndarray):
        """
        Updates the Open3D point cloud data using an internal buffer, which makes execution faster.

        Args:
            points (np.ndarray): A NumPy array of 3D points.
        """
        if points.shape[0] > self.points_buffer_plane.shape[0]:
            self.points_buffer_plane = np.empty((points.shape[0], 3), dtype=np.float64)

        np.copyto(self.points_buffer_plane[: points.shape[0]], points)
        self.point_cloud_plane.points = o3d.utility.Vector3dVector(
            self.points_buffer_plane[: points.shape[0]]
        )

    def set_point_cloud(
        self, pcl_points: np.ndarray, colors: Optional[np.ndarray] = None
    ):
        """
        Sets the point cloud for the fitter, applying filtering and downsampling.

        Args:
            pcl_points (np.ndarray): The 3D points of the point cloud.
            colors (np.ndarray, optional): The colors corresponding to the points. Defaults to None.
        """
        self.update_point_cloud(pcl_points)

        if colors is not None and colors.shape == pcl_points.shape:
            self.point_cloud.colors = o3d.utility.Vector3dVector(colors)

        self.filter_point_cloud()
        idx = self.MAD_filtering(self.point_cloud, k=3)
        if idx.size == 0:
            return

        self.point_cloud = self.point_cloud.select_by_index(idx)

    def set_point_cloud_plane(self, pcl_points: np.ndarray):
        self.update_point_cloud_plane(pcl_points)
        self.filter_point_cloud_plane()

    def filter_point_cloud(self):
        self.point_cloud = self.point_cloud.voxel_down_sample(
            voxel_size=self.voxel_size
        )
        self.point_cloud, _ = self.point_cloud.remove_statistical_outlier(20, 0.1)

        points = np.asarray(self.point_cloud.points)

        # removes points with near z = 0 values
        eps = 1e-6
        mask = points[:, 2] > eps
        self.point_cloud = self.point_cloud.select_by_index(np.where(mask)[0])

    def filter_point_cloud_plane(self):
        self.point_cloud_plane = self.point_cloud_plane.voxel_down_sample(voxel_size=10)
        self.point_cloud_plane, _ = self.point_cloud_plane.remove_statistical_outlier(
            20, 0.1
        )

        points = np.asarray(self.point_cloud_plane.points)

        # removes points with near z = 0 values
        eps = 1e-6
        mask = points[:, 2] > eps
        self.point_cloud_plane = self.point_cloud_plane.select_by_index(
            np.where(mask)[0]
        )

    def MAD_filtering(self, pcl: o3d.geometry.PointCloud, k: int = 3):
        """
        Filters the point cloud using the Median Absolute Deviation (MAD) method.

        This method is robust to outliers and filters points that are far from the median.

        Args:
            pcl (o3d.geometry.PointCloud): The input point cloud.
            k (int, optional): The number of MADs to use as a threshold. Defaults to 3.

        Returns:
            Returns indices of inlier points after the filtering.
        """
        points = np.asarray(pcl.points)

        if points.shape[0] == 0:
            return np.empty(0, dtype=int)

        median_point = np.median(points, axis=0)
        distances = np.linalg.norm(points - median_point, axis=1)
        median_distance = np.median(distances)
        mad = np.median(np.abs(distances - median_distance))

        if mad == 0:
            mask = np.ones_like(distances, dtype=bool)
        else:
            mask = np.abs(distances - median_distance) < k * mad

        return np.flatnonzero(mask)

    def fit_plane(self, g) -> Tuple[Optional[np.ndarray], Optional[List[int]], bool]:
        """
        Fits a plane to the point cloud using RANSAC.

        Returns:
            tuple: A tuple containing the plane equation, the inlier indices, and a boolean indicating success.
        """
        if len(self.point_cloud_plane.points) < self.sample_points:
            return None, None, False

        try:
            plane_eq, plane_inliers = self.point_cloud_plane.segment_plane(
                self.distance_thr, self.sample_points, self.max_iterations
            )
        except RuntimeError:
            return None, None, False

        inlier_ratio = len(plane_inliers) / len(self.point_cloud_plane.points)
        # print('inlier ratio: ', inlier_ratio)
        if inlier_ratio >= self.ransac_inlier_ratio_thr:
            if self.is_ground_plane(g, plane_eq):
                return np.array(plane_eq), plane_inliers, True
        return None, None, False

    def is_ground_plane(self, g, plane_eq):
        """
        Checks if the plane represents the ground using the gravity vector from the IMU.
        If the plane is the ground, the normal of the plane and the gravity vector should be parallel (theta = 0).
        """
        n = plane_eq[:3]
        theta_max_deg = 10.0
        thr = -np.cos(np.deg2rad(theta_max_deg))
        ok = np.dot(n / np.linalg.norm(n), g / np.linalg.norm(g)) <= thr
        return ok

    def clear_plane(self):
        self.plane_eq = None
        self.R_w2t = None
        self.t_w2t = None

    def to_table_frame(self):
        """
        Transforms point cloud from world to table/plane frame
        """
        peq = np.asarray(self.plane_eq, dtype=np.float64).ravel()
        if peq.size != 4 or not np.all(np.isfinite(peq)):
            raise ValueError("Bad plane_eq (must be 4 finite coeffs)")

        a, b, c, d = peq
        n = np.array([a, b, c], dtype=np.float64)
        n_norm = np.linalg.norm(n)
        if not np.isfinite(n_norm) or n_norm == 0.0:
            raise ValueError("Bad plane normal")

        n /= n_norm
        d /= n_norm

        # Find point on the plane
        p0 = -d * n

        # Ensure the normal points up, away from the plane
        if self.center is not None:
            dotc = float(np.dot(self.center - p0, n))
            if np.isfinite(dotc) and dotc < 0.0:
                n = -n
                d = -d
                p0 = -d * n

        # Build an orthonormal basis (X, Y, Z) for the table frame
        ref = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        if abs(float(np.dot(n, ref))) > 0.99:
            ref = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        z_axis = n
        x_axis = np.cross(ref, n)
        nx = np.linalg.norm(x_axis)
        if nx == 0.0 or not np.isfinite(nx):
            ref = np.array([0.0, 1.0, 0.0], dtype=np.float64)
            x_axis = np.cross(ref, z_axis)
            nx = np.linalg.norm(x_axis)
            if nx == 0.0:
                raise ValueError("Could not build orthonormal basis")
        x_axis /= nx
        y_axis = np.cross(z_axis, x_axis)

        # R transforms vectors from the world frame to the table frame
        R = np.column_stack([x_axis, y_axis, z_axis]).T
        t = -R @ p0

        P = np.asarray(self.point_cloud.points, dtype=np.float64)
        if P.ndim != 2 or P.shape[1] != 3 or P.size == 0:
            raise ValueError("Empty or invalid object point cloud")

        P_tf = P @ R.T + t
        P_tf = np.ascontiguousarray(P_tf, dtype=np.float64)
        self.point_cloud_tf.points = o3d.utility.Vector3dVector(P_tf)

        if self.point_cloud.has_colors():
            self.point_cloud_tf.colors = self.point_cloud.colors

        self.R_w2t = R
        self.t_w2t = t

    def size_from_table_frame(self):
        pts = np.asarray(self.point_cloud_tf.points)
        z_rel = np.clip(pts[:, 2] - self.z_base, 0, None)
        H = float(np.percentile(z_rel, 98))
        L, W, rect_xy = self.min_area_rect_from_points(pts[:, :2])
        return L, W, H, rect_xy

    def convex_hull_2d(self, xy: np.ndarray):
        """
        Convex hull of 2D points
        Returns:
            Hull vertices as an (M, 2) array in CCW order
        """
        pts = np.unique(xy, axis=0)
        pts = pts[np.lexsort((pts[:, 1], pts[:, 0]))]

        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        lower = []
        for p in pts:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)
        upper = []
        for p in pts[::-1]:
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)
        return np.array(lower[:-1] + upper[:-1])

    def min_area_rect_from_points(self, xy: np.ndarray):
        hull = self.convex_hull_2d(xy)
        # With less than 3 unique XY points, we cannot form a polygon hull - fallback to AABB
        if hull.shape[0] < 3:
            mn, mx = xy.min(0), xy.max(0)
            L, W = mx - mn
            rect_xy = np.array(
                [[mn[0], mn[1]], [mx[0], mn[1]], [mx[0], mx[1]], [mn[0], mx[1]]],
                dtype=float,
            )
            if L < W:
                L, W = W, L
                rect_xy = rect_xy[[3, 0, 1, 2]]
            return float(L), float(W), rect_xy
        edges = np.diff(np.vstack([hull, hull[0]]), axis=0)
        angs = np.unique(np.mod(np.arctan2(edges[:, 1], edges[:, 0]), np.pi / 2))
        best = (np.inf, None)
        for th in angs:
            c, s = np.cos(th), np.sin(th)
            R = np.array([[c, -s], [s, c]])
            q = hull @ R.T
            mn, mx = q.min(0), q.max(0)
            area = (mx - mn).prod()
            if area < best[0]:
                best = (area, (mn, mx, R))
        mn, mx, R = best[1]
        rect = np.array(
            [[mn[0], mn[1]], [mx[0], mn[1]], [mx[0], mx[1]], [mn[0], mx[1]]]
        )
        rect_xy = rect @ R
        L, W = mx - mn
        if L < W:
            L, W = W, L
            rect_xy = rect_xy[[3, 0, 1, 2]]
        return float(L), float(W), rect_xy

    def points_in_poly(self, pts_xy: np.ndarray, poly_xy: np.ndarray):
        x, y = pts_xy[:, 0], pts_xy[:, 1]
        px, py = poly_xy[:, 0], poly_xy[:, 1]
        n = len(poly_xy)
        inside = np.zeros(len(pts_xy), dtype=bool)
        j = n - 1
        for i in range(n):
            xi, yi = px[i], py[i]
            xj, yj = px[j], py[j]
            cond = ((yi > y) != (yj > y)) & (
                x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
            )
            inside ^= cond
            j = i
        return inside

    def _grid_and_masks(self, polygon_xy, cell):
        xmin, ymin = polygon_xy.min(axis=0)
        xmax, ymax = polygon_xy.max(axis=0)
        nx = int(np.ceil((xmax - xmin) / cell))
        ny = int(np.ceil((ymax - ymin) / cell))
        cx = xmin + (np.arange(nx) + 0.5) * cell
        cy = ymin + (np.arange(ny) + 0.5) * cell
        CX, CY = np.meshgrid(cx, cy)
        inside_cells = self.points_in_poly(
            np.c_[CX.ravel(), CY.ravel()], polygon_xy
        ).reshape(ny, nx)
        return xmin, ymin, nx, ny, inside_cells

    def _assign_vertex_heights(
        self, pts, xmin, ymin, nx, ny, cell, inside_cells, z_base, fill_iters
    ):
        x, y, z = pts[:, 0], pts[:, 1], np.clip(pts[:, 2] - z_base, 0, None)
        Hv = np.full((ny + 1, nx + 1), -np.inf, float)
        i0 = np.floor((x - xmin) / cell).astype(int)
        j0 = np.floor((y - ymin) / cell).astype(int)
        for ii, jj, h in zip(i0, j0, z):
            if ii < 0 or jj < 0 or ii >= nx or jj >= ny:
                continue
            if not inside_cells[jj, ii]:
                continue
            Hv[jj, ii] = max(Hv[jj, ii], h)
            Hv[jj, ii + 1] = max(Hv[jj, ii + 1], h)
            Hv[jj + 1, ii] = max(Hv[jj + 1, ii], h)
            Hv[jj + 1, ii + 1] = max(Hv[jj + 1, ii + 1], h)
        Hv[~np.isfinite(Hv)] = 0.0
        mask_v = np.zeros_like(Hv, dtype=bool)
        mask_v[:-1, :-1] |= inside_cells
        mask_v[1:, :-1] |= inside_cells
        mask_v[:-1, 1:] |= inside_cells
        mask_v[1:, 1:] |= inside_cells
        for _ in range(fill_iters):
            Hpad = np.pad(Hv, 1, mode="edge")
            max8 = np.maximum.reduce(
                [
                    Hpad[0:-2, 0:-2],
                    Hpad[0:-2, 1:-1],
                    Hpad[0:-2, 2:],
                    Hpad[1:-1, 0:-2],
                    Hpad[1:-1, 2:],
                    Hpad[2:, 0:-2],
                    Hpad[2:, 1:-1],
                    Hpad[2:, 2:],
                ]
            )
            Hv = np.where((Hv == 0) & mask_v, max8, Hv)
        return Hv, mask_v

    def make_height_surface_grid(self, polygon_xy):
        pts = np.asarray(self.point_cloud_tf.points)
        xmin, ymin, nx, ny, inside = self._grid_and_masks(polygon_xy, self.cell)
        Hv, mask_v = self._assign_vertex_heights(
            pts, xmin, ymin, nx, ny, self.cell, inside, self.z_base, self.fill_iters
        )
        gx = xmin + np.arange(nx + 1) * self.cell
        gy = ymin + np.arange(ny + 1) * self.cell
        return dict(
            xmin=xmin,
            ymin=ymin,
            nx=nx,
            ny=ny,
            cell=self.cell,
            inside=inside,
            Hv=Hv,
            mask_v=mask_v,
            z_base=self.z_base,
            gx=gx,
            gy=gy,
        )

    def volume_from_height_grid(self, G):
        """Integrate the same top: two triangles per inside cell, vertex heights in Hv."""
        nx, ny, cell, inside, Hv = G["nx"], G["ny"], G["cell"], G["inside"], G["Hv"]
        Atri = 0.5 * cell * cell
        V = 0.0
        for j in range(ny):
            for i in range(nx):
                if not inside[j, i]:
                    continue
                h00 = Hv[j, i]
                h10 = Hv[j, i + 1]
                h11 = Hv[j + 1, i + 1]
                h01 = Hv[j + 1, i]
                V += Atri * (h00 + h10 + h11) / 3.0
                V += Atri * (h00 + h11 + h01) / 3.0
        return float(V)  # mm^3

    # --------------- Filtering bbox positions-------------------

    def get_measurement_OBB(self):
        """
        Object-oriented bbox with temporal stabilization/smoothing
        Pipeline:
        raw OBB -> axis alignment -> smoothing (center, extents, rotation) -> outlier rejection -> build corners
        """

        obb = self.point_cloud.get_minimal_oriented_bounding_box()
        c_new = np.asarray(obb.center, float)
        R_new = self._ensure_right_handed(np.asarray(obb.R, float))
        e_new = np.asarray(obb.extent, float)

        prev_c = self.prev_c
        prev_R = self.prev_R
        prev_e = self.prev_e
        from_reset = bool(self.from_reset)

        # Init for filtering
        need_init = from_reset or self._need_init_state(prev_c, prev_R, prev_e)
        if need_init:
            prev_c, prev_R, prev_e = c_new, R_new, e_new
            self.from_reset = False

        # Axis alignment to previous frame's axes
        R_aligned, e_perm = self._align_axes_to_prev(R_new, e_new, prev_R)

        # Filtering/smoothing
        # center EMA
        c_s = (1.0 - self.alpha_pos) * prev_c + self.alpha_pos * c_new

        # Rotation (SLERP on quaternions)
        q_prev = self._rot_to_quat(prev_R)
        q_new = self._rot_to_quat(R_aligned)
        q_s = self._slerp(q_prev, q_new, self.alpha_rot)
        R_s = self._quat_to_rot(q_s)

        # Extents - EMA
        delta_e = np.clip(
            e_perm - prev_e, -self.extent_delta_clamp, +self.extent_delta_clamp
        )
        e_s = np.maximum(prev_e + self.alpha_ext * delta_e, 1e-3)

        # Outlier rejection
        if np.linalg.norm(c_new - prev_c) > self.max_center_jump:
            c_s, R_s, e_s = prev_c, prev_R, prev_e

        self.obb_pts = self._build_corners(c_s, R_s, e_s)

        self.dimensions = (e_s / 10.0).astype(float)
        self.volume = float((e_s[0] * e_s[1] * e_s[2]) / 1000.0)
        self.prev_c, self.prev_R, self.prev_e = c_s, R_s, e_s

        # Sanity check if points inside the box
        P = np.asarray(self.point_cloud.points)
        inside_ratio = self.ratio_inside_box(
            P, c_s, R_s, e_s, margin=self.inlier_margin_mm
        )
        if inside_ratio < self.reinit_inlier_ratio:
            self.prev_c, self.prev_R, self.prev_e = c_new, R_new, e_new
            self.obb_pts = self._build_corners(self.prev_c, self.prev_R, self.prev_e)
            self.dimensions = (self.prev_e / 10.0).astype(float)
            self.volume = float(
                (self.prev_e[0] * self.prev_e[1] * self.prev_e[2]) / 1000.0
            )
            self.from_reset = True

    def get_measurement_groundHG(self):
        """
        Height-grid measurement with temporal stabilization/filtering.
        """

        if self.plane_eq is None:
            print("Ground plane not set!")
            return

        # Transform current object points to the table frame
        self.center = np.asarray(self.point_cloud.points).mean(axis=0)
        self.to_table_frame()

        L, W, H, rect_xy = self.size_from_table_frame()
        center2d = rect_xy.mean(axis=0)
        # Yaw (rot angle along z) from min-area rectangle on (X,Y)
        v = rect_xy[1] - rect_xy[0]
        yaw = float(np.arctan2(v[1], v[0]))

        yaw_can, LW_can = self._best_rect_candidate(yaw, L, W, self.hg_prev_yaw)
        L_can, W_can = float(LW_can[0]), float(LW_can[1])

        prev_center2 = self.hg_prev_center2
        prev_H = self.hg_prev_H
        prev_LW = self.hg_prev_LW
        prev_yaw = self.hg_prev_yaw
        from_reset = bool(self.from_reset)

        # Init filter
        need_init = from_reset or self._need_init_state(
            prev_center2, prev_H, prev_LW, prev_yaw
        )
        if need_init:
            prev_center2 = center2d
            prev_yaw = yaw_can
            prev_LW = np.array([L_can, W_can], float)
            prev_H = H
            self.from_reset = False

        # Filtering/smoothig
        c2_s = (1.0 - self.alpha_pos) * prev_center2 + self.alpha_pos * center2d

        u_prev = self._yaw_vec(prev_yaw)
        u_new = self._yaw_vec(yaw_can)
        u_s = (1.0 - self.alpha_rot) * u_prev + self.alpha_rot * u_new
        if np.allclose(u_s, 0):
            u_s = u_prev
        u_s /= np.linalg.norm(u_s) + 1e-12
        yaw_s = self._yaw_from_vec(u_s)

        dLW = np.clip(
            np.array([L_can, W_can]) - prev_LW,
            -self.extent_delta_clamp_hg,
            +self.extent_delta_clamp_hg,
        )
        LW_s = np.maximum(prev_LW + self.alpha_ext * dLW, 1e-3)

        # Outlier rejection (big center jump in plane)
        if np.linalg.norm(center2d - prev_center2) > self.max_hg_center_jump:
            c2_s, yaw_s, LW_s, H_s = prev_center2, prev_yaw, prev_LW, prev_H

        rect_xy_s = self._rect_xy_from_params(c2_s, yaw_s, LW_s[0], LW_s[1])

        G = self.make_height_surface_grid(rect_xy_s)
        Hv = G["Hv"]
        mask_v = G["mask_v"]
        if np.any(mask_v):
            H = float(np.percentile(Hv[mask_v], 98))

        # Smooth H
        dH = np.clip(
            float(H) - prev_H, -self.extent_delta_clamp_hg, +self.extent_delta_clamp_hg
        )
        H_s = max(prev_H + self.alpha_ext * dH, 1e-3)

        # Build filtered corners
        bottom_t = np.c_[rect_xy_s, np.full(4, self.z_base)]
        top_t = np.c_[rect_xy_s, np.full(4, H_s + self.z_base)]
        corners_t = np.vstack([bottom_t, top_t])  # 0..3 bottom CCW, 4..7 top

        # convert back to world/camera coords
        corners_w = (corners_t - self.t_w2t) @ self.R_w2t

        self.corners3d_table = corners_t
        self.corners3d = corners_w
        self.dimensions = np.array([LW_s[0], LW_s[1], H_s], float) / 10.0  # cm
        self.volume = self.volume_from_height_grid(G) / 1000.0  # cm^3

        self.hg_prev_center2 = c2_s
        self.hg_prev_yaw = yaw_s
        self.hg_prev_LW = LW_s
        self.hg_prev_H = H_s

        # Sanity check if points inside the box
        C, R, E = self.box_from_corners(self.corners3d)
        P = np.asarray(self.point_cloud.points)
        inside_ratio = self.ratio_inside_box(P, C, R, E, margin=self.inlier_margin_mm)
        if inside_ratio < self.reinit_inlier_ratio:
            self.from_reset = True
