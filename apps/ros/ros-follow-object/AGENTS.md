# AGENTS.md

## Summary

This is the best ROS example in the repo for turning spatial detections into robot motion commands. It combines a stock spatial-bounding-box launch with a local `follow_object` node that filters for one class label and publishes `/cmd_vel`.

## Use This Example When

- You need a packaged ROS workspace plus a custom control node.
- You want to consume `/spatial_bb` and drive robot motion from it.
- You need a concrete example of extending a stock DepthAI ROS launch with local behavior.
- You want a simpler custom ROS app than building a template workspace from scratch.

## Do Not Use This Example When

- You only need visualization of spatial detections.
- You need local ROS source but no control logic.
- You need browser frontend interaction or non-ROS apps.
- You need a production-ready robot controller with safety layers.

## Quick Facts

- `Category:` `apps/ros/ros-follow-object`
- `Shape:` `ros`
- `Primary task:` follow a selected detected class by publishing `/cmd_vel`
- `Entrypoint:` [entrypoint.sh](entrypoint.sh)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC4 standalone only
- `Requires:` RVC4 device; host ROS 2 environment; a robot or simulator listening on `/cmd_vel` if you want actual motion
- `Input:` `/spatial_bb` marker messages from the background spatial-bounding-box launch
- `Output:` `/cmd_vel`
- `Models:` spatial-detection details come from the installed external ROS launch packages, not local repo source
- `Visualizer / UI:` ROS 2 tools such as `rviz2`

## Read First

- [README.md](README.md): host usage, target-object note, and deployment context
- [oakapp.toml](oakapp.toml): workspace build and app entrypoint
- [entrypoint.sh](entrypoint.sh): actual runtime orchestration
- [parameters.yaml](parameters.yaml): driver parameter overrides
- [src/follow_object/follow_object/follow_object_node.py](src/follow_object/follow_object/follow_object_node.py): the local control node

## Architecture

- The build copies the local ROS workspace into `/ws/src` and runs `colcon build`.
- [entrypoint.sh](entrypoint.sh) sources the built workspace.
- It launches `depthai_filters spatial_bb.launch.py` in the background.
- It then runs the local `follow_object_node`.
- The node subscribes to `/spatial_bb`, picks the first marker whose `text` matches `OBJECT_MARKER_TEXT`, and publishes a `Twist` to `/cmd_vel`.

## Data Flow

- `device detections -> external spatial_bb launch -> /spatial_bb`
- `/spatial_bb -> follow_object_node.py -> /cmd_vel`

## Modification Guide

- `Safe to change:` target class label, controller gains, desired following distance, launch orchestration in [entrypoint.sh](entrypoint.sh)
- `Requires care:` topic names, marker text semantics, controller stability, workspace/package naming
- `Likely to break if changed blindly:` the startup sequence between the background launch and the control node, or the assumptions about marker contents in `/spatial_bb`

## Common Adaptations

- `To follow a different class:` edit `OBJECT_MARKER_TEXT` in [src/follow_object/follow_object/follow_object_node.py](src/follow_object/follow_object/follow_object_node.py)
- `To change motion behavior:` tune `ANGULAR_SPEED_COEF`, `LINEAR_SPEED_COEF`, `KEEP_LINEAR_DIST_M`, and `MAX_ANG_SPEED`
- `To replace the stock spatial launch with your own:` compare against [../ros-driver-custom-workspace](../ros-driver-custom-workspace/)
- `To use this only for visualization:` compare against [../ros-driver-spatial-bb](../ros-driver-spatial-bb/)

## Constraints

- This example is RVC4 standalone only.
- The controller is intentionally simple and does not include safety, obstacle avoidance, or watchdog logic.
- The object-selection mechanism is a hardcoded label match on marker text.
- The actual detection and spatial-bounding-box publication come from an external ROS launch, not local repo code.

## Non-Obvious Repo Conventions

- The control node searches for the first matching marker rather than tracking identities across frames.
- If the target label is not present, the node keeps rotating using the sign of the previous angular command.
- [oakapp.toml](oakapp.toml) installs `ros-kilted-teleop-twist-keyboard`, but the default app entrypoint does not launch it.

## Related Examples

- [../ros-driver-spatial-bb](../ros-driver-spatial-bb/): use this when you only need `/spatial_bb` visualization
- [../ros-driver-custom-workspace](../ros-driver-custom-workspace/): use this when you need a more general custom ROS workspace template
- [../ros-driver-basic](../ros-driver-basic/): use this when you only need stock driver topics
- [../../../neural-networks/object-tracking/people-tracker](../../../neural-networks/object-tracking/people-tracker/): use this when you want a non-ROS people-tracking reference

## Validation

- `Run:` `oakctl app run .`
- `Host validation:` `ros2 topic list`, `ros2 topic echo /cmd_vel`, and `rviz2` if needed
- `Success looks like:` `/spatial_bb` is present, matching detections cause `/cmd_vel` updates, and changing `OBJECT_MARKER_TEXT` changes the target class
- `Common failure meaning:` the workspace did not build, `/spatial_bb` is not being published by the background launch, or the target class label does not match the marker text
