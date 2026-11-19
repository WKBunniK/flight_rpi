#!/usr/bin/env python3
from collections import deque
from datetime import datetime
from pathlib import Path
import math
import shutil
import time

import cv2
import rclpy
from cv_bridge import CvBridge, CvBridgeError
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.clock import Clock, ClockType
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image


class CameraFrameSaver(Node):
    def __init__(self):
        super().__init__('camera_frame_saver')

        # Все параметры задаются при запуске.
        self.declare_parameter(
            'image_topic',
            '/usb_cam/image_raw',
            descriptor=ParameterDescriptor(read_only=True),
        )
        self.declare_parameter(
            'output_root',
            '/workspaces/flight_rpi/data/camera_frames',
            descriptor=ParameterDescriptor(read_only=True),
        )
        self.declare_parameter(
            'save_rate_hz',
            1.0,
            descriptor=ParameterDescriptor(read_only=True),
        )
        self.declare_parameter(
            'retention_seconds',
            300,
            descriptor=ParameterDescriptor(read_only=True),
        )
        self.declare_parameter(
            'min_free_mib',
            1024,
            descriptor=ParameterDescriptor(read_only=True),
        )

        topic = self.get_parameter('image_topic').value
        root = Path(self.get_parameter('output_root').value).expanduser()
        self.save_rate_hz = self.get_parameter('save_rate_hz').value
        self.retention_seconds = self.get_parameter('retention_seconds').value
        min_free_mib = self.get_parameter('min_free_mib').value

        if not math.isfinite(self.save_rate_hz) or self.save_rate_hz <= 0:
            raise ValueError('save_rate_hz must be finite and positive')

        if self.retention_seconds <= 0 or min_free_mib <= 0:
            raise ValueError(
                'retention_seconds and min_free_mib must be positive'
            )

        self.min_free_bytes = min_free_mib * 1024 * 1024

        # Каждый запуск создаёт новый каталог.
        # Существующие каталоги не открываем для записи или очистки.
        session = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        self.output_dir = root / session
        self.output_dir.mkdir(parents=True, exist_ok=False)

        self.bridge = CvBridge()
        self.latest_image = None
        self.saved_count = 0

        # Очередь содержит только время записи и путь к файлам,
        # успешно сохранённым этим экземпляром ноды.
        self.saved_files = deque()

        # Для выборочного сохранения достаточно последнего сообщения.
        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.subscription = self.create_subscription(
            Image,
            topic,
            self.on_image,
            qos,
        )

        # Монотонные часы не зависят от перевода системного времени.
        self.save_clock = Clock(clock_type=ClockType.STEADY_TIME)

        self.save_timer = self.create_timer(
            1.0 / self.save_rate_hz,
            self.save_frame,
            clock=self.save_clock,
        )

        # Очистка работает раз в секунду независимо от частоты
        # сохранения и наличия сообщений от камеры.
        self.cleanup_timer = self.create_timer(
            1.0,
            self.cleanup_expired,
            clock=self.save_clock,
        )

        self.get_logger().info(
            f'Saving from {topic} at {self.save_rate_hz:g} Hz; '
            f'retention={self.retention_seconds}s; '
            f'min_free={min_free_mib} MiB; '
            f'current session only: {self.output_dir}'
        )

    def on_image(self, msg):
        # Получение кадра не вызывает преобразование или запись на диск.
        self.latest_image = msg

    def cleanup_expired(self):
        cutoff = time.monotonic() - self.retention_seconds

        # Никакого обхода каталогов: только собственная очередь файлов.
        while self.saved_files and self.saved_files[0][0] <= cutoff:
            _, path = self.saved_files[0]

            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                self.get_logger().error(
                    f'Cleanup failed; skipping save: {exc}',
                    throttle_duration_sec=5.0,
                )
                return False

            self.saved_files.popleft()

        return True

    def save_frame(self):
        # Дополнительная очистка перед записью.
        # Если удалить просроченные файлы не удалось, объём не увеличиваем.
        if not self.cleanup_expired():
            return

        msg = self.latest_image
        if msg is None:
            self.get_logger().warning(
                'No new image; skipping save',
                throttle_duration_sec=5.0,
            )
            return

        # Повторно сохранять это же сообщение без новых кадров не будем.
        self.latest_image = None

        stamp = msg.header.stamp
        filename = (
            f'frame_{self.saved_count + 1:06d}_'
            f'{stamp.sec}_{stamp.nanosec:09d}.png'
        )
        destination = self.output_dir / filename
        temporary = destination.with_suffix('.png.tmp')

        try:
            # OpenCV ожидает BGR. Размер изображения не меняем.
            frame = self.bridge.imgmsg_to_cv2(
                msg,
                desired_encoding='bgr8',
            )

            # PNG без потерь. Сначала кодируем в памяти,
            # чтобы узнать размер предстоящей записи.
            encoded_ok, png = cv2.imencode(
                '.png',
                frame,
                [cv2.IMWRITE_PNG_COMPRESSION, 1],
            )
            if not encoded_ok:
                raise OSError('PNG encoding failed')

            free_bytes = shutil.disk_usage(self.output_dir).free

            # Резерв + PNG + небольшой запас на файловую систему.
            required_bytes = (
                self.min_free_bytes + png.nbytes + 1024 * 1024
            )

            if free_bytes < required_bytes:
                self.get_logger().warning(
                    f'Not enough free disk space: '
                    f'{free_bytes / (1024 * 1024):.0f} MiB; skipping save',
                    throttle_duration_sec=5.0,
                )
                return

            # Итоговое имя появляется после завершения записи.
            with temporary.open('xb') as stream:
                stream.write(png.tobytes())

            temporary.replace(destination)

            # Только этот файл становится кандидатом на автоудаление.
            self.saved_files.append((time.monotonic(), destination))

        except (CvBridgeError, cv2.error, OSError) as exc:
            self.get_logger().error(f'Frame save failed: {exc}')

            # Удаляем только временный файл собственной попытки записи.
            try:
                temporary.unlink(missing_ok=True)
            except OSError as cleanup_error:
                self.get_logger().error(
                    f'Cannot remove partial file: {cleanup_error}'
                )
            return

        self.saved_count += 1
        self.get_logger().info(
            f'Saved {filename} ({msg.width}x{msg.height})'
        )


def main(args=None):
    rclpy.init(args=args)
    node = None

    try:
        node = CameraFrameSaver()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        # При остановке оставшиеся фотографии сохраняются.
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()