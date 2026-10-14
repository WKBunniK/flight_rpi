#!/usr/bin/env bash
set -e
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH PYTHONPATH LD_LIBRARY_PATH
export PATH=/opt/flight-venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
source /opt/ros/jazzy/setup.bash
export CMAKE_PREFIX_PATH="/opt/ceres/2.1.0:${CMAKE_PREFIX_PATH:-}"
export Ceres_DIR=/opt/ceres/2.1.0/lib/cmake/Ceres
export CMAKE_BUILD_PARALLEL_LEVEL="${CMAKE_BUILD_PARALLEL_LEVEL:-2}"
cd /workspaces/flight_rpi/ros2_ws
exec colcon build --symlink-install --executor sequential \
    --cmake-args -DCMAKE_BUILD_TYPE=Release -DCeres_DIR="$Ceres_DIR" "$@"
