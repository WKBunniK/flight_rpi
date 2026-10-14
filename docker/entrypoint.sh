#!/usr/bin/env bash
set -e
source /opt/ros/jazzy/setup.bash
export PATH="/opt/flight-venv/bin:${PATH}"
export VIRTUAL_ENV=/opt/flight-venv
export CMAKE_PREFIX_PATH="/opt/ceres/2.1.0:${CMAKE_PREFIX_PATH:-}"
export Ceres_DIR=/opt/ceres/2.1.0/lib/cmake/Ceres
if [[ -f /workspaces/flight_rpi/ros2_ws/install/setup.bash ]]; then
    source /workspaces/flight_rpi/ros2_ws/install/setup.bash
fi
exec "$@"
