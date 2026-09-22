#!/usr/bin/env python3

import cv2
import numpy as np
import threading
import time
import warnings
import open3d as o3d

## GUI-related imports
import tkinter as tk
from tkinter import ttk

import depthai as dai

# Point cloud globals
latest_pointcloud_raw = None
latest_pointcloud_final = None
pointcloud_lock = threading.Lock()
vis_raw = None
vis_final = None
pointcloud_thread = None
pointcloud_running = False
needs_update_raw = False
needs_update_final = False

# Pause/unpause control
paused = False
pause_lock = threading.Lock()

# View reset control
first_update_raw = True
first_update_final = True

# Store latest frames for point cloud updates
latest_frames = {"raw": None, "final": None}

# Live update timing control
last_pointcloud_update_time = 0
POINTCLOUD_UPDATE_INTERVAL = 0.1  # Update every 100ms (10 FPS)

# To be set before starting the gui
CAMERA_INTRINSICS = {
    "fx": None,
    "fy": None,
    "cx": None,
    "cy": None,
}

# Point cloud parameters
pointcloud_params = {"enabled": True, "decimation": 1, "max_distance": 7500}


def is_paused():
    """Thread-safe check if point cloud updates are paused"""
    with pause_lock:
        return paused


def toggle_pause():
    """Toggle pause state and return new state"""
    global paused
    with pause_lock:
        paused = not paused
        return paused


def depth_to_pointcloud(depth_frame, intrinsics, max_distance=3000, decimation=1):
    """Convert depth frame to 3D point cloud"""
    if depth_frame is None or depth_frame.size == 0:
        return np.array([]), np.array([]), np.array([])

    h, w = depth_frame.shape
    fx, fy = intrinsics["fx"], intrinsics["fy"]
    cx, cy = intrinsics["cx"], intrinsics["cy"]

    # Create coordinate grids
    u, v = np.meshgrid(np.arange(0, w, decimation), np.arange(0, h, decimation))

    # Get corresponding depth values
    depth_decimated = depth_frame[::decimation, ::decimation]

    # Filter out invalid depths
    valid_mask = (depth_decimated > 0) & (depth_decimated < max_distance)

    if np.sum(valid_mask) == 0:
        return np.array([]), np.array([]), np.array([])

    # Extract valid coordinates and depths
    u_valid = u[valid_mask]
    v_valid = v[valid_mask]
    z_valid = depth_decimated[valid_mask]

    # Convert to 3D coordinates (in mm)
    x = (u_valid - cx) * z_valid / fx
    y = (v_valid - cy) * z_valid / fy
    z = z_valid

    return x, y, z


def create_colored_pointcloud(x, y, z):
    """Create an Open3D point cloud with colors based on depth"""
    if len(x) == 0:
        return o3d.geometry.PointCloud()

    # Create point cloud
    pcd = o3d.geometry.PointCloud()
    points = np.column_stack((x, y, z))
    pcd.points = o3d.utility.Vector3dVector(points)

    # Create colors based on depth (z values)
    if len(z) > 0:
        # Normalize z values to 0-1
        z_min, z_max = np.min(z), np.max(z)
        if z_max > z_min:
            z_norm = (z - z_min) / (z_max - z_min)
        else:
            z_norm = np.zeros_like(z)

        # Apply colormap (jet-like: blue -> cyan -> yellow -> red)
        colors = np.zeros((len(z), 3))
        for i, val in enumerate(z_norm):
            if val < 0.25:
                # Blue to cyan
                colors[i] = [0, 4 * val, 1]
            elif val < 0.5:
                # Cyan to green
                colors[i] = [0, 1, 1 - 4 * (val - 0.25)]
            elif val < 0.75:
                # Green to yellow
                colors[i] = [4 * (val - 0.5), 1, 0]
            else:
                # Yellow to red
                colors[i] = [1, 1 - 4 * (val - 0.75), 0]

        pcd.colors = o3d.utility.Vector3dVector(colors)

    return pcd


