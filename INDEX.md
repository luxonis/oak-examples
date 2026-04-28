# INDEX.md

Agent-focused catalog of runnable/reference examples in this repository.

Use this file to find the closest existing implementation before writing code. After choosing a candidate, open that example's `AGENTS.md` first if present, then read its `README.md` and entrypoint.

## How To Use This Index

- Match the user task to the summary and `Tags`.
- Prefer the closest model or task match first, then the closest execution shape.
- Use `Mode` to filter for host-driven, standalone, frontend/backend, ROS, or C++ references.
- Use category overview docs when you need exact compatibility tables.

## When Not To Use This Index

If the task is primarily about contribution workflow, CI/publishing, or custom frontend build mechanics rather than choosing a runnable example, go to [CONTRIBUTING.md](CONTRIBUTING.md), `.github/ci/`, or [custom-frontend/GETTING_STARTED.md](custom-frontend/GETTING_STARTED.md) instead.

## Shape, Mode, And Tags

- `Shape: script` means a Python example where the primary reference is a host-side script layout with a direct entrypoint such as `main.py`.
- `Shape: script+standalone` means a Python example where standalone packaging through `oakapp.toml` is part of the intended reference shape, even if the same code can also run in host/peripheral mode, including on RVC2 where supported.
- `Shape: frontend` means a custom frontend plus backend app.
- `Shape: ros` means a ROS-based standalone app.
- `Shape: cpp` means a C++ example.
- `Shape: eval` means a host-side evaluation or analysis tool rather than a normal app.
- `Mode: host` means host/peripheral usage is the main path.
- `Mode: host + standalone` means both host/peripheral use and standalone OAK app packaging are relevant.
- `Mode: standalone-only` means the example is mainly intended for standalone OAK app deployment.
- `Mode: multi-device host` means a host-driven multi-camera or multi-device setup.
- `Tags` summarize the high-signal features an agent would usually filter on first, for example `stereo`, `tof`, `thermal`, `frontend`, `pointcloud`, `ros`, `tracking`, `ocr`, `open-vocab`, or `multi-device`.

## Platform Notes

- RVC2 devices run host/peripheral workflows only. They do not run standalone OAK apps.
- RVC4 devices can run both host/peripheral workflows and standalone OAK apps when the example supports it.
- Any `oakapp` mode implies an RVC4 standalone packaging path.
- The presence of `oakapp.toml` does not imply that the example is unusable on RVC2 peripheral mode. It only means the example also has an RVC4 standalone packaging path.
- `Mode` is intentionally compact. It describes how to use the example, not the full compatibility matrix.
- For exact per-example compatibility, check the category `README.md` and the example `README.md`.

## Category Overviews

- [apps/README.md](apps/README.md)
- [camera-controls/README.md](camera-controls/README.md)
- [cpp/README.md](cpp/README.md)
- [custom-frontend/README.md](custom-frontend/README.md)
- [depth-measurement/README.md](depth-measurement/README.md)
- [integrations/README.md](integrations/README.md)
- [neural-networks/README.md](neural-networks/README.md)
- [streaming/README.md](streaming/README.md)
- [tutorials/README.md](tutorials/README.md)

## Fast Paths

