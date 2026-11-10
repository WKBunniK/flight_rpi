#!/usr/bin/env python3
"""Check sensor timestamps in an MCAP rosbag without replaying it."""

import argparse

import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import Image, Imu


TOPICS = {
    "/usb_cam/image_raw": (Image, 30.0),
    "/mavros/imu/data_raw": (Imu, 200.0),
}


def ms_summary(values_ns):
    # В float переводим только интервалы.
    # Абсолютные метки времени храним целыми, сохраняя наносекунды.
    values_ms = np.asarray(values_ns, dtype=np.int64) / 1_000_000.0
    percentiles = np.percentile(values_ms, [0, 50, 99, 100])
    return " / ".join(f"{value:.3f}" for value in percentiles)


def summarize(rows, expected_hz):
    timestamps = np.asarray(rows, dtype=np.int64)
    stamps = timestamps[:, 0]
    bag_times = timestamps[:, 1]

    # Сохраняем порядок чтения: сортировка скрыла бы движение времени назад.
    dt = np.diff(stamps)
    valid_order = bool(np.all(dt > 0))

    return {
        "count": len(stamps),
        "zero": int(np.count_nonzero(stamps == 0)),
        "duplicates": int(np.count_nonzero(dt == 0)),
        "backward": int(np.count_nonzero(dt < 0)),
        # Превышение порога подозрительно, но само по себе не доказывает потерю.
        "long_gaps": int(np.count_nonzero(dt > 1.5e9 / expected_hz)),
        "hz": (
            (len(stamps) - 1) * 1e9 / int(stamps[-1] - stamps[0])
            if valid_order else float("nan")
        ),
        "dt_ms": ms_summary(dt),
        "bag_dt_ms": ms_summary(np.diff(bag_times)),
        "age_ms": ms_summary(bag_times - stamps),
        "first": int(stamps[0]),
        "last": int(stamps[-1]),
    }


def format_stamp(ns):
    return f"{ns // 1_000_000_000}.{ns % 1_000_000_000:09d}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bag", help="Directory containing metadata.yaml")
    args = parser.parse_args()

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=args.bag, storage_id="mcap"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )

    rows = {topic: [] for topic in TOPICS}

    while reader.has_next():
        topic, raw, bag_time_ns = reader.read_next()
        if topic not in TOPICS:
            continue

        message_type, _ = TOPICS[topic]
        message = deserialize_message(raw, message_type)
        stamp = message.header.stamp
        stamp_ns = stamp.sec * 1_000_000_000 + stamp.nanosec

        # Изображения не накапливаем: сохраняем только временные метки.
        rows[topic].append((stamp_ns, int(bag_time_ns)))

    for topic, (_, expected_hz) in TOPICS.items():
        print(f"\n{topic}")

        if len(rows[topic]) < 2:
            print(f"Недостаточно сообщений: {len(rows[topic])}")
            continue

        stats = summarize(rows[topic], expected_hz)
        print(f"messages={stats['count']}; header_rate={stats['hz']:.3f} Hz")
        print(
            f"header_range: {format_stamp(stats['first'])} -> "
            f"{format_stamp(stats['last'])}"
        )
        print(
            f"zero_stamps={stats['zero']}; "
            f"duplicate_steps={stats['duplicates']}; "
            f"backward_steps={stats['backward']}"
        )
        print("Статистика в мс: min / median / p99 / max")
        print(f"  header_dt:          {stats['dt_ms']}")
        print(f"  bag_dt:             {stats['bag_dt_ms']}")
        print(f"  bag_time - header:  {stats['age_ms']}")
        print(
            f"header_dt > {1500 / expected_hz:.3f} ms: "
            f"{stats['long_gaps']}"
        )


if __name__ == "__main__":
    main()