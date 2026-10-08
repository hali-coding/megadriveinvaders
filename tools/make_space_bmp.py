#!/usr/bin/env python3
# Generates the two parallax background layers that scroll behind the play field:
#
#   deepspace.bmp - 256x512, 2bpp art for BG2, the slow "far away" layer: faint
#                   planets (a ringed gas giant with a small moon, a teal crescent
#                   world, a rusty dwarf), a comet, a violet nebula, a distant
#                   spiral galaxy and a dusting of dim far stars.
#   nearstars.bmp - 256x512, 4bpp art for BG1, the fast "close by" layer:
#                   brighter, coloured stars, some soft-edged, and a handful of
#                   sparkles drawn in the twinkle colours main.c palette-cycles.
#   skygrad.bmp / skygrad_flip.bmp
#                 - 256x224 backdrop gradient, one colour per scanline, that
#                   gfx4snes -n turns into an HDMA table (normal / upside-down).
#
# Palette indices ARE the final CGRAM entries (main.c's DEEP_CG / NEAR_CG copy
# them straight across). gfx4snes derives each tile's sub-palette from
# index // 4 (2bpp) or index // 16 (4bpp), so every 8x8 tile may only draw from
# one sub-palette; Layer.put() enforces that. Index 0 is transparent.
#
# The maps wrap vertically (512px loop), so y coordinates wrap too. The layout
# is seeded, so re-running reproduces the same art byte-for-byte.
import math
import os
import random

from snesbmp import Canvas, save_bmp

W, H = 256, 512

# 4x4 ordered-dither thresholds: smooth shading out of only 3 colours per tile.
BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def dither(v, x, y, top):
    """Quantise v (0..1) to an integer 0..top with 4x4 ordered dithering."""
    t = max(0.0, min(1.0, v)) * top
    base = int(t)
    if base < top and (t - base) * 16 > BAYER[y & 3][x & 3] + 0.5:
        base += 1
    return base


def unit(x, y, z):
    n = math.sqrt(x * x + y * y + z * z)
    return (x / n, y / n, z / n)


# One light source for the whole scene, up and to the left of the viewer.
LIGHT = unit(-0.55, -0.5, 0.67)


def rgb5(r, g, b):
    """SNES 5-bit colour -> 8-bit BMP colour (gfx4snes maps it back exactly)."""
    return (r * 8, g * 8, b * 8)


