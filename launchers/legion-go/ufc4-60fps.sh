#!/usr/bin/env bash
# UFC 4 at 60 FPS on an AMD handheld (tested: Legion Go, Bazzite): the PC memory model, 720p
# internal rendering (FSR to the screen size), no diagnostics, and the port's frame-deadline GPU
# clock governor. Needs a GTT of ~7 GiB (see docs/ufc4/README.md, "Handhelds").
export BB_FLIP_RATE=0 BB_VBLANK_HZ=60 BB_PC_MODEL=1
export BB_INTERNAL_WIDTH=${BB_INTERNAL_WIDTH:-1280} BB_INTERNAL_HEIGHT=${BB_INTERNAL_HEIGHT:-720}
export BB_SAVE_LOG=${BB_SAVE_LOG:-0}
export BB_GPU_GOVERNOR=${BB_GPU_GOVERNOR:-1}
exec "$(dirname -- "$(readlink -f -- "$0")")/ufc4.sh" "$@"
