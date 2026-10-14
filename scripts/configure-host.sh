#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
if [[ "$(id -u)" -eq 0 ]]; then
    printf '%s\n' 'Run this script as your normal Raspberry Pi user, without sudo.' >&2
    exit 1
fi
if [[ "$(dpkg --print-architecture)" != arm64 ]]; then
    printf '%s\n' 'Expected arm64 host.' >&2
    exit 1
fi
host_uid="$(id -u)"
host_gid="$(id -g)"
if ! getent group plugdev >/dev/null; then
    sudo groupadd --system plugdev
fi
group_id() {
    local value
    value="$(getent group "$1" | cut -d: -f3 || true)"
    printf '%s' "${value:-$host_gid}"
}
if [[ ! -f .env ]]; then
    cat > .env <<EOF
ROS_BASE_IMAGE=ros:jazzy-ros-base-noble
HOST_UID=${host_uid}
HOST_GID=${host_gid}
HOST_DIALOUT_GID=$(group_id dialout)
HOST_VIDEO_GID=$(group_id video)
HOST_PLUGDEV_GID=$(group_id plugdev)
HOST_INPUT_GID=$(group_id input)
ROS_DOMAIN_ID=42
FOXGLOVE_PORT=8765
BUILD_JOBS=2
EOF
    chmod 0600 .env
    printf '%s\n' 'Created .env with host UID/GID and device groups.'
else
    printf '%s\n' 'Existing .env preserved. Check UID/GID values against id.'
fi
touch .gitignore
while IFS= read -r pattern; do
    if [[ -n "$pattern" ]] && ! grep -qxF -- "$pattern" .gitignore; then
        printf '\n%s\n' "$pattern" >> .gitignore
    fi
done < .gitignore.container
mkdir -p ros2_ws/src config
printf '%s\n' 'Prepared ros2_ws/src and config. Added container ignore rules.'