def pointcloud_visualization():
    """Open3D point cloud visualization - TWO windows: raw + final"""
    global vis_raw, vis_final, pointcloud_running
    global \
        latest_pointcloud_raw, \
        latest_pointcloud_final, \
        needs_update_raw, \
        needs_update_final
    global first_update_raw, first_update_final

    try:
        # Create two visualization windows
        vis_raw = o3d.visualization.Visualizer()
        vis_final = o3d.visualization.Visualizer()

        # Initialize raw window
        vis_raw.create_window(
            window_name="RAW Point Cloud", width=800, height=600, left=100, top=100
        )
        if vis_raw.get_render_option() is not None:
            vis_raw.get_render_option().background_color = np.array([0.1, 0.1, 0.1])
            vis_raw.get_render_option().point_size = 2.0
        else:
            warnings.warn(
                "If visualization fails on Linux or in WSL, try running with: export XDG_SESSION_TYPE=x11"
            )

        # Initialize final window
        vis_final.create_window(
            window_name="FINAL Point Cloud", width=800, height=600, left=950, top=100
        )
        if vis_final.get_render_option() is not None:
            vis_final.get_render_option().background_color = np.array([0.1, 0.1, 0.1])
            vis_final.get_render_option().point_size = 2.0
        else:
            warnings.warn(
                "If visualization fails on Linux or in WSL, try running with: export XDG_SESSION_TYPE=x11"
            )

        # Add initial empty point clouds
        empty_pcd = o3d.geometry.PointCloud()
        vis_raw.add_geometry(empty_pcd)
        vis_final.add_geometry(empty_pcd)

        print("✅ Open3D windows created - LIVE RAW vs FINAL comparison")
        print(
            "🎮 Use mouse to rotate/zoom, 'p' to pause/unpause, keys 1/2 for manual updates"
        )
        print("📌 CAMERA POSITION PRESERVED during live updates!")

        # Main visualization loop
        while pointcloud_running:
            with pointcloud_lock:
                # Update raw point cloud if needed
                if latest_pointcloud_raw is not None and needs_update_raw:
                    x, y, z, source = latest_pointcloud_raw

                    if len(x) > 0:
                        # Save current camera parameters BEFORE updating geometry
                        if not source.startswith("Manual") and not first_update_raw:
                            try:
                                view_control_raw = vis_raw.get_view_control()
                                camera_params_raw = view_control_raw.convert_to_pinhole_camera_parameters()
                            except Exception:
                                camera_params_raw = None
                        else:
                            camera_params_raw = None

                        # Clear and create new point cloud
                        vis_raw.clear_geometries()
                        pcd_raw = create_colored_pointcloud(x, y, z)
                        vis_raw.add_geometry(pcd_raw)

                        # Restore camera position for live updates, reset for manual/first updates
                        if source.startswith("Manual") or first_update_raw:
                            vis_raw.reset_view_point(True)
                            if first_update_raw:
                                first_update_raw = False
                                print("🔄 RAW: First update - camera view set")
                        elif camera_params_raw is not None:
                            try:
                                view_control_raw = vis_raw.get_view_control()
                                view_control_raw.convert_from_pinhole_camera_parameters(
                                    camera_params_raw, allow_arbitrary=True
                                )
                            except Exception:
                                pass  # If restore fails, just continue

                        if not is_paused() or source.startswith("Manual"):
                            status = "⏸️ PAUSED" if is_paused() else "🔴 LIVE"
                            print(
                                f"📊 {status} RAW point cloud: {len(x)} points ({source})"
                            )

                    needs_update_raw = False

                # Update final point cloud if needed
                if latest_pointcloud_final is not None and needs_update_final:
                    x, y, z, source = latest_pointcloud_final

                    if len(x) > 0:
                        # Save current camera parameters BEFORE updating geometry
                        if not source.startswith("Manual") and not first_update_final:
                            try:
                                view_control_final = vis_final.get_view_control()
                                camera_params_final = view_control_final.convert_to_pinhole_camera_parameters()
                            except Exception:
                                camera_params_final = None
                        else:
                            camera_params_final = None

                        # Clear and create new point cloud
                        vis_final.clear_geometries()
                        pcd_final = create_colored_pointcloud(x, y, z)
                        vis_final.add_geometry(pcd_final)

                        # Restore camera position for live updates, reset for manual/first updates
                        if source.startswith("Manual") or first_update_final:
                            vis_final.reset_view_point(True)
                            if first_update_final:
                                first_update_final = False
                                print("🔄 FINAL: First update - camera view set")
                        elif camera_params_final is not None:
                            try:
                                view_control_final = vis_final.get_view_control()
                                view_control_final.convert_from_pinhole_camera_parameters(
                                    camera_params_final, allow_arbitrary=True
                                )
                            except Exception:
                                pass  # If restore fails, just continue

                        if not is_paused() or source.startswith("Manual"):
                            status = "⏸️ PAUSED" if is_paused() else "🔴 LIVE"
                            print(
                                f"📊 {status} FINAL point cloud: {len(x)} points ({source})"
                            )

                    needs_update_final = False

            # Update visualization windows
            if not vis_raw.poll_events() or not vis_final.poll_events():
                break

            vis_raw.update_renderer()
            vis_final.update_renderer()

            # Short sleep to prevent high CPU usage
            time.sleep(0.01)

    except Exception as e:
        print(f"❌ Error in Open3D visualization: {e}")

    finally:
        # Clean up
        try:
            if vis_raw:
                vis_raw.destroy_window()
            if vis_final:
                vis_final.destroy_window()
        except Exception:
            pass
        print("🔄 Open3D windows closed")


def start_pointcloud_thread():
    """Start the point cloud visualization thread"""
    global pointcloud_thread, pointcloud_running

    if not pointcloud_running:
        try:
            # Test if Open3D can be initialized
            print("Testing Open3D compatibility...")
            test_vis = o3d.visualization.Visualizer()
            test_vis.create_window(
                window_name="Test", width=100, height=100, visible=False
            )
            test_vis.destroy_window()
            print("✅ Open3D test successful")

            # If test passes, start the real visualization
            pointcloud_running = True
            pointcloud_thread = threading.Thread(
                target=pointcloud_visualization, daemon=True
            )
            pointcloud_thread.start()
            print("🚀 Open3D LIVE point cloud visualization started")

        except Exception as e:
            print(f"❌ Open3D initialization failed: {e}")
            print(
                "Point cloud visualization disabled. You can still use 2D depth windows."
            )
            print("Try installing: sudo apt-get install libgl1-mesa-glx libglib2.0-0")
            return False

    return True


def stop_pointcloud_thread():
    """Stop the point cloud visualization thread"""
    global pointcloud_running, vis_raw, vis_final
    pointcloud_running = False
    if pointcloud_thread:
        pointcloud_thread.join(timeout=3)
    print("🔄 Open3D point cloud visualization stopped")


def update_pointcloud_live(source_key):
    """Automatically update point cloud from latest frame data (live mode)"""
    global latest_pointcloud_raw, latest_pointcloud_final, latest_frames
    global needs_update_raw, needs_update_final, last_pointcloud_update_time

    # Check if enough time has passed since last update
    current_time = time.time()
    if current_time - last_pointcloud_update_time < POINTCLOUD_UPDATE_INTERVAL:
        return

    if not pointcloud_params["enabled"] or not pointcloud_running or is_paused():
        return

    if source_key not in latest_frames or latest_frames[source_key] is None:
        return

    try:
        depth_frame = latest_frames[source_key]

        x, y, z = depth_to_pointcloud(
            depth_frame,
            CAMERA_INTRINSICS,
            max_distance=pointcloud_params["max_distance"],
            decimation=max(1, pointcloud_params["decimation"]),
        )

        with pointcloud_lock:
            if source_key == "raw":
                latest_pointcloud_raw = (x, y, z, "Live Raw")
                needs_update_raw = True
            elif source_key == "final":
                latest_pointcloud_final = (x, y, z, "Live Final")
                needs_update_final = True

        last_pointcloud_update_time = current_time

    except Exception as e:
        print(f"Error in live point cloud update from {source_key}: {e}")


