import math

import rclpy
from mavros_msgs.msg import State
from mavros_msgs.srv import MessageInterval
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


class SetMessageInterval(Node):
    def __init__(self):
        super().__init__('set_message_interval')

        self.message_id = self.declare_parameter('message_id', 105).value
        self.message_rate = self.declare_parameter('message_rate', 400.0).value
        self.request_timeout = self.declare_parameter(
            'request_timeout_sec', 10.0
        ).value
        state_topic = self.declare_parameter(
            'state_topic', '/mavros/state'
        ).value
        self.service_name = self.declare_parameter(
            'service_name', '/mavros/set_message_interval'
        ).value

        if not 0 <= self.message_id <= 16777215:
            raise ValueError('message_id must be in [0, 16777215]')
        if not math.isfinite(self.message_rate) or (
            self.message_rate < 0.0 and self.message_rate != -1.0
        ):
            raise ValueError('message_rate must be non-negative or -1.0')
        if not math.isfinite(self.request_timeout) or self.request_timeout <= 0.0:
            raise ValueError('request_timeout_sec must be finite and positive')

        self.connected = False
        state_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.subscription = self.create_subscription(
            State, state_topic, self.on_state, state_qos
        )
        self.client = self.create_client(MessageInterval, self.service_name)

    def on_state(self, msg):
        self.connected = msg.connected

    def configure(self):
        self.get_logger().info(
            f'Waiting for FCU connection and service {self.service_name}'
        )
        while rclpy.ok():
            if self.connected and self.client.service_is_ready():
                break
            rclpy.spin_once(self, timeout_sec=0.5)
        else:
            return 1

        request = MessageInterval.Request()
        request.message_id = self.message_id
        request.message_rate = self.message_rate

        self.get_logger().info(
            f'Requesting message {self.message_id}: '
            f'message_rate={self.message_rate}'
        )
        future = self.client.call_async(request)
        rclpy.spin_until_future_complete(
            self, future, timeout_sec=self.request_timeout
        )

        if not future.done():
            future.cancel()
            self.get_logger().error('MAVROS service response timed out')
            return 1

        try:
            response = future.result()
        except Exception as error:
            self.get_logger().error(f'MAVROS service call failed: {error}')
            return 1

        if response is None or not response.success:
            self.get_logger().error('MAVROS reported unsuccessful configuration')
            return 1

        self.get_logger().info('MAVROS reported successful configuration')
        return 0


def main(args=None):
    rclpy.init(args=args)
    node = None
    exit_code = 1

    try:
        node = SetMessageInterval()
        exit_code = node.configure()
    except (KeyboardInterrupt, ExternalShutdownException):
        exit_code = 0
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    raise SystemExit(exit_code)


if __name__ == '__main__':
    main()