#!/usr/bin/env python3
"""Import a game's save data from shadPS4 into the port.

shadPS4:  <shadPS4>/home/<user>/savedata/<TITLE>/<DIR>/{game files, NAME, sce_sys/param.sfo, sce_sys/icon0.png}
port:     <data>/user/savedata/<user>/<TITLE>/<DIR>/{game files}
          <data>/user/savedata/<user>/<TITLE>/<DIR>.sce_sys/{param.bin, icon0.png}

The game's own files are copied unchanged; shadPS4's NAME file and sce_sys folder are its
metadata: param.sfo becomes the port's param.bin (src/runtime_savedata.c, `Param`: title,
subtitle, detail, user parameter). The port's current saves for the title are copied to
<TITLE>.bak-<time> first. Run it with the game closed.

  tools/import_shadps4_saves.py CUSA14204 \
      --shadps4 ~/.local/share/shadPS4/home/1000/savedata --data ~/.local/share/UFC3Native
"""
import argparse
import shutil
import struct
import sys
import time
from pathlib import Path

PARAM = struct.Struct('<128s128s1024sIiq32s')  # Param in src/runtime_savedata.c (1328 bytes)


def read_sfo(path):
    """PARAM.SFO: key -> str or int."""
    data = path.read_bytes()
    magic, _version, keys, values, count = struct.unpack_from('<4sIIII', data, 0)
    if magic != b'\0PSF':
        raise ValueError(f'{path}: not a PARAM.SFO')
    out = {}
    for i in range(count):
        key_off, fmt, length, _max, value_off = struct.unpack_from('<HHIII', data, 20 + i * 16)
        key = data[keys + key_off:data.index(b'\0', keys + key_off)].decode()
        raw = data[values + value_off:values + value_off + length]
        out[key] = struct.unpack('<I', raw[:4])[0] if fmt == 0x0404 else raw.rstrip(b'\0').decode('utf-8', 'replace')
    return out


def fixed(text, size):
    """UTF-8, cut on a character boundary, NUL-terminated within `size` bytes."""
    raw = str(text or '').encode('utf-8')[:size - 1].decode('utf-8', 'ignore').encode('utf-8')
    return raw.ljust(size, b'\0')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('title', help='title ID, e.g. CUSA14204')
    parser.add_argument('--shadps4', type=Path, default=Path.home() / '.local/share/shadPS4/home/1000/savedata',
                        help="shadPS4's savedata folder (default: %(default)s)")
    parser.add_argument('--data', type=Path, default=Path.home() / '.local/share/UFC3Native',
                        help="the port's data folder, BB_DATA_DIR (default: %(default)s)")
    parser.add_argument('--user', type=int, default=1, help="the port's user ID (default: 1)")
    parser.add_argument('--only', nargs='*', help='only these save directories (default: all)')
    parser.add_argument('--dry-run', action='store_true', help='show what would be copied')
    args = parser.parse_args()

    source = args.shadps4 / args.title
    target = args.data / 'user/savedata' / str(args.user) / args.title
    if not source.is_dir():
        sys.exit(f'No shadPS4 saves for {args.title} in {source}')
    saves = sorted(d for d in source.iterdir() if d.is_dir() and (not args.only or d.name in args.only))
    if not saves:
        sys.exit('Nothing to import')

    if target.exists() and not args.dry_run:
        backup = target.with_name(f'{args.title}.bak-{time.strftime("%Y%m%d-%H%M%S")}')
        shutil.copytree(target, backup)
        print(f'Backup of the port\'s saves: {backup}')

    for save in saves:
        sfo = save / 'sce_sys/param.sfo'
        info = read_sfo(sfo) if sfo.is_file() else {}
        files = [f for f in save.iterdir() if f.is_file() and f.name != 'NAME']
        print(f'{save.name}: {len(files)} files, "{info.get("MAINTITLE", "")}" / "{info.get("SUBTITLE", "")}"')
        if args.dry_run:
            continue
        dest = target / save.name
        meta = target / f'{save.name}.sce_sys'
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        meta.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(f, dest / f.name)
        for sub in (p for p in save.iterdir() if p.is_dir() and p.name != 'sce_sys'):
            shutil.copytree(sub, dest / sub.name)
        param = PARAM.pack(fixed(info.get('MAINTITLE'), 128), fixed(info.get('SUBTITLE'), 128),
                           fixed(info.get('DETAIL'), 1024), int(info.get('SAVEDATA_LIST_PARAM', 0)) & 0xFFFFFFFF,
                           0, int(time.time()), b'\0' * 32)
        (meta / 'param.bin').write_bytes(param)
        if (save / 'sce_sys/icon0.png').is_file():
            shutil.copy2(save / 'sce_sys/icon0.png', meta / 'icon0.png')
    print('Done' if not args.dry_run else 'Dry run: nothing written')


if __name__ == '__main__':
    main()