- Minimal camera streaming: [tutorials/camera-demo](tutorials/camera-demo/) or [cpp/camera_stream](cpp/camera_stream/). Tags: `rgb`, `visualizer`, `minimal`.
- Fast C++ starting point: [cpp/camera_stream](cpp/camera_stream/) for minimal streaming, or [cpp/uvc](cpp/uvc/) for standalone USB camera behavior on RVC4. Tags: `cpp`, `minimal`, `uvc`.
- Baseline packaged app: [apps/default-app](apps/default-app/). Tags: `rgb`, `detections`, `stereo-depth`, `visualizer`.
- Single-model inference scaffold: [neural-networks/generic-example](neural-networks/generic-example/). Tags: `model-zoo`, `single-model`, `reusable`.
- Spatial detections with stereo depth: [neural-networks/object-detection/spatial-detections](neural-networks/object-detection/spatial-detections/). Tags: `detections`, `spatial`, `stereo`.
- Custom frontend with two-way UI: [custom-frontend/raw-stream](custom-frontend/raw-stream/). Tags: `frontend`, `minimal`, `two-way-ui`.
- Standalone frontend/backend app: [custom-frontend/open-vocabulary-object-detection](custom-frontend/open-vocabulary-object-detection/). Tags: `frontend`, `open-vocab`, `standalone`.
- Multi-device setups: [tutorials/multiple-devices/multiple-devices-preview](tutorials/multiple-devices/multiple-devices-preview/) and [tutorials/multiple-devices/spatial-detection-fusion](tutorials/multiple-devices/spatial-detection-fusion/). Tags: `multi-device`, `preview`, `fusion`.
- ROS deployment: [apps/ros/ros-driver-basic](apps/ros/ros-driver-basic/). Tags: `ros`, `rgb`, `stereo`, `imu`.
- Streaming protocols: [streaming/](streaming/). Tags: `mjpeg`, `rtsp`, `webrtc`, `mqtt`, `tcp`.

## Apps

- [apps/default-app](apps/default-app/): baseline packaged app with RGB video, H.264, detections, and optional stereo depth. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `rgb`, `detections`, `stereo-depth`, `visualizer`, `baseline`.
- [apps/conference-demos/rgb-depth-connections](apps/conference-demos/rgb-depth-connections/): side-by-side RGB and depth view with spatial object detections. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `rgb`, `depth`, `spatial`, `detections`, `visualizer`.
- [apps/focused-vision](apps/focused-vision/): two-stage detection pipeline that preserves detail when the object occupies a small image region. Shape: `frontend`. Mode: `standalone-only`. Tags: `frontend`, `two-stage`, `detail-preserving`, `standalone`.
- [apps/data-collection](apps/data-collection/): open-vocabulary snap collection app with configurable conditions and interactive UI. Shape: `frontend`. Mode: `standalone-only`. Tags: `frontend`, `open-vocab`, `dataset-collection`, `snaps`, `standalone`.
- [apps/dino-tracking](apps/dino-tracking/): interactive similarity-based tracking with FastSAM segmentation and DINO embeddings. Shape: `frontend`. Mode: `standalone-only`. Tags: `frontend`, `tracking`, `segmentation`, `embeddings`, `standalone`.
- [apps/people-demographics-and-sentiment-analysis](apps/people-demographics-and-sentiment-analysis/): person analytics app with face detection, re-identification, and age/gender/emotion estimation. Shape: `frontend`. Mode: `standalone-only`. Tags: `frontend`, `people`, `face-analytics`, `reid`, `standalone`.
- [apps/object-volume-measurement-3d](apps/object-volume-measurement-3d/): click-to-measure 3D object dimensions and volume from segmented point clouds. Shape: `frontend`. Mode: `standalone-only`. Tags: `frontend`, `measurement`, `pointcloud`, `segmentation`, `standalone`.
- [apps/p2p-measurement](apps/p2p-measurement/): interactive 3D point-to-point distance measurement with a frontend. Shape: `frontend`. Mode: `standalone-only`. Tags: `frontend`, `spatial`, `measurement`, `distance`, `standalone`.
- [apps/qr-tiling](apps/qr-tiling/): high-resolution QR detection with dynamic tiling and a live configuration UI. Shape: `frontend`. Mode: `standalone-only`. Tags: `frontend`, `qr`, `tiling`, `small-objects`, `standalone`.

### ROS Apps

