# Montage native Windows build (Stage 1, route 1) [real]

Date: 2026-10-11. Route used: native Windows build with a MinGW-w64 toolchain (authorised route 1). No WSL2, container or admin rights were needed. The Montage `Windows/Notes.txt` says the supported Windows build is a Docker cross-compile; this is a different, direct build and several parts needed workarounds, all listed below. The build copy lives outside the project (`C:\Users\Venkatesh\cao_montage\`, a path without spaces is required by the Makefiles); only the resulting executables and their hashes are recorded in the project.

## Sources and tools (URLs, versions, licences, hashes)

| Item | Source | Version / hash | Licence (file read) |
|---|---|---|---|
| Montage toolkit | https://github.com/Caltech-IPAC/Montage (shallow clone) | commit `ac0a15334f670ed83e328b6c5768f94b4b847359`, 2026-04-06 | BSD 3-clause (header of `LICENSE`) |
| Workflow generator | https://github.com/pegasus-isi/montage-workflow-v3 | commit `975047e916d3d049d9ff0da17e7fe5aaac979c64`, 2026-09-22 | Apache-2.0 (`LICENSE`) |
| Toolchain | https://github.com/skeeto/w64devkit/releases/tag/v2.10.0 `w64devkit-x64-2.10.0.7z.exe` | SHA-256 `18d0a4c71a166f8401ab6305781bec5882b40b5e06ba9807c61cb5f3b3c6325e` (matches the digest GitHub shows for the asset); GCC 16.2.0, GNU Make 4.4.1 | Mixed licences of the bundled tools; **not read, not redistributed** |
| Shell for autoconf/libtool | Git for Windows `usr/bin/sh` (already installed), reached through a junction `C:\Users\Venkatesh\cao_montage\git` to avoid the space in `Program Files` | - | - |
| Python packages | `requirements-lock.txt` | - | - |

Bundled third-party libraries come inside the Montage tree (cfitsio 3.49, bzip2 1.0.6, wcssubs, freetype 2.13.3, jpeg-8b, lodepng); their licences were not read here.

## Workarounds (all applied to the build copy, none to the upstream clone)

Files: [`montage_build/`](montage_build/) holds the helper sources and patch scripts; the executables are hashed in `montage_build/bin_win64_sha256.txt`.

1. **Compiler flags.** GCC 16 defaults to C23 (`nullptr` keyword, K&R declarations rejected, implicit declarations are errors). A small launcher `gcc.exe` (`gccshim.c`) first on `PATH` prepends `-std=gnu99 -fcommon -Wno-implicit-function-declaration -Wno-int-conversion -Wno-incompatible-pointer-types -Wno-implicit-int -Wno-return-mismatch`, an include directory with stub headers (`sys/wait.h`, `sys/socket.h`/`netdb.h`/`netinet/in.h` mapped to winsock2) and `compat.h` (`strcasestr`). Needed because several Makefiles hard-code `CC = gcc`.
2. **bzip2** self-test (`make test`) fails on Windows text-mode redirection; only `libbz2.a` is built.
3. **configure scripts** (cfitsio) need `--build=x86_64-w64-mingw32`.
4. **WCS names.** `wcsinit/wcsset/wcsrev` clash with Windows wide-character functions. The upstream Windows port renames them (`Windows/sedScripts/*.sh`); I applied the same rename globally (`\bwcsinit\b` etc. to `wcsInit/wcsSet/wcsRev`) in the library, `MontageLib`, `util`, `grid`, `Montage`, `ancillary` and `HiPS` sources of the build copy.
5. **libjpeg** (needed by `mViewer`): the libtool-based build fails on Windows; the 46 source files were compiled directly and archived into `libjpeg.a`.
6. **FreeType** (needed by `mViewer`): its GNU-make build fails with this `make`; compiled directly (base, truetype, sfnt, smooth, psnames, raster, gzip modules) with a hand-written `objs/ftmodule.h` listing exactly those modules.
7. **`svc` library** (fork/exec based; linked by the `grid/Pegasus` tools including `mConcatFit` and `mDAGTbls`, which were built from it; whether those two call it at run time was not checked): ported with `_pipe` + `_spawnvp` (`patch_svc.py`). Only the process-spawning part changed.
8. **`mArchiveList`** (needs network): ported to winsock with `patch_archivelist.py` (WSAStartup, `recv`, `-lws2_32`); it speaks plain HTTP to `montage.ipac.caltech.edu`.
9. **`mViewer`**: the `FONT_DIR` macro quoting was fixed in the build copy's Makefile; the font path is compiled in (`C:/Users/Venkatesh/cao_montage/src/data/fonts/`). The final PNG step depends on that directory existing.
10. **`mImgtbl` option order.** The workflow calls `mImgtbl . -t tbl out` (options after the directory). The mingw `getopt` does not permute arguments, so the first build wrote a file literally named `-t` and no output table. `patch_imgtbl.py` moves options (and their arguments) in front of the positionals before `getopt` runs. Found by a debug resume run (below).
11. **`mViewer` stack.** `mViewer` crashed with exit 0xC00000FD (stack overflow; Windows default stack is 1 MB). Linked with `-Wl,--stack,268435456`.
12. **Not built:** modules that need Linux sockets or MPI and are not used by the generator (`mHdr`, `mCatSearch` and similar). The top-level `make` was not used as a whole: after the libraries the executables were built module by module (`MontageLib/<module>`, `grid/Pegasus/{mConcatFit,mDAGTbls}`).

## Generator changes (for Windows only)

`data/montage/montage-workflow-windows.py` is a copy of the upstream `montage-workflow.py` with three edits (diff: `montage_build/montage-workflow-windows.diff`): `which()` also tries `.exe`; the transformation catalog lists only `*.exe` files and strips the extension; the centre argument is passed to `mArchiveList` in double quotes (cmd.exe does not understand single quotes). The workflow content it writes (jobs, arguments, files) is the upstream generator's, unedited.

## Executables used by the workflow

`mProject, mDiffFit (the `grid/Pegasus` version), mDiff, mFitplane, mConcatFit (grid/Pegasus), mBgModel, mBackground, mImgtbl, mAdd, mViewer, mArchiveList, mDAGTbls (grid/Pegasus), mOverlaps` - all present in `data/montage/bin_win64/` (hashes recorded).

## mDiffFit variant: a failed first attempt (kept)

Sequential run 1 (`data/results/stage1_20261011/seq_run1/`, status `failed:ID0000011`) used the `MontageLib` `mDiffFit`, which exits 1 with `Images don't overlap` for pairs that `mOverlaps` listed but whose projected images do not overlap. The `grid/Pegasus` `mDiffFit` (source read: it ignores exactly the messages "Images don't overlap" and "All pixels are blank.", creates an empty output and exits 0) is the variant the Pegasus workflow needs; it spawns `mDiff`/`mFitplane` through the ported `svc` library. `bin_win64/mDiffFit.exe` is now the grid version (tested on the failing pair: exit 0, status file written); the MontageLib build is kept as `bin_alt/mDiffFit_MontageLib.exe`. Run 1 is not a valid reference and is excluded from every gate; it is kept as evidence of the failure. Runs A, B and C (`seq_runA/B/C`) then also FAILED at the first `mDiffFit`: the grid `mDiffFit` spawns `mDiff` by name through the `svc` library and the runner had not put `bin_win64` on `PATH` (`svc_init(): fork() failed`, exit 0xC0000005). They are kept as evidence of that failure and excluded from every gate. The valid Stage 1 runs are `rep1`, `rep2`, `rep3` (runner fixed to put `bin_win64` on `PATH`, as Pegasus would).

## Further failed attempts before the valid reference runs (kept)

* `rep1`, `rep2`, `rep3` (first set, started 18:23/18:57, three of them partly concurrent) all stopped at the first tolerated non-overlap `mDiffFit`: the sequential runner treated the text `stat="ERROR"` that the grid `mDiffFit` prints (and then exits 0 on purpose) as a failure. Runner fixed (exit status plus declared outputs decide). Those directories and `stage1_gate_INVALID_failed_runs_20261011.json` are kept as evidence and excluded. Running three at once also made `mProject` 2-4 times slower than alone (191-484 s versus about 115 s), so timing runs are not run concurrently.
* A debug resume (`debug_resume1..3`, seeded from the projected images of `rep1`, label `debug`, not evidence) found the `mImgtbl` and `mViewer` problems above; `debug_resume3` completed all downstream tasks. Per-task times of the 48 downstream tasks were seconds, almost all of the work is the nine `mProject` tasks.
