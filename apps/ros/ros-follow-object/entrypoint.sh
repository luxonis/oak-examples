#!/usr/bin/env bash
set -e

echo "Listing workspace:"
ls -la /ws

echo "Sourcing ROS workspace:"
source /ws/install/setup.bash

echo "Starting depthai launch..."
ros2 launch depthai_filters spatial_bb.launch.py &
LAUNCH_PID=$!

echo "Starting follow_object node..."
ros2 run follow_object follow_object_node

# If follow_object exits, stop launch as well
echo "follow_object exited, stopping launch..."
kill -TERM "$LAUNCH_PID"
wait "$LAUNCH_PID"