- [apps/ros/ros-driver-basic](apps/ros/ros-driver-basic/): standalone ROS driver app publishing RGB, stereo, and IMU topics. Shape: `ros`. Mode: `standalone-only`. Tags: `ros`, `rgb`, `stereo`, `imu`, `rviz`.
- [apps/ros/ros-driver-custom-workspace](apps/ros/ros-driver-custom-workspace/): template for building a custom ROS workspace and pipeline plugins on-device. Shape: `ros`. Mode: `standalone-only`. Tags: `ros`, `workspace-template`, `plugins`, `custom-pipeline`, `rviz`.
- [apps/ros/ros-driver-rgb-pcl](apps/ros/ros-driver-rgb-pcl/): standalone ROS app publishing RGB point clouds for RViz. Shape: `ros`. Mode: `standalone-only`. Tags: `ros`, `pointcloud`, `rgbd`, `rviz`, `standalone`.
- [apps/ros/ros-driver-spatial-bb](apps/ros/ros-driver-spatial-bb/): ROS app publishing RGB point clouds and 3D spatial bounding boxes. Shape: `ros`. Mode: `standalone-only`. Tags: `ros`, `pointcloud`, `spatial-detections`, `rviz`, `standalone`.
- [apps/ros/ros-follow-object](apps/ros/ros-follow-object/): ROS app that follows a selected detected object via `/cmd_vel`. Shape: `ros`. Mode: `standalone-only`. Tags: `ros`, `tracking`, `robot-control`, `cmd_vel`, `standalone`.

## Camera Controls

- [camera-controls/manual-camera-control](camera-controls/manual-camera-control/): manual exposure, focus, white balance, ISO, and related camera controls. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `camera-controls`, `rgb`, `keyboard`, `manual-control`, `visualizer`.
- [camera-controls/depth-driven-focus](camera-controls/depth-driven-focus/): autofocus driven by detected face distance and stereo depth. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `camera-controls`, `autofocus`, `face`, `stereo`, `depth`.
- [camera-controls/lossless-zooming](camera-controls/lossless-zooming/): device-side crop control for lossless zoom around detected faces. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `camera-controls`, `zoom`, `crop-control`, `face`, `rgb`.

## C++ Examples

- [cpp/camera_stream](cpp/camera_stream/): smallest C++ DepthAI pipeline streaming camera frames to the Visualizer. Shape: `cpp`. Mode: `host + standalone`. Tags: `cpp`, `rgb`, `visualizer`, `minimal`, `baseline`.
- [cpp/uvc](cpp/uvc/): standalone RVC4 C++ app exposing the device as a UVC camera over USB. Shape: `cpp`. Mode: `standalone-only`. Tags: `cpp`, `uvc`, `usb`, `standalone`, `rvc4`.

## Custom Frontend

- [custom-frontend/raw-stream](custom-frontend/raw-stream/): smallest custom frontend/backend example with two-way text input and a simple Python web server. Shape: `frontend`. Mode: `host + standalone`. Tags: `frontend`, `minimal`, `two-way-ui`, `web-server`, `visualizer`.
- [custom-frontend/open-vocabulary-object-detection](custom-frontend/open-vocabulary-object-detection/): advanced standalone frontend/backend app using YOLOE or YOLO-World with interactive prompts and WebRTC access. Shape: `frontend`. Mode: `standalone-only`. Tags: `frontend`, `open-vocab`, `prompts`, `webrtc`, `standalone`.

## Depth Measurement

