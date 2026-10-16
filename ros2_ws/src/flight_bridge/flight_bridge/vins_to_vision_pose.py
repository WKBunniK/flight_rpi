import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


class VinsToVisionPose(Node):
    def __init__(self):
        super().__init__('vins_to_vision_pose')

        self.declare_parameter('input_topic', '/odometry')
        self.declare_parameter('output_topic', '/mavros/vision_pose/pose')

        input_topic = self.get_parameter('input_topic').value
        output_topic = self.get_parameter('output_topic').value

        self.publisher = self.create_publisher(
            PoseStamped, output_topic, 30
        )
        self.subscription = self.create_subscription(
            Odometry, input_topic, self.on_odometry, 30
        )

        self.get_logger().info(
            f'Forwarding {self.subscription.topic_name} -> '
            f'{self.publisher.topic_name}'
        )

    def on_odometry(self, msg):
        out = PoseStamped()
        out.header = msg.header
        out.pose = msg.pose.pose
        self.publisher.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = VinsToVisionPose()

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()