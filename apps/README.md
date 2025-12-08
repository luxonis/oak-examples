# Apps Overview

This section contains ready-to-use applications that demonstrate the capabilities of DepthAI and OAK devices. These applications are designed to be user-friendly and showcase real-world implementations.

## Platform Compatibility

| Name                                                             | RVC2 | RVC4 (peripheral) | RVC4 (standalone) | DepthAIv2 | Notes                                                                                                                                      |
| ---------------------------------------------------------------- | ---- | ----------------- | ----------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| [default-app](default-app/)                                      | ✅   | ✅                | ✅                |           | Default application pre-loaded on OAK4 devices showing color stream, depth stream, encoded stream and object detections using YOLO network |
| [rgb-depth-connections](conference-demos/rgb-depth-connections/) | ✅   | ✅                | ✅                |           | Demo combining RGB camera feed with depth information and object detection capabilities.                                                   |
| [focused-vision](focused-vision/)                                | ❌   | ❌                | ✅                |           | 2stage detection pipeline that preserves detail.                                                                                           |
| [data-collection](data-collection/)                              | ❌   | ❌                | ✅                |           | Demo showcasing how to use YOLOE for automatic data capture with an interactive UI for configuration.                                      |
| [ros-driver-basic](ros/ros-driver-basic/)                        | ❌   | ❌                | ✅                |           | Demo showcasing how ROS driver can be run as an APP on RVC4 device.                                                                        |
| [ros-driver-custom-workspace](ros/ros-driver-custom-workspace/)  | ❌   | ❌                | ✅                |           | Demo showcasing creation of a custom workspace that is built and run on the device itself.                                                 |
| [ros-driver-rgb-pcl](ros/ros-driver-rgb-pcl/)                    | ❌   | ❌                | ✅                |           | Demo showcasing how to publish RGB pointcloud using ROS driver on the device.                                                              |
| [ros-driver-spatial-bb](ros/ros-driver-spatial-bb/)              | ❌   | ❌                | ✅                |           | Demo showcasing how to publish RGB pointcloud and bounding boxes from detections in 3D space using ROS driver.                             |

✅: available; ❌: not available; 🚧: work in progress