class Layer:
    """A W x H canvas of CGRAM indices that tracks which sub-palette owns each tile."""

    def __init__(self, colors_per_pal):
        self.c = Canvas(W, H)
        self.cpp = colors_per_pal
        self.owner = {}

    def put(self, x, y, pal, shade):
        """Draw colour `shade` (1..cpp-1) of sub-palette `pal`; 0 draws nothing."""
        if shade <= 0 or not 0 <= x < W:
            return
        y %= H
        tile = (x >> 3, y >> 3)
        if self.owner.setdefault(tile, pal) != pal:
            raise SystemExit(f"tile {tile} would mix sub-palettes "
                             f"{self.owner[tile]} and {pal} -- move an object")
        self.c.g[y][x] = pal * self.cpp + shade

    def tile_free(self, tx, ty):
        return (tx, ty % (H // 8)) not in self.owner

    def finish(self):
        """Return the canvas, ready for gfx4snes.

        gfx4snes takes a tile's sub-palette from its top-left pixel, so a tile
        whose corner is index 0 lands in sub-palette 0 whatever it draws. Fill
        each tile's transparent pixels with its own sub-palette's colour 0 --
        still transparent on the SNES, but tagged with the right palette.
        """
        for (tx, ty), pal in self.owner.items():
            for y in range(ty * 8, ty * 8 + 8):
                row = self.c.g[y]
                for x in range(tx * 8, tx * 8 + 8):
                    if row[x] == 0:
                        row[x] = pal * self.cpp
        return self.c


# =============================================================================
# Deep space (2bpp: sub-palettes 2..7 = CGRAM 8..31; 0..1 belong to the font)
# =============================================================================
P_GIANT, P_ICE, P_RUST, P_MOON, P_NEBULA, P_STARS = 2, 3, 4, 5, 6, 7

# Each sub-palette: shadow, body, lit -- all kept dim and low-contrast against
# the navy sky so the planets read as faint and far away, never competing with
# the sprites.
DEEP_COLORS = {
    P_GIANT:  (rgb5(6, 5, 14),  rgb5(10, 7, 16),  rgb5(15, 10, 18)),   # dusky violet-rose
    P_ICE:    (rgb5(2, 7, 14),  rgb5(4, 11, 17),  rgb5(8, 16, 21)),    # teal ice world + comet
    P_RUST:   (rgb5(7, 4, 11),  rgb5(12, 7, 12),  rgb5(17, 10, 13)),   # rusty dwarf
    P_MOON:   (rgb5(6, 7, 14),  rgb5(10, 11, 17), rgb5(15, 16, 21)),   # grey moon
    P_NEBULA: (rgb5(5, 4, 14),  rgb5(8, 5, 16),   rgb5(11, 7, 19)),    # violet haze
    P_STARS:  (rgb5(8, 10, 18), rgb5(13, 15, 22), rgb5(20, 22, 27)),   # far stars + galaxy
}


def planet(layer, cx, cy, r, pal, light=LIGHT, surface=None):
    """Lambert-shaded disc. The shadow side still gets colour 1, so the disc
    blots out the far stars behind it -- a faint silhouette, not a hole."""
    for y in range(int(cy - r) - 1, int(cy + r) + 2):
        for x in range(int(cx - r) - 1, int(cx + r) + 2):
            dx = (x + 0.5 - cx) / r
            dy = (y + 0.5 - cy) / r
            d2 = dx * dx + dy * dy
            if d2 > 1.0:
                continue
            nz = math.sqrt(1.0 - d2)
            v = max(0.0, dx * light[0] + dy * light[1] + nz * light[2])
            if surface:
                v = surface(dx, dy, v)
            layer.put(x, y, pal, 1 + dither(v, x, y, 2))


def ringed_giant(layer, cx, cy, r, tilt_deg):
    """Banded gas giant with a tilted ring. The ring's near half (lower on
    screen) passes in front of the planet; its far half is hidden behind it."""
    ct, st = math.cos(math.radians(tilt_deg)), math.sin(math.radians(tilt_deg))
    incline = 0.28                       # ring ellipse minor/major ratio

    def bands(dx, dy, v):
        lat = -dx * st + dy * ct         # latitude measured across the ring plane
        return v * (0.74 + 0.26 * math.sin(lat * 10.5 + 0.9 * math.sin(lat * 4.0)))

    planet(layer, cx, cy, r, P_GIANT, surface=bands)

    reach = int(r * 2.1) + 1
    for y in range(int(cy) - reach, int(cy) + reach + 1):
        for x in range(int(cx) - reach, int(cx) + reach + 1):
            dx = (x + 0.5 - cx) / r
            dy = (y + 0.5 - cy) / r
            u = dx * ct + dy * st
            w = -dx * st + dy * ct
            rr = math.sqrt(u * u + (w / incline) ** 2)
            if not 1.3 <= rr <= 2.0 or 1.62 <= rr <= 1.70:     # inner edge, Cassini gap
                continue
            if dx * dx + dy * dy <= 1.0 and w < 0:              # far side, behind the disc
                continue
            v = 0.5 - 0.3 * (u / 2.0) - 0.15 * (rr - 1.3)       # brighter toward the light
            layer.put(x, y, P_GIANT, 1 + dither(v, x, y, 2))


def craters(spots):
    def surface(dx, dy, v):
        for sx, sy, sr in spots:
            if (dx - sx) ** 2 + (dy - sy) ** 2 <= sr * sr:
                return v * 0.45
        return v
    return surface


def rusty(dx, dy, v):
    if dy < -0.72:                       # bright polar cap
        return min(1.0, v + 0.45)
    if -0.12 < dy < 0.05:                # dark equatorial dust belt
        return v * 0.55
    return v


def comet(layer, hx, hy, length, angle_deg):
    """Bright head with a tail that fans out away from the light."""
    ca, sa = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    for y in range(int(hy) - length - 3, int(hy) + length + 4):
        for x in range(int(hx) - length - 3, int(hx) + length + 4):
            px, py = x + 0.5 - hx, y + 0.5 - hy
            along = px * ca + py * sa
            across = -px * sa + py * ca
            if along < -1.5 or along > length:
                continue
            width = 0.7 + along * 0.11
            fade = (1.0 - max(0.0, along) / length) ** 1.4
            v = fade * math.exp(-(across / width) ** 2)
            if along < 1.2 and abs(across) < 1.2:             # the head itself
                v = 1.0
            layer.put(x, y, P_ICE, dither(v * 1.15, x, y, 3))


def galaxy(layer, gx, gy, a, b, tilt_deg):
    """Small, tilted two-armed spiral: a bright core, faint dithered arms."""
    ct, st = math.cos(math.radians(tilt_deg)), math.sin(math.radians(tilt_deg))
    reach = int(a) + 2
    for y in range(int(gy) - reach, int(gy) + reach + 1):
        for x in range(int(gx) - reach, int(gx) + reach + 1):
            px, py = x + 0.5 - gx, y + 0.5 - gy
            gxp = (px * ct + py * st) / a
            gyp = (-px * st + py * ct) / b
            rho = math.sqrt(gxp * gxp + gyp * gyp)
            if rho > 1.15:
                continue
            phi = math.atan2(gyp, gxp)
            arms = 0.5 + 0.5 * math.cos(2.0 * (phi - 2.4 * math.log(rho + 0.06)))
            v = 1.1 * math.exp(-(rho / 0.16) ** 2) + 0.75 * math.exp(-rho * 2.4) * arms ** 1.5
            layer.put(x, y, P_STARS, dither(v, x, y, 3))


class ValueNoise:
    """Smooth value noise on a lattice that wraps vertically (seamless loop)."""

    def __init__(self, rng, cell):
        self.cell = cell
        self.rows = H // cell
        self.cols = W // cell + 2
        self.v = [[rng.random() for _ in range(self.cols)] for _ in range(self.rows)]

    def __call__(self, x, y):
        fx, fy = x / self.cell, y / self.cell
        ix, iy = int(math.floor(fx)), int(math.floor(fy))
        tx, ty = fx - ix, fy - iy
        tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
        r0, r1 = self.v[iy % self.rows], self.v[(iy + 1) % self.rows]
        top = r0[ix] + (r0[ix + 1] - r0[ix]) * tx
        bot = r1[ix] + (r1[ix + 1] - r1[ix]) * tx
        return top + (bot - top) * ty


def nebula(layer, rng, blobs, x0, x1, y0, y1):
    """Wispy violet haze: fractal noise shaped by a few soft elliptical blobs.
    Below a threshold it is transparent, so the edges break up into specks."""
    octaves = [(ValueNoise(rng, c), amp) for c, amp in ((32, 0.5), (16, 0.27), (8, 0.15), (4, 0.08))]
    for y in range(y0, y1):
        for x in range(x0, x1):
            mask = 0.0
            for bx, by, rx, ry, k in blobs:
                mask += k * math.exp(-(((x - bx) / rx) ** 2 + ((y - by) / ry) ** 2))
            if mask < 0.05:
                continue
            n = sum(noise(x, y) * amp for noise, amp in octaves)
            v = mask * (0.25 + 1.1 * n) - 0.3
            layer.put(x, y, P_NEBULA, dither(v / 0.75, x, y, 3))


def deep_space():
    rng = random.Random(0x5EED)
    d = Layer(4)

    # Ringed gas giant, its little cratered moon, and a distant spiral galaxy.
    ringed_giant(d, 176, 96, 21, -18)
    planet(d, 92, 60, 6, P_MOON, surface=craters(((-0.3, 0.1, 0.32), (0.35, -0.3, 0.22), (0.1, 0.55, 0.2))))
    galaxy(d, 52, 180, 17, 7, 28)

    # Teal ice world lit from behind: a thin crescent on the upper-left limb,
    # the rest of the disc a faint, dark silhouette against the stars.
    planet(d, 196, 252, 19, P_ICE, light=unit(-0.75, -0.4, -0.55),
           surface=lambda dx, dy, v: min(1.0, v * 2.4))

    # Comet streaking past, tail pointing away from the light (down-right).
    comet(d, 70, 318, 34, 38)

    # Rusty dwarf planet with a polar cap.
    planet(d, 40, 384, 9, P_RUST, surface=rusty)

    # Nebula drifting through the lower part of the loop.
    nebula(d, rng,
           blobs=((150, 438, 52, 22, 1.0), (196, 414, 30, 26, 0.8),
                  (110, 462, 36, 16, 0.75), (230, 452, 26, 14, 0.5)),
           x0=64, x1=256, y0=384, y1=496)
    # A few brighter stars embedded in the nebula glow.
    for sx, sy in ((132, 432), (178, 420), (204, 446), (118, 458)):
        if d.c.g[sy][sx]:
            d.put(sx, sy, P_NEBULA, 3)

    # Dim far stars, at most one per otherwise-empty tile so they never share
    # a tile (and a palette) with an object. A few are tiny 3x3 crosses.
    placed = 0
    while placed < 150:
        tx, ty = rng.randrange(W // 8), rng.randrange(H // 8)
        if not d.tile_free(tx, ty):
            continue
        roll = rng.random()
        if placed % 25 == 0:                                 # small cross
            x, y = tx * 8 + rng.randint(1, 6), ty * 8 + rng.randint(1, 6)
            d.put(x, y, P_STARS, 3)
            for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                d.put(x + ox, y + oy, P_STARS, 1)
        else:
            shade = 1 if roll < 0.6 else (2 if roll < 0.9 else 3)
            d.put(tx * 8 + rng.randrange(8), ty * 8 + rng.randrange(8), P_STARS, shade)
        placed += 1

    pal = [(248, 0, 248)] + [(0, 0, 0)] * 7          # 0..7: unused here (font's CGRAM)
    for p in range(2, 8):
        pal += [(0, 0, 0)] + list(DEEP_COLORS[p])
    return d.finish(), pal


# =============================================================================
# Near stars (4bpp: sub-palette 2 = CGRAM 32..47)
# =============================================================================
NEAR_PAL = 2

# Static star colours: (bright core, matching dim halo) pairs plus a dim grey.
WHITE, WHITE_MID, DIM, BLUE, BLUE_DIM, YELLOW, YELLOW_DIM, ORANGE, ORANGE_DIM = range(1, 10)
HALO = {WHITE: DIM, BLUE: BLUE_DIM, YELLOW: YELLOW_DIM, ORANGE: ORANGE_DIM}
# 10..15: three twinkle groups x (core, arm). main.c cycles these in CGRAM, so
# these are just the starting colours -- keep them equal to TWK_CORE0 /
# TWK_ARM0 there.
TWINKLE_CORE = (10, 12, 14)
TWINKLE_ARM = (11, 13, 15)

NEAR_COLORS = [
    (248, 0, 248),        # 0 transparent
    rgb5(31, 31, 31),     # 1 white
    rgb5(22, 23, 27),     # 2 white, mid
    rgb5(13, 15, 22),     # 3 dim grey-blue (white halo)
    rgb5(25, 28, 31),     # 4 blue-white
    rgb5(13, 17, 28),     # 5 blue halo
    rgb5(31, 29, 21),     # 6 pale yellow
    rgb5(20, 18, 14),     # 7 yellow halo
    rgb5(31, 22, 15),     # 8 orange
    rgb5(20, 12, 11),     # 9 orange halo
] + [rgb5(31, 31, 31), rgb5(24, 25, 31)] * 3   # 10..15 twinkle core/arm, phase 0


def near_stars():
    rng = random.Random(0x57A5)
    n = Layer(16)

    # Pick distinct, well-spread tiles: no two stars in neighbouring tiles
    # (wrapping vertically), so the field stays even with no clumps.
    cells = []
    while len(cells) < 44:
        tx, ty = rng.randrange(W // 8), rng.randrange(H // 8)
        if any(abs(tx - cx) <= 1 and min(abs(ty - cy), H // 8 - abs(ty - cy)) <= 1 for cx, cy in cells):
            continue
        cells.append((tx, ty))

    # Every star sits wholly inside its own tile, which keeps the tile count low.
    for i, (tx, ty) in enumerate(cells):
        ox, oy = tx * 8, ty * 8
        if i < 6:                                            # twinkling sparkle (5x5 cross)
            g = i % 3
            x, y = ox + rng.randint(2, 5), oy + rng.randint(2, 5)
            n.put(x, y, NEAR_PAL, TWINKLE_CORE[g])
            for d in (1, 2):
                for sx, sy in ((d, 0), (-d, 0), (0, d), (0, -d)):
                    n.put(x + sx, y + sy, NEAR_PAL, TWINKLE_ARM[g])
        elif i < 18:                                         # soft star (3x3 plus)
            core = rng.choice((WHITE, WHITE, BLUE, YELLOW, ORANGE))
            x, y = ox + rng.randint(1, 6), oy + rng.randint(1, 6)
            n.put(x, y, NEAR_PAL, core)
            for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n.put(x + sx, y + sy, NEAR_PAL, HALO[core])
        else:                                                # single-pixel star
            c = rng.choice((WHITE, WHITE, WHITE_MID, WHITE_MID, DIM, DIM,
                            BLUE, BLUE, YELLOW, ORANGE))
            n.put(ox + rng.randrange(8), oy + rng.randrange(8), NEAR_PAL, c)

    pal = [(248, 0, 248)] + [(0, 0, 0)] * 31 + NEAR_COLORS    # 0..31 unused here
    return n.finish(), pal


# =============================================================================
# Sky gradient (HDMA rewrites the backdrop colour, CGRAM 0, every scanline)
# =============================================================================
# Near-black navy at the top easing into the game's familiar navy toward the
# bottom. With only 32 levels per channel a smooth ramp shows as hard bands,
# so each scanline is ordered-dithered between its two nearest levels.
# gfx4snes -n turns the colour of each image row into an HDMA table entry.
SKY_TOP = (0.4, 1.0, 5.0)
SKY_BOTTOM = (3.4, 4.6, 14.6)
LINE_DITHER = (0.125, 0.625, 0.375, 0.875)


def sky_gradient(flip):
    """256x224 image, one colour per scanline. flip=True is the same ramp
    upside down, for the upside-down world."""
    c = Canvas(256, 224)
    pal = []
    for y in range(224):
        t = (223 - y if flip else y) / 223
        col = rgb5(*(min(31, int(a + (b - a) * t + LINE_DITHER[y & 3]))
                     for a, b in zip(SKY_TOP, SKY_BOTTOM)))
        if col not in pal:
            pal.append(col)
        c.rect(0, y, 255, y, pal.index(col))
    return c, pal


def main():
    root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
    for name, (canvas, pal) in (("deepspace.bmp", deep_space()), ("nearstars.bmp", near_stars()),
                                ("skygrad.bmp", sky_gradient(False)),
                                ("skygrad_flip.bmp", sky_gradient(True))):
        size = save_bmp(os.path.join(root, name), canvas, pal)
        print(f"Wrote {name} ({size} bytes)")


if __name__ == "__main__":
    main()
