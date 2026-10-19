#!/usr/bin/env python3
"""A system report for bug reports: ./ufc3.sh --doctor [GAME_DIR]

Collects what usually explains a problem (port version, distribution, glibc, CPU, memory, the
Vulkan GPU and driver, AMD GTT size and GPU clock mode, the game files check, launcher settings
and the end of the newest log), flags the known pitfalls, prints it and saves it to
<data>/doctor-<time>.txt to attach to an issue. It only reads: nothing is changed or sent.
The home folder and user name are replaced by ~ and <user> in the report.
"""
import datetime
import getpass
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent      # the package (or repository) folder
sys.path.insert(0, str(HERE / 'scripts'))
MIN_GLIBC = (2, 43)
MIN_GTT_GIB = 7      # the PC memory model (60 FPS) needs about this much GTT on APUs


def read(path, default=''):
    try:
        return Path(path).read_text(errors='replace').strip()
    except OSError:
        return default


def run(command, timeout=20):
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        return (done.stdout + done.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        return f'({error})'


def glibc_version():
    try:
        name = os.confstr('CS_GNU_LIBC_VERSION') or ''
    except (ValueError, OSError):
        name = ''
    m = re.search(r'(\d+)\.(\d+)', name)
    return (int(m[1]), int(m[2])) if m else None


def meminfo_gib(key, text=None):
    text = text if text is not None else read('/proc/meminfo')
    m = re.search(rf'^{key}:\s+(\d+) kB', text, re.M)
    return int(m[1]) / 1048576 if m else None


def amd_gpus(drm=Path('/sys/class/drm')):
    """[(card, {gtt_gib, vram_gib, level, sclk})] for the amdgpu cards sysfs describes."""
    found = []
    for card in sorted(drm.glob('card[0-9]*')):
        device = card / 'device'
        if '-' in card.name or not (device / 'mem_info_gtt_total').exists():
            continue
        info = {}
        for key, name in [('gtt_gib', 'mem_info_gtt_total'), ('vram_gib', 'mem_info_vram_total')]:
            value = read(device / name)
            info[key] = int(value) / 2**30 if value.isdigit() else None
        info['level'] = read(device / 'power_dpm_force_performance_level', '?')
        current = [l for l in read(device / 'pp_dpm_sclk').splitlines() if l.endswith('*')]
        info['sclk'] = current[0].split(':', 1)[-1].strip(' *') if current else '?'
        found.append((card.name, info))
    return found


def data_dir():
    return Path(os.environ.get('BB_DATA_DIR') or
                Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'UFC3Native')


def game_folder(data, given=None):
    if given:
        return Path(given)
    try:
        saved = json.loads(read(data / 'launcher.json', '{}'))
        if isinstance(saved, dict) and saved.get('game'):
            return Path(saved['game'])
    except ValueError:
        pass
    text = read(data / 'game-folder')
    return Path(text) if text else None


def check_game(game):
    """Lines about the game folder, and warnings."""
    import game_check
    lines, warnings = [], []
    if game is None:
        return ['Game folder: not set (pass it: ./ufc3.sh --doctor /path/CUSA14204)'], warnings
    lines.append(f'Game folder: {game}')
    if not (game / 'eboot.bin').is_file():
        warnings.append(f'No eboot.bin in the game folder {game}.')
        return lines, warnings
    merged = game.with_name(game.name + '-merged')
    if game_check.problem(game) and (merged / 'eboot.bin').is_file():
        lines.append(f'Merged folder: {merged}')
        game = merged
    info = game_check.sfo_info(game)
    lines.append(f"param.sfo: {info.get('TITLE_ID', '?')} version {info.get('APP_VER', '?')}")
    try:
        image = game_check.image_sha256(game)
    except (OSError, ValueError, IndexError, StopIteration, KeyError):
        image = None
    lines.append(f'eboot.bin image sha256: {image or "unreadable"}')
    found = game_check.problem(game, image)
    if found:
        warnings.append('Game files: ' + game_check.explain(*found))
    else:
        p = game_check.profile(game, image)
        lines.append(f"Profile: {p['name']} ({p['game']} {p['version']}, build {p.get('variant', '?')})"
                     if p else 'Profile: unknown')
    return lines, warnings


def latest_log(data, lines=40):
    logs = sorted((data / 'logs').glob('*.log'), key=lambda p: p.stat().st_mtime)
    if not logs:
        return ['(no saved log: turn on "Save log" in the launcher, or BB_SAVE_LOG=1, and play once)']
    text = read(logs[-1]).splitlines()
    return ([f'{logs[-1].name} (last {min(lines, len(text))} of {len(text)} lines):'] +
            [l if len(l) <= 300 else l[:300] + ' [...]' for l in text[-lines:]])


def report(game_arg=None, data=None, now=None):
    data = data or data_dir()
    now = now or datetime.datetime.now()
    out, warnings = [], []
    section = lambda title: out.extend(['', f'== {title} =='])

    out.append(f"UFC native port doctor, {now:%Y-%m-%d %H:%M}")
    section('Port')
    out.append(f"Version: {read(HERE / 'VERSION') or read(HERE / 'out/VERSION', 'unknown (not built yet)')}")
    out.append(f'Folder: {HERE}')
    out.append(f'Data: {data}')

    section('System')
    release = dict(re.findall(r'^(\w+)="?([^"\n]*)"?$', read('/etc/os-release'), re.M))
    out.append(f"OS: {release.get('PRETTY_NAME', '?')}, kernel {platform.release()}")
    model = ' '.join(filter(None, (read('/sys/class/dmi/id/sys_vendor'), read('/sys/class/dmi/id/product_name'),
                                   read('/sys/class/dmi/id/product_version'))))
    out.append(f'Machine: {model or "?"}')
    cpu = re.search(r'^model name\s*:\s*(.+)$', read('/proc/cpuinfo'), re.M)
    out.append(f"CPU: {cpu[1] if cpu else platform.processor() or '?'}, {os.cpu_count()} threads")
    total, available = meminfo_gib('MemTotal'), meminfo_gib('MemAvailable')
    if total:
        out.append(f'RAM: {total:.1f} GiB ({available or 0:.1f} GiB available)')
    glibc = glibc_version()
    out.append(f"glibc: {'.'.join(map(str, glibc)) if glibc else '?'}; Python {platform.python_version()}")
    if glibc and glibc < MIN_GLIBC:
        warnings.append(f'glibc {glibc[0]}.{glibc[1]} is older than {MIN_GLIBC[0]}.{MIN_GLIBC[1]}: the packaged '
                        'binaries will not start. Use a newer distribution or build from source.')
    session = os.environ.get('XDG_CURRENT_DESKTOP') or os.environ.get('XDG_SESSION_DESKTOP') or '?'
    out.append(f"Session: {session}, {os.environ.get('XDG_SESSION_TYPE', '?')}"
               f"{', gamescope' if os.environ.get('GAMESCOPE_WAYLAND_DISPLAY') else ''}")

    section('GPU')
    capabilities = HERE / 'bin/bb-gpu-capabilities'
    if not capabilities.exists():
        capabilities = HERE / 'out/bb-gpu-capabilities'
    if capabilities.exists():
        device = run([str(capabilities), '--device'])
        out.append(f'Vulkan device the game takes: {device or "(none)"}')
        if not device or device.startswith('('):
            warnings.append('No Vulkan GPU found: install your distribution\'s Vulkan driver (Mesa RADV for AMD).')
    else:
        out.append('Vulkan device: bb-gpu-capabilities is missing (build first)')
    if shutil.which('vulkaninfo'):
        summary = run(['vulkaninfo', '--summary'])
        keep = [l.strip() for l in summary.splitlines()
                if re.match(r'\s*(Vulkan Instance Version|deviceName|driverName|driverInfo|apiVersion|deviceType)\b', l)]
        out.extend(keep[:12] or ['vulkaninfo: no devices'])
    for card, info in amd_gpus():
        gtt = info['gtt_gib']
        out.append(f"{card}: amdgpu, VRAM {info['vram_gib'] or 0:.1f} GiB, GTT {gtt or 0:.1f} GiB, "
                   f"clock mode {info['level']}, GPU clock now {info['sclk']}")
        if gtt is not None and gtt < MIN_GTT_GIB and (info['vram_gib'] or 0) < 4:
            warnings.append(f'{card}: GTT is {gtt:.1f} GiB; 60 FPS with the PC memory model needs about '
                            f'{MIN_GTT_GIB} GiB (docs/ufc4/README.md, Handhelds).')
        if info['level'] not in ('auto', '?'):
            warnings.append(f"{card}: GPU clock mode is '{info['level']}' (Steam's per-game manual GPU clock?). "
                            'It can starve the CPU; turn it off unless you set it on purpose.')
    cmdline = read('/proc/cmdline')
    tuned = [w for w in cmdline.split() if w.startswith(('amdgpu.', 'ttm.'))]
    if tuned:
        out.append('Kernel options: ' + ' '.join(tuned))

    section('Game files')
    lines, found = check_game(game_folder(data, game_arg))
    out.extend(lines)
    warnings.extend(found)

    section('Settings')
    settings = read(data / 'launcher.json')
    out.append('launcher.json: ' + (settings.replace('\n', ' ') if settings else '(none)'))
    conf = [l for l in read(data / 'ufc3.conf').splitlines() if re.match(r'[A-Z][A-Z0-9_]*=.', l)]
    out.append('ufc3.conf: ' + (', '.join(conf) if conf else '(defaults)'))
    env = sorted(f'{k}={v}' for k, v in os.environ.items() if k.startswith('BB_') and k != 'BB_DATA_DIR')
    if env:
        out.append('Environment: ' + ', '.join(env))

    section('Newest log')
    out.extend(latest_log(data))

    head = ['', '== Warnings ==']
    head += [f'- {w}' for w in warnings] if warnings else ['- none found']
    text = '\n'.join(out[:1] + head + out[1:]) + '\n'
    return scrub(text)


def scrub(text):
    # Longest first: on Bazzite/Silverblue /home is a link to /var/home.
    for home in sorted({str(Path.home()), os.path.realpath(Path.home())}, key=len, reverse=True):
        if home not in ('/', ''):
            text = text.replace(home, '~')
    try:
        user = getpass.getuser()
    except (KeyError, OSError):
        user = ''
    if len(user) > 2:
        text = re.sub(rf'\b{re.escape(user)}\b', '<user>', text)
    return text


def main(argv):
    game = argv[0] if argv else None
    data = data_dir()
    text = report(game, data)
    print(text, end='')
    try:
        data.mkdir(parents=True, exist_ok=True)
        path = data / f'doctor-{datetime.datetime.now():%Y%m%d-%H%M%S}.txt'
        path.write_text(text)
        print(f'\nSaved: {path}\nAttach this file to your issue: '
              'https://github.com/cgodoi/UFC-4-PS4-PORT-LINUX/issues/new/choose')
    except OSError as error:
        print(f'\n(could not save the report: {error})')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
