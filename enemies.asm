;==============================================================================
; enemies.asm - the per-enemy inner loops, hand-written in 65816 assembly.
;
; 816-tcc rebuilds a 24-bit pointer for every C array access, so once the board
; fills up these loops were most of each frame. Here they walk the enemy arrays
; with one index register instead -- X = enemy index * 2, which is why every
; enemy array these routines touch is 16 bits wide -- and leave all the game
; logic (spawning, scoring, sound) to src/main.c.
;
; ptrBank at the end is a small helper main.c needs for its HDMA setup.
;
; Called from C: 16-bit A/X/Y on entry and exit, arguments on the stack from
; 4,s up (first argument lowest), return value in tcc__r0. tcc__r0..r2 are the
; compiler's scratch registers, free to clobber here. Data is reached with long
; addressing, so the data bank register is never touched.
;==============================================================================

.include "hdr.asm"

.accu 16
.index 16
.16bit

; Mirrors of main.c's constants -- keep in sync.
.define ENEMY_SIZE       21
.define PLAYFIELD_TOP    24
.define PLAYFIELD_BOTTOM 200
.define OFFSCREEN_Y      224     ; parked sprites, and the line enemies escape past
.define SPRITE_SIZE      32      ; enemy sprites are 32x32 cells
.define NO_ENEMY         $FFFF

.RAMSECTION ".enemyasm_bss" BANK $7E SLOT 2
enemyEscapes dsb 2               ; out: enemies that escaped un-hit this frame
.ENDS

.SECTION ".enemyasm_text" SUPERFREE

;------------------------------------------------------------------------------
; unsigned short enemyMoveAll(void)
;
; One frame of timers and movement for every active enemy:
;   - the chipped-hit flicker (enemyHurt) counts down whatever else happens;
;   - a dying enemy (enemyFlash > 0) holds still while its blink counts down,
;     and is due a respawn when it reaches 0;
;   - any other enemy adds its sub-pixel speed to enemyFrac and moves the
;     whole pixels toward the ship (down normally, up when upsideDown), and is
;     due a respawn -- plus a score penalty -- once it escapes past the far
;     edge (y >= 224 going down, y <= -ENEMY_SIZE going up).
; Returns the respawn mask (bit i = enemy i) and counts escapes in enemyEscapes.
; The caller runs the respawns in index order, so the RNG sequence -- and the
; game -- play out exactly as when C did it all inline.
;------------------------------------------------------------------------------
enemyMoveAll:
    rep #$30
    lda.w #0
    sta.l enemyEscapes
    sta.b tcc__r0               ; respawn mask, built up below
    lda.l activeEnemies
    and.w #$00FF
    beq @done
    tay                         ; Y = enemies left to do
    lda.w #1
    sta.b tcc__r1               ; mask bit of the current enemy
    ldx.w #0                    ; X = enemy index * 2

@loop:
    lda.l enemyHurt,x           ; chipped flicker fades
    beq +
    dec a
    sta.l enemyHurt,x
+
    lda.l enemyFlash,x
    beq @move
    dec a                       ; dying: count the blink down...
    sta.l enemyFlash,x
    bne @next
    bra @respawn                ; ...and drop a fresh enemy in at 0

@move:
    lda.l enemyFrac,x           ; acc = frac + speed (both < 256)
    clc
    adc.l enemySpeed,x
    pha
    and.w #$00FF
    sta.l enemyFrac,x           ; keep the fraction
    pla
    xba
    and.w #$00FF
    sta.b tcc__r2               ; whole pixels to move (0 or 1)
    lda.l upsideDown
    and.w #$00FF
    bne @climb

    lda.l enemyY,x              ; descend toward the ship at the bottom
    clc
    adc.b tcc__r2
    sta.l enemyY,x
    cmp.w #OFFSCREEN_Y          ; (y stays well inside +-16K, so N is the
    bmi @next                   ; signed result) y < 224: still on screen
    bra @escaped

@climb:
    lda.l enemyY,x              ; upside-down: climb toward the ship at the top
    sec
    sbc.b tcc__r2
    sta.l enemyY,x
    clc
    adc.w #ENEMY_SIZE
    beq @escaped                ; y + ENEMY_SIZE <= 0: gone off the top
    bpl @next

@escaped:
    lda.l enemyEscapes
    inc a
    sta.l enemyEscapes
@respawn:
    lda.b tcc__r0
    ora.b tcc__r1
    sta.b tcc__r0
