#!/usr/bin/env bash
set -euo pipefail
mkdir -p /workspaces/flight_rpi/ros2_ws/src /home/flight/.history
if ! tmux has-session -t flight 2>/dev/null; then
    tmux new-session -d -s flight -n shell -c /workspaces/flight_rpi
    tmux new-window -t flight -n ros -c /workspaces/flight_rpi/ros2_ws
    tmux new-window -t flight -n devices -c /workspaces/flight_rpi
    tmux select-window -t flight:0
fi
exec sleep infinity