def update_pointcloud_manual(source_key):
    """Manually update point cloud from stored frame data (works when paused)"""
    global latest_pointcloud_raw, latest_pointcloud_final, latest_frames
    global needs_update_raw, needs_update_final

    if not pointcloud_params["enabled"] or not pointcloud_running:
        print("❌ Point cloud visualization not enabled")
        return

    if source_key not in latest_frames or latest_frames[source_key] is None:
        print(f"❌ No {source_key} frame data available")
        return

    try:
        depth_frame = latest_frames[source_key]

        x, y, z = depth_to_pointcloud(
            depth_frame,
            CAMERA_INTRINSICS,
            max_distance=pointcloud_params["max_distance"],
            decimation=max(1, pointcloud_params["decimation"]),
        )

        with pointcloud_lock:
            if source_key == "raw":
                latest_pointcloud_raw = (x, y, z, "Manual Raw")
                needs_update_raw = True
            elif source_key == "final":
                latest_pointcloud_final = (x, y, z, "Manual Final")
                needs_update_final = True

        status = "⏸️ PAUSED" if is_paused() else "🔴 LIVE"
        print(
            f"🎯 {status} Manual update: {source_key.upper()} point cloud - {len(x)} points (view reset)"
        )

    except Exception as e:
        print(f"❌ Error updating point cloud from {source_key}: {e}")


