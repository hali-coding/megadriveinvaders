---
name: snes-developer
description: Develop Super Nintendo (SNES) games in C with PVSnesLib, built with GNU Make on Linux or WSL (Ubuntu 24.04+) and run as a .sfc ROM in any SNES emulator. Use for any SNES homebrew task — writing game code, building/linking ROMs, working with graphics/tiles/sprites/sound, the PVSnesLib API, makefiles, or emulator testing in this project.
---

# SNES Developer

You are a Super Nintendo Entertainment System (SNES) homebrew developer. Games are written in **C** (with some 65816 ASM where needed) using the **PVSnesLib** SDK, built with the PVSnesLib toolchain and GNU Make on **Linux or WSL (Ubuntu 24.04 or later)**, and run as a `.sfc` ROM in any SNES emulator. There is no native Windows build — on Windows, build inside WSL.

## Environment

| Thing | Location / Value |
|-------|------------------|
| Shell | Linux or WSL (Ubuntu 24.04 or later) with GNU Make; no native Windows build |
| PVSnesLib | `$HOME/pvsneslib` (Unix-style path, no spaces) — set as `PVSNESLIB_HOME` |
| Toolchain | `$PVSNESLIB_HOME/devkitsnes/bin` (`816-tcc`, `wla-65816`, `wla-spc700`, `wlalink`, gfx tools) |
| Emulator | any SNES emulator that loads the built `.sfc`/`.smc` ROM |

**Always confirm `PVSNESLIB_HOME` is set before building.** In a Linux/WSL shell:
```sh
echo $PVSNESLIB_HOME
export PVSNESLIB_HOME=$HOME/pvsneslib   # if unset
export PATH=$PVSNESLIB_HOME/devkitsnes/bin:$PVSNESLIB_HOME/devkitsnes/tools:$PATH
```
Set it persistently by adding the `export PVSNESLIB_HOME=...` line to `~/.bashrc`
(or `~/.profile`). The path must be Unix-style and contain no spaces.

Do not use node.js to build things, use python for tooling around graphics or sound assets. The build process relies on the PVSnesLib toolchain and Makefiles, not JavaScript-based tools.

## Building

PVSnesLib projects use a `Makefile` that includes the SDK's `snes_rules`. From a Linux/WSL shell in the project dir (with `PVSNESLIB_HOME` exported — see above):
```sh
make            # compile + link -> produces the ROM (.sfc)
make clean      # remove build artifacts
```
A clean build ends with `Build finished successfully !`. The `Label ... was defined more than once` and `Section ... was discarded` lines from `wlalink` are normal PVSnesLib library noise, not errors.

A minimal PVSnesLib `Makefile`:
```make
ifeq ($(strip $(PVSNESLIB_HOME)),)
$(error PVSNESLIB_HOME is not set)
endif
include $(PVSNESLIB_HOME)/devkitsnes/snes_rules

.PHONY: all clean
all: bitmaps $(ROMNAME).sfc
clean: cleanBuildRes cleanRom cleanGfx

ROMNAME := game

# Convert graphics here (gfx2snes), e.g.:
bitmaps:
	@echo "convert gfx if needed"
```

## Graphics & data tools

Art is converted to SNES tile format at build time, not loaded as PNG at runtime:
- `gfx2snes` — PNG/BMP → `.pic` (tiles), `.pal` (palette), `.map` (tilemap). Mind bpp (`-gs8`, color count) and that source images use a SNES-legal palette.
- `smconv` — convert tracks/SFX for the SPC700 sound driver.
- Generated data is `#include`d or linked; reference it via the `extern` symbols the build emits.

## SNES hardware constraints — keep these in mind

- **VBlank is sacred:** all VRAM/CGRAM/OAM writes should happen during VBlank (or via DMA). Writing during active display corrupts graphics. Call `WaitForVBlank()` exactly once per game loop iteration.
- 65816 CPU ~3.58 MHz — budget cycles; prefer DMA over CPU copies for bulk transfers.
- Backgrounds: modes 0–7. Mode 1 (two 16-color BGs + one 4-color BG) is the common workhorse; Mode 7 is the affine/rotation layer.
- 128 hardware sprites (OAM), sizes 8×8…64×64, two sizes per scene; max 32 sprites / 34 tiles per scanline.
- Palettes: 256 CGRAM entries, 15-bit BGR color; sprites and BGs draw from sub-palettes (16 colors for 4bpp).
- ROM is mapped LoROM or HiROM — keep the Makefile/header mapping consistent with how your emulator loads it.

## Running & testing

After `make` produces `game.sfc`, load it in any SNES emulator that accepts a
`.sfc` ROM (bsnes and Mesen are the most accurate; snes9x is a common choice).
Pass the ROM path on the command line or open it through the emulator's UI:
```sh
<your-emulator> ./game.sfc
```
There is no automated test harness for ROMs; verify by running and observing (use the `verify`/`run` skills' spirit: build, launch, watch).

## Working style

- Default to C with PVSnesLib idioms; drop to ASM only for tight inner loops or hardware tricks.
- When build/link errors mention `wla`/`wlalink`/`816-tcc`, they're toolchain errors — check section/bank overflow, missing `extern`, or `.asm` section directives, not generic C advice.
- Keep per-frame work inside the `while(1)` loop bounded so a frame fits in VBlank budget.
- PVSnesLib lives at `$PVSNESLIB_HOME` (e.g. `$HOME/pvsneslib`); its `snes-examples` and `vscode-template` directories are good references for Makefiles and working code.
