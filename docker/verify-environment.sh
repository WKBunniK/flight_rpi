#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import importlib
import platform
from importlib.metadata import version

print("Architecture:", platform.machine())
assert platform.machine() == "aarch64", "Expected Raspberry Pi ARM64"
for name in ("rclpy", "cv_bridge", "numpy", "scipy", "cv2", "yaml", "pyproj", "geographiclib.geodesic", "serial", "transforms3d", "pymavlink", "nav_msgs.msg", "sensor_msgs.msg", "mavros_msgs.msg"):
    importlib.import_module(name)
    print("Import OK:", name)
for name in ("pymavlink", "MAVProxy"):
    print(name, version(name))
PY
for package in mavros mavros_extras foxglove_bridge usb_cam v4l2_camera rosbag2_storage_mcap rmw_cyclonedds_cpp; do
    ros2 pkg prefix "$package"
done
test -s /usr/share/GeographicLib/geoids/egm96-5.pgm
tmux -V
zsh --version
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT
cmake -S /opt/flight-checks -B "$temp_dir/build" -DCeres_DIR="$Ceres_DIR"
cmake --build "$temp_dir/build" --parallel 1
"$temp_dir/build/flight_ceres_probe"
printf '%s\n' 'Environment checks passed.'