class FilterGUI:
    def __init__(self, config_queue):
        self.config_queue = config_queue
        self.base_config_queue = None
        self.confidence_config_queue = None

        self.root = tk.Tk()
        self.root.title("ToF Depth Filters + Point Cloud")
        self.root.geometry("250x1000")

        # Filter parameters
        self.median_filter_var = tk.StringVar(value="MEDIAN_OFF")

        # Temporal filter parameters
        self.temporal_enable_var = tk.BooleanVar(value=True)
        self.temporal_persistency_var = tk.StringVar(value="VALID_1_IN_LAST_5")
        self.temporal_alpha_var = tk.DoubleVar(value=0.1)
        self.temporal_delta_var = tk.IntVar(value=40)

        # Speckle filter parameters
        self.speckle_enable_var = tk.BooleanVar(value=True)
        self.speckle_range_var = tk.IntVar(value=6)
        self.speckle_diff_threshold_var = tk.IntVar(value=130)

        # Spatial filter parameters
        self.spatial_enable_var = tk.BooleanVar(value=True)
        self.spatial_hole_filling_radius_var = tk.IntVar(value=2)
        self.spatial_alpha_var = tk.DoubleVar(value=0.5)
        self.spatial_delta_var = tk.IntVar(value=20)
        self.spatial_num_iterations_var = tk.IntVar(value=1)

        # Point cloud parameters
        self.pointcloud_enable_var = tk.BooleanVar(value=True)
        self.pointcloud_decimation_var = tk.IntVar(value=1)
        self.pointcloud_max_distance_var = tk.IntVar(value=7500)

        # ToF Base Configuration parameters
        self.phase_unwrap_threshold_var = tk.IntVar(value=100)
        self.phase_unwrap_level_var = tk.IntVar(value=4)
        self.enable_phase_unwrapping_var = tk.BooleanVar(value=True)
        self.enable_phase_shuffle_var = tk.BooleanVar(value=True)
        self.enable_temperature_correction_var = tk.BooleanVar(value=True)
        self.enable_fppn_correction_var = tk.BooleanVar(value=True)
        self.enable_optical_correction_var = tk.BooleanVar(value=True)
        self.enable_wiggle_correction_var = tk.BooleanVar(value=True)
        self.enable_distortion_correction_var = tk.BooleanVar(value=True)
        self.enable_burst_mode_var = tk.BooleanVar(value=False)

        # ToF Confidence Filter parameters
        self.confidence_threshold_var = tk.IntVar(value=128)

        self.create_widgets()

    def create_widgets(self):
        # Create a scrollable frame
        canvas = tk.Canvas(self.root)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # ToF Base Configuration
        tof_base_frame = ttk.LabelFrame(
            scrollable_frame, text="ToF Base Configuration", padding=10
        )
        tof_base_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(tof_base_frame, text="Phase Unwrap Threshold:").pack(anchor="w")
        phase_threshold_scale = ttk.Scale(
            tof_base_frame,
            from_=1,
            to=1000,
            variable=self.phase_unwrap_threshold_var,
            orient="horizontal",
            command=self.update_tof_base_config,
        )
        phase_threshold_scale.pack(fill="x", pady=2)

        phase_threshold_label = ttk.Label(tof_base_frame, text="100")
        phase_threshold_label.pack(anchor="w")

        def update_phase_threshold_label(*args):
            phase_threshold_label.config(
                text=f"{self.phase_unwrap_threshold_var.get()}"
            )

        self.phase_unwrap_threshold_var.trace("w", update_phase_threshold_label)

        ttk.Label(tof_base_frame, text="Phase Unwrapping Level:").pack(anchor="w")
        phase_level_scale = ttk.Scale(
            tof_base_frame,
            from_=0,
            to=10,
            variable=self.phase_unwrap_level_var,
            orient="horizontal",
            command=self.update_tof_base_config,
        )
        phase_level_scale.pack(fill="x", pady=2)

        phase_level_label = ttk.Label(tof_base_frame, text="4")
        phase_level_label.pack(anchor="w")

        def update_phase_level_label(*args):
            phase_level_label.config(text=f"{self.phase_unwrap_level_var.get()}")

        self.phase_unwrap_level_var.trace("w", update_phase_level_label)

        ttk.Checkbutton(
            tof_base_frame,
            text="Enable Phase Unwrapping",
            variable=self.enable_phase_unwrapping_var,
            command=self.update_tof_base_config,
        ).pack(anchor="w")

        ttk.Checkbutton(
            tof_base_frame,
            text="Enable Phase Shuffle Filter",
            variable=self.enable_phase_shuffle_var,
            command=self.update_tof_base_config,
        ).pack(anchor="w")

        ttk.Checkbutton(
            tof_base_frame,
            text="Enable Temperature Correction",
            variable=self.enable_temperature_correction_var,
            command=self.update_tof_base_config,
        ).pack(anchor="w")

        ttk.Checkbutton(
            tof_base_frame,
            text="Enable FPPN Correction",
            variable=self.enable_fppn_correction_var,
            command=self.update_tof_base_config,
        ).pack(anchor="w")

        ttk.Checkbutton(
            tof_base_frame,
            text="Enable Optical Correction",
            variable=self.enable_optical_correction_var,
            command=self.update_tof_base_config,
        ).pack(anchor="w")

        ttk.Checkbutton(
            tof_base_frame,
            text="Enable Wiggle Correction",
            variable=self.enable_wiggle_correction_var,
            command=self.update_tof_base_config,
        ).pack(anchor="w")

        ttk.Checkbutton(
            tof_base_frame,
            text="Enable Distortion Correction",
            variable=self.enable_distortion_correction_var,
            command=self.update_tof_base_config,
        ).pack(anchor="w")

        ttk.Checkbutton(
            tof_base_frame,
            text="Enable Burst Mode",
            variable=self.enable_burst_mode_var,
            command=self.update_tof_base_config,
        ).pack(anchor="w")

        # ToF Confidence Filter
        confidence_frame = ttk.LabelFrame(
            scrollable_frame, text="ToF Confidence Filter", padding=10
        )
        confidence_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(confidence_frame, text="Confidence Threshold:").pack(anchor="w")
        confidence_scale = ttk.Scale(
            confidence_frame,
            from_=0,
            to=255,
            variable=self.confidence_threshold_var,
            orient="horizontal",
            command=self.update_confidence_filter,
        )
        confidence_scale.pack(fill="x", pady=2)

        confidence_label = ttk.Label(confidence_frame, text="128")
        confidence_label.pack(anchor="w")

        def update_confidence_label(*args):
            confidence_label.config(text=f"{self.confidence_threshold_var.get()}")

        self.confidence_threshold_var.trace("w", update_confidence_label)

        # Point Cloud Controls (at top)
        pointcloud_frame = ttk.LabelFrame(
            scrollable_frame, text="Point Cloud Settings", padding=10
        )
        pointcloud_frame.pack(fill="x", padx=10, pady=5)

        pointcloud_enable_cb = ttk.Checkbutton(
            pointcloud_frame,
            text="Enable Point Clouds",
            variable=self.pointcloud_enable_var,
            command=self.update_pointcloud_settings,
        )
        pointcloud_enable_cb.pack(anchor="w")

        ttk.Label(pointcloud_frame, text="Decimation:").pack(anchor="w")
        decimation_scale = ttk.Scale(
            pointcloud_frame,
            from_=1,
            to=10,
            variable=self.pointcloud_decimation_var,
            orient="horizontal",
            command=self.update_pointcloud_settings,
        )
        decimation_scale.pack(fill="x", pady=2)

        decimation_label = ttk.Label(pointcloud_frame, text="1")
        decimation_label.pack(anchor="w")

        def update_decimation_label(*args):
            decimation_label.config(text=f"{self.pointcloud_decimation_var.get()}")

        self.pointcloud_decimation_var.trace("w", update_decimation_label)

        ttk.Label(pointcloud_frame, text="Max Distance (mm):").pack(anchor="w")
        max_distance_scale = ttk.Scale(
            pointcloud_frame,
            from_=1000,
            to=10000,
            variable=self.pointcloud_max_distance_var,
            orient="horizontal",
            command=self.update_pointcloud_settings,
        )
        max_distance_scale.pack(fill="x", pady=2)

        max_distance_label = ttk.Label(pointcloud_frame, text="7500")
        max_distance_label.pack(anchor="w")

        def update_max_distance_label(*args):
            max_distance_label.config(text=f"{self.pointcloud_max_distance_var.get()}")

        self.pointcloud_max_distance_var.trace("w", update_max_distance_label)

        # Control buttons
        control_frame = ttk.LabelFrame(
            scrollable_frame, text="Point Cloud Controls", padding=10
        )
        control_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(control_frame, text="Pause/Resume", command=self.toggle_pause).pack(
            side="left", padx=5
        )
        ttk.Button(
            control_frame, text="Update Raw", command=lambda: self.manual_update("raw")
        ).pack(side="left", padx=5)
        ttk.Button(
            control_frame,
            text="Update Final",
            command=lambda: self.manual_update("final"),
        ).pack(side="left", padx=5)

        # Median Filter
        median_frame = ttk.LabelFrame(
            scrollable_frame, text="Median Filter", padding=10
        )
        median_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(median_frame, text="Kernel Size:").pack(anchor="w")
        median_combo = ttk.Combobox(
            median_frame,
            textvariable=self.median_filter_var,
            values=["MEDIAN_OFF", "KERNEL_3x3", "KERNEL_5x5"],
            state="readonly",
        )
        median_combo.pack(fill="x", pady=2)
        median_combo.bind("<<ComboboxSelected>>", self.update_median_filter)

        # Temporal Filter
        temporal_frame = ttk.LabelFrame(
            scrollable_frame, text="Temporal Filter", padding=10
        )
        temporal_frame.pack(fill="x", padx=10, pady=5)

        temporal_enable_cb = ttk.Checkbutton(
            temporal_frame,
            text="Enable",
            variable=self.temporal_enable_var,
            command=self.update_temporal_filter,
        )
        temporal_enable_cb.pack(anchor="w")

        ttk.Label(temporal_frame, text="Persistency Mode:").pack(anchor="w")
        persistency_combo = ttk.Combobox(
            temporal_frame,
            textvariable=self.temporal_persistency_var,
            values=[
                "PERSISTENCY_OFF",
                "VALID_8_OUT_OF_8",
                "VALID_2_IN_LAST_3",
                "VALID_2_IN_LAST_4",
                "VALID_2_OUT_OF_8",
                "VALID_1_IN_LAST_2",
                "VALID_1_IN_LAST_5",
                "VALID_1_IN_LAST_8",
                "PERSISTENCY_INDEFINITELY",
            ],
            state="readonly",
        )
        persistency_combo.pack(fill="x", pady=2)
        persistency_combo.bind("<<ComboboxSelected>>", self.update_temporal_filter)

        ttk.Label(temporal_frame, text="Alpha:").pack(anchor="w")
        alpha_scale = ttk.Scale(
            temporal_frame,
            from_=0.0,
            to=1.0,
            variable=self.temporal_alpha_var,
            orient="horizontal",
            command=self.update_temporal_filter,
        )
        alpha_scale.pack(fill="x", pady=2)

        temporal_alpha_label = ttk.Label(temporal_frame, text="0.6")
        temporal_alpha_label.pack(anchor="w")

        def update_temporal_alpha_label(*args):
            temporal_alpha_label.config(text=f"{self.temporal_alpha_var.get():.2f}")

        self.temporal_alpha_var.trace("w", update_temporal_alpha_label)

        ttk.Label(temporal_frame, text="Delta:").pack(anchor="w")
        temporal_delta_scale = ttk.Scale(
            temporal_frame,
            from_=1,
            to=50,
            variable=self.temporal_delta_var,
            orient="horizontal",
            command=self.update_temporal_filter,
        )
        temporal_delta_scale.pack(fill="x", pady=2)

        temporal_delta_label = ttk.Label(temporal_frame, text="3")
        temporal_delta_label.pack(anchor="w")

        def update_temporal_delta_label(*args):
            temporal_delta_label.config(text=f"{self.temporal_delta_var.get()}")

        self.temporal_delta_var.trace("w", update_temporal_delta_label)

        # Speckle Filter
        speckle_frame = ttk.LabelFrame(
            scrollable_frame, text="Speckle Filter", padding=10
        )
        speckle_frame.pack(fill="x", padx=10, pady=5)

        speckle_enable_cb = ttk.Checkbutton(
            speckle_frame,
            text="Enable",
            variable=self.speckle_enable_var,
            command=self.update_speckle_filter,
        )
        speckle_enable_cb.pack(anchor="w")

        ttk.Label(speckle_frame, text="Speckle Range:").pack(anchor="w")
        speckle_range_scale = ttk.Scale(
            speckle_frame,
            from_=1,
            to=200,
            variable=self.speckle_range_var,
            orient="horizontal",
            command=self.update_speckle_filter,
        )
        speckle_range_scale.pack(fill="x", pady=2)

        speckle_range_label = ttk.Label(speckle_frame, text="50")
        speckle_range_label.pack(anchor="w")

        def update_speckle_range_label(*args):
            speckle_range_label.config(text=f"{self.speckle_range_var.get()}")

        self.speckle_range_var.trace("w", update_speckle_range_label)

        ttk.Label(speckle_frame, text="Difference Threshold:").pack(anchor="w")
        speckle_diff_scale = ttk.Scale(
            speckle_frame,
            from_=1,
            to=150,
            variable=self.speckle_diff_threshold_var,
            orient="horizontal",
            command=self.update_speckle_filter,
        )
        speckle_diff_scale.pack(fill="x", pady=2)

        speckle_diff_label = ttk.Label(speckle_frame, text="2")
        speckle_diff_label.pack(anchor="w")

        def update_speckle_diff_label(*args):
            speckle_diff_label.config(text=f"{self.speckle_diff_threshold_var.get()}")

        self.speckle_diff_threshold_var.trace("w", update_speckle_diff_label)

        # Spatial Filter
        spatial_frame = ttk.LabelFrame(
            scrollable_frame, text="Spatial Filter", padding=10
        )
        spatial_frame.pack(fill="x", padx=10, pady=5)

        spatial_enable_cb = ttk.Checkbutton(
            spatial_frame,
            text="Enable",
            variable=self.spatial_enable_var,
            command=self.update_spatial_filter,
        )
        spatial_enable_cb.pack(anchor="w")

        ttk.Label(spatial_frame, text="Hole Filling Radius:").pack(anchor="w")
        spatial_hole_scale = ttk.Scale(
            spatial_frame,
            from_=0,
            to=10,
            variable=self.spatial_hole_filling_radius_var,
            orient="horizontal",
            command=self.update_spatial_filter,
        )
        spatial_hole_scale.pack(fill="x", pady=2)

        spatial_hole_label = ttk.Label(spatial_frame, text="2")
        spatial_hole_label.pack(anchor="w")

        def update_spatial_hole_label(*args):
            spatial_hole_label.config(
                text=f"{self.spatial_hole_filling_radius_var.get()}"
            )

        self.spatial_hole_filling_radius_var.trace("w", update_spatial_hole_label)

        ttk.Label(spatial_frame, text="Alpha:").pack(anchor="w")
        spatial_alpha_scale = ttk.Scale(
            spatial_frame,
            from_=0.0,
            to=1.0,
            variable=self.spatial_alpha_var,
            orient="horizontal",
            command=self.update_spatial_filter,
        )
        spatial_alpha_scale.pack(fill="x", pady=2)

        spatial_alpha_label = ttk.Label(spatial_frame, text="0.5")
        spatial_alpha_label.pack(anchor="w")

        def update_spatial_alpha_label(*args):
            spatial_alpha_label.config(text=f"{self.spatial_alpha_var.get():.2f}")

        self.spatial_alpha_var.trace("w", update_spatial_alpha_label)

        ttk.Label(spatial_frame, text="Delta:").pack(anchor="w")
        spatial_delta_scale = ttk.Scale(
            spatial_frame,
            from_=1,
            to=20,
            variable=self.spatial_delta_var,
            orient="horizontal",
            command=self.update_spatial_filter,
        )
        spatial_delta_scale.pack(fill="x", pady=2)

        spatial_delta_label = ttk.Label(spatial_frame, text="3")
        spatial_delta_label.pack(anchor="w")

        def update_spatial_delta_label(*args):
            spatial_delta_label.config(text=f"{self.spatial_delta_var.get()}")

        self.spatial_delta_var.trace("w", update_spatial_delta_label)

        ttk.Label(spatial_frame, text="Number of Iterations:").pack(anchor="w")
        spatial_iter_scale = ttk.Scale(
            spatial_frame,
            from_=1,
            to=10,
            variable=self.spatial_num_iterations_var,
            orient="horizontal",
            command=self.update_spatial_filter,
        )
        spatial_iter_scale.pack(fill="x", pady=2)

        spatial_iter_label = ttk.Label(spatial_frame, text="1")
        spatial_iter_label.pack(anchor="w")

        def update_spatial_iter_label(*args):
            spatial_iter_label.config(text=f"{self.spatial_num_iterations_var.get()}")

        self.spatial_num_iterations_var.trace("w", update_spatial_iter_label)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def update_tof_base_config(self, event=None):
        """Update ToF base configuration"""
        if self.base_config_queue is None:
            return

        try:
            config = dai.ToFConfig()
            config.phaseUnwrapErrorThreshold = self.phase_unwrap_threshold_var.get()
            config.phaseUnwrappingLevel = self.phase_unwrap_level_var.get()
            config.enablePhaseUnwrapping = self.enable_phase_unwrapping_var.get()
            config.enablePhaseShuffleTemporalFilter = (
                self.enable_phase_shuffle_var.get()
            )
            config.enableTemperatureCorrection = (
                self.enable_temperature_correction_var.get()
            )
            config.enableFPPNCorrection = self.enable_fppn_correction_var.get()
            config.enableOpticalCorrection = self.enable_optical_correction_var.get()
            config.enableWiggleCorrection = self.enable_wiggle_correction_var.get()
            config.enableDistortionCorrection = (
                self.enable_distortion_correction_var.get()
            )
            config.enableBurstMode = self.enable_burst_mode_var.get()

            self.base_config_queue.send(config)

            corrections = []
            if config.enableTemperatureCorrection:
                corrections.append("Temperature")
            if config.enableFPPNCorrection:
                corrections.append("FPPN")
            if config.enableOpticalCorrection:
                corrections.append("Optical")
            if config.enableWiggleCorrection:
                corrections.append("Wiggle")
            if config.enableDistortionCorrection:
                corrections.append("Distortion")

            corrections_str = ", ".join(corrections) if corrections else "None"

            print("ToF Base config updated:")
            print(
                f"  Phase unwrap: threshold={config.phaseUnwrapErrorThreshold}, level={config.phaseUnwrappingLevel}"
            )
            print(f"  Phase unwrapping: {config.enablePhaseUnwrapping}")
            print(f"  Phase shuffle filter: {config.enablePhaseShuffleTemporalFilter}")
            print(f"  Corrections enabled: {corrections_str}")
            print(f"  Burst mode: {config.enableBurstMode}")

        except Exception as e:
            print(f"Error updating ToF base config: {e}")

    def update_confidence_filter(self, event=None):
        """Update ToF confidence filter"""
        if self.confidence_config_queue is None:
            return

        try:
            config = dai.ToFDepthConfidenceFilterConfig()
            config.confidenceThreshold = self.confidence_threshold_var.get()

            self.confidence_config_queue.send(config)
            print(f"Confidence filter updated: threshold={config.confidenceThreshold}")
        except Exception as e:
            print(f"Error updating confidence filter: {e}")

    def update_pointcloud_settings(self, event=None):
        """Update point cloud settings"""
        global pointcloud_params
        pointcloud_params["enabled"] = self.pointcloud_enable_var.get()
        pointcloud_params["decimation"] = self.pointcloud_decimation_var.get()
        pointcloud_params["max_distance"] = self.pointcloud_max_distance_var.get()

        if pointcloud_params["enabled"] and not pointcloud_running:
            start_pointcloud_thread()
        elif not pointcloud_params["enabled"] and pointcloud_running:
            stop_pointcloud_thread()

        print(
            f"Point cloud settings updated: enabled={pointcloud_params['enabled']}, "
            f"decimation={pointcloud_params['decimation']}, max_distance={pointcloud_params['max_distance']}"
        )

    def toggle_pause(self):
        """Toggle pause/resume for point cloud updates"""
        new_state = toggle_pause()
        status = "⏸️ PAUSED" if new_state else "🔴 LIVE"
        print(f"{status} Point cloud updates {'paused' if new_state else 'resumed'}")

    def manual_update(self, source):
        """Manually update point cloud"""
        update_pointcloud_manual(source)

    def get_median_filter_params(self):
        filter_map = {
            "MEDIAN_OFF": dai.node.ImageFilters.MedianFilterParams.MEDIAN_OFF,
            "KERNEL_3x3": dai.node.ImageFilters.MedianFilterParams.KERNEL_3x3,
            "KERNEL_5x5": dai.node.ImageFilters.MedianFilterParams.KERNEL_5x5,
            "KERNEL_7x7": dai.node.ImageFilters.MedianFilterParams.KERNEL_7x7,
        }
        return filter_map[self.median_filter_var.get()]

    def get_temporal_filter_params(self):
        params = dai.node.ImageFilters.TemporalFilterParams()
        params.enable = self.temporal_enable_var.get()

        persistency_map = {
            "PERSISTENCY_OFF": dai.filters.params.TemporalFilter.PersistencyMode.PERSISTENCY_OFF,
            "VALID_8_OUT_OF_8": dai.filters.params.TemporalFilter.PersistencyMode.VALID_8_OUT_OF_8,
            "VALID_2_IN_LAST_3": dai.filters.params.TemporalFilter.PersistencyMode.VALID_2_IN_LAST_3,
            "VALID_2_IN_LAST_4": dai.filters.params.TemporalFilter.PersistencyMode.VALID_2_IN_LAST_4,
            "VALID_2_OUT_OF_8": dai.filters.params.TemporalFilter.PersistencyMode.VALID_2_OUT_OF_8,
            "VALID_1_IN_LAST_2": dai.filters.params.TemporalFilter.PersistencyMode.VALID_1_IN_LAST_2,
            "VALID_1_IN_LAST_5": dai.filters.params.TemporalFilter.PersistencyMode.VALID_1_IN_LAST_5,
            "VALID_1_IN_LAST_8": dai.filters.params.TemporalFilter.PersistencyMode.VALID_1_IN_LAST_8,
            "PERSISTENCY_INDEFINITELY": dai.filters.params.TemporalFilter.PersistencyMode.PERSISTENCY_INDEFINITELY,
        }
        params.persistencyMode = persistency_map[self.temporal_persistency_var.get()]
        params.alpha = self.temporal_alpha_var.get()
        params.delta = self.temporal_delta_var.get()
        return params

    def get_speckle_filter_params(self):
        params = dai.node.ImageFilters.SpeckleFilterParams()
        params.enable = self.speckle_enable_var.get()
        params.speckleRange = self.speckle_range_var.get()
        params.differenceThreshold = self.speckle_diff_threshold_var.get()
        return params

    def get_spatial_filter_params(self):
        params = dai.node.ImageFilters.SpatialFilterParams()
        params.enable = self.spatial_enable_var.get()
        params.holeFillingRadius = self.spatial_hole_filling_radius_var.get()
        params.alpha = self.spatial_alpha_var.get()
        params.delta = self.spatial_delta_var.get()
        params.numIterations = self.spatial_num_iterations_var.get()
        return params

    def update_temporal_filter(self, event=None):
        params = self.get_temporal_filter_params()
        config = dai.ImageFiltersConfig().updateFilterAtIndex(index=0, params=params)
        self.config_queue.send(config)
        print(f"Temporal filter at index 0 updated: {params}")

    def update_speckle_filter(self, event=None):
        params = self.get_speckle_filter_params()
        config = dai.ImageFiltersConfig().updateFilterAtIndex(index=1, params=params)
        self.config_queue.send(config)
        print(f"Speckle filter at index 1 updated: {params}")

    def update_spatial_filter(self, event=None):
        params = self.get_spatial_filter_params()
        config = dai.ImageFiltersConfig().updateFilterAtIndex(index=2, params=params)
        self.config_queue.send(config)
        print(f"Spatial filter at index 2 updated: {params}")

    def update_median_filter(self, event=None):
        params = self.get_median_filter_params()
        config = dai.ImageFiltersConfig().updateFilterAtIndex(index=3, params=params)
        self.config_queue.send(config)
        print(f"Median filter at index 3 updated: {params}")

    def run(self):
        self.root.mainloop()


