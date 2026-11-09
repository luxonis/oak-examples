# AGENTS.md

## Summary

A minimal ToF colorized point-cloud pipeline displayed in the DepthAI Viewer, copied from the DepthAI-core ToF point-cloud example. Use it as a starting point for RGB-aligned ToF point clouds.

## Use This Example When

- You need ToF depth aligned to a color camera.
- You want a colorized point cloud in the browser-based Viewer.

## Do Not Use This Example When

- You need a ToF-only device without a color camera.
- You need individual filter controls or standalone packaging.

## Quick Facts

- `Category:` `depth-measurement/measurement-3d/tof-pointcloud`
- `Shape:` `script`
- `Primary task:` RGB-aligned ToF point-cloud visualization
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` none
- `Runs on:` host Python with RVC2 or RVC4 ToF and color hardware
- `Requires:` DepthAI and a browser
- `Output:` Viewer `pcl` topic in the `3d` group at http://localhost:8082

## Read First

- [main.py](main.py): complete pipeline
- [README.md](README.md): running the example
- [requirements.txt](requirements.txt): SDK version

## Architecture

- Based on `depthai-core/examples/python/ToF/tof_pointcloud.py`.
- ToF uses automatic socket selection, high-range preset, and a requested 30 FPS.
- Color uses `CAM_A` on RVC4 or `CAM_C` on RVC2, with undistorted 640×400 RGB output.
- Host `ImageAlign` aligns ToF depth to color; `PointCloud` combines aligned depth and color.
- `RemoteConnection` publishes the point cloud. Viewer `q` exits the pipeline.
- [utils/mode_menu.py](utils/mode_menu.py) serves a range selector at port 8082 around the Viewer iframe at port 8083. [utils/mode_menu.html](utils/mode_menu.html) provides Close, Mid, and Far range choices.
- The menu starts serving only after the pipeline starts and the Viewer is registered, so its iframe cannot load before the Viewer server is ready.
- Mode changes send a `ToFConfig` with the selected low/mid/high range profile to `tofBaseInputConfig` without restarting the pipeline. RVC2 also receives the corresponding `ImageFiltersConfig` preset; RVC4 uses device processing.

## Constraints

- Requires a color camera at the selected socket as well as ToF.
- RVC4 ToF depth already includes device processing; this example does not request `rawDepth`.
- There is no Open3D, OpenCV display, Tkinter UI, or custom confidence filter.
- The pipeline runs on the host and has no standalone packaging.
- Both HTTP ports 8082 and 8083, and Viewer WebSocket port 8765, must be accessible when viewing remotely.

## Related Examples

- [RGBD point cloud](https://github.com/luxonis/oak-examples/tree/main/depth-measurement/measurement-3d/rgbd-pointcloud): unified-depth alternative

## Validation

- Run `DEPTHAI_DEVICE_NAME_LIST=<device-ip> python3 main.py`.
- Open http://localhost:8082 and display the `pcl` topic in 3D.
- Success: a live colorized point cloud, with no desktop display windows.
- Switch between Close, Mid, and Far range and confirm the stream continues.
