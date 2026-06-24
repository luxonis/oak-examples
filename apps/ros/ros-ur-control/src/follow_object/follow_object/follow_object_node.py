#!/usr/bin/env python3

import rclpy
from moveit_py import moveit
from geometry_msgs.msg import Pose


def main():
    # 1. Initialize ROS 2 and the MoveIt 2 node
    rclpy.init()
    node = rclpy.create_node("simple_move_ros2")

    # 2. Initialize MoveIt 2 (requires a moveit_config package launched separately)
    # The 'panda_moveit_config' is a common example; replace with your robot's config
    moveit_config = "panda_moveit_config"
    move_group = moveit.MoveGroup(node, moveit_config, "panda_arm")

    # 3. Define the target pose
    pose_target = Pose()
    pose_target.orientation.w = 1.0
    pose_target.position.x = 0.4
    pose_target.position.y = 0.0
    pose_target.position.z = 0.4

    # 4. Set the target and plan/execute
    move_group.set_pose_target(pose_target)

    # Plan and execute in one step (blocking)
    success = move_group.go(wait=True)

    if success:
        node.get_logger().info("Motion successful!")
    else:
        node.get_logger().error("Planning or execution failed.")

    # 5. Cleanup
    move_group.clear_pose_targets()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