def get_initial_filter_params():
    speckle_params = dai.node.ImageFilters.SpeckleFilterParams()
    speckle_params.enable = False
    speckle_params.speckleRange = 50
    speckle_params.differenceThreshold = 2

    temporal_params = dai.node.ImageFilters.TemporalFilterParams()
    temporal_params.enable = False
    temporal_params.persistencyMode = (
        dai.filters.params.TemporalFilter.PersistencyMode.PERSISTENCY_OFF
    )
    temporal_params.alpha = 0.6
    temporal_params.delta = 3

    spatial_params = dai.node.ImageFilters.SpatialFilterParams()
    spatial_params.enable = False
    spatial_params.holeFillingRadius = 2
    spatial_params.alpha = 0.5
    spatial_params.delta = 3
    spatial_params.numIterations = 1

    median_params = dai.node.ImageFilters.MedianFilterParams.MEDIAN_OFF

    return [speckle_params, temporal_params, spatial_params, median_params]


def colorizeDepth(frameDepth: np.ndarray) -> np.ndarray:
    invalidMask = frameDepth == 0  # zero depth is invalid

    # Log the depth, minDepth and maxDepth
    try:
        minDepth = np.percentile(frameDepth[frameDepth != 0], 3)
        maxDepth = np.percentile(frameDepth[frameDepth != 0], 95)
        logDepth = np.log(frameDepth, where=frameDepth != 0)
        logMinDepth = np.log(minDepth)
        logMaxDepth = np.log(maxDepth)
        np.nan_to_num(logDepth, copy=False, nan=logMinDepth)
        # Clip the values to be in the 0-255 range
        logDepth = np.clip(logDepth, logMinDepth, logMaxDepth)

        # Interpolate only valid logDepth values, setting the rest based on the mask
        depthFrameColor = np.interp(logDepth, (logMinDepth, logMaxDepth), (0, 255))
        depthFrameColor = np.nan_to_num(depthFrameColor)
        depthFrameColor = depthFrameColor.astype(np.uint8)
        depthFrameColor = cv2.applyColorMap(depthFrameColor, cv2.COLORMAP_JET)
        # Set invalid depth pixels to black
        depthFrameColor[invalidMask] = 0

        # Add status overlay
        status_text = "PAUSED" if is_paused() else "LIVE"
        status_color = (0, 255, 255) if is_paused() else (0, 255, 0)
        cv2.putText(
            depthFrameColor,
            f"Point Clouds: {status_text}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            status_color,
            2,
        )

    except IndexError:
        # Frame is likely empty
        depthFrameColor = np.zeros(
            (frameDepth.shape[0], frameDepth.shape[1], 3), dtype=np.uint8
        )
    except Exception as e:
        raise e
    return depthFrameColor


