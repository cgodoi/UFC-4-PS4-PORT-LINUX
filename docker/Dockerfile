# Linux build environment for the UFC 4 port (also builds UFC 3): Ubuntu 26.04 with the libraries
# Ubuntu lacks or ships too old built from source: miniz 3, Vulkan-Headers 1.4.365 (the renderer
# uses recent extensions) and SDL 3.4.18 (its audio/video backends are loaded at run time, so the
# packaged library has no hard dependency on the build machine's PulseAudio, X11 or Wayland).
# The binaries need glibc 2.43 or newer (Ubuntu 26.04, Bazzite/Fedora 44, Arch).
#   docker build -t ufc4-port-build docker/      then      bash scripts/build-docker.sh
FROM ubuntu:26.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake ninja-build pkg-config python3 git ca-certificates patchelf \
    libvulkan-dev glslang-tools spirv-headers libboost-dev libfmt-dev libzydis-dev libxxhash-dev \
    robin-map-dev libx11-dev libxcb1-dev libwayland-dev wayland-protocols libxkbcommon-dev \
    libxext-dev libxrandr-dev libxcursor-dev libxi-dev libxss-dev libxfixes-dev libxtst-dev \
    libpipewire-0.3-dev libpulse-dev libasound2-dev libudev-dev libdbus-1-dev libdrm-dev libgbm-dev \
    libdecor-0-dev libegl-dev \
 && rm -rf /var/lib/apt/lists/*
RUN git clone -q --depth 1 --branch 3.1.0 https://github.com/richgel999/miniz.git /tmp/miniz \
 && cmake -S /tmp/miniz -B /tmp/miniz/b -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON \
      -DBUILD_EXAMPLES=OFF -DBUILD_TESTS=OFF -DCMAKE_INSTALL_PREFIX=/usr/local -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
 && ninja -C /tmp/miniz/b install && rm -rf /tmp/miniz
RUN git clone -q --depth 1 --branch v1.4.365 https://github.com/KhronosGroup/Vulkan-Headers.git /tmp/vkh \
 && cmake -S /tmp/vkh -B /tmp/vkh/b -G Ninja -DCMAKE_INSTALL_PREFIX=/usr && ninja -C /tmp/vkh/b install && rm -rf /tmp/vkh
RUN git clone -q --depth 1 --branch release-3.4.18 https://github.com/libsdl-org/SDL.git /tmp/sdl \
 && cmake -S /tmp/sdl -B /tmp/sdl/b -G Ninja -DCMAKE_BUILD_TYPE=Release -DSDL_SHARED=ON -DSDL_STATIC=OFF \
      -DSDL_TESTS=OFF -DSDL_EXAMPLES=OFF -DCMAKE_INSTALL_PREFIX=/usr/local \
 && ninja -C /tmp/sdl/b install && rm -rf /tmp/sdl && ldconfig
