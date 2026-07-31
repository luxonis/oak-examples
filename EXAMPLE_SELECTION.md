# Example Selection Guide

Use this guide to choose an implementation base by product outcome. Use [INDEX.md](INDEX.md) afterward to find nearby alternatives and read the selected example's `AGENTS.md` before adapting it.

The best base is the smallest example that already contains the product's hard requirements. A task-specific directory name is not enough: sensor topology, application shape, state, processing, and output integrations often matter more than the model.

## Selection Process

1. Define the business outcome: perception, measurement, counting, safety, collection, streaming, robotics, or another operator workflow.
2. Fix the required sensors and hardware: RGB, stereo, ToF, thermal, IMU, autofocus, or multiple devices.
3. Choose the application shape: host script, packaged app, custom frontend/backend, ROS, C++, or evaluation tool.
4. Identify required behavior outside inference: tracking, tiling, calibration, fusion, host processing, alerts, or user interaction.
5. Choose the required output or integration: Visualizer, browser video, RTSP, MQTT, Hub events, ROS topics, or files.
6. Start from the simplest example satisfying those constraints, then borrow isolated patterns from other examples.
7. Confirm model/platform support and validate accuracy, latency, and edge cases on representative data.

## Business-Outcome Routing

| Product requirement                                        | Primary starting point                                                                                                   | Choose a more specialized example when                                                     |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| Camera inference where one model returns the needed result | [generic-example](neural-networks/generic-example/AGENTS.md)                                                             | The pipeline also needs stereo, tracking, tiling, custom UI, transport, or multiple stages |
| Camera or sensor exploration without inference             | [camera-demo](tutorials/camera-demo/AGENTS.md)                                                                           | A packaged app or stereo-specific baseline is already required                             |
| Packaged RGB, detection, streaming, and optional depth     | [default-app](apps/default-app/AGENTS.md)                                                                                | A smaller script or custom frontend is a better product shape                              |
| Custom browser UI and backend controls                     | [raw-stream](custom-frontend/raw-stream/AGENTS.md)                                                                       | An existing domain app already provides the required workflow                              |
| Detected objects with XYZ coordinates                      | [spatial-detections](neural-networks/object-detection/spatial-detections/AGENTS.md)                                      | Full RGBD, point clouds, or measurement are required                                       |
| RGBD or colored point-cloud processing                     | [rgbd-pointcloud](depth-measurement/3d-measurement/rgbd-pointcloud/AGENTS.md)                                            | The product specifically needs interactive or automatic measurement                        |
| Tracking, counting, or alert state over time               | Closest tracking, counting, or safety example in [INDEX.md](INDEX.md)                                                    | Per-frame inference is sufficient                                                          |
| Small or distant targets                                   | [focused-vision](apps/focused-vision/AGENTS.md) or [qr-with-tiling](tutorials/qr-with-tiling/AGENTS.md)                  | Normal model resize preserves enough target detail                                         |
| Open-vocabulary detection or prompted collection           | [yolo-world](neural-networks/object-detection/yolo-world/AGENTS.md) or [data-collection](apps/data-collection/AGENTS.md) | Fixed model classes are sufficient                                                         |
| Video or telemetry transport                               | Matching streaming or integration example in [INDEX.md](INDEX.md)                                                        | The output can remain in the DepthAI Visualizer                                            |
| ROS product                                                | [ros-driver-custom-workspace](apps/ros/ros-driver-custom-workspace/AGENTS.md)                                            | Stock ROS driver topics need no custom workspace                                           |
| Multi-camera product                                       | Closest multiple-device tutorial in [INDEX.md](INDEX.md)                                                                 | One OAK device is sufficient                                                               |

## Generic Example — Model-Driven Camera Inference

**Type:** Product base

Use [neural-networks/generic-example](neural-networks/generic-example/AGENTS.md) when one parser-supported model accepts an image-like input and returns the product's primary perception result. This includes classification, detection, pose, instance or semantic segmentation, monocular depth, line detection, and image-to-image inference.

Move away from it when behavior outside that model is a hard requirement, not merely because another example's directory name matches the task.

## Camera Demo — Sensor-First Development

**Type:** Product base

Use [tutorials/camera-demo](tutorials/camera-demo/AGENTS.md) to verify connected sensors and establish camera streams before adding perception. Use [tutorials/camera-stereo-depth](tutorials/camera-stereo-depth/AGENTS.md) when stereo depth is the first required capability.

## Default App — Packaged Multi-Capability App

**Type:** Product base

