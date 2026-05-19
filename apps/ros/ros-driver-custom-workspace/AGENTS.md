# AGENTS.md

## Summary

This is the best template in the repository for shipping a custom ROS workspace inside an OAK app. Use it when you need your own ROS packages, your own launch file, or a custom `depthai_ros_driver` pipeline plugin that is built on-device during app build.

## Use This Example When

- You need to add local ROS nodes or packages to the app.
- You need to build a ROS workspace with `colcon` inside the oakapp.
- You want a template for custom `depthai_ros_driver` pipeline plugins.
- You need a reference for wiring a custom launch file as the app entrypoint.

## Do Not Use This Example When

- You only need the stock ROS driver launch with parameter overrides.
- You need a ready-made pointcloud or spatial-bounding-box app without local ROS development.
- You need a non-ROS standalone app.
- You need a fully host-driven ROS workspace rather than one packaged into the device app.

## Quick Facts

- `Category:` `apps/ros/ros-driver-custom-workspace`
- `Shape:` `ros`
- `Primary task:` template for custom on-device ROS workspace builds and custom pipeline plugins
- `Entrypoint:` [oakapp.toml](oakapp.toml)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC4 standalone only
- `Requires:` RVC4 device; host ROS 2 environment for inspection; network access during build for ROS dependencies
- `Input:` whatever the custom launch file and plugin define
- `Output:` ROS topics from the custom workspace; the bundled example also publishes a `topic` string message
- `Models:` none defined locally in this repo
- `Visualizer / UI:` ROS 2 tools such as `rviz2`

## Read First

- [README.md](README.md): high-level template intent
- [oakapp.toml](oakapp.toml): workspace copy, `colcon build`, and launch entrypoint
- [src/example_package/launch/example.launch.py](src/example_package/launch/example.launch.py): actual launch used by the app
- [src/example_package/params/params.yaml](src/example_package/params/params.yaml): parameters used by the custom launch path
- [src/dai_ros_plugins/src/dai_ros_plugins.cpp](src/dai_ros_plugins/src/dai_ros_plugins.cpp): custom `depthai_ros_driver` pipeline plugin example
- [src/dai_ros_plugins/plugins.xml](src/dai_ros_plugins/plugins.xml): plugin registration
- [src/example_package/src/example.cpp](src/example_package/src/example.cpp): extra local ROS node example
- [parameters.yaml](parameters.yaml): top-level parameter file present in the example directory

## Architecture

- The base image is ROS Kilted.
- [oakapp.toml](oakapp.toml) installs `ros-kilted-depthai-ros` and `python3-colcon-common-extensions`.
- Build steps copy the repo `src/` tree into `/ws/src` and run `colcon build`.
- The app entrypoint sources `/ws/install/setup.bash` and launches [src/example_package/launch/example.launch.py](src/example_package/launch/example.launch.py).
- That launch file includes `depthai_ros_driver/driver.launch.py` and also starts a custom example node.
- The example package params select the custom plugin type `dai_ros_plugins::DaiRosPlugins`, whose sample implementation builds only left and right sensor wrappers.

## Data Flow

- `workspace source -> colcon build -> /ws/install`
- `example.launch.py -> depthai_ros_driver launch + local example node`
- `custom plugin -> device pipeline topics -> ROS 2 DDS graph`
- `example.cpp -> ROS topic "topic" -> host subscribers`

## Modification Guide

- `Safe to change:` local packages under [src/](src/), launch files, custom plugin implementation, package dependencies
- `Requires care:` ROS package manifests, plugin registration, launch argument wiring, build-time dependency installation
- `Likely to break if changed blindly:` plugin class names, launch entrypoint names, or assumptions about which params file is actually used

## Common Adaptations

- `To add your own ROS package:` copy the pattern under [src/example_package/](src/example_package/)
- `To customize the device pipeline:` edit [src/dai_ros_plugins/src/dai_ros_plugins.cpp](src/dai_ros_plugins/src/dai_ros_plugins.cpp)
- `To change launch behavior:` start in [src/example_package/launch/example.launch.py](src/example_package/launch/example.launch.py)
- `To simplify back to stock driver behavior:` compare against [apps/ros/ros-driver-basic](https://github.com/luxonis/oak-examples/tree/main/apps/ros/ros-driver-basic)

## Constraints

- This example is RVC4 standalone only.
- Build time is longer than the other ROS wrappers because it runs `colcon build` inside the app image.
- The example depends on network/package availability during build.
- The bundled custom plugin example is intentionally minimal and only wraps left and right sensors.

## Non-Obvious Repo Conventions

- The top-level [parameters.yaml](parameters.yaml) is not the primary params file for the default entrypoint; [src/example_package/params/params.yaml](src/example_package/params/params.yaml) is the one selected by the launch file unless you override it.
- The entrypoint prints `/ws` contents before sourcing the built workspace, which is useful when debugging build or install issues.
- The example package publishes a trivial `Hello, world!` topic alongside the DepthAI driver to demonstrate how custom nodes fit into the packaged workspace.

## Related Examples

- [apps/ros/ros-driver-basic](https://github.com/luxonis/oak-examples/tree/main/apps/ros/ros-driver-basic): use this when the stock driver launch is enough
- [apps/ros/ros-follow-object](https://github.com/luxonis/oak-examples/tree/main/apps/ros/ros-follow-object): use this when you want a packaged ROS workspace plus a control node
- [apps/ros/ros-driver-spatial-bb](https://github.com/luxonis/oak-examples/tree/main/apps/ros/ros-driver-spatial-bb): use this when you want a ready-made spatial marker app instead of a template
- [apps/ros/ros-driver-rgb-pcl](https://github.com/luxonis/oak-examples/tree/main/apps/ros/ros-driver-rgb-pcl): use this when you want a ready-made pointcloud app instead of a template

## Validation

- `Run:` `oakctl app run .`
- `Host validation:` `ros2 topic list`, `ros2 topic echo /topic`, and `rviz2` as needed
- `Success looks like:` the workspace builds inside the app image, the launch file starts, and both the custom example node and the DepthAI ROS pipeline publish topics
- `Common failure meaning:` `colcon` build issues, missing dependencies, plugin registration mismatches, or editing the wrong params file
