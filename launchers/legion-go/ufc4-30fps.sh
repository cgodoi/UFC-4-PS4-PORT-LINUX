#!/usr/bin/env bash
# UFC 4 at the console's 30 FPS with the PC memory model and the GPU governor: the coolest option.
export BB_PC_MODEL=1 BB_GPU_GOVERNOR=${BB_GPU_GOVERNOR:-1}
export BB_SAVE_LOG=${BB_SAVE_LOG:-0}
exec "$(dirname -- "$(readlink -f -- "$0")")/ufc4.sh" "$@"
