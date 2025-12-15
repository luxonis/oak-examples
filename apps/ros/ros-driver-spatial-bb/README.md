# ROS driver Spatial bounding boxes example

![Image](./media/ros_main.png)

This is an example of ROS driver being run as an OAK 4 app. It launches ROS driver that publishes spatial image detections and rgb pointcloud.
Additinally, `spatial_bb` composable node from `depthai_filters` is also being run which republishes spatial detections as Marker messages to visualize bounding boxes in 3D space.
These topics can be accessible for viewing and/or further processing directly on host.
It is based on ROS2 Kilted, but you should be able to subscribe to topics in other distributions such as Humble or Jazzy.

## Prerequisites

Before you begin, ensure you have the following installed on your host machine:

- ROS2 (Humble, Jazzy, or Kilted)
- Rviz2

## Setup Instructions

1. Install the required ROS packages:

   ```bash
   sudo apt update
   sudo apt install ros-$ROS_DISTRO-image-transport-plugins ros-$ROS_DISTRO-rviz2
   ```

2. Source your ROS2 environment:

   ```bash
   source /opt/ros/$ROS_DISTRO/setup.bash
   ```

## Running the Example

1. Launch the OAK 4 app with the ROS driver:

   ```bash
   cd <path_to_this_example>
   oakctl app run .
   ```

2. In a new terminal, source your ROS2 environment and run Rviz2:

   ```bash
   source /opt/ros/$ROS_DISTRO/setup.bash
   rviz2
   ```

## Visualizing Data in Rviz

1. In Rviz, add a new display by clicking the "Add" button in the bottom toolbar.
   Note, you can add by display type, or just by topic which will automatically add the correct display type.

2. For RGB camera visualization:

   - Add a "Image" display
   - Set the topic to `/oak/rgb/image_raw`
   - Adjust the display settings as needed

3. For depth stream visualization:

   - Add a "Image" display for left camera: `/oak/stereo/image_raw`

4. For RGB Pointcloud visualization:

   - Add a "Pointcloud" display
   - Set the topic to `/oak/rgbd/points`
   - Adjust the display settings as needed

5. For Marker message visualization:

   - Add a "Marker" display
   - Set the topic to `/spatial_bb`
   - Adjust the display settings as needed

6. Save your Rviz configuration for future use by clicking "File" > "Save Config".

## Troubleshooting

If you encounter issues with topic names or data types, verify that your ROS2 distribution matches the one used in the example.
You may need to adjust topic names or data types accordingly.
Or change DDS implementation, as following:

```bash
sudo apt install ros-$ROS_DISTRO-rmw-cyclonedds-cpp
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```
