# AGENTS.md

## Summary

This is the smallest ROS app wrapper in the repo for RGB pointcloud publishing. Use it when you want a stock standalone `depthai_ros_driver` app that already exposes `/oak/rgbd/points` without building a custom workspace.

## Use This Example When

- You need RGB pointcloud output in ROS.
- You want a stock launch wrapper rather than local ROS source code.
- You need a standalone RVC4 app that can be inspected from a host ROS environment.
- You want the shortest path from oakapp packaging to RViz pointcloud visualization.

## Do Not Use This Example When

- You need custom ROS nodes or custom pipeline plugins.
- You need 3D markers for detections rather than just pointcloud output.
- You need a non-ROS app or default Visualizer topics.
- You need `/cmd_vel` control outputs.

## Quick Facts

- `Category:` `apps/ros/ros-driver-rgb-pcl`
- `Shape:` `ros`
- `Primary task:` standalone ROS RGB pointcloud publishing
- `Entrypoint:` [oakapp.toml](oakapp.toml)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC4 standalone only
- `Requires:` RVC4 device; host ROS 2 environment; `rviz2` for pointcloud visualization
- `Input:` RGBD pipeline from the installed ROS driver launch
- `Output:` `/oak/rgbd/points`
- `Models:` none defined locally in this repo
- `Visualizer / UI:` ROS 2 tools such as `rviz2`

## Read First

- [README.md](README.md): host setup and RViz usage
- [oakapp.toml](oakapp.toml): exact launch command and container image

## Architecture

- The app installs `ros-kilted-depthai-ros` into a ROS Kilted base image.
- The entrypoint sources ROS and launches `depthai_ros_driver/rgbd_pcl.launch.py`.
- All pipeline specifics live in the installed ROS package, not local source files in this example directory.

## Data Flow

- `device RGBD pipeline -> depthai_ros_driver -> /oak/rgbd/points`
- `/oak/rgbd/points -> host ROS subscribers / rviz2`

## Modification Guide

- `Safe to change:` the launch command in [oakapp.toml](oakapp.toml) if you know the target external launch file
- `Requires care:` ROS launch names, package versions, RViz topic expectations
- `Likely to break if changed blindly:` assuming there is local pipeline code to edit here when the real implementation is external

## Common Adaptations

- `To move to a custom workspace:` compare against [apps/ros/ros-driver-custom-workspace](https://github.com/luxonis/oak-examples/tree/main/apps/ros/ros-driver-custom-workspace)
- `To publish spatial markers too:` compare against [apps/ros/ros-driver-spatial-bb](https://github.com/luxonis/oak-examples/tree/main/apps/ros/ros-driver-spatial-bb)
- `To use the broader RGB/stereo/IMU driver app:` compare against [apps/ros/ros-driver-basic](https://github.com/luxonis/oak-examples/tree/main/apps/ros/ros-driver-basic)

## Constraints

- This example is RVC4 standalone only.
- There is no local params file or local ROS source controlling the pointcloud pipeline here.
- Exact topic behavior depends on the installed version of `depthai_ros_driver`.

## Non-Obvious Repo Conventions

- This example is intentionally thinner than the other ROS entries; the point is to show the packaging shape for an external launch, not to provide local source to modify.
- [resolv.conf](resolv.conf) is copied into the container to support package installation during build.

## Related Examples

- [apps/ros/ros-driver-basic](https://github.com/luxonis/oak-examples/tree/main/apps/ros/ros-driver-basic): use this when you need RGB, stereo, and IMU rather than just pointclouds
- [apps/ros/ros-driver-spatial-bb](https://github.com/luxonis/oak-examples/tree/main/apps/ros/ros-driver-spatial-bb): use this when you need 3D marker visualization for detections
- [apps/ros/ros-driver-custom-workspace](https://github.com/luxonis/oak-examples/tree/main/apps/ros/ros-driver-custom-workspace): use this when you need local ROS source and custom launch behavior
- [apps/ros/ros-follow-object](https://github.com/luxonis/oak-examples/tree/main/apps/ros/ros-follow-object): use this when you need detections to drive robot control

## Validation

- `Run:` `oakctl app run .`
- `Host validation:` `ros2 topic echo /oak/rgbd/points` or view the topic in `rviz2`
- `Success looks like:` the pointcloud topic is present and RViz can display it
- `Common failure meaning:` the host ROS environment is not prepared, the external launch package differs from expectations, or DDS communication is not configured correctly
