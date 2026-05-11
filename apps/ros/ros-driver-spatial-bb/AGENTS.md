# AGENTS.md

## Summary

This is the stock ROS wrapper to reach for when you need pointclouds plus 3D spatial bounding-box markers. It is the best reference in `apps/ros/` for launching `depthai_filters spatial_bb` as an RVC4 standalone app without maintaining a local ROS workspace.

## Use This Example When

- You need RGB pointclouds and 3D marker output in ROS.
- You want ready-made spatial bounding-box visualization in RViz.
- You want a stock launch wrapper rather than local ROS source.
- You need an RVC4 standalone ROS app that can be consumed from a host ROS machine.

## Do Not Use This Example When

- You need to edit the ROS node implementation locally in this repo.
- You need only stock RGB/stereo/IMU topics.
- You need `/cmd_vel` control logic.
- You need a non-ROS standalone app or browser frontend.

## Quick Facts

- `Category:` `apps/ros/ros-driver-spatial-bb`
- `Shape:` `ros`
- `Primary task:` standalone ROS spatial detections with 3D marker output
- `Entrypoint:` [oakapp.toml](oakapp.toml)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC4 standalone only
- `Requires:` RVC4 device; host ROS 2 environment; `rviz2` for visualization
- `Input:` spatial-detection pipeline from the installed ROS launch
- `Output:` RGB topics, `/oak/rgbd/points`, and `/spatial_bb`
- `Models:` determined by the installed ROS launch packages, not by local source in this repo
- `Visualizer / UI:` ROS 2 tools such as `rviz2`

## Read First

- [README.md](README.md): host setup and RViz instructions
- [oakapp.toml](oakapp.toml): exact standalone launch command and container image

## Architecture

- The app installs `ros-kilted-depthai-ros`.
- The entrypoint sources ROS Kilted and launches `depthai_filters/spatial_bb.launch.py`.
- The actual pipeline and marker-publication logic live in the external ROS packages, not local source files in this example directory.

## Data Flow

- `device spatial-detection pipeline -> depthai_filters spatial_bb launch -> ROS topics`
- `ROS topics -> host RViz displays for images, pointclouds, and markers`

## Modification Guide

- `Safe to change:` the launch command in [oakapp.toml](oakapp.toml) if you know the external package behavior
- `Requires care:` external launch/package assumptions, marker topic names, RViz display configuration
- `Likely to break if changed blindly:` assuming this repo contains the spatial-bounding-box node implementation locally

## Common Adaptations

- `To add local ROS code around this behavior:` compare against [../ros-driver-custom-workspace](../ros-driver-custom-workspace/)
- `To turn detections into robot motion:` compare against [../ros-follow-object](../ros-follow-object/)
- `To drop back to stock RGBD publishing:` compare against [../ros-driver-basic](../ros-driver-basic/) or [../ros-driver-rgb-pcl](../ros-driver-rgb-pcl/)

## Constraints

- This example is RVC4 standalone only.
- There is no local params file or launch source in this directory controlling the spatial-bounding-box logic.
- Topic names and exact launch internals depend on the installed ROS packages.

## Non-Obvious Repo Conventions

- The repo intentionally treats this as a launch-wrapper example, not a source-code example.
- [resolv.conf](resolv.conf) is part of the container build setup even though there is no local ROS source here.

## Related Examples

- [../ros-driver-rgb-pcl](../ros-driver-rgb-pcl/): use this when you only need pointclouds
- [../ros-follow-object](../ros-follow-object/): use this when you want to consume `/spatial_bb` and publish `/cmd_vel`
- [../ros-driver-basic](../ros-driver-basic/): use this when you need the broader stock driver topics
- [../ros-driver-custom-workspace](../ros-driver-custom-workspace/): use this when you need local ROS source and custom launches

## Validation

- `Run:` `oakctl app run .`
- `Host validation:` `rviz2` with `Image`, `PointCloud`, and `Marker` displays
- `Success looks like:` RViz can show pointcloud output and the `/spatial_bb` marker topic updates with 3D boxes
- `Common failure meaning:` host ROS setup is incomplete, DDS communication is misconfigured, or the installed external launch packages differ from the expected topic schema
