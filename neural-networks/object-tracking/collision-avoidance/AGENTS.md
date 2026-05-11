# AGENTS.md

## Summary

This is the repository reference for tracking objects moving toward the camera and flagging dangerous passes. Use it when you need motion-based safety logic on top of spatial detections and tracking.

## Use This Example When

- You need person tracking with a “moving toward camera” signal.
- You want a bird’s-eye view plus directional alert outputs.
- You need stereo-backed tracking rather than 2D-only tracklets.

## Do Not Use This Example When

- You only need standard person tracking.
- You need person-to-person distance checks instead of motion-toward-camera logic.
- You need a generic object tracker with no spatial branch.

## Quick Facts

- `Category:` `neural-networks/object-tracking/collision-avoidance`
- `Shape:` `script+standalone`
- `Primary task:` detect and track people moving dangerously toward the camera
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` devices with `CAM_A`, `CAM_B`, and `CAM_C`; RVC2 peripheral, RVC4 peripheral, and RVC4 standalone packaging
- `Requires:` stereo depth, person detections, tracking, and calibration
- `Input:` live color plus stereo pair
- `Output:` `Video`, `Tracklets`, `Direction`, and `Bird Frame`
- `Models:` YOLOv6 YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/collision_avoidance_node.py](utils/collision_avoidance_node.py)
- [utils/host_bird_eye_view.py](utils/host_bird_eye_view.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- A `SpatialDetectionNetwork` runs on `CAM_A` with stereo depth from `CAM_B/C`.
- `ImgDetectionsFilter` keeps only the `person` label.
- `ObjectTracker` produces tracklets from the filtered spatial detections.
- [utils/collision_avoidance_node.py](utils/collision_avoidance_node.py) derives the “approaching camera” direction/alert stream.
- [utils/host_bird_eye_view.py](utils/host_bird_eye_view.py) renders the overhead motion view.

## Constraints

- The current repo state is person-only because `person_label` is selected explicitly in [main.py](main.py).
- The example requires three cameras and aligned stereo depth.
- Alert quality depends on tracklet stability and Z-motion estimation, not just 2D motion.

## Related Examples

- [../kalman](../kalman/): use this when you want smoothing of tracked spatial boxes instead of collision alerts
- [../../object-detection/social-distancing](../../object-detection/social-distancing/): use this when you need person distance monitoring rather than motion-toward-camera logic
- [../people-tracker](../people-tracker/): use this when you need directional people-flow counts

## Validation

- `Run:` `python3 main.py`
- `Success looks like:` the Visualizer shows tracked people, direction output, and a bird’s-eye view that reacts to movement toward the camera
- `Common failure meaning:` the device lacks stereo cameras, tracklets are unstable, or the person-only filtering does not match the scene
