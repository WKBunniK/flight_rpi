#!/usr/bin/env python3
from datetime import datetime
from pathlib import Path
import time

import cv2
import numpy as np
import rclpy
import yaml
from cv_bridge import CvBridge
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image


TOPIC = "/usb_cam/image_raw"
BOARD = (10, 7)          # Внутренние углы доски из 11 × 8 клеток.
SQUARE_M = 0.025         # Сторона клетки, метры.
IMAGE_SIZE = (640, 480)  # Калибруем именно рабочее разрешение.
MIN_VIEWS = 20           # Защита от расчёта по слишком малой выборке.
ROOT = Path("/workspaces/flight_rpi/ros2_ws/log")


def board_distance(a, b):
    """Среднее смещение углов, учитывая обратный порядок нумерации."""
    return min(
        np.linalg.norm(a - b, axis=-1).mean(),
        np.linalg.norm(a - b[::-1], axis=-1).mean(),
    )


class Collector(Node):
    def __init__(self):
        super().__init__("camera_calibration_headless")
        self.bridge = CvBridge()
        self.points = []
        self.next_check = 0.0

        # Каждый запуск сохраняется отдельно, прежние результаты остаются.
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.output = ROOT / f"camera_calibration_{stamp}"
        self.output.mkdir(parents=True)

        # Обрабатываем свежие кадры, без накопления очереди.
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.subscription = self.create_subscription(
            Image, TOPIC, self.on_image, qos
        )
        print(f"Ожидаю изображения: {TOPIC}", flush=True)
        print(f"Данные: {self.output}", flush=True)
        print("После 30–40 разных положений нажми Ctrl+C для расчёта.")

    def on_image(self, msg):
        now = time.monotonic()
        if now < self.next_check:
            return
        self.next_check = now + 1.0  # Проверяем примерно один кадр в секунду.

        if (msg.width, msg.height) != IMAGE_SIZE:
            raise RuntimeError(
                f"Ожидалось {IMAGE_SIZE}, получено {(msg.width, msg.height)}"
            )

        gray = self.bridge.imgmsg_to_cv2(msg, desired_encoding="mono8")

        # SB сразу определяет углы с субпиксельной точностью.
        found, corners = cv2.findChessboardCornersSB(
            gray, BOARD, flags=cv2.CALIB_CB_NORMALIZE_IMAGE
        )
        if not found:
            print("Доска целиком не найдена.", flush=True)
            return

        # Простая эвристика: не собирать почти одинаковые изображения.
        if any(board_distance(corners, old) < 20.0 for old in self.points):
            print("Похожее положение уже есть. Измени ракурс или расстояние.",
                  flush=True)
            return

        number = len(self.points) + 1
        filename = self.output / f"frame_{number:03d}.png"
        if not cv2.imwrite(str(filename), gray):
            raise RuntimeError(f"Не удалось сохранить {filename}")

        self.points.append(corners.astype(np.float32))
        print(f"Принят кадр {number}.", flush=True)

    def calibrate(self):
        count = len(self.points)
        if count < MIN_VIEWS:
            print(f"Получено {count} кадров, нужно минимум {MIN_VIEWS}.")
            print(f"Снятые изображения сохранены в {self.output}")
            return

        # Известные координаты углов на плоскости доски: Z = 0.
        object_points = np.zeros((BOARD[0] * BOARD[1], 3), np.float32)
        object_points[:, :2] = (
            np.mgrid[0:BOARD[0], 0:BOARD[1]].T.reshape(-1, 2) * SQUARE_M
        )

        print("Вычисляю калибровку...", flush=True)
        rms, k, d, _, _, _, _, errors = cv2.calibrateCameraExtended(
            [object_points.copy() for _ in self.points],
            self.points,
            IMAGE_SIZE,
            None,
            None,
            flags=cv2.CALIB_FIX_K3,
        )

        if not (
            np.isfinite(rms)
            and np.isfinite(k).all()
            and np.isfinite(d).all()
        ):
            raise RuntimeError("Получены некорректные параметры калибровки.")

        # Формат отдельного файла камеры для VINS-Fusion.
        result = {
            "model_type": "PINHOLE",
            "camera_name": "flight_camera",
            "image_width": IMAGE_SIZE[0],
            "image_height": IMAGE_SIZE[1],
            "distortion_parameters": {
                name: float(value)
                for name, value in zip(
                    ("k1", "k2", "p1", "p2"), d.ravel()[:4]
                )
            },
            "projection_parameters": {
                "fx": float(k[0, 0]),
                "fy": float(k[1, 1]),
                "cx": float(k[0, 2]),
                "cy": float(k[1, 2]),
            },
        }

        filename = self.output / "flight_camera_vins.yaml"
        with filename.open("w", encoding="utf-8") as stream:
            # Заголовок для OpenCV FileStorage, которым пользуется VINS.
            stream.write("%YAML:1.0\n---\n")
            stream.write(f"# views: {count}\n# rms_px: {rms:.6f}\n")
            yaml.safe_dump(result, stream, sort_keys=False)

        worst = int(np.argmax(errors))
        print(f"\nКадров: {count}")
        print(f"Общая RMS-ошибка: {rms:.3f} px")
        print(f"Максимальная ошибка кадра: {errors.max():.3f} px")
        print(f"Кадр с максимальной ошибкой: frame_{worst + 1:03d}.png")
        print("K:\n", k)
        print("D [k1, k2, p1, p2, k3]:", d.ravel())
        print(f"Результат: {filename}")


def main():
    cv2.setNumThreads(2)
    rclpy.init()
    node = Collector()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    # Расчёт выполняется после завершения приёма ROS-сообщений.
    node.calibrate()


if __name__ == "__main__":
    main()n