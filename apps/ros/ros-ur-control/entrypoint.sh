#!/usr/bin/env bash
set -e

echo "Listing workspace:"
ls -la /ws

echo "Sourcing ROS workspace:"
source /ws/install/setup.bash

echo "Starting depthai launch..."
ros2 launch depthai_filters spatial_bb.launch.py &
LAUNCH_PID=$!

echo "Starting ur robot driver"
ros2 launch ur_robot_driver ur_control.launch.py ur_type:=ur5e robot_ip:=192.168.2.52 launch_rviz:=false &
LAUNCH_PID2=$!

echo "Starting moveit"
ros2 launch ur_moveit_config ur_moveit.launch.py ur_type:=ur5e launch_rviz:=false
LAUNCH_PID3=$!


# If follow_object exits, stop launch as well
echo "follow_object exited, stopping launch..."
kill -TERM "$LAUNCH_PID"
wait "$LAUNCH_PID"

kill -TERM "$LAUNCH_PID2"
wait "$LAUNCH_PID1"

kill -TERM "$LAUNCH_PID3"
wait "$LAUNCH_PID"