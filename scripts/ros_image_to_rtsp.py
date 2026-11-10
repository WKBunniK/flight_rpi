#!/usr/bin/env python3
"""Публикация ROS Image в виде RTSP-потока H.264."""

import subprocess

import rclpy
from cv_bridge import CvBridge
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image


TOPIC = '/usb_cam/image_raw'
RTSP_URL = 'rtsp://127.0.0.1:8554/camera'
WIDTH, HEIGHT, FPS = 640, 480, 30


class ImageToRtsp(Node):
    def __init__(self):
        super().__init__('camera_rtsp')
        self.bridge = CvBridge()
        self.encoder = None

        # При перегрузке оставляем только последний ожидающий кадр.
        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.subscription = self.create_subscription(
            Image, TOPIC, self.on_image, qos
        )

        self.get_logger().info(
            f'Waiting for {TOPIC}; destination: {RTSP_URL}'
        )

    def on_image(self, message):
        frame = self.bridge.imgmsg_to_cv2(
            message, desired_encoding='rgb8'
        )

        # Формат входа должен совпадать с описанием rawvideo ниже.
        if frame.shape != (HEIGHT, WIDTH, 3):
            raise RuntimeError(
                f'Unexpected image shape: {frame.shape}'
            )

        # Запускаем кодировщик при поступлении первого изображения.
        if self.encoder is None:
            command = [
                'ffmpeg', '-hide_banner', '-loglevel', 'warning',
                '-thread_queue_size', '1',

                # На stdin поступают несжатые RGB-кадры.
                '-f', 'rawvideo', '-pixel_format', 'rgb24',
                '-video_size', f'{WIDTH}x{HEIGHT}',
                '-framerate', str(FPS), '-i', 'pipe:0',

                # Программное кодирование H.264.
                '-an', '-c:v', 'libx264',
                '-preset', 'ultrafast', '-tune', 'zerolatency',
                '-pix_fmt', 'yuv420p',
                '-b:v', '1000k',
                '-maxrate', '1000k',
                '-bufsize', '100k',
                '-g', '15', '-keyint_min', '15',
                '-bf', '0', '-sc_threshold', '0',
                '-threads', '2',

                # Публикация в локальный RTSP-сервер.
                '-flush_packets', '1', '-muxdelay', '0',
                '-f', 'rtsp', '-rtsp_transport', 'tcp',
                RTSP_URL,
            ]

            self.encoder = subprocess.Popen(
                command, stdin=subprocess.PIPE
            )
            self.get_logger().info(
                'FFmpeg started: H.264, 640x480, 30 fps'
            )

        if self.encoder.poll() is not None:
            raise RuntimeError(
                f'FFmpeg exited: {self.encoder.returncode}'
            )

        # tobytes() также убирает возможные отступы между строками.
        self.encoder.stdin.write(frame.tobytes())
        self.encoder.stdin.flush()

    def close_encoder(self):
        if self.encoder is None:
            return

        if self.encoder.poll() is None:
            self.encoder.terminate()
            try:
                self.encoder.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.encoder.kill()
                self.encoder.wait()

        try:
            self.encoder.stdin.close()
        except BrokenPipeError:
            pass


def main():
    rclpy.init()
    node = ImageToRtsp()
    result = 0

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except (OSError, RuntimeError) as error:
        if rclpy.ok():
            node.get_logger().error(str(error))
            result = 1
    finally:
        node.close_encoder()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    return result


if __name__ == '__main__':
    raise SystemExit(main())