- [depth-measurement/3d-measurement/box-measurement](depth-measurement/3d-measurement/box-measurement/): box dimension measurement from depth data. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `stereo`, `measurement`, `box`, `depth`, `geometry`.
- [depth-measurement/3d-measurement/rgbd-pointcloud](depth-measurement/3d-measurement/rgbd-pointcloud/): RGB-aligned point cloud generation and visualization. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `stereo`, `rgbd`, `pointcloud`, `alignment`, `visualizer`.
- [depth-measurement/3d-measurement/tof-pointcloud](depth-measurement/3d-measurement/tof-pointcloud/): ToF depth and point cloud visualization with interactive filter tuning. Shape: `script`. Mode: `host`. Tags: `tof`, `pointcloud`, `open3d`, `filter-tuning`, `host-processing`.
- [depth-measurement/calc-spatial-on-host](depth-measurement/calc-spatial-on-host/): host-side ROI spatial coordinate calculation from device depth frames. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `stereo`, `spatial`, `roi`, `host-processing`, `depth`.
- [depth-measurement/dynamic-calibration](depth-measurement/dynamic-calibration/): runtime stereo recalibration with host-side controller and coverage/quality UI. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `stereo`, `calibration`, `runtime-tuning`, `host-ui`, `depth`.
- [depth-measurement/stereo-on-host](depth-measurement/stereo-on-host/): host-side stereo disparity with `cv2.StereoSGBM` plus comparison against device disparity. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `stereo`, `host-processing`, `disparity`, `ssim`, `comparison`.
- [depth-measurement/stereo-runtime-configuration](depth-measurement/stereo-runtime-configuration/): live keyboard-driven tuning of stereo depth node parameters. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `stereo`, `runtime-tuning`, `keyboard`, `depth`, `visualizer`.
- [depth-measurement/triangulation](depth-measurement/triangulation/): host-side triangulation of detected faces from stereo cameras. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `stereo`, `face`, `triangulation`, `host-processing`, `spatial`.
- [depth-measurement/wls-filter](depth-measurement/wls-filter/): host-side weighted least squares filtering for depth refinement. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `stereo`, `depth-filtering`, `wls`, `host-processing`, `keyboard`.

## Integrations

- [integrations/hub-snaps-events](integrations/hub-snaps-events/): send Hub snaps when low-confidence detections match configured conditions. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `hub`, `dataset-collection`, `detections`, `events`, `snaps`.
- [integrations/foxglove](integrations/foxglove/): stream DepthAI data into Foxglove Studio, including frames and point clouds. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `foxglove`, `frames`, `pointcloud`, `websocket`, `visualization`.
- [integrations/rerun](integrations/rerun/): stream device data into Rerun Viewer. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `rerun`, `visualization`, `telemetry`, `viewer`.
- [integrations/roboflow-dataset](integrations/roboflow-dataset/): build a Roboflow dataset from device detections. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `roboflow`, `dataset-collection`, `detections`, `export`.
- [integrations/roboflow-workflow](integrations/roboflow-workflow/): custom frontend/backend app connected to Roboflow Workflow through the inference package. Shape: `frontend`. Mode: `standalone-only`. Tags: `roboflow`, `frontend`, `workflow`, `inference`, `standalone`.

## Neural Networks

### Generic And Reusable Inference

- [neural-networks/generic-example](neural-networks/generic-example/): generic single-model, single-image-input, single-head-output pipeline. Best starting point for simple inference reuse. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `model-zoo`, `single-model`, `reusable`, `single-input`, `visualizer`.

### 3D Detection

- [neural-networks/3D-detection/objectron](neural-networks/3D-detection/objectron/): two-stage detection plus 3D bounding box estimation for chairs, cameras, cups, and shoes. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `2-stage`, `3d-bbox`, `detections`, `objectron`, `geometry`.

### Counting

- [neural-networks/counting/crowdcounting](neural-networks/counting/crowdcounting/): crowd density map generation and counting with DM-Count. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `counting`, `crowd`, `density-map`, `people`.
- [neural-networks/counting/cumulative-object-counting](neural-networks/counting/cumulative-object-counting/): count objects crossing a line in up/down directions. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `counting`, `line-crossing`, `detections`, `tracking`.
- [neural-networks/counting/depth-people-counting](neural-networks/counting/depth-people-counting/): privacy-preserving people counting from depth only. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `counting`, `depth-only`, `privacy`, `stereo`, `people`.
- [neural-networks/counting/people-counter](neural-networks/counting/people-counter/): people counting from person detections in the current frame. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `counting`, `people`, `detections`, `visualizer`.

### Depth Estimation

