#---------------------------------------------------------------------------------
# snesgame2 - PVSnesLib build (Linux / WSL)
#
# Requires PVSNESLIB_HOME to point at your PVSnesLib install. Set it once in your
# shell profile (~/.bashrc), using a Unix-style path:
#
#     export PVSNESLIB_HOME=/opt/pvsneslib
#
# Targets:
#   make            build everything (assets + ROM)  ->  snesgame2.sfc
#   make all        same as `make`
#   make artifacts  convert source art/sound into SNES data, without linking the ROM
#   make clean      remove the ROM, build intermediates, and generated asset data
#---------------------------------------------------------------------------------

ifeq ($(strip $(PVSNESLIB_HOME)),)
$(error PVSNESLIB_HOME is not set. Point it at your PVSnesLib install with a Unix-style path, e.g. `export PVSNESLIB_HOME=/opt/pvsneslib`)
endif

# BEFORE including snes_rules:
# list every .it file (effects first, then any music) in AUDIOFILES so smconv
# builds the soundbank, and point SOUNDBANK at where to emit it. sfx.it MUST
# stay first -- smconv treats the first IT file as the shared effects bank and
# bakes it into every module after it, so effects stay playable once a music
# module is loaded (see res/summergames.it's recipe below and the
# PVSnesLib audio/effectsandmusic example).
AUDIOFILES := res/sfx.it res/summergames.it
export SOUNDBANK := res/soundbank

include $(PVSNESLIB_HOME)/devkitsnes/snes_rules

# ROMNAME is used by snes_rules to name the linked ROM.
export ROMNAME := snesgame2

# smconv flags: -s strip, -o output, -V verbose, -b 5 = place the bank in ROM
# bank 5, -f = check combined size against the 1st (effects) IT file.
SMCONVFLAGS := -s -o $(SOUNDBANK) -V -b 5 -f

.PHONY: all artifacts bitmaps musics brrsound clean

#---------------------------------------------------------------------------------
# Top-level targets
#---------------------------------------------------------------------------------
# Everything: convert the assets, then compile + link the ROM.
all: artifacts $(ROMNAME).sfc

# Just the converted SNES data: graphics, the sound bank, and the BRR sample.
# Useful to refresh assets (or sanity-check conversions) without a full link.
artifacts: bitmaps musics brrsound

# The ROM embeds the converted assets, so make sure they exist before linking
# (order-only: regenerated assets don't force a needless relink).
$(ROMNAME).sfc: | artifacts

# Remove build results and generated graphics/audio (rules from snes_rules).
clean: cleanBuildRes cleanRom cleanGfx cleanAudio

#---------------------------------------------------------------------------------
# Graphics: convert source images -> .pic + .pal (+ .inc / _data.as)
#---------------------------------------------------------------------------------
# Bundled console font (8x8 tiles)
pvsneslibfont.pic: pvsneslibfont.png
	@echo convert font ... $(notdir $@)
	$(GFXCONV) -s 8 -o 16 -u 16 -p -e 0 -i $<

# Player sprite sheet (32x32)
sprites.pic: sprites.bmp
	@echo convert sprite ... $(notdir $@)
	$(GFXCONV) -s 32 -o 16 -u 16 -t bmp -i $<

# Sega Genesis enemy (32x32)
enemy.pic: enemy.bmp
	@echo convert enemy ... $(notdir $@)
	$(GFXCONV) -s 32 -o 16 -u 16 -t bmp -i $<

# Player bullet (8x8)
bullet.pic: bullet.bmp
	@echo convert bullet ... $(notdir $@)
	$(GFXCONV) -s 8 -o 16 -u 16 -t bmp -i $<

# Bomb power-up pickup (32x32)
powerup.pic: powerup.bmp
	@echo convert powerup ... $(notdir $@)
	$(GFXCONV) -s 32 -o 16 -u 16 -t bmp -i $<

# TAC-2 joystick, the tough 3-hit enemy (32x32)
tac2.pic: tac2.bmp
	@echo convert tac2 ... $(notdir $@)
	$(GFXCONV) -s 32 -o 16 -u 16 -t bmp -i $<

# Parallax space backdrop. The source BMPs are produced by
# tools/make_space_bmp.py -- regenerate them with `python3 tools/make_space_bmp.py`
# when tweaking the art. Their palette indices are the final CGRAM entries.
# Deep-space layer (BG2, 2bpp): -u 4 takes each tile's sub-palette from index // 4.
deepspace.pic: deepspace.bmp
	@echo convert deep space ... $(notdir $@)
	$(GFXCONV) -s 8 -o 32 -u 4 -p -m -t bmp -i $<

# Near starfield (BG1, 4bpp, sub-palette 2 = indices 32..47)
nearstars.pic: nearstars.bmp
	@echo convert near stars ... $(notdir $@)
	$(GFXCONV) -s 8 -o 48 -u 16 -p -m -t bmp -i $<

# Backdrop gradient -> HDMA colour table, plus its upside-down twin
skygrad_grad_data.as: skygrad.bmp
	@echo make gradient list ... $(notdir $@)
	$(GFXCONV) -n -t bmp -i $<

skygrad_flip_grad_data.as: skygrad_flip.bmp
	@echo make gradient list ... $(notdir $@)
	$(GFXCONV) -n -t bmp -i $<

bitmaps: pvsneslibfont.pic sprites.pic enemy.pic bullet.pic powerup.pic tac2.pic \
         deepspace.pic nearstars.pic skygrad_grad_data.as skygrad_flip_grad_data.as

#---------------------------------------------------------------------------------
# Sound: music/effects bank (smconv) + gun-fire BRR sample (snesbrr)
#---------------------------------------------------------------------------------
musics: $(SOUNDBANK).obj

# Gun-fire effect: snesbrr-encode the synthesized WAV into a BRR sample.
# res/gunshot.wav is produced by tools/make_gunshot.py -- regenerate it with
# `python3 tools/make_gunshot.py` when tweaking the sound; the build itself only
# needs snesbrr, so it has no Python dependency.
res/gunshot.brr: res/gunshot.wav
	@echo convert gunshot wav -> brr ... $(notdir $@)
	$(BRCONV) -e $< $@

brrsound: res/gunshot.brr

# Game-completion music: converted from the MIDI by tools/make_music_it.py
# (smconv only accepts Impulse Tracker modules, not raw MIDI). Regenerate with
# `python3 tools/make_music_it.py` when tweaking the MIDI or the converter.
res/summergames.it: music/summergames.mid tools/make_music_it.py
	@echo convert midi -> it ... $(notdir $@)
	python3 tools/make_music_it.py
