**Experimental.** EA SPORTS UFC 4 (PS4 `CUSA14204`, update **28.00**) running natively on Linux.
**No game files are included**: you need your own dump of the game and its 28.00 update.

### Requirements
- Linux x86-64 with **glibc 2.43 or newer** (Bazzite / Fedora 44, Arch, Ubuntu 26.04, SteamOS
  builds based on them), Python 3 and a Vulkan 1.3 driver (Mesa RADV on AMD).
- 60 FPS needs the PC memory model (AMD GPUs only) and about 7 GiB of GTT on APUs; see
  `docs/UFC4.md` inside the archive.

### Quick start
```bash
tar xzf UFC4Native-*-linux-x86_64.tar.gz && cd UFC4Native
python3 scripts/merge_update.py /path/CUSA14204      # with /path/CUSA14204-patch next to it
./ufc3.sh --play /path/CUSA14204-merged
```
Check the download: `sha256sum -c UFC4Native-*.tar.gz.sha256`.

### Known issues
- At 60 FPS the fight clock runs faster than real time; 30 FPS keeps the correct speed.
- Career mode, online play, NVIDIA and Intel GPUs are not tested yet.

### Reporting a problem
Run `./ufc3.sh --doctor /path/CUSA14204-merged` with the game closed and attach the file it saves
to a [new issue](https://github.com/cgodoi/UFC-4-PS4-PORT-LINUX/issues/new/choose).