- [neural-networks/depth-estimation/crestereo-stereo-matching](neural-networks/depth-estimation/crestereo-stereo-matching/): compare neural stereo matching against classic stereo disparity. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `stereo`, `neural-depth`, `comparison`, `disparity`.
- [neural-networks/depth-estimation/foundation-stereo](neural-networks/depth-estimation/foundation-stereo/): host-run Foundation Stereo model compared with device stereo output. Shape: `script`. Mode: `host`. Tags: `stereo`, `host-model`, `comparison`, `foundation-stereo`.
- [neural-networks/depth-estimation/neural-depth](neural-networks/depth-estimation/neural-depth/): Luxonis NeuralDepth running on-device on RVC4. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `stereo`, `neural-depth`, `rvc4`, `on-device`.
- [neural-networks/depth-estimation/neural-depth/host_eval](neural-networks/depth-estimation/neural-depth/host_eval/): evaluate NeuralDepth models on stereo datasets with host-supplied image pairs and accuracy metrics. Shape: `eval`. Mode: `host`. Tags: `eval`, `stereo-dataset`, `metrics`, `accuracy`.

### Face Detection And Face Analytics

- [neural-networks/face-detection/age-gender](neural-networks/face-detection/age-gender/): two-stage face detection plus age/gender recognition. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `face`, `2-stage`, `age-gender`, `analytics`.
- [neural-networks/face-detection/blur-faces](neural-networks/face-detection/blur-faces/): blur detected faces in real time. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `face`, `privacy`, `blur`, `visualizer`.
- [neural-networks/face-detection/emotion-recognition](neural-networks/face-detection/emotion-recognition/): two-stage face detection plus emotion recognition. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `face`, `2-stage`, `emotion`, `analytics`.
- [neural-networks/face-detection/face-mask-detection](neural-networks/face-detection/face-mask-detection/): single-stage PPE/face-mask detection pipeline. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `face`, `ppe`, `single-stage`, `mask-detection`.
- [neural-networks/face-detection/fatigue-detection](neural-networks/face-detection/fatigue-detection/): fatigue detection from face detection plus facial landmarks. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `face`, `landmarks`, `fatigue`, `analytics`.
- [neural-networks/face-detection/gaze-estimation](neural-networks/face-detection/gaze-estimation/): multi-stage pipeline for gaze estimation with multi-input models. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `face`, `multi-stage`, `multi-input`, `gaze`.
- [neural-networks/face-detection/head-posture-detection](neural-networks/face-detection/head-posture-detection/): face detection plus pitch/yaw/roll estimation. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `face`, `2-stage`, `head-pose`, `pitch-yaw-roll`.

### Feature Detection

- [neural-networks/feature-detection/xfeat](neural-networks/feature-detection/xfeat/): local feature extraction with compact descriptors for matching or tracking tasks. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `features`, `descriptors`, `matching`, `tracking`.

### Object Detection

- [neural-networks/object-detection/barcode-detection-conveyor-belt](neural-networks/object-detection/barcode-detection-conveyor-belt/): barcode region detection plus host-side decoding for conveyor use cases. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `barcode`, `decoding`, `conveyor`, `host-processing`.
- [neural-networks/object-detection/human-machine-safety](neural-networks/object-detection/human-machine-safety/): dangerous-object and palm detection with 3D distance checks. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `palm`, `dangerous-objects`, `spatial`, `safety`, `distance`.
- [neural-networks/object-detection/social-distancing](neural-networks/object-detection/social-distancing/): people detection plus 3D distance monitoring. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `people`, `spatial`, `distance-monitoring`, `safety`.
- [neural-networks/object-detection/spatial-detections](neural-networks/object-detection/spatial-detections/): standard reference for real-time object detections with spatial coordinates. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `detections`, `spatial`, `stereo`, `reusable`, `baseline`.
- [neural-networks/object-detection/text-blur](neural-networks/object-detection/text-blur/): text detection followed by selective blur inside detected regions. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `text`, `detection`, `blur`, `privacy`.
- [neural-networks/object-detection/thermal-detection](neural-networks/object-detection/thermal-detection/): person detection on thermal camera input. Shape: `script`. Mode: `host`. Tags: `thermal`, `people`, `detections`, `special-sensor`.
- [neural-networks/object-detection/yolo-host-decoding](neural-networks/object-detection/yolo-host-decoding/): run YOLO on-device and decode raw outputs on the host. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `yolo`, `host-decoding`, `detections`, `raw-output`.
- [neural-networks/object-detection/yolo-p](neural-networks/object-detection/yolo-p/): ADAS-style object detection with road and lane segmentation. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `adas`, `detections`, `road-segmentation`, `lane-segmentation`.
- [neural-networks/object-detection/yolo-world](neural-networks/object-detection/yolo-world/): open-vocabulary multi-input object detection with configurable class names. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `open-vocab`, `multi-input`, `detections`, `prompts`.