Use [apps/default-app](apps/default-app/AGENTS.md) when packaging, encoded streaming, detections, and optional depth are already part of the intended product. Do not take its extra branches into a single-purpose proof of concept.

## Raw Stream — Custom Frontend Foundation

**Type:** Product base

Use [custom-frontend/raw-stream](custom-frontend/raw-stream/AGENTS.md) when the reusable requirement is a browser stream plus frontend-to-backend controls. Add the selected perception pipeline rather than copying a large domain app only for its UI shell.

## Spatial Detections — Detection with Physical Location

**Type:** Product base

Use [neural-networks/object-detection/spatial-detections](neural-networks/object-detection/spatial-detections/AGENTS.md) for object distance, XYZ coordinates, occupancy zones, or spatial decisions. Select it for calibrated stereo fusion, not for its detector.

## RGBD Point Cloud — General 3D Foundation

**Type:** Product base

Use [depth-measurement/3d-measurement/rgbd-pointcloud](depth-measurement/3d-measurement/rgbd-pointcloud/AGENTS.md) for aligned RGB/depth and point-cloud output. Move to `p2p-measurement`, `box-measurement`, or `object-volume-measurement-3d` only when their interaction or measurement logic is itself required.

## Tracking, Counting, and Safety — Stateful Products

**Type:** Product patterns

Choose the example whose state transition matches the outcome: directional flow, occupancy, track identity, collision trajectory, pairwise distance, or debounced alerting. Reuse its state and host-processing logic while independently selecting the simplest suitable detector.

Start with [people-tracker](neural-networks/object-tracking/people-tracker/AGENTS.md) for directional flow, [collision-avoidance](neural-networks/object-tracking/collision-avoidance/AGENTS.md) for approaching-object risk, or [human-machine-safety](neural-networks/object-detection/human-machine-safety/AGENTS.md) for multi-model spatial alert logic.

## Focused Vision and Tiling — Small-Target Products

**Type:** Technique references

Use [apps/focused-vision](apps/focused-vision/AGENTS.md) to compare high-resolution crop and tiling strategies when resize destroys target detail. Use [tutorials/qr-with-tiling](tutorials/qr-with-tiling/AGENTS.md) for tiled detection plus host decoding or aggregation.

Do not inherit a two-stage or tiled architecture until representative media shows that normal full-frame inference is insufficient.

## Open-Vocabulary Workflows — Runtime Classes and Collection

**Type:** Product patterns

Use [neural-networks/object-detection/yolo-world](neural-networks/object-detection/yolo-world/AGENTS.md) for prompted detection without a custom operator UI. Use [apps/data-collection](apps/data-collection/AGENTS.md) when operators need runtime class controls, thresholds, prompt sources, and automatic capture.

## Streaming and External Integrations

**Type:** Integration references

Choose the protocol consumers require: [MJPEG](streaming/mjpeg-streaming/AGENTS.md), [RTSP](streaming/rtsp-streaming/AGENTS.md), [WebRTC](streaming/webrtc-streaming/AGENTS.md), [MQTT](streaming/poe-mqtt/AGENTS.md), or [Hub events](integrations/hub-snaps-events/AGENTS.md).

Treat transport as a composable concern. Keep its connection and lifecycle code, but do not inherit its model or business rule unless those also match.

## ROS and Multi-Device Systems

**Type:** Integration and architecture references

Use [apps/ros/ros-driver-custom-workspace](apps/ros/ros-driver-custom-workspace/AGENTS.md) when custom ROS packages or launch files must ship with the app. For multiple OAK devices, choose independently between device orchestration, calibrated spatial fusion, and stitched inference using the matching tutorials in [INDEX.md](INDEX.md).

## Known Selection Traps

- **Educational complexity:** A technique showcase is appropriate only when the product needs that technique.
- **Single-model versus staged inference:** If one supported model already returns the required result, begin with the single-model path. Human pose and instance segmentation commonly fall into this category; use staged examples when independent models or crop quality are justified by requirements or measurements.
- **Large domain apps:** Measurement, collection, and frontend apps are not general-purpose bases for one capability they happen to contain.
- **Integration examples:** Select them for transport and lifecycle behavior, not for their bundled detector.
- **Directory matching:** A closer task name can still be a worse base than an example with the correct sensors, state, runtime mode, or UI shape.
- **Maximal examples:** Prefer composing a focused pattern into a small base over removing unrelated subsystems from the largest example.

After selecting a base, use [INDEX.md](INDEX.md) to compare nearby examples and read the candidate `AGENTS.md` constraints before copying code.
