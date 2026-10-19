# UFC 4 on the UFC 3 native port — notes

What was needed to run EA SPORTS UFC 4 (`CUSA14204`, update 28.00, US) on the UFC 3 port, what
each change fixes, the settings that matter, and the measurements behind them. Tested on a
Lenovo Legion Go (Ryzen Z1 Extreme, RDNA 3 iGPU, 16 GB with 6 GB reserved for the GPU), Bazzite
(SteamOS-like, gamescope), October 2026.

## Handhelds (AMD APUs)

### Settings

| What | Value | Why |
|---|---|---|
| Launcher | `launchers/legion-go/ufc4-60fps.sh` (or `ufc4-30fps.sh`) | PC memory model, 720p + FSR, no diagnostics, GPU governor |
| GTT size | ~7 GiB (kernel arguments below) | the PC memory model puts the game's ~5 GB of memory in GTT; the default (half the RAM Linux sees, 4.69 GiB with 6 GB reserved) is too small and the game stops with `radv/amdgpu: Not enough memory for command submission` |
| TDP | ~24 W for 60 FPS, 15-20 W for 30 FPS | at 20 W the GPU took the CPU's share at 60 FPS (CPU ~1 GHz, ~48 FPS); 24 W held 60 |
| Steam per-game GPU clock | **off** | with it on, Steam re-applies its manual GPU clock every ~30 s (`SetManualGpuClock`); at 2700 MHz the GPU took the whole power budget and the CPU dropped to 544 MHz (20 FPS) |
| SMT | on | with SMT off the game (~45 threads) and the port share 8 threads |
| gamescope FSR / scaling | on | gamescope then composites every frame at its refresh rate, which hides the phase difference between the port's virtual vblank and the display's (an overlay showed 21-45 ms frames while the port delivered every frame at 33.3 ms) |

GTT on Bazzite / Fedora Atomic (reboot needed; `--delete=` instead of `--append=` undoes it):

```bash
sudo rpm-ostree kargs --append=ttm.pages_limit=1835008 --append=ttm.page_pool_size=1835008 --append=amdgpu.gttsize=7168
```

Heat: the one firmware power cut we saw came at 60 FPS with the native resolution, a 35 W
"docked" profile (OpenGamepadUI's default when charging) and the GPU forced to 2200 MHz (~86 °C,
no kernel message). With 720p and the governor the package stayed at ~17-18 W and ~65 °C.

### The GPU governor (`BB_GPU_GOVERNOR=1`)

AMD's clock governor follows GPU utilisation. This port keeps the GPU idle much of the time
(35-65 % busy), so the GPU stays at 800 MHz, while frames still miss their vblank because their
GPU work starts late in the frame. A fixed minimum (1600 MHz) fixed the frame time but costs
power in light scenes. `gpu/shim/bbport_gpu_governor.cpp` watches frame deadlines instead: every
500 ms it raises the GPU's minimum clock by 200 MHz when more than 3 % of the frames were late
while the GPU was ≥ 75 % busy, lowers it by 100 MHz when frames were late with the GPU below
60 % busy (the CPU is short of the shared power: a higher GPU clock would take power from it),
and lowers it by 100 MHz after 3 s without late frames and below 80 % busy. (A first version
raised the clock from 55 % busy: at 18 W it drove the GPU to 2000 MHz at 53 % busy while the CPU
fell to 0.9 GHz, and frames got later.)
It writes `pp_od_clk_voltage` and `power_dpm_force_performance_level` (writable by the user on
Bazzite/SteamOS), re-applies them when Steam resets the GPU to auto, and logs every change.

| Variable | Default | |
|---|---|---|
| `BB_GPU_GOVERNOR` | 0 (1 in the handheld launchers) | on/off |
| `BB_GPU_GOV_START` / `_MIN` / `_MAX` | 1300 / 800 / 2000 MHz | the minimum clock it starts at and its range (2200 MHz starved the CPU at 24 W) |
| `BB_GPU_GOV_CEILING` | 2700 MHz | the range's maximum, left to the driver |