### Object Tracking

- [neural-networks/object-tracking/collision-avoidance](neural-networks/object-tracking/collision-avoidance/): detect tracked objects moving toward the camera and flag dangerous passes. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `tracking`, `spatial`, `trajectory`, `safety`, `stereo`.
- [neural-networks/object-tracking/deepsort-tracking](neural-networks/object-tracking/deepsort-tracking/): DeepSORT-style tracking using detections plus OSNet embeddings. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `tracking`, `embeddings`, `reid`, `host-tracker`.
- [neural-networks/object-tracking/kalman](neural-networks/object-tracking/kalman/): Kalman filtering of 2D boxes and spatial coordinates for tracked objects. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `tracking`, `filtering`, `kalman`, `spatial`.
- [neural-networks/object-tracking/people-tracker](neural-networks/object-tracking/people-tracker/): directional people flow counting using tracked person detections. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `tracking`, `counting`, `people-flow`, `directions`.

### OCR

- [neural-networks/ocr/general-ocr](neural-networks/ocr/general-ocr/): two-stage text detection and text recognition pipeline. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `ocr`, `2-stage`, `text-detection`, `text-recognition`.
- [neural-networks/ocr/license-plate-recognition](neural-networks/ocr/license-plate-recognition/): three-stage ALPR pipeline with vehicle, plate, and OCR stages. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `ocr`, `3-stage`, `alpr`, `vehicles`, `license-plates`.

### Pose Estimation

- [neural-networks/pose-estimation/animal-pose](neural-networks/pose-estimation/animal-pose/): animal detection plus pose estimation. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `pose`, `animals`, `2-stage`, `detections`.
- [neural-networks/pose-estimation/hand-pose](neural-networks/pose-estimation/hand-pose/): palm detection plus hand landmark estimation. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `pose`, `hands`, `2-stage`, `landmarks`.
- [neural-networks/pose-estimation/human-pose](neural-networks/pose-estimation/human-pose/): person detection plus pose estimation with Lite-HRNet. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `pose`, `humans`, `2-stage`, `landmarks`.

### Reidentification

- [neural-networks/reidentification/human-reidentification](neural-networks/reidentification/human-reidentification/): person or face re-identification with interchangeable detector and embedding models. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `reid`, `person`, `face`, `embeddings`, `interchangeable-models`.

### Segmentation

- [neural-networks/segmentation/blur-background](neural-networks/segmentation/blur-background/): segment people and blur the background. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `segmentation`, `privacy`, `blur`, `people`.
- [neural-networks/segmentation/depth-crop](neural-networks/segmentation/depth-crop/): combine segmentation with stereo depth and crop the depth image by mask. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `segmentation`, `stereo`, `depth`, `masking`.

### Speech Recognition

- [neural-networks/speech-recognition/whisper-tiny-en](neural-networks/speech-recognition/whisper-tiny-en/): short audio capture and transcription on OAK4 with LED/stream feedback. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `audio`, `speech`, `transcription`, `rvc4`, `led-feedback`.

## Streaming

- [streaming/mjpeg-streaming](streaming/mjpeg-streaming/): MJPEG-over-HTTP streaming with detections. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `streaming`, `http`, `mjpeg`, `detections`.
- [streaming/on-device-encoding](streaming/on-device-encoding/): encoded frame streaming to the host and direct container writing. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `streaming`, `encoded-video`, `container`, `host-save`.
- [streaming/poe-mqtt](streaming/poe-mqtt/): publish MQTT messages directly from a PoE camera script node. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `streaming`, `poe`, `mqtt`, `script-node`.
- [streaming/poe-tcp-streaming](streaming/poe-tcp-streaming/): bidirectional TCP streaming between device and host. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `streaming`, `poe`, `tcp`, `bidirectional`.
- [streaming/rtsp-streaming](streaming/rtsp-streaming/): H.265 RTSP server example. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `streaming`, `rtsp`, `h265`, `encoded-video`.
- [streaming/webrtc-streaming](streaming/webrtc-streaming/): WebRTC server for device configuration and preview streaming. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `streaming`, `webrtc`, `control`, `preview`.

