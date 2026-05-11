# AGENTS.md

## Summary

This is the smallest ROS app wrapper in the repository. It is the best starting point when you need to run `depthai_ros_driver` as an RVC4 standalone app and publish standard RGB, stereo, and IMU topics to a host ROS graph.

## Use This Example When

- You need the simplest ROS app packaging example under `apps/ros/`.
- You want a wrapper around the packaged `depthai_ros_driver` launch files rather than a custom ROS workspace.
- You need RGBD and IMU topics that can be visualized from a host machine.
- You want the most direct reference for how a ROS app is launched from `oakapp.toml`.

## Do Not Use This Example When

- You need local ROS source code in the repo that changes behavior.
- You need RGB pointclouds or spatial bounding boxes as the main output.
- You need `/cmd_vel` control logic or a custom robot node.
- You need a non-ROS standalone app or a Visualizer-based frontend.

## Quick Facts

- `Category:` `apps/ros/ros-driver-basic`
- `Shape:` `ros`
- `Primary task:` standalone ROS driver app for RGB, stereo, and IMU publishing
- `Entrypoint:` [oakapp.toml](oakapp.toml)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC4 standalone only
- `Requires:` RVC4 device; host ROS 2 environment to subscribe; `rviz2` for visualization
- `Input:` on-device RGB, stereo, and IMU sensors
- `Output:` ROS topics such as `/oak/rgb/image_raw`, `/oak/stereo/image_raw`, and `/oak/imu/data`
- `Models:` none defined locally in this repo
- `Visualizer / UI:` ROS 2 tools such as `rviz2`

## Read First

- [README.md](README.md): host ROS setup, visualization guidance, and troubleshooting notes
- [oakapp.toml](oakapp.toml): container image, package installation, and exact launch command
- [parameters.yaml](parameters.yaml): local ROS parameter overrides passed to the driver

## Architecture

- The app uses the `library/ros:kilted-ros-base` base image.
- [oakapp.toml](oakapp.toml) installs `ros-kilted-depthai-ros`.
- The entrypoint sources ROS Kilted and launches `depthai_ros_driver/driver.launch.py`.
- [parameters.yaml](parameters.yaml) enables IR and requests the `RGBD` pipeline type.
- All pipeline and topic behavior beyond that comes from the installed ROS package, not local source files in this example directory.

## Data Flow

- `device sensors -> depthai_ros_driver -> ROS 2 DDS graph`
- `ROS graph -> host subscribers / rviz2`

## Modification Guide

- `Safe to change:` [parameters.yaml](parameters.yaml), host RViz usage, launch arguments in [oakapp.toml](oakapp.toml)
- `Requires care:` ROS distribution assumptions, topic expectations on the host, parameter names defined by external ROS packages
- `Likely to break if changed blindly:` assuming there is local pipeline source here, or changing launch/package names without matching the installed ROS package version

## Common Adaptations

- `To change driver behavior:` start in [parameters.yaml](parameters.yaml)
- `To add local ROS code:` move to [../ros-driver-custom-workspace](../ros-driver-custom-workspace/)
- `To publish pointclouds instead:` compare against [../ros-driver-rgb-pcl](../ros-driver-rgb-pcl/)
- `To publish spatial 3D markers:` compare against [../ros-driver-spatial-bb](../ros-driver-spatial-bb/)

## Constraints

- This example is RVC4 standalone only.
- There is no local ROS package source in this example directory; the real runtime behavior comes from the installed `depthai_ros_driver`.
- Host-side ROS setup is still required to inspect or visualize the published topics.

## Non-Obvious Repo Conventions

- The example copies [resolv.conf](resolv.conf) into the container so package installation works during build.
- The local [parameters.yaml](parameters.yaml) is part of the launch command; this file is the main place to customize behavior here.
- `INDEX.md` classifies this as a standalone ROS app, so do not treat it like a general-purpose peripheral example.

## Related Examples

- [../ros-driver-rgb-pcl](../ros-driver-rgb-pcl/): use this when you need RGB pointcloud output
- [../ros-driver-spatial-bb](../ros-driver-spatial-bb/): use this when you need 3D markers for spatial detections
- [../ros-driver-custom-workspace](../ros-driver-custom-workspace/): use this when you need local ROS code and custom plugins
- [../ros-follow-object](../ros-follow-object/): use this when you need control outputs from detections

## Validation

- `Run:` `oakctl app run .`
- `Host validation:` `ros2 topic list` and `rviz2`
- `Success looks like:` the app publishes RGB, stereo, and IMU topics and they can be visualized from the host ROS environment
- `Common failure meaning:` the host ROS environment is not sourced, the wrong ROS middleware is being used, or the installed package versions do not match the topic expectations
