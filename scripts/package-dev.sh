#!/usr/bin/env bash
# Stages out/dev/UFC4Native from the current build (run inside the docker/Dockerfile image, or on
# a host with the same libraries): the binaries with their non-system libraries in bin/lib (fmt,
# miniz, xxhash, Zydis, SDL3, libstdc++, libgcc_s) and relative rpaths; glibc, Vulkan and the
# window system come from the system. Copy the folder anywhere and run ./ufc3.sh --play <game>.
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
[[ -f out/sacredfire && -f out/gpu/libbbgpu.so ]] || { echo 'Build first: bash build.sh' >&2; exit 1; }
stage=out/dev/UFC4Native
rm -rf out/dev; mkdir -p "$stage/bin/gpu" "$stage/bin/lib" "$stage/scripts" "$stage/tools" "$stage/share" "$stage/patches" "$stage/launcher"
install -m755 out/sacredfire out/bb-gpu-capabilities "$stage/bin/"
install -m755 out/gpu/libbbgpu.so "$stage/bin/gpu/"
strip --strip-debug "$stage/bin/sacredfire" "$stage/bin/bb-gpu-capabilities" "$stage/bin/gpu/libbbgpu.so"
ldd out/sacredfire out/gpu/libbbgpu.so > out/dev/ldd.txt || true
for lib in libfmt.so libminiz.so libxxhash.so libZydis.so libSDL3.so libstdc++.so.6 libgcc_s.so.1; do
    path=$(awk -v l="$lib" 'index($1, l) == 1 && !found {print $3; found = 1}' out/dev/ldd.txt)
    [[ -n $path ]] || { echo "package-dev: $lib not found" >&2; exit 1; }
    cp -L "$path" "$stage/bin/lib/$(basename "$path")"
done
patchelf --set-rpath '$ORIGIN/gpu:$ORIGIN/lib' "$stage/bin/sacredfire"
patchelf --set-rpath '$ORIGIN/lib' "$stage/bin/bb-gpu-capabilities"
patchelf --set-rpath '$ORIGIN/../lib' "$stage/bin/gpu/libbbgpu.so"
for f in "$stage"/bin/lib/*.so*; do patchelf --set-rpath '$ORIGIN' "$f"; done
install -m755 run.sh packaging/linux/ufc3.sh packaging/linux/UFC3.sh "$stage/"
cp launcher/*.py "$stage/launcher/"
cp packaging/linux/ufc3.conf.example LICENSE "$stage/"
cp out/VERSION "$stage/VERSION"
cp scripts/*.py "$stage/scripts/"; cp tools/*.py "$stage/tools/"
find patches -maxdepth 1 -type f -name '*.xml' -exec cp {} "$stage/patches/" \;
cp share/skip_movie.mkv "$stage/share/"
# shadPS4's import name list (aerolib), fetched by tools/gen_import_names.py when missing.
[[ -f out/aerolib.inl ]] && cp out/aerolib.inl "$stage/share/"
echo "package-dev: $stage"
