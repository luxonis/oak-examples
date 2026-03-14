import rclpy
from rclpy.node import Node
from visualization_msgs.msg import MarkerArray, Marker
from geometry_msgs.msg import Twist
import numpy as np


class FollowObject(Node):
    def __init__(self):
        super().__init__("follow_object")
        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.ANGULAR_SPEED_COEF = -1.5  # Yaw gain for horizontal target offset.
        self.LINEAR_SPEED_COEF = 1.0  # Forward speed gain for depth error.
        self.KEEP_LINEAR_DIST_M = 1.0  # Desired distance to target (m).
        self.OBJECT_MARKER_TEXT = "person"  # Marker text label to follow.
        self.MAX_ANG_SPEED = 1.0  # Search rotation speed when target is missing.

        self.prev_cmd_msg = Twist()
        self.spatian_nn_sub = self.create_subscription(
            MarkerArray, "/spatial_bb", self.spatian_nn_cb, 10
        )

    def spatian_nn_cb(self, msg: MarkerArray):
        person_marker = Marker()
        for marker in msg.markers:
            if marker.text == self.OBJECT_MARKER_TEXT:
                person_marker = marker
                break

        cmd_msg = Twist()

        if self.OBJECT_MARKER_TEXT not in person_marker.text:
            print(f"{self.OBJECT_MARKER_TEXT} not detected")
            cmd_msg.linear.x = 0.0
            cmd_msg.angular.z = (
                float(np.sign(self.prev_cmd_msg.angular.z)) * self.MAX_ANG_SPEED
            )
        else:
            dist = person_marker.pose.position.z - self.KEEP_LINEAR_DIST_M
            if dist > 0:
                cmd_msg.linear.x = self.LINEAR_SPEED_COEF * dist
            else:
                cmd_msg.linear.x = 0.0
            cmd_msg.angular.z = self.ANGULAR_SPEED_COEF * person_marker.pose.position.x
            print(f"Sent command {cmd_msg}")

        self.cmd_pub.publish(cmd_msg)
        self.prev_cmd_msg = cmd_msg


def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(FollowObject())
    rclpy.shutdown()


if __name__ == "__main__":
    main()
