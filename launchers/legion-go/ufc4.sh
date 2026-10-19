#!/usr/bin/env bash
# UFC 4 on the native port — base launcher: fullscreen, FSR 1, the game paces itself.
# Set UFC4_DIR (the folder holding UFC4Native/ and CUSA14204-merged/) and BB_DATA_DIR as needed.
root=${UFC4_DIR:-$(dirname -- "$(readlink -f -- "$0")")}
cd "$root/UFC4Native"
export BB_DATA_DIR=${BB_DATA_DIR:-$root/data}
export BB_FULLSCREEN=${BB_FULLSCREEN:-1}
export BB_FPS_LIMIT=${BB_FPS_LIMIT:-0}  # the game paces itself
export BB_PRESENT_MODE=${BB_PRESENT_MODE:-Fifo}
export BB_FSR1=${BB_FSR1:-1} BB_RCAS=${BB_RCAS:-1}
export BB_LANGUAGE=${BB_LANGUAGE:-20}
export BB_USER_NAME=${BB_USER_NAME:-Player 1}
game=("${UFC4_GAME:-$root/CUSA14204-merged}")

# GPU clock while the game runs. BB_GPU_GOVERNOR=1: the port's frame-deadline governor sets the
# GPU minimum itself (gpu/shim/bbport_gpu_governor.cpp). Else BB_GPU_MIN_MHZ (0 = leave it alone):
# a fixed minimum, re-applied every 2 s because Steam resets the GPU to auto. Either way the
# previous setting is restored when the game exits (also when Steam closes it).
gpu=$(ls -d /sys/class/drm/card*/device 2>/dev/null | while read d; do [ -w "$d/pp_od_clk_voltage" ] && echo "$d" && break; done)
min=${BB_GPU_MIN_MHZ:-1600}
[[ ${BB_GPU_GOVERNOR:-0} == 1 ]] && min=-1
if [[ -z $gpu || $min -eq 0 ]]; then exec ./ufc3.sh --play "${game[@]}" "$@"; fi
od_value() { awk -v n="$1" '/^OD_SCLK/{f=1;next} /^OD_RANGE/{f=0} f&&$1==n":"{print int($2)}' "$gpu/pp_od_clk_voltage"; }
old_level=$(cat "$gpu/power_dpm_force_performance_level"); old_min=$(od_value 0); old_max=$(od_value 1)
max=$(awk '/^SCLK:/{print int($3)}' "$gpu/pp_od_clk_voltage"); max=${max:-2700}
apply() {
    (( min > 0 )) || return
    [[ $(cat "$gpu/power_dpm_force_performance_level") == manual && $(od_value 0) -eq $min && $(od_value 1) -ge $max ]] && return
    echo manual > "$gpu/power_dpm_force_performance_level"
    { echo "s 1 $max"; echo "s 0 $min"; echo c; } > "$gpu/pp_od_clk_voltage"
    echo "GPU: minimum $min MHz applied ($(date +%T))"
} 2>/dev/null
restore() {
    echo manual > "$gpu/power_dpm_force_performance_level"
    { echo "s 0 $old_min"; echo "s 1 $old_max"; echo c; } > "$gpu/pp_od_clk_voltage"
    echo "$old_level" > "$gpu/power_dpm_force_performance_level"
    echo "GPU: restored $old_level, $old_min-$old_max MHz"
} 2>/dev/null
apply
./ufc3.sh --play "${game[@]}" "$@" & child=$!
trap 'kill -TERM "$child" 2>/dev/null' TERM INT HUP
while kill -0 "$child" 2>/dev/null; do apply; sleep 2; done
wait "$child"; status=$?
restore; exit $status