@next:
    asl.b tcc__r1
    inx
    inx
    dey
    bne @loop
@done:
    rtl

;------------------------------------------------------------------------------
; void enemyDrawAll(void)
;
; Write every active enemy's position into the OAM shadow buffer (enemy i is
; sprite i + 1, as main.c's OAM_ENEMY). Nothing is hidden behind the stats bar
; here: the HDMA sprite window (main.c, setScreenOrientation) masks the bar's
; scanlines, so an enemy slides out from under the bar instead of popping in
; at its edge. An enemy is only parked off-screen while it's wholly above the
; screen (y < -31: an 8-bit sprite Y would wrap it round to the bottom) or
; below it (y >= 224), on the off beat of its death blink (enemyFlash bit 1)
; or mid chipped-hit flicker (enemyHurt bit 0). X and Y go in as one 16-bit
; store: enemy x stays within 0..255, so OAM's X bit 8 never changes.
;------------------------------------------------------------------------------
enemyDrawAll:
    rep #$30
    lda.l activeEnemies
    and.w #$00FF
    beq @done
    asl a
    sta.b tcc__r0               ; loop limit: active enemies * 2
    ldx.w #0

@loop:
    lda.l enemyFlash,x
    and.w #2
    bne @hide
    lda.l enemyHurt,x
    and.w #1
    bne @hide
    lda.l enemyY,x
    cmp.w #(1 - SPRITE_SIZE)
    bmi @hide                   ; wholly above the screen
    cmp.w #OFFSCREEN_Y
    bpl @hide                   ; wholly below it
    xba                         ; y's low byte to the high half...
    and.w #$FF00
    ora.l enemyX,x              ; ...x (0..255) in the low half
    bra @store
@hide:
    lda.w #(OFFSCREEN_Y << 8)   ; x = 0, y = OFFSCREEN_Y
@store:
    tay                         ; hold the OAM word while X is rescaled:
    phx                         ; sprite i + 1's bytes start at 4 + 4i = 4 + 2X
    txa
    asl a
    tax
    tya
    sta.l oamMemory + 4,x
    plx
    inx
    inx
    cpx.b tcc__r0
    bcc @loop
@done:
    rtl

;------------------------------------------------------------------------------
; unsigned short enemyFindHit(short x, short y, unsigned short span,
;                             unsigned short skipHud)
;
; Index of the first active, non-dying enemy whose box overlaps the caller's,
; or NO_ENEMY. Each axis is one unsigned compare: the caller adds its own box
; size - 1 to x and y and passes span = ENEMY_SIZE + its size - 1, so the axis
; overlaps when (unsigned)(x - enemyX) < span. skipHud = 1 (the ship) also
; ignores enemies still behind the stats bar.
;------------------------------------------------------------------------------
enemyFindHit:
    rep #$30
    lda.l activeEnemies
    and.w #$00FF
    beq @none
    tay
    ldx.w #0

@loop:
    lda 4,s                     ; x
    sec
    sbc.l enemyX,x
    cmp 8,s                     ; < span?
    bcs @next
    lda 6,s                     ; y
    sec
    sbc.l enemyY,x
    cmp 8,s
    bcs @next
    lda.l enemyFlash,x          ; already dying: not a target
    bne @next
    lda 10,s
    beq @hit                    ; bullets don't care about the stats bar
    lda.l upsideDown
    and.w #$00FF
    bne @barBottom
    lda.l enemyY,x
    cmp.w #PLAYFIELD_TOP
    bmi @next                   ; behind the bar at the top
    bra @hit
@barBottom:
    lda.l enemyY,x
    cmp.w #(PLAYFIELD_BOTTOM - ENEMY_SIZE + 1)
    bpl @next                   ; behind the bar at the bottom
@hit:
    txa
    lsr a                       ; X / 2 = enemy index
    sta.b tcc__r0
    rtl
@next:
    inx
    inx
    dey
    bne @loop
@none:
    lda.w #NO_ENEMY
    sta.b tcc__r0
    rtl

;------------------------------------------------------------------------------
; unsigned short ptrBank(const void *p)
;
; The bank byte of a 24-bit pointer, for programming an HDMA channel's source
; bank from C: 816-tcc drops it in an (unsigned long) cast.
;------------------------------------------------------------------------------
ptrBank:
    rep #$30
    lda 6,s                     ; pointer = address word at 4,s, bank word at 6,s
    and.w #$00FF
    sta.b tcc__r0
    rtl

.ENDS
