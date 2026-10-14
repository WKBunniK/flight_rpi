# syntax=docker/dockerfile:1
ARG ROS_BASE_IMAGE=ros:jazzy-ros-base-noble
FROM ${ROS_BASE_IMAGE}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ARG HOST_UID=1000
ARG HOST_GID=1000
ARG BUILD_JOBS=2
ARG CERES_VERSION=2.1.0

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/flight-venv \
    GEOGRAPHICLIB_DATA=/usr/share/GeographicLib \
    OPENBLAS_NUM_THREADS=1

COPY docker/apt-packages.txt /tmp/flight-apt-packages.txt
RUN apt-get update \
    && xargs -r apt-get install -y --no-install-recommends < /tmp/flight-apt-packages.txt \
    && rm -rf /var/lib/apt/lists/* /tmp/flight-apt-packages.txt

RUN curl --fail --location --retry 3 \
      "https://github.com/ceres-solver/ceres-solver/archive/refs/tags/${CERES_VERSION}.tar.gz" \
      -o /tmp/ceres.tar.gz \
    && mkdir /tmp/ceres-src \
    && tar -xzf /tmp/ceres.tar.gz -C /tmp/ceres-src --strip-components=1 \
    && cmake -S /tmp/ceres-src -B /tmp/ceres-build -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_INSTALL_PREFIX=/opt/ceres/${CERES_VERSION} \
      -DCMAKE_INSTALL_LIBDIR=lib \
      -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
      -DBUILD_SHARED_LIBS=ON \
      -DBUILD_TESTING=OFF \
      -DBUILD_EXAMPLES=OFF \
      -DBUILD_BENCHMARKS=OFF \
      -DCUDA=OFF \
      -DSUITESPARSE=OFF \
      -DCXSPARSE=OFF \
      -DEIGENSPARSE=ON \
      -DLAPACK=ON \
    && cmake --build /tmp/ceres-build --parallel "${BUILD_JOBS}" \
    && cmake --install /tmp/ceres-build \
    && printf '%s\n' "/opt/ceres/${CERES_VERSION}/lib" > /etc/ld.so.conf.d/flight-ceres.conf \
    && ldconfig \
    && rm -rf /tmp/ceres-src /tmp/ceres-build /tmp/ceres.tar.gz

COPY docker/python-requirements.txt /tmp/flight-python-requirements.txt
RUN python3 -m venv --system-site-packages /opt/flight-venv \
    && /opt/flight-venv/bin/python -m pip install --no-cache-dir -r /tmp/flight-python-requirements.txt \
    && rm /tmp/flight-python-requirements.txt \
    && geographiclib-get-geoids egm96-5 \
    && test -s /usr/share/GeographicLib/geoids/egm96-5.pgm \
    && if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then rosdep init; fi

RUN if id ubuntu >/dev/null 2>&1; then userdel ubuntu; fi \
    && if ! getent group "${HOST_GID}" >/dev/null; then groupadd --gid "${HOST_GID}" flight; fi \
    && useradd --uid "${HOST_UID}" --gid "${HOST_GID}" --create-home --shell /usr/bin/zsh flight \
    && printf '%s\n' 'flight ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/flight \
    && chmod 0440 /etc/sudoers.d/flight \
    && visudo -cf /etc/sudoers.d/flight \
    && mkdir -p /home/flight/.history /home/flight/.vscode-server /workspaces/flight_rpi \
    && chown -R "${HOST_UID}:${HOST_GID}" /home/flight /workspaces /opt/flight-venv

COPY docker/entrypoint.sh /usr/local/bin/flight-entrypoint
COPY docker/start-dev.sh /usr/local/bin/flight-start-dev
COPY docker/colcon-wrapper.sh /usr/local/bin/colcon
COPY docker/verify-environment.sh /usr/local/bin/flight-verify
COPY docker/build-workspace.sh /usr/local/bin/flight-build
COPY docker/checks/ /opt/flight-checks/
COPY --chown=flight docker/zshrc /home/flight/.zshrc
COPY --chown=flight docker/bashrc /home/flight/.bashrc
COPY --chown=flight docker/tmux.conf /home/flight/.tmux.conf
RUN chmod 0755 /usr/local/bin/flight-entrypoint /usr/local/bin/flight-start-dev \
      /usr/local/bin/colcon /usr/local/bin/flight-verify /usr/local/bin/flight-build \
    && mkdir -p /opt/flight-build \
    && dpkg-query -W > /opt/flight-build/apt-packages.tsv \
    && /opt/flight-venv/bin/python -m pip freeze > /opt/flight-build/python-packages.txt

ENV PATH=/opt/flight-venv/bin:${PATH} \
    Ceres_DIR=/opt/ceres/2.1.0/lib/cmake/Ceres \
    HOME=/home/flight
USER flight
WORKDIR /workspaces/flight_rpi
EXPOSE 8765/tcp 14540/udp 14550/udp
ENTRYPOINT ["/usr/local/bin/flight-entrypoint"]
CMD ["/usr/local/bin/flight-start-dev"]