def camera_pipeline(gui):
    pipeline = dai.Pipeline()

    # ToF node
    socket, preset_mode = (
        dai.CameraBoardSocket.CAM_A,
        dai.ImageFiltersPresetMode.TOF_MID_RANGE,
    )
    tof = pipeline.create(dai.node.ToF).build(socket, preset_mode)

    tofSocket = tof.tofBaseNode.getBoardSocket()
    calibration_handler = pipeline.getDefaultDevice().readCalibration()
    intrinsics = calibration_handler.getCameraIntrinsics(tofSocket)

    CAMERA_INTRINSICS["fx"] = intrinsics[0][0]
    CAMERA_INTRINSICS["fy"] = intrinsics[1][1]
    CAMERA_INTRINSICS["cx"] = intrinsics[0][2]
    CAMERA_INTRINSICS["cy"] = intrinsics[1][2]

    print("Found intrinsics:")
    print(f"  fx: {intrinsics[0][0]}")
    print(f"  fy: {intrinsics[1][1]}")
    print(f"  cx: {intrinsics[0][2]}")
    print(f"  cy: {intrinsics[1][2]}")

    # Output queues
    depthQueue = tof.depth.createOutputQueue()
    depthRawQueue = tof.rawDepth.createOutputQueue()

    # Set the config queues in GUI for filter updates
    gui.config_queue = tof.imageFiltersInputConfig.createInputQueue()
    gui.base_config_queue = tof.tofBaseInputConfig.createInputQueue()
    gui.confidence_config_queue = (
        tof.tofDepthConfidenceFilterInputConfig.createInputQueue()
    )

    # Start point cloud visualization if enabled
    if pointcloud_params["enabled"]:
        start_pointcloud_thread()

    print("=" * 80)
    print("🔴 TOF DEPTH FILTER WITH POINT CLOUD VISUALIZATION")
    print("=" * 80)
    print("FEATURES:")
    print("  ✅ ToF sensor with runtime filter control")
    print("  ✅ Live dual point cloud visualization (RAW + FINAL)")
    print("  ✅ Tkinter GUI for all parameters")
    print("  ✅ Phase unwrap threshold and confidence threshold controls")
    print("  ✅ Camera position preservation")
    print("  ✅ Pause/resume functionality")
    print("")
    print("KEYBOARD CONTROLS (in OpenCV windows):")
    print("  p: Pause/resume live updates")
    print("  1: Manual RAW point cloud update")
    print("  2: Manual FINAL point cloud update")
    print("  v: Reset point cloud views")
    print("  q: Quit application")
    print("")
    print("POINT CLOUD WINDOWS:")
    print("  - RAW Point Cloud: Direct from ToF sensor")
    print("  - FINAL Point Cloud: After all filters applied")
    print("=" * 80)

    with pipeline as p:
        p.start()
        while p.isRunning():
            ## Visualize raw depth (unfiltered depth directly from the ToF sensor)
            depthRaw: dai.ImgFrame = depthRawQueue.get()
            if depthRaw is not None:
                depthRawFrame = depthRaw.getFrame()
                latest_frames["raw"] = depthRawFrame  # Store for point cloud

                # Live point cloud update for raw data
                update_pointcloud_live("raw")

                depthRawImage = colorizeDepth(depthRawFrame)
                cv2.imshow("ToF Raw Depth", depthRawImage)

            ## Visualize depth (which is filtered depthRaw)
            depth: dai.ImgFrame = depthQueue.get()
            if depth is not None:
                depthFrame = depth.getFrame()
                latest_frames["final"] = depthFrame  # Store for point cloud

                # Live point cloud update for final data
                update_pointcloud_live("final")

                depthImage = colorizeDepth(depthFrame)
                cv2.imshow("ToF Filtered Depth", depthImage)

            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("p"):
                # Toggle pause/unpause
                new_state = toggle_pause()
                status = "⏸️ PAUSED" if new_state else "🔴 LIVE"
                print(
                    f"{status} Point cloud updates {'paused' if new_state else 'resumed'}"
                )
            elif key == ord("1"):
                # Manual update RAW point cloud
                update_pointcloud_manual("raw")
            elif key == ord("2"):
                # Manual update FINAL point cloud
                update_pointcloud_manual("final")
            elif key == ord("v"):
                # Reset point cloud views
                if vis_raw:
                    vis_raw.reset_view_point(True)
                if vis_final:
                    vis_final.reset_view_point(True)
                print("🔄 Reset both point cloud views to fit data")

    stop_pointcloud_thread()


def main():
    gui = FilterGUI(None)
    camera_thread = threading.Thread(target=camera_pipeline, args=(gui,))
    camera_thread.daemon = True
    camera_thread.start()
    gui.run()


if __name__ == "__main__":
    main()
