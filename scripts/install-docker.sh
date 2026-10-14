#!/usr/bin/env bash
set -euo pipefail
if [[ "$(id -u)" -ne 0 ]]; then
    printf '%s\n' 'Run: sudo bash scripts/install-docker.sh' >&2
    exit 1
fi
source /etc/os-release
host_arch="$(dpkg --print-architecture)"
if [[ "$host_arch" != arm64 ]]; then
    printf '%s\n' 'This setup requires 64-bit Raspberry Pi OS (arm64).' >&2
    exit 1
fi
if [[ "${ID:-}" != debian && "${ID:-}" != raspbian ]]; then
    printf '%s\n' 'This installer targets Debian-based Raspberry Pi OS.' >&2
    exit 1
fi
case "${VERSION_CODENAME:-}" in
    bookworm|trixie) ;;
    *) printf 'Unsupported Debian release: %s\n' "${VERSION_CODENAME:-unknown}" >&2; exit 1 ;;
esac
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
    for package in docker.io docker-compose docker-compose-v2 docker-doc podman-docker containerd runc; do
        if dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q '^install ok installed$'; then
            printf 'Conflicting package installed: %s. Review Docker Debian installation instructions first.\n' "$package" >&2
            exit 1
        fi
    done
    apt-get update
    apt-get install -y ca-certificates curl
    install -m 0755 -d /etc/apt/keyrings
    curl --fail --silent --show-error --location --retry 3 \
      https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: ${VERSION_CODENAME}
Components: stable
Architectures: ${host_arch}
Signed-By: /etc/apt/keyrings/docker.asc
EOF
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != root ]]; then
    usermod -aG docker "$SUDO_USER"
    printf 'Added %s to docker group. Open a fresh SSH/VS Code session before using Docker without sudo.\n' "$SUDO_USER"
fi
docker version
docker compose version
