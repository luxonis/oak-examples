# ROS follow object example

This is an example of ROS driver being run as an OAK 4 app together with a custom `follow_object` ROS2 node.
The app launches `depthai_filters` spatial bounding boxes (`/spatial_bb`) and then uses spatial detections to follow a selected object.
Object selection is done by filtering marker text in code with `self.OBJECT_MARKER_TEXT` (default: `"person"`).
The node computes linear/angular velocity commands from the selected marker position and publishes them to `/cmd_vel`.
It is based on ROS2 Kilted, but you should be able to subscribe to topics in other distributions such as Humble or Jazzy.

## Demo

![person_follow_demo](media/oak4_person_follow.gif)

## Prerequisites

Before you begin, ensure you have the following installed on your host machine:

- ROS2 (Humble, Jazzy, or Kilted)
- Rviz2

## Setup Instructions

1. Install the required ROS packages:

   ```bash
   sudo apt update
   sudo apt install ros-$ROS_DISTRO-rviz2
   ```

2. Source your ROS2 environment:

   ```bash
   source /opt/ros/$ROS_DISTRO/setup.bash
   ```

## Running the Example

1. Launch the OAK 4 app:

   ```bash
   cd <path_to_this_example>
   oakctl app run .
   ```

2. In a new terminal, source your ROS2 environment and inspect topics:

   ```bash
   source /opt/ros/$ROS_DISTRO/setup.bash
   ros2 topic list
   ```

3. Optionally monitor output commands:

   ```bash
   ros2 topic echo /cmd_vel
   ```

## Changing the Target Object

To follow another detected object class, edit:

- `apps/ros/ros-follow-object/src/follow_object/follow_object/follow_object_node.py`

and change:

```python
self.OBJECT_MARKER_TEXT = "person"
```

to the desired marker text label (for example `"bottle"` or `"car"`), then rebuild/restart the app.

## Visualizing Data in Rviz

1. In Rviz, add a "Marker" display.
2. Set the topic to `/spatial_bb`.
3. Optionally add other displays from depthai ROS topics if needed.

## Package deployed on an iRobot Create 3

This package can be adapted to any robot that listens to the `/cmd_vel` topic for motion control. We deployed it on an iRobot Create 3; read more in [this blog post](https://discuss.luxonis.com/blog/6695-running-ros2-onboard-oak4-d).

## Troubleshooting

If you encounter issues with topic names or data types, verify that your ROS2 distribution matches the one used in the example.
You may need to adjust topic names or data types accordingly.

```bash
sudo apt install ros-$ROS_DISTRO-rmw-cyclonedds-cpp
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
```