The launcher (`launchers/legion-go/ufc4.sh`) saves the GPU's setting before the game and restores
it afterwards. Without the governor it can hold a fixed minimum instead (`BB_GPU_MIN_MHZ`,
default 1600, 0 = do not touch the GPU), re-applied every 2 s.

Measured in the same kind of fight: menus at 800 MHz / 14-15 W / 62 °C; the fight raised the
minimum 1000 → 1400 MHz within 6 s, then it settled at 1200-1300 MHz, ~17-18 W, ~65 °C.

### Resolution and power (Legion Go, the same heavy fight, 60 FPS, PC memory model, governor)

| Game resolution | TDP | Result |
|---|---|---|
| 960x540 | 15 W | ~31 FPS, uneven (CPU at its 544 MHz minimum) |
| 960x540 | 18-20 W | 60 FPS with occasional 33 ms frames, ~20-21 W, ~68 °C |
| 960x540 | 25 W | 60 FPS flat, ~22-25 W, ~76 °C |
| 1280x720 | 28 W | 60 FPS flat, ~27 W, ~76 °C |

The game resolution is in the in-game menu (Insert or L3+R3 → *Game resolution*: the launcher's,
960x540, 1024x576, 1152x648, 1280x720, 1600x900 or 1920x1080). The game sizes its render targets from its video output
when it starts, so the choice is saved to `bbport.ini` (`game_resolution`) and applied by
*Apply and restart game*; it wins over the launcher's `BB_INTERNAL_WIDTH/HEIGHT`. The port's FSR 1
scales it to the window; gamescope's FSR on top cost ~10 FPS here (a second upscale to the panel's
2560x1600) and is not needed once the TDP is enough. The menu's *Upscaling* section switches the
port's FSR 1 and RCAS sharpening and sets the sharpness, live (`bbport.ini` `fsr1`, `rcas`,
`rcas_attenuation`; "launcher" keeps `BB_FSR1`, `BB_RCAS`, `BB_RCAS_ATTENUATION`). The menu is in English unless `bbport.ini`
says `menu_language=ru`.

### Display sync (experimental, off: `BB_VBLANK_SYNC=1`)

