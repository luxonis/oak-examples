import numpy as np
import open3d as o3d
from itertools import combinations
from typing import List, Tuple, Optional


class CuboidFitter:
    """
    A class to fit a 3D cuboid to a point cloud.

    This class takes a point cloud as input and fits a cuboid to it by finding
    three orthogonal planes. It can then calculate the dimensions and corners
    of the fitted cuboid.
    """

    def __init__(
        self,
        distance_threshold: float = 10,
        sample_points: int = 3,
        max_iterations: int = 500,
        voxel_size: float = 10,
        max_attempts: int = 20,
    ):
        """
        Initializes the CuboidFitter.

        Args:
            distance_threshold (float, optional): The maximum distance a point can be from a plane to be considered an inlier. Defaults to 10.
            sample_points (int, optional): The number of points to sample when fitting a plane. Defaults to 3.
            max_iterations (int, optional): The maximum number of iterations for the RANSAC algorithm. Defaults to 500.
            voxel_size (float, optional): The size of the voxels for downsampling the point cloud. Defaults to 10.
            max_attempts (int, optional): The maximum number of attempts to fit orthogonal planes. Defaults to 20.
        """
        self.distance_threshold: float = distance_threshold
        self.sample_points: int = sample_points
        self.max_iterations: int = max_iterations
        self.voxel_size: float = voxel_size
        self.max_attempts: int = max_attempts
        self.orthogonality_thr: float = 0.1
        self.point_cloud: o3d.geometry.PointCloud = o3d.geometry.PointCloud()
        self.points_buffer: np.ndarray = np.empty((0, 3), dtype=np.float64)
        self.line_set: o3d.geometry.LineSet = o3d.geometry.LineSet()
        self.all_planes: Optional[np.ndarray] = None
        self.corners: Optional[np.ndarray] = None
        self.center: Optional[np.ndarray] = None
        self.planes: List[np.ndarray] = []
        self.plane_points: List[o3d.geometry.PointCloud] = []
        self.reset()

    def update_point_cloud(self, points: np.ndarray) -> None:
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

    def reset(self) -> None:
        """
        Resets the fitter for a new frame, clearing all previously fitted planes and corners.
        """
        self.all_planes = None
        self.corners = None
        self.center = None
        self.planes = []
        self.plane_points = []

    def set_point_cloud(
        self, pcl_points: np.ndarray, colors: Optional[np.ndarray] = None
    ) -> None:
        """
        Sets the point cloud for the fitter, applying filtering and downsampling.

        Args:
            pcl_points (np.ndarray): The 3D points of the point cloud.
            colors (np.ndarray, optional): The colors corresponding to the points. Defaults to None.
        """
        self.center = pcl_points.mean(axis=0)
        self.update_point_cloud(pcl_points)
        if colors is not None and colors.size > 0:
            self.point_cloud.colors = o3d.utility.Vector3dVector(colors / 255.0)

        self.point_cloud = self.point_cloud.voxel_down_sample(
            voxel_size=self.voxel_size
        )
        self.point_cloud, _ = self.point_cloud.remove_statistical_outlier(40, 0.1)

        filtered_points, filtered_colors = self.MAD_filtering(self.point_cloud)
        if filtered_points.size == 0:
            return
        self.point_cloud.colors = o3d.utility.Vector3dVector(filtered_colors)
        self.point_cloud.points = o3d.utility.Vector3dVector(filtered_points)

    def MAD_filtering(
        self, pcl: o3d.geometry.PointCloud, k: int = 3
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Filters the point cloud using the Median Absolute Deviation (MAD) method.

        This method is robust to outliers and filters points that are far from the median.

        Args:
            pcl (o3d.geometry.PointCloud): The input point cloud.
            k (int, optional): The number of MADs to use as a threshold. Defaults to 3.

        Returns:
            tuple[np.ndarray, np.ndarray]: A tuple containing the filtered points and colors.
        """
        colors = np.asarray(pcl.colors)
        points = np.asarray(pcl.points)
        if points.shape[0] == 0:
            return np.array([]), np.array([])

        median_point = np.median(points, axis=0)
        distances = np.linalg.norm(points - median_point, axis=1)
        median_distance = np.median(distances)
        mad = np.median(np.abs(distances - median_distance))

        if mad == 0:
            mask = np.ones_like(distances, dtype=bool)
        else:
            mask = np.abs(distances - median_distance) < k * mad

        return points[mask], colors[mask]

    def distance_between_planes(
        self, plane1: np.ndarray, plane2: np.ndarray
    ) -> Optional[float]:
        """
        Calculates the distance between two parallel planes.

        Args:
            plane1 (np.ndarray): The equation of the first plane [a, b, c, d].
            plane2 (np.ndarray): The equation of the second plane [a, b, c, d].

        Returns:
            Optional[float]: The distance between the two planes, or None if they are not parallel.
        """
        normal1 = np.array(plane1[:3])
        normal2 = np.array(plane2[:3])
        norm1 = np.linalg.norm(normal1)
        norm2 = np.linalg.norm(normal2)
        if (
            norm1 == 0
            or norm2 == 0
            or not np.allclose(normal1 / norm1, normal2 / norm2, atol=1e-6)
        ):
            return None
        return abs(plane2[3] / norm2 - plane1[3] / norm1)

    def translate_planes(self, distances: np.ndarray) -> np.ndarray:
        """
        Translates multiple planes at once.

        Args:
            distances (np.ndarray): An array of distances to translate each plane.

        Returns:
            np.ndarray: An array of the translated plane equations.
        """
        planes = np.asarray(self.planes)
        normal = planes[:, :3]
        norm = np.linalg.norm(normal, axis=1, keepdims=True)

        s = np.sign(normal[:, 2])
        s[s == 0] = 1

        normalized_normal = normal / norm

        translated_d = planes[:, 3] - s * distances
        return np.column_stack((normalized_normal, translated_d))

    def intersect_planes(
        self,
        plane_eq1: np.ndarray,
        plane_eq2: np.ndarray,
        plane_eq3: np.ndarray,
        tol: float = 1e-6,
    ) -> Optional[np.ndarray]:
        """
        Finds the intersection point of three planes.

        Args:
            plane_eq1 (np.ndarray): The equation of the first plane.
            plane_eq2 (np.ndarray): The equation of the second plane.
            plane_eq3 (np.ndarray): The equation of the third plane.
            tol (float, optional): The tolerance for checking if the planes are parallel. Defaults to 1e-6.

        Returns:
            Optional[np.ndarray]: The intersection point, or None if the planes are parallel.
        """
        A = np.array([plane_eq1[:3], plane_eq2[:3], plane_eq3[:3]])
        B = -np.array([plane_eq1[3], plane_eq2[3], plane_eq3[3]])
        det_A = np.linalg.det(A)
        if np.abs(det_A) < tol:
            return None
        return np.linalg.solve(A, B)

    def dist_to_plane(self, points: np.ndarray, plane_eq: np.ndarray) -> np.ndarray:
        """
        Calculates the distances from multiple points to a plane.

        Args:
            points (np.ndarray): An array of 3D points.
            plane_eq (np.ndarray): The equation of the plane.

        Returns:
            np.ndarray: An array of distances from the points to the plane.
        """
        normal = np.array(plane_eq[:3])
        norm = np.linalg.norm(normal)
        if norm == 0:
            return np.zeros(points.shape[0])
        dot_product = np.dot(points, normal)
        return np.abs(dot_product + plane_eq[3]) / norm

    def fit_plane(self) -> Tuple[Optional[np.ndarray], Optional[List[int]], bool]:
        """
        Fits a plane to the point cloud using RANSAC.

        Returns:
            tuple: A tuple containing the plane equation, the inlier indices, and a boolean indicating success.
        """
        if len(self.point_cloud.points) < self.sample_points:
            return None, None, False

        try:
            plane_eq, plane_inliers = self.point_cloud.segment_plane(
                self.distance_threshold, self.sample_points, self.max_iterations
            )
        except RuntimeError:
            return None, None, False

        inlier_count = len(plane_inliers)
        if len(self.point_cloud.points) == 0:
            return None, None, False
        inlier_ratio = inlier_count / len(self.point_cloud.points)

        if inlier_ratio >= 0.2:
            return np.array(plane_eq), plane_inliers, True

        return None, None, False

    def check_orthogonal(self, plane_eq1: np.ndarray, plane_eq2: np.ndarray) -> bool:
        """
        Checks if two planes are orthogonal.

        Args:
            plane_eq1 (np.ndarray): The equation of the first plane.
            plane_eq2 (np.ndarray): The equation of the second plane.

        Returns:
            bool: True if the planes are orthogonal, False otherwise.
        """
        normal1 = np.array(plane_eq1[:3])
        normal2 = np.array(plane_eq2[:3])
        norm1 = np.linalg.norm(normal1)
        norm2 = np.linalg.norm(normal2)
        if norm1 == 0 or norm2 == 0:
            return False
        return bool(
            np.isclose(
                np.dot(normal1, normal2) / (norm1 * norm2),
                0,
                atol=self.orthogonality_thr,
            )
        )

    def fit_orthogonal_planes(self) -> bool:
        """
        Fits three orthogonal planes to the point cloud.

        This method iteratively fits planes and checks for orthogonality.

        Returns:
            bool: True if three orthogonal planes were successfully fitted, False otherwise.
        """
        if self.point_cloud is None or len(self.point_cloud.points) == 0:
            return False

        attempts = 0
        while len(self.planes) < 3 and attempts < self.max_attempts:
            plane_eq, inliers, success = self.fit_plane()
            if not success or inliers is None or plane_eq is None:
                if len(self.point_cloud.points) < self.sample_points:
                    return False
                attempts += 1
                continue

            attempts += 1
            if all(
                self.check_orthogonal(plane_eq, existing) for existing in self.planes
            ):
                self.planes.append(plane_eq)
                points = self.point_cloud.select_by_index(inliers)
                self.plane_points.append(points)
                self.point_cloud = self.point_cloud.select_by_index(
                    inliers, invert=True
                )

        return len(self.planes) == 3

    def calculate_dimensions_corners_MAD(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculates the dimensions and corners of the cuboid using a robust percentile-based method.

        Returns:
            tuple: A tuple containing the sorted dimensions and the corners of the cuboid.
        """
        for i, pcl in enumerate(self.plane_points):
            self.plane_points[i] = pcl.voxel_down_sample(voxel_size=self.voxel_size)

        distances = np.zeros(len(self.planes))
        for i, plane in enumerate(self.planes):
            if not self.plane_points or all(
                len(p.points) == 0 for p in self.plane_points
            ):
                return np.array([0, 0, 0]), np.array([])

            combined_points_list = [
                np.asarray(pts.points)
                for j, pts in enumerate(self.plane_points)
                if j != i and len(pts.points) > 0
            ]
            if not combined_points_list:
                distances[i] = 0
                continue
            combined_points = np.vstack(combined_points_list)

            plane_distances = self.dist_to_plane(combined_points, plane)
            median_dist = np.median(plane_distances)
            mad = np.median(np.abs(plane_distances - median_dist))

            threshold = median_dist + 2 * mad
            filtered_distances = [dist for dist in plane_distances if dist <= threshold]

            if not filtered_distances:
                distances[i] = median_dist
            else:
                distances[i] = np.percentile(filtered_distances, 98)

        translated_planes = self.translate_planes(distances)
        self.all_planes = np.vstack((self.planes, translated_planes))

        self.corners = []
        for plane_comb in combinations(self.all_planes, 3):
            point = self.intersect_planes(*plane_comb)
            if point is not None:
                self.corners.append(point)

        if len(self.corners) < 8:
            return np.array([0, 0, 0]), np.array([])

        dimensions = np.array(
            [
                self.distance_between_planes(self.planes[i], translated_planes[i])
                / 10.0
                for i in range(len(self.planes))
                if self.distance_between_planes(self.planes[i], translated_planes[i])
                is not None
            ]
        )

        if len(dimensions) < 3:
            return np.array([0, 0, 0]), np.array(self.corners)

        sorted_dims = np.sort(dimensions)[::-1]
        return sorted_dims, np.array(self.corners)

    def get_3d_lines_o3d(self, corners: np.ndarray) -> o3d.geometry.LineSet:
        """
        Generate 3D line segments for the edges of a rectangular cuboid given its corners,
        and returns them as an Open3D LineSet.

        Args:
            corners (np.ndarray): An array of 8 corner points.

        Returns:
            o3d.geometry.LineSet: An Open3D LineSet representing the cuboid edges.
        """
        if corners.shape[0] != 8:
            return o3d.geometry.LineSet()

        sorted_corners = self.sort_corners(corners)
        self.line_set.points = o3d.utility.Vector3dVector(sorted_corners)
        connections = [
            [0, 1],
            [1, 2],
            [2, 3],
            [3, 0],
            [4, 5],
            [5, 6],
            [6, 7],
            [7, 4],
            [0, 4],
            [1, 5],
            [2, 6],
            [3, 7],
        ]
        self.line_set.lines = o3d.utility.Vector2iVector(connections)
        self.line_set.paint_uniform_color([1, 0, 0])
        return self.line_set

    def create_R_from_normals(self) -> np.ndarray:
        """
        Creates a rotation matrix from the normal vectors of the three orthogonal planes.
        """
        if len(self.planes) < 3:
            return np.identity(3)

        normals = np.array([p[:3] for p in self.planes])
        normals /= np.linalg.norm(normals, axis=1)[:, np.newaxis]

        global_z = np.array([0, 0, 1])
        global_x = np.array([1, 0, 0])

        z_idx = np.argmax([np.abs(np.dot(normal, global_z)) for normal in normals])
        z_normal = normals[z_idx]

        remaining_indices = [i for i in range(3) if i != z_idx]
        if not remaining_indices:
            return np.identity(3)

        x_idx = max(
            remaining_indices, key=lambda i: np.abs(np.dot(normals[i], global_x))
        )
        x_normal = normals[x_idx]

        y_idx_list = [i for i in remaining_indices if i != x_idx]
        if not y_idx_list:
            y_normal = np.cross(z_normal, x_normal)
        else:
            y_idx = y_idx_list[0]
            y_normal = normals[y_idx]

        rotation_matrix = np.column_stack((x_normal, y_normal, z_normal))
        return rotation_matrix

    def sort_plane_clockwise(self, plane: np.ndarray) -> np.ndarray:
        """
        Sorts a plane's points in a consistent order (e.g., clockwise) based on the centroid.

        Args:
            plane (np.ndarray): 4x3 array of points in the plane.

        Returns:
            np.ndarray: Sorted 4x3 array of points in clockwise order.
        """
        center = np.mean(plane[:, :2], axis=0)
        angles = np.arctan2(plane[:, 1] - center[1], plane[:, 0] - center[0])
        return plane[np.argsort(angles)]

    def sort_corners(self, corners: np.ndarray) -> np.ndarray:
        """
        Sorts the corners of the cuboid in a consistent order.

        This is important for drawing the cuboid correctly.

        Args:
            corners (np.ndarray): An array of 8 corner points.

        Returns:
            np.ndarray: The sorted array of corner points.
        """
        if self.center is None:
            self.center = np.mean(corners, axis=0)

        R = self.create_R_from_normals()
        U, _, Vt = np.linalg.svd(R)
        R_orthogonal = np.dot(U, Vt)

        centered_corners = corners - self.center
        rotated_corners = np.dot(centered_corners, R_orthogonal)

        sorted_indices = np.argsort(rotated_corners[:, 2])
        bottom_plane = rotated_corners[sorted_indices[:4]]
        top_plane = rotated_corners[sorted_indices[4:]]

        bottom_plane = self.sort_plane_clockwise(bottom_plane)
        top_plane = self.sort_plane_clockwise(top_plane)
        sorted_corners = np.vstack([bottom_plane, top_plane])

        back_rotated = np.dot(sorted_corners, R_orthogonal.T)
        return back_rotated + self.center
