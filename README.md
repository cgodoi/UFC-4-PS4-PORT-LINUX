# UFC 4 — native PS4 port for Linux (experimental)

**EA SPORTS UFC 4** (PlayStation 4, `CUSA14204`, update **28.00**) running as a **native x86-64**
program on Linux, built on the [UFC 3 native port](https://github.com/GNSB/UFC-3-PS4-PORT-LINUX-WINDOWS)
by GNSB (itself based on [SacredFire](https://github.com/T3CHNOLOG1C/SacredFire) and
[bbport](https://github.com/deadinside28/bloodborne_pc)). The game's own code runs directly on the
PC's processor, a runtime replaces the PS4 system libraries, and a renderer derived from
[shadPS4](https://github.com/shadps4-emu/shadPS4) translates its GPU work to Vulkan. UFC 3 and
UFC 4 share the same EA engine, so this repository keeps the UFC 3 port working and adds what
UFC 4 needs. All code is GPL-2.0-or-later.

> **No game files are included.** You need your own dump of UFC 4 (`CUSA14204`) and its 28.00
> update. This project is not affiliated with or endorsed by Electronic Arts, Sony Interactive
> Entertainment or the UFC; the names are used only to identify the game.

## Status

**Boots, menus and fights play** — tested on a **Lenovo Legion Go** (Ryzen Z1 Extreme, Bazzite):

| Setup | Result in fights |
|---|---|
| 30 FPS (the console's rate), PC memory model | flat 33.3 ms frame time (measured) |
| 60 FPS, PC memory model, native resolution, GPU minimum 1600 MHz, 24 W TDP | 60 FPS, frame time p99 17.8 ms (measured), ~29-30 W, ~82 °C |
| 60 FPS, PC memory model, 720p internal + FSR, GPU governor, 24 W TDP | smooth in play (frame log off), ~17-18 W, ~65 °C |

Not tested yet: career mode, online, other GPUs (NVIDIA, Intel) and desktop PCs.
Known limits: 60 FPS needs the PC memory model (AMD only) and enough GTT memory (see
[Handhelds](docs/ufc4/README.md#handhelds-amd-apus)); the PC memory model is experimental.

## Getting the game files

The port checks the executable: only the US `CUSA14204` update **28.00** build listed in
[`scripts/game_check.py`](scripts/game_check.py) is accepted. Put the base game and the update
next to each other and merge them (hard links, no extra space):

```bash
python3 scripts/merge_update.py /path/CUSA14204      # with /path/CUSA14204-patch next to it
# -> /path/CUSA14204-merged
```

If you start from `.pkg` files, extract them with a tool that handles PS4 PFS compression
correctly. **LibOrbisPkg (`PkgTool.Core pkg_extract`) produced files with corrupted blocks** in
our tests (no error reported; the game then hangs at a black screen).

## Building

Only Docker is needed on the host:

```bash
git clone --recursive <this repo> ufc4-port && cd ufc4-port
bash scripts/build-docker.sh          # image from docker/Dockerfile, build, package
# -> out/dev/UFC4Native (portable: copy it anywhere; needs glibc 2.43+)
```

Without Docker, `bash build.sh` works on a host with the libraries listed in `docker/Dockerfile`.

## Playing

```bash
cd out/dev/UFC4Native
./ufc3.sh --play /path/CUSA14204-merged        # the "ufc4" profile is picked from the executable
```

Coming from shadPS4? Its save data (career, created fighters, profile) imports into the port
with the game closed; the port's current saves are backed up first (tested with a UFC 4 career):

```bash
python3 tools/import_shadps4_saves.py CUSA14204 \
    --shadps4 ~/.local/share/shadPS4/home/1000/savedata --data ~/.local/share/UFC3Native
```

For handhelds there are ready-made launchers in [`launchers/legion-go/`](launchers/legion-go/)
(30 FPS, and 60 FPS with the PC memory model, 720p and the GPU governor); add them to Steam as
non-Steam games. Read [docs/ufc4/README.md](docs/ufc4/README.md) for the settings that matter
(GTT size, TDP, Steam's per-game GPU clock).

## What this port adds (UFC 4)

- A `ufc4` game profile (the UFC 3 engine defaults, without UFC 3's address-keyed hooks).
- The system functions UFC 4 uses and UFC 3 does not (Remote Play, live streaming, microphone,
  `sceKernelIsProspero`, PFT flag, POSIX rwlocks).
- Offline networking that lets EA's network startup (UPnP) succeed instead of crashing.
- Thread creation that copies EA's `pthread_create` hand-over slot (a 32-slot ring that was
  reused before the NetLib thread read it).
- Short game timers that sleep instead of spinning (power and heat on handhelds).
- A frame-deadline **GPU clock governor** for AMD APUs (the driver's governor keeps the GPU at
  its lowest clock because this port leaves it idle much of the time).
- A GPU translator fix (an unused descriptor format stopped the game).
- A reproducible Docker build and portable packaging.

### Brought over from PORTHEON

[PORTHEON](https://github.com/XAndromedaXR/UFC-4-PS4-PORT) (XAndromedaXR) is another UFC 4 port
built on the same GNSB base. Two of its changes are included here, cherry-picked with their
original commits (`git log --grep "cherry picked"`):

- **The PS4's floating-point mode on the game's threads** (flush-to-zero, denormals-are-zero,
  MXCSR `0x9fc0`): the game was built for it, and without it every very small number in
  animation, physics or audio takes the CPU's slow path. `BB_GUEST_MXCSR=0` turns it off.
- **Depth images read as raw bits are converted again only when they change**: a shadow map
  was converted for every part of a fighter drawn, which made the frame rate collapse in Career.

Their third fix of that series (game copies next to GPU-written memory no longer read pages
back) was already in this repository's base (GNSB 0.1.6), done differently, so it is not
duplicated.

Details, measurements and settings: [docs/ufc4/README.md](docs/ufc4/README.md).
The original UFC 3 port's README (UFC 3 instructions, launcher settings, credits):
[README.UFC3.md](README.UFC3.md).

## Credits

- **GNSB** — the [UFC 3 native port](https://github.com/GNSB/UFC-3-PS4-PORT-LINUX-WINDOWS) this
  repository is built on, and everyone credited in [README.UFC3.md](README.UFC3.md).
- **XAndromedaXR** — [PORTHEON](https://github.com/XAndromedaXR/UFC-4-PS4-PORT): the
  floating-point mode and the depth conversion fix above.
- [SacredFire](https://github.com/T3CHNOLOG1C/SacredFire), [bbport](https://github.com/deadinside28/bloodborne_pc)
  and [shadPS4](https://github.com/shadps4-emu/shadPS4).

## License

GPL-2.0-or-later, like the projects it comes from (see [`LICENSE`](LICENSE)).
