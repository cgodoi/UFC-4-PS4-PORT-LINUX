#!/usr/bin/env bash
# Builds the port inside the docker/Dockerfile image and stages a runnable folder in
# out/dev/UFC4Native (scripts/package-dev.sh). Needs only Docker on the host.
#   bash scripts/build-docker.sh            # build + package
#   IMAGE=name LTO=ON bash scripts/build-docker.sh
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
image=${IMAGE:-ufc4-port-build}
docker image inspect "$image" >/dev/null 2>&1 || docker build -t "$image" docker/
git submodule update --init --recursive
mkdir -p out          # a fresh checkout has none; the build log goes there
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/src -w /src "$image" bash -c '
    git config --global --add safe.directory "*"
    BB_LTO='"${LTO:-OFF}"' bash build.sh > out/build.log 2>&1 || { grep -E "error|Error" out/build.log | head -30; exit 1; }
    tail -2 out/build.log
    bash scripts/package-dev.sh'
