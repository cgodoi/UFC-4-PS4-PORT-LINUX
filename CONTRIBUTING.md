# Contributing to the UFC 4 native port

## Game files

This project contains no game data and accepts none. Do not attach, paste or link eboot.bin,
sce_module files, saves, dumps, decryption material or anything else from the game folder in
issues, pull requests or discussions; such content is removed and the issue closed. The project
does not help with obtaining or dumping the game. You need your own copy of
*EA SPORTS UFC 4* (CUSA14204) and its 28.00 update (or UFC 3, CUSA06534, with 1.14).

Generated files derived from the game (`out/`, `user/`, logs of the game's own output) stay out
of the repository too; `.gitignore` covers the usual places.

## Bug reports

Use the issue forms. Run `./ufc3.sh --doctor /path/CUSA14204-merged` with the game closed and
attach the report it saves: it holds the version, system, GPU driver, GTT size, the game files
check and the end of the newest log. For a crash, also a log with *Save log* on (`BB_SAVE_LOG=1`):
everything from `STOP` or `Guest fault` to the end. For rendering or speed problems, the
`Frame stats:` lines.

## Changes

- Build with `bash scripts/build-docker.sh` (or `bash build.sh` on a host with the libraries of
  `docker/Dockerfile`); run `python3 -m unittest discover -s tests` (and `bash build.sh --test`)
  before a pull request. The GPU library takes about 40 CPU-minutes to build; the Python tests
  run in seconds and also run in CI.
- Changes inside `gpu/shadps4/` (the vendored shadPS4 video core) are marked with a `bbport:` or
  `sacredfire:` comment, as the existing ones are, so the vendored code can be compared with
  upstream later.
- The runtime (`src/runtime_*.c`) implements what the game calls. A new import gets a real
  implementation or an honest, logged stub that fails visibly; no blanket "return 0".
- Keep a note in `docs/ufc4/README.md` for anything that took investigation (what was observed,
  what was tried, what fixed it).
- Commit messages say what changed and why.

## Releases

A published build is a GPL binary, so each one has to match a published commit:

1. Commit everything on `main` and tag it: `git tag vX.Y.Z && git push origin vX.Y.Z`.
2. The `release` workflow (`.github/workflows/release.yml`) builds it in the Docker image,
   checks the packaged libraries and publishes `UFC4Native-vX.Y.Z-linux-x86_64.tar.gz` with its
   `.sha256` as a pre-release. The notes are `packaging/linux/RELEASE-NOTES.md` plus the commits
   since the previous release; `VERSION` in the archive reads `vX.Y.Z`.
3. Running the workflow by hand builds the same archive as a workflow artifact without
   publishing anything.

## Licenses

The port is GPL-2.0-or-later (see `LICENSE`), as are SacredFire, bbport and shadPS4 it is built
on. Contributions are accepted under the same license. Third-party components keep theirs
(README.UFC3.md, *Credits*). Keep the attribution of game patches (`Author=` in `patches/*.xml`)
when touching them.