The port's virtual vblank runs on its own clock. `bbport_vblank_sync.cpp` waits for each presented
frame to reach the screen (`VK_KHR_present_wait`) and the present thread phase-locks its ticks to
those times. Under gamescope the "on screen" time follows the port's own present (it locked at
60 FPS with a +1.5 ms offset that did not converge, and drifted when frames ran late), so it does
not help there; a lock check turns it off when the tick period drifts > 1 % from nominal. AMD only
(NVIDIA's 580 driver divides by zero inside `vkWaitForPresentKHR`; `BB_VBLANK_SYNC=2` forces it).
What looked like display judder was mostly a power shortage: with enough TDP the frame time is
flat without it.

## What changed, and why

### Game profile — `scripts/game_check.py`, `run.sh`
- Profile `ufc4` for the 28.00 executable (image hash in `SUPPORTED`), base 1.00 listed as old.
  Its own variant (`ufc4`) keeps UFC 3's address-keyed diagnostics (heap hooks, free check) off.
- `run.sh` gives `ufc4` the UFC 3 engine defaults (precise readbacks, write windows, pre-upload,
  movie skip) plus: `BB_THREAD_START_WAIT=1`, `BB_TIMER_SLEEP=1`, and the game's own flip rate on a
  60 Hz vblank (`BB_FLIP_RATE=-1`, `BB_VBLANK_HZ=60`). UFC 3's simulation follows the real frame
  time, so its profile unlocks the frame rate; UFC 4 asks for 30 Hz and an unlocked rate made it
  run fast. `BB_FLIP_RATE=0` asks for 60 Hz (the 60 FPS launcher).

### System functions — `src/runtime_services.c`, `src/runtime_rwlock.c`
UFC 4 imports ~19 functions UFC 3 does not; the GPU/video ones exist in the GPU library. Added:
`sceRemoteplayInitialize/Prohibit/Terminate`, `sceGameLiveStreamingPermitLiveStreaming`,
`sceNpWebApiAddHttpRequestHeader`, `sceAudioInIsSharedDevice/GetSilentState` (no microphone),
`sceAppContentGetPftFlag` (no PFT), `sceKernelIsProspero` (a PS4), and the POSIX
`pthread_rwlock_rdlock/wrlock/unlock` (same lock as `scePthreadRwlock*`, errno results).

### Network startup — `src/runtime_services.c`
EA's `NetConnStartup` creates a UPnP object over a UDP socket. Offline, every socket call failed,
the whole startup failed (error -6), it freed its state, and other code read the freed state
(`mov 0x18(%rax)` on a null global, `+0x137cde4`). For the `ufc4` profile, offline sockets can be
created, bound, configured, named (`sceNetGetsockname` returns 0.0.0.0 and an ephemeral port) and
closed; sending and receiving still fail as unplugged.

### Thread start — `src/runtime_thread.c`
EA's `pthread_create` wrapper (`+0x8b1b0`) hands each new thread its entry and argument through a
32-slot ring; a thread that starts after 32 more creations reads a reused slot and calls garbage
(the `NetLib` thread jumped into the host heap, only without a debugger). With
`BB_THREAD_START_WAIT=1` thread creation returns once the new thread is about to run its guest
entry, as a new PS4 thread starts at once.

### Short timers — `gpu/shadps4/core/libraries/kernel/equeue.cpp`
The game's small HR timers (EA's timer queues, frame pacing) were waited for with a
`sched_yield` loop: the main thread and SimThread each showed ~100 % of a core. On a handheld the
spinning cores take power from the threads doing the work. With `BB_TIMER_SLEEP=1` the wait
sleeps on the queue's condition variable until `BB_TIMER_SPIN_US` (200) before the earliest
timer and spins only for the rest; events, new timers and deleted timers wake it. Result: those
threads 100-128 % → ~20 %, CPU clocks held at 3-4.7 GHz, frame time p99 33.4 ms flat at 30 FPS.

### GPU translator — `gpu/shadps4/video_core/amdgpu/pixel_format.h`
A `SnormNz` number format on data format 0 (an unused descriptor, in a heavy fight) hit an
`UNREACHABLE` and stopped the game; it is now "no conversion", like the other formats there.

### Diagnostics — `src/runtime_thread.c`, `src/platform/platform_posix.c`
Thread creation logs the guest entry address; a host fault outside any mapped code prints the
guest return addresses found on the stack and a few registers; concurrent faults are reported
one at a time (a second thread's `_exit` used to cut the first report short).

## Measurements (Legion Go, fights)

| Configuration | FPS | Port GPU thread | Notes |
|---|---|---|---|
| 0.3 memory model, 60 Hz | 36-46 | 14-16 µs/draw, idle 5-10 % | 1.7-2.3 k write faults/s, 15-17 % waiting for host copies |
| PC memory model, 60 Hz, 1600 MHz | 48-52 | ~9 µs/draw, idle ~50 % | 0 write faults, the GPU (84 % busy) became the limit |
| PC model, 30 FPS, timers sleeping | 30.0 flat | 3.5-5 µs/draw, idle 83 % | ~28 W at the 35 W docked profile |
| PC model, 60 Hz, 24 W | 60 (94 % of frames on time) | ~6 µs/draw | ~29-30 W, 81-82 °C |
| PC model, 60 Hz, 720p, governor, 24 W | smooth in play | — | ~17-18 W, ~65 °C (frame log off) |

## Debugging notes

- `BB_FILE_TRACE=1`, `BB_SAVE_LOG=1` (log and per-frame CSV in the data folder's `logs/`).
- Attaching gdb (`BB_ALLOW_PTRACE=1` on Ubuntu's Yama scope; Bazzite allows it) changes timing:
  the thread-start race above did not happen under gdb.
- `tools/got_import.py`-style lookups: a call to `0x1ef7xxx` in the guest is an import stub;
  `out/boot.bin`'s relocations map its GOT slot to a NID, `out/import_names.txt` to a name.
