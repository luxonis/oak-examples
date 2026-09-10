# Depth Measurement Overview

This section contains examples demonstrating depth perception capabilities and spatial measurements using DepthAI and OAK devices. Examples below only work with devices that have stereo depth capabilities (mono cameras).

## Platform Compatibility

| Name                                                              | RVC2 | RVC4 (peripheral) | RVC4 (standalone) | DepthAIv2                                                                                                    | Notes                                                                |
| ----------------------------------------------------------------- | ---- | ----------------- | ----------------- | ------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------- |
| [measurement-3d/box-measurement](measurement-3d/box-measurement/) | ✅   | 🚧                | 🚧                | [gen2-box_measurement](https://github.com/luxonis/oak-examples/tree/master/gen2-box_measurement)             | Example measuring box dimensions using depth information             |
| [measurement-3d/rgbd-pointcloud](measurement-3d/rgbd-pointcloud/) | ✅   | ✅                | ✅                | [gen2-pointcloud](https://github.com/luxonis/oak-examples/tree/master/gen2-pointcloud)                       | Demonstration of 3D point cloud generation from depth data           |
| [measurement-3d/tof-pointcloud](measurement-3d/tof-pointcloud/)   | ✅   | ❌                | ❌                | ❌                                                                                                           | Basic ToF depth and pointcloud data visualization                    |
| [calc-spatial-on-host](calc-spatial-on-host/)                     | ✅   | ✅                | ✅                | [gen2-calc-spatials-on-host](https://github.com/luxonis/oak-examples/tree/master/gen2-calc-spatials-on-host) | Example showing spatial calculations performed on host               |
| [wls-filter](wls-filter/)                                         | ✅   | ✅                | ✅                | [gen2-wls-filter](https://github.com/luxonis/oak-examples/tree/master/gen2-wls-filter)                       | Implementation of Weighted Least Squares filter for depth refinement |
| [stereo-on-host](stereo-on-host/)                                 | ✅   | ✅                | ✅                | [gen2-stereo-on-host](https://github.com/luxonis/oak-examples/tree/master/gen2-stereo-on-host)               | Example performing stereo depth calculations on host                 |
| [stereo-runtime-configuration](stereo-runtime-configuration/)     | ✅   | ✅                | ✅                | [gen2-qt-gui](https://github.com/luxonis/oak-examples/tree/master/gen2-qt-gui)                               | Stereo depth configuration during runtime                            |
| [triangulation](triangulation/)                                   | ✅   | ✅                | ✅                | [gen2-triangulation](https://github.com/luxonis/oak-examples/tree/master/gen2-triangulation)                 | Demonstration of 3D position calculation using triangulation         |
| [dynamic-calibration](dynamic-calibration/)                       | ✅   | ✅                | ✅                |                                                                                                              | Shows off the dynamic recalibration in action                        |

✅: available; ❌: not available; 🚧: work in progress
