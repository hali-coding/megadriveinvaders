.include "hdr.asm"

; --- Console font (text) ---
.section ".rodata1" superfree

tilfont:
.incbin "pvsneslibfont.pic"

palfont:
.incbin "pvsneslibfont.pal"

.ends

; --- Sprite graphics (generated from sprites.bmp by gfx4snes) ---
.section ".rosprite" superfree

.include "sprites_data.as"

.ends

; --- Sega Genesis enemy graphics (generated from enemy.bmp by gfx4snes) ---
.section ".roenemy" superfree

enemy_til:
.incbin "enemy.pic"
enemy_tilend:

enemy_pal:
.incbin "enemy.pal"
enemy_palend:

.ends

; --- Player bullet graphics (generated from bullet.bmp by gfx4snes) ---
.section ".robullet" superfree

bullet_til:
.incbin "bullet.pic"
bullet_tilend:

bullet_pal:
.incbin "bullet.pal"
bullet_palend:

.ends

; --- Bomb power-up graphics (generated from powerup.bmp by gfx4snes) ---
.section ".ropowerup" superfree

powerup_til:
.incbin "powerup.pic"
powerup_tilend:

powerup_pal:
.incbin "powerup.pal"
powerup_palend:

.ends

; --- TAC-2 joystick enemy graphics (generated from tac2.bmp by gfx4snes) ---
.section ".rotac2" superfree

tac2_til:
.incbin "tac2.pic"
tac2_tilend:

tac2_pal:
.incbin "tac2.pal"
tac2_palend:

.ends

; --- Parallax space backdrop (generated from deepspace.bmp / nearstars.bmp) ---
.section ".rodeepspace" superfree

deepspace_til:
.incbin "deepspace.pic"
deepspace_tilend:

deepspace_map:
.incbin "deepspace.map"
deepspace_mapend:

deepspace_pal:
.incbin "deepspace.pal"
deepspace_palend:

.ends

.section ".ronearstars" superfree

nearstars_til:
.incbin "nearstars.pic"
nearstars_tilend:

nearstars_map:
.incbin "nearstars.map"
nearstars_mapend:

nearstars_pal:
.incbin "nearstars.pal"
nearstars_palend:

.ends

; --- Backdrop gradient HDMA tables (generated from skygrad*.bmp by gfx4snes -n) ---
.section ".roskygrad" superfree

.include "skygrad_grad_data.as"
.include "skygrad_flip_grad_data.as"

.ends

; --- Gun-fire sound effect (BRR sample, snesbrr-encoded from res/gunshot.wav) ---
.section ".robrr" superfree

gunshot_brr:
.incbin "res/gunshot.brr"
gunshot_brrend:

.ends