## Tutorials

- [tutorials/camera-demo](tutorials/camera-demo/): minimal all-camera streaming example with H.264 encoding. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `rgb`, `multi-camera`, `visualizer`, `minimal`, `encoded-video`.
- [tutorials/camera-stereo-depth](tutorials/camera-stereo-depth/): minimal stereo depth setup. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `stereo`, `depth`, `minimal`, `baseline`.
- [tutorials/custom-models](tutorials/custom-models/): custom PyTorch/Kornia model creation, conversion, and execution on DepthAI. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `custom-models`, `conversion`, `pytorch`, `kornia`.
- [tutorials/display-detections](tutorials/display-detections/): strategies for drawing detections on higher-resolution streams than the NN input. Shape: `script`. Mode: `host`. Tags: `detections`, `high-res-display`, `visualization`, `host-processing`.
- [tutorials/full-fov-nn](tutorials/full-fov-nn/): full-field-of-view inference with aspect-ratio handling. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `detections`, `fov`, `aspect-ratio`, `resolution-techniques`.
- [tutorials/play-encoded-stream](tutorials/play-encoded-stream/): several ways to decode and play H264/H265/MJPEG on the host. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `encoded-video`, `playback`, `host`, `h264`, `h265`.
- [tutorials/qr-with-tiling](tutorials/qr-with-tiling/): SAHI-style tiled QR detection for small-object recovery. Shape: `script+standalone`. Mode: `host + standalone`. Tags: `qr`, `tiling`, `small-objects`, `sahi`.

### Multiple Devices

- [tutorials/multiple-devices/multi-cam-calibration](tutorials/multiple-devices/multi-cam-calibration/): estimate extrinsics for multiple cameras. Shape: `script`. Mode: `multi-device host`. Tags: `multi-device`, `calibration`, `extrinsics`, `geometry`.
- [tutorials/multiple-devices/multiple-devices-preview](tutorials/multiple-devices/multiple-devices-preview/): connect to multiple OAK devices and preview each stream independently. Shape: `script`. Mode: `multi-device host`. Tags: `multi-device`, `preview`, `rgb`, `visualizer`.
- [tutorials/multiple-devices/multiple-device-stitch-nn](tutorials/multiple-devices/multiple-device-stitch-nn/): stitch multiple camera streams and run tiled object detection over the wide view. Shape: `script`. Mode: `multi-device host`. Tags: `multi-device`, `stitching`, `tiling`, `detections`, `wide-view`.
- [tutorials/multiple-devices/spatial-detection-fusion](tutorials/multiple-devices/spatial-detection-fusion/): fuse 3D detections from multiple OAK cameras into one bird's-eye view. Shape: `script`. Mode: `multi-device host`. Tags: `multi-device`, `spatial`, `fusion`, `birds-eye-view`, `detections`.

## Supporting Overview Docs

These are not standalone runnable examples, but they are useful when the chosen runnable reference is `generic-example` or another broad scaffold:

- [neural-networks/classification/README.md](neural-networks/classification/README.md)
- [neural-networks/image-to-image-translation/README.md](neural-networks/image-to-image-translation/README.md)
- [neural-networks/keypoint-detection/README.md](neural-networks/keypoint-detection/README.md)
- [neural-networks/line-detection/README.md](neural-networks/line-detection/README.md)
- [tutorials/custom-models/generate_model/README.md](tutorials/custom-models/generate_model/README.md)

If you are about to build a new app, first select the closest runnable example above, then use these overview docs only as supporting context.
