#!/usr/bin/env python3
"""Sketches of the eight level backgrounds (work in progress, approved style).

Draws the 256x192 backgrounds procedurally with the C64 palette and applies the
real limits of the C64 screen: 2 colours per 8x8 cell, rows 0-2 left black for
the texts, and one flat colour under each floor line (that cell shares its
colour with the floor). Writes assets/backgrounds/scheme<N>_<name>.png, one per
colour scheme (level = scheme, scheme + 8, ...). These PNGs are the masters:
they can also be retouched by hand with any paint program, as long as they keep
the limits above (platforms/c64/tools/convert_c64.py checks them).

usage: sketch_backgrounds.py [OUTDIR [MOCKUP.png]]     (needs numpy and Pillow)
"""
import math, os, random, sys
import numpy as np
from PIL import Image, ImageDraw

W, H = 256, 192
K, WH, R, C, P, G, B, Y, O, BR, LR, DG, MG, LG, LB, LGR = range(16)
PEPTO = [(0,0,0),(255,255,255),(104,55,43),(112,164,178),(111,61,134),
         (88,141,67),(53,40,121),(184,199,111),(111,79,37),(67,57,0),
         (154,103,89),(68,68,68),(108,108,108),(154,210,132),(108,94,181),
         (149,149,149)]
NAMES = ["NIGHT SKY", "SUNSET", "DEEP SEA", "CRIMSON", "PURPLE HAZE",
         "TWILIGHT", "VOLCANO", "AURORA"]
# floor colours, floor 0 (ground) .. 6, per colour scheme (from lev_floor)
FLOORS = [[13,13,7,3,1,1,7], [7,1,7,3,13,7,3], [3,3,13,7,3,1,1],
          [7,7,3,13,7,3,1], [3,3,1,1,7,3,13], [13,3,13,7,3,1,1],
          [7,7,3,13,7,3,1], [13,1,7,3,13,7,3]]
FLOOR_ROW = [23, 20, 17, 14, 11, 8, 5]

yy, xx = np.mgrid[0:H, 0:W]
BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16 + 1 / 32
TH = BAYER[yy % 4, xx % 4]


def mix(c1, c2, t):
    """Ordered dither between two colours; t=0 -> c1, t=1 -> c2."""
    return np.where(np.asarray(t) > TH, c2, c1).astype(np.uint8)


def chain(img, stops):
    """Vertical gradient through (y, colour) stops, dithered between them."""
    for (y0, c0), (y1, c1) in zip(stops, stops[1:]):
        t = np.clip((yy - y0) / max(1, (y1 - y0)), 0, 1)
        m = (yy >= y0) & (yy < y1)
        img[m] = mix(c0, c1, t)[m]
    img[yy >= stops[-1][0]] = stops[-1][1]


def shape(draw_fn):
    im = Image.new("L", (W, H), 0)
    draw_fn(ImageDraw.Draw(im))
    return np.array(im) > 0


def disc(cx, cy, r):
    return (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r


def ridge(seed, base, amp, periods=(110, 47, 19), weights=(0.6, 0.3, 0.1), jag=0.0, peaky=False):
    rnd = random.Random(seed)
    x = np.arange(W)
    y = np.zeros(W)
    for per, wt in zip(periods, weights):
        s = np.sin(x / per * 2 * math.pi + rnd.uniform(0, 6.28))
        if peaky:
            s = 1 - 2 * np.abs(s)
        y += wt * s
    if jag:
        y += np.array([rnd.uniform(-jag, jag) for _ in x]) / max(amp, 1)
    return base + amp * y


def below(r):
    return yy >= np.round(r).astype(int)[xx]


def flat_cells(img):
    """Boolean 24x32 map: cell holds a single colour."""
    c = img.reshape(24, 8, 32, 8).transpose(0, 2, 1, 3).reshape(24, 32, 64)
    return (c.max(axis=2) == c.min(axis=2))


def is_floor_row(r):
    return r in FLOOR_ROW


def stars(img, n, seed, colours=(WH, LGR, LGR, Y, LB), big=6, on=K, ymax=H):
    """Stars only in cells that are entirely colour `on` and not floor rows."""
    rnd = random.Random(seed)
    flat = flat_cells(img)
    placed = 0
    tries = 0
    while placed < n and tries < n * 40:
        tries += 1
        x, y = rnd.randrange(W), rnd.randrange(24, min(ymax, 184))
        r, c = y // 8, x // 8
        if is_floor_row(r) or not flat[r, c] or img[y, x] != on:
            continue
        col = rnd.choice(colours)
        img[y, x] = col
        if placed < big and 1 <= x % 8 <= 6 and 1 <= y % 8 <= 6:
            img[y - 1, x] = img[y + 1, x] = img[y, x - 1] = img[y, x + 1] = col
        flat[r, c] = False          # one star per cell keeps cells at 2 colours
        placed += 1


# ------------------------------------------------------------------ scenes
def night_sky():
    img = np.zeros((H, W), np.uint8)
    chain(img, [(24, K), (104, K), (168, B), (184, B)])
    # big moon centred on a floor line, edges on cell boundaries there
    moon = disc(195.5, 67.5, 20)
    img[moon] = MG
    for cx, cy, r in ((188, 59, 4), (202, 73, 5), (204, 56, 3), (189, 78, 3), (182, 69, 2)):
        img[disc(cx, cy, r) & disc(195.5, 67.5, 16)] = DG
    stars(img, 70, 11, ymax=150)
    # hills and a sleeping village
    chain_end = None
    hr = np.clip(ridge(5, 176, 5, periods=(140, 60, 23)), 171, 182)
    hills = below(hr)
    img[hills] = K
    for px in (14, 22, 31, 66, 74, 118, 127, 135, 180, 189, 226, 234, 243):
        base = int(hr[px])
        ph = 7 + (px * 3) % 5
        for i in range(ph):
            wdt = i // 2
            y = base - ph + i
            if y >= 168:
                img[y, max(0, px - wdt):px + wdt + 1] = K
    return img


def sunset():
    img = np.zeros((H, W), np.uint8)
    chain(img, [(24, K), (40, B), (72, P), (104, R), (120, LR), (160, LR)])
    # clouds: thin streaks
    rnd = random.Random(8)
    for cy, col, base in ((52, P, B), (58, P, B), (84, R, P), (90, R, P)):
        for _ in range(3):
            cx, ln = rnd.randrange(10, 230), rnd.randrange(18, 46)
            for i in range(3):
                x0 = cx + i * 4
                img[cy + i, x0:x0 + ln - i * 8] = col
    # the sun: 40 px disc, sitting on the horizon (y=160)
    sun = disc(123.5, 139.5, 20) & (yy < 160)
    img[sun] = O
    for sy, th in ((132, 1), (140, 2), (147, 2), (153, 3)):
        img[sun & (yy >= sy) & (yy < sy + th)] = LR
    # distant islands on the horizon
    for x0, x1, hgt in ((14, 62, 7), (190, 250, 9)):
        m = shape(lambda d: d.polygon([(x0, 160), ((x0 * 2 + x1) // 3, 160 - hgt), ((x0 + x1 * 2) // 3, 160 - hgt + 2), (x1, 160)], fill=255))
        img[m] = K
    # birds
    for bx, by in ((60, 112), (72, 107), (180, 100), (194, 105), (40, 130)):
        for i in range(3):
            img[by + i, bx - 3 + i] = K
            img[by + i, bx + 3 - i] = K
    # sea: flat blue, dark ripples at the sides, sun glitter in the middle
    img[yy >= 160] = B
    rnd = random.Random(4)
    for y in range(169, 184, 2):
        for _ in range(9):
            x0 = rnd.choice((rnd.randrange(0, 80), rnd.randrange(168, 250)))
            img[y, x0:x0 + rnd.randrange(4, 12)] = K
    for y in range(168, 184, 2):
        half = 22 - (y - 168)
        for _ in range(4):
            x0 = 124 + rnd.randrange(-half, half)
            img[y, max(98, x0 - 4):min(150, x0 + rnd.randrange(3, 9))] = O
    return img


def deep_sea():
    img = np.zeros((H, W), np.uint8)
    chain(img, [(24, B), (64, B), (150, K)])
    # light shafts from the surface (in the flat blue zone only)
    for x0, wd in ((40, 14), (100, 20), (170, 12), (215, 16)):
        sh = (xx - (x0 + (yy - 24) * 0.45))
        m = (sh >= 0) & (sh < wd) & (yy >= 24) & (yy < 64)
        t = np.clip(0.55 - (yy - 24) / 80, 0, 1)
        img[m] = mix(B, LB, t)[m]
    rnd = random.Random(21)
    # rocks and corals on the sea bed
    bed = below(ridge(9, 180, 3, periods=(70, 31, 13)))
    img[bed] = DG
    for cx, col in ((30, P), (92, R), (158, P), (236, R)):
        for i in range(5):
            bx = cx + (i - 2) * 3
            hgt = 5 + rnd.randrange(6)
            img[178 - hgt:178, bx:bx + 1] = col
            img[178 - hgt, bx - 1:bx + 2] = col
    # seaweed
    for wx in (12, 56, 70, 120, 134, 190, 204, 250):
        hgt = rnd.randrange(9, 15)
        ph = rnd.uniform(0, 6)
        for i in range(hgt):
            x = wx + int(round(1.5 * math.sin(i / 2.2 + ph)))
            x = max(wx // 8 * 8, min(wx // 8 * 8 + 6, x))
            img[180 - i, x:x + 2] = G
    # fish (inside the 16 px bays between floors)
    def fish(x, y, col, flip=False, big=False):
        L = 11 if big else 7
        for i in range(L):
            hh = max(0, int(round((2.4 if big else 1.6) * math.sin(math.pi * i / (L - 1)))))
            xi = x + (L - 1 - i if flip else i)
            img[y - hh:y + hh + 1, xi] = col
        tx = x - 2 if not flip else x + L + 1
        img[y - 2:y + 3, tx] = col
        img[y - 1:y + 2, tx + (1 if not flip else -1)] = col
    for fx, fy, col, fl, bg in ((30, 104, O, False, False), (44, 108, O, False, False), (38, 99, O, False, False),
                                (200, 128, P, True, True), (120, 152, LR, False, False), (136, 156, LR, False, False),
                                (226, 82, DG, True, True), (70, 130, DG, False, True)):
        fish(fx, fy, col, fl, bg)
    # bubbles
    for bx, by in ((84, 150), (86, 128), (83, 103), (176, 156), (178, 132), (240, 108), (16, 150), (150, 104)):
        img[by, bx:bx + 2] = LB
        img[by + 1, bx - 1] = LB
        img[by + 1, bx + 2] = LB
        img[by + 2, bx:bx + 2] = LB
    return img


def crimson():
    img = np.zeros((H, W), np.uint8)
    chain(img, [(24, K), (112, R), (184, R)])
    moon = disc(51.5, 91.5, 20)          # blood moon on the floor line y=88
    img[moon] = LR
    for cx, cy, r in ((44, 84, 4), (58, 99, 5), (60, 80, 3), (42, 100, 2)):
        img[disc(cx, cy, r) & disc(51.5, 91.5, 16)] = R
    # hill
    hill = below(ridge(2, 176, 6, periods=(200, 80, 31)))
    img[hill] = K
    # castle: walls on cell boundaries, details inside the 16 px bays
    def block(x0, x1, y0, y1=184):
        img[y0:y1, x0:x1] = K
    block(136, 232, 152)                 # curtain wall
    block(144, 160, 120)                 # towers
    block(176, 200, 96)
    block(216, 232, 128)
    for x0, x1, top in ((144, 160, 120), (176, 200, 96), (216, 232, 128), (136, 232, 152)):
        for x in range(x0, x1, 4):       # battlements
            img[top - 3:top, x:x + 2] = K
    m = shape(lambda d: d.polygon([(176, 96), (188, 76), (199, 96)], fill=255))
    img[m & (yy >= 72)] = K              # spire (inside the bay 72..87)
    m = shape(lambda d: d.polygon([(144, 120), (152, 106), (159, 120)], fill=255))
    img[m & (yy >= 96)] = K
    for wx, wy in ((150, 128), (186, 104), (186, 124), (222, 136), (166, 160), (204, 160)):
        img[wy:wy + 4, wx:wx + 2] = O    # lit windows
    # bats
    for bx, by in ((100, 52), (118, 58), (88, 126), (30, 150), (244, 104), (120, 100)):
        for i in range(4):
            img[by + abs(i - 1), bx - 4 + i] = K
            img[by + abs(i - 1), bx + 4 - i] = K
        img[by:by + 2, bx] = K
    # dead tree (inside the lowest bay)
    for (x0, y0, x1, y1) in ((40, 183, 40, 170), (40, 174, 34, 169), (40, 172, 46, 168), (34, 169, 32, 168), (46, 168, 47, 168)):
        m = shape(lambda d: d.line([(x0, y0), (x1, y1)], fill=255, width=1))
        img[m] = K
    return img


def purple_haze():
    img = np.zeros((H, W), np.uint8)
    chain(img, [(24, K), (46, P), (184, P)])
    img[disc(179.5, 67.5, 20)] = LR                       # pale sun in the haze
    # ranges, far to near. Each ridge stays inside one 16 px bay and has a
    # hazy (dithered) rim; the floor rows only ever see flat colour.
    prev = P
    for sd, (base, col) in enumerate(((80, LR), (104, P), (128, B), (152, K))):
        r = np.clip(ridge(31 + sd, base, 5, periods=(120, 50, 23), peaky=True), base - 7, base + 2)
        ri = np.round(r).astype(int)[xx]
        img[yy >= ri] = col
        rim = (yy >= ri) & (yy < ri + 5)
        img[rim] = mix(prev, col, 0.25 + (yy - ri) * 0.15)[rim]
        prev = col
    # foreground boulders
    rnd = random.Random(9)
    for bx in (20, 70, 110, 150, 200, 236):
        r = rnd.randrange(4, 8)
        img[disc(bx, 184, r) & (yy >= 168)] = DG
    return img


def twilight():
    img = np.zeros((H, W), np.uint8)
    chain(img, [(24, K), (48, K), (96, B), (144, P), (168, LR), (184, LR)])
    stars(img, 26, 5, ymax=48, big=3)
    # crescent moon in the top bay
    m = disc(40, 32, 6) & ~disc(43, 30, 6)
    img[m] = LGR
    # skyline: every block is aligned to the 8 px grid
    rnd = random.Random(12)
    x = 0
    while x < W:
        wd = rnd.choice((8, 16, 16, 24))
        top = rnd.choice((120, 128, 136, 136, 144, 152, 160, 104))
        img[top:184, x:x + wd] = K
        for wy in range(top + 3, 182, 6):
            for wx in range(x + 2, x + wd - 2, 4):
                if rnd.random() < 0.32 and (wy // 8) not in FLOOR_ROW:
                    img[wy:wy + 2, wx:wx + 2] = Y if rnd.random() < 0.8 else O
        x += wd
    return img


def volcano():
    img = np.zeros((H, W), np.uint8)
    rnd = random.Random(6)
    # ash sky lit from below: black -> brown -> orange
    chain(img, [(24, K), (56, K), (112, BR), (168, O)])
    # smoke: black puffs (they share the colours of the sky)
    for cx, cy, r in ((128, 50, 15), (142, 38, 13), (116, 36, 11), (156, 30, 10), (172, 34, 9), (188, 30, 7)):
        img[disc(cx, cy, r) & (yy >= 24)] = K
    # cone: black silhouette with a rough edge
    top = np.full(W, 168.0)
    for x in range(W):
        if 8 <= x <= 104:
            top[x] = 168 - (x - 8) * (106 / 96)
        elif x <= 150:
            top[x] = 62 + 3 * math.sin((x - 104) / 46 * math.pi)
        elif x <= 248:
            top[x] = 62 + (x - 150) * (106 / 98)
    top += np.array([rnd.randrange(-2, 3) for _ in range(W)])
    cone = (yy >= np.round(top).astype(int)[xx]) & (yy < 168)
    img[cone] = K
    # lava: glowing crater and streams (kept away from the edge of the cone)
    img[66:69, 112:144] = LR
    for x0, sway, y1 in ((116, -0.42, 168), (128, 0.04, 168), (141, 0.45, 168), (122, -0.15, 120)):
        x = float(x0)
        for y in range(69, y1):
            x += sway + rnd.uniform(-0.5, 0.5)
            xi = int(round(x))
            img[y, xi:xi + (3 if (y // 6) % 2 else 2)] = LR
    # sparks
    flat = flat_cells(img)
    for _ in range(40):
        ang, dist = rnd.uniform(-1.3, 1.3), rnd.uniform(8, 64)
        sx, sy = int(128 + math.sin(ang) * dist * 1.4), int(62 - math.cos(ang) * dist * 0.62)
        if 24 <= sy < 62 and 0 <= sx < W and img[sy, sx] == K and flat[sy // 8, sx // 8]:
            img[sy, sx] = LR if rnd.random() < 0.5 else O
            flat[sy // 8, sx // 8] = False
    # lava lake
    lake = yy >= 168
    wave = 0.5 + 0.4 * np.sin(xx / 9.0 + yy * 0.9)
    img[lake] = mix(R, LR, wave)[lake]
    return img


def aurora():
    img = np.zeros((H, W), np.uint8)
    rnd = random.Random(15)
    x = np.arange(W)
    stri = np.array([rnd.uniform(0.35, 1.0) for _ in range(W)])
    for i in range(1, W):
        stri[i] = 0.55 * stri[i - 1] + 0.45 * stri[i]
    stri = np.clip((stri - stri.min()) / (stri.max() - stri.min()) * 0.75 + 0.25, 0, 1)

    def ribbon(base, amp, lam, ph, hgt, col, y_min, y_max, gain, x0=0, x1=W):
        yb = base + amp * np.sin(x / lam + ph) + amp * 0.35 * np.sin(x / (lam * 0.37) + ph * 2)
        h = hgt * (0.8 + 0.3 * np.sin(x / 29.0 + ph))
        env = np.clip(np.minimum(x - x0, x1 - x) / 40.0, 0, 1)
        up = yb[xx] - yy
        t = np.clip(1 - up / h[xx], 0, 1) ** 0.8 * (up >= 0) * stri[xx] * env[xx] * gain
        t = t * np.clip((yy - y_min) / 14.0, 0, 1)          # fade out at the top limit
        m = (yy >= y_min) & (yy < y_max) & (t > 0)
        img[m] = mix(K, col, t)[m]

    # purple veil high up, green curtains below it (colours change on a cell row)
    ribbon(56, 6, 47.0, 0.6, 30, P, 24, 64, 0.8, 10, 246)
    ribbon(126, 16, 52.0, 2.2, 58, G, 64, 144, 1.15)
    stars(img, 46, 2, ymax=140)
    # snowy mountains and pines
    # (the ridge stays inside the bay y=144..159, so no floor row cuts it)
    r1 = np.clip(ridge(40, 153, 9, periods=(70, 31, 13), peaky=True, jag=0.8), 145, 159)
    ri = np.round(r1).astype(int)
    mt = yy >= ri[xx]
    img[mt] = DG
    snow = mt & (yy < ri[xx] + 2 + (xx * 5 + ri[xx]) % 3) & (ri[xx] < 152)
    img[snow] = LGR
    for px in range(4, W, 9):
        ph = 8 + (px * 5) % 6
        for i in range(ph):
            wdt = i // 2
            img[183 - ph + i, max(0, px - wdt):px + wdt + 1] = K
        img[183, px] = K
    return img


SCENES = [night_sky, sunset, deep_sea, crimson, purple_haze, twilight, volcano, aurora]


# ---------------------------------------------------------------- resolver
def nearest_of(col, choices):
    return min(choices, key=lambda c: sum((a - b) ** 2 for a, b in zip(PEPTO[col], PEPTO[c])))


def resolve(img, scheme):
    """Apply the real constraints. Returns (image, ink[24][32], paper[24][32],
    number of pixels that had to change)."""
    out = img.copy()
    ink = np.zeros((24, 32), np.uint8)
    paper = np.zeros((24, 32), np.uint8)
    changed = 0
    floors = FLOORS[scheme]
    for r in range(24):
        for c in range(32):
            cell = out[r * 8:r * 8 + 8, c * 8:c * 8 + 8]
            if r < 3:                       # HUD and messages: plain black
                cell[:] = K
                continue
            if r == 23:                     # the ground is solid
                continue
            if r in FLOOR_ROW:
                f = floors[FLOOR_ROW.index(r)]
                part = cell[3:]
                # only one colour fits under a floor line: the commonest one,
                # or the darker of the two in a dithered area (an even "shadow")
                vals, cnt = np.unique(part, return_counts=True)
                order = [int(v) for v in vals[np.argsort(-cnt)]]
                p = order[0]
                if len(order) > 1 and cnt[np.argsort(-cnt)][1] >= 0.2 * part.size:
                    p = min(order[:2], key=lambda v: sum(PEPTO[v]))
                changed += int((part != p).sum())
                cell[:] = p
                ink[r, c], paper[r, c] = f, p
                continue
            vals, cnt = np.unique(cell, return_counts=True)
            order = [int(v) for v in vals[np.argsort(-cnt)]]
            if len(order) == 1:
                ink[r, c] = paper[r, c] = order[0]
                continue
            a, b = order[0], order[1]
            for v in order[2:]:
                tgt = nearest_of(v, (a, b))
                changed += int((cell == v).sum())
                cell[cell == v] = tgt
            paper[r, c], ink[r, c] = a, b
    return out, ink, paper, changed


def to_rgb(img):
    pal = np.array(PEPTO, np.uint8)
    return Image.fromarray(pal[img], "RGB")


def preview(img, scheme, sprites=True):
    """Offline mock-up: floors with a gap each, ground, some sprites."""
    im = img.copy()
    floors = FLOORS[scheme]
    rnd = random.Random(scheme + 100)
    gaps = {}
    for fl in range(7):
        y = FLOOR_ROW[fl] * 8
        if fl == 0:
            im[y:y + 8] = floors[0]
        else:
            im[y:y + 3] = floors[fl]
            gs = rnd.randrange(16, 200)
            gaps[fl] = gs
            im[y:y + 3, gs:gs + 40] = img[y + 4, gs:gs + 40]
    rgb = to_rgb(im).convert("RGBA")
    if sprites:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "sprites")
        pl = Image.open(os.path.join(base, "player_04.png"))
        rgb.alpha_composite(pl, (120, 184 - 16))
        for i in range(6):
            en = Image.open(os.path.join(base, "enemy_v%d_k%d_f0.png" % ((scheme + i) % 3, i)))
            fl = i % 5 + 1
            rgb.alpha_composite(en, (30 + i * 37 % 200, FLOOR_ROW[fl] * 8 - 11))
    return rgb.convert("RGB")


if __name__ == "__main__":
    # default output: the art masters used by the ports
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "assets", "backgrounds")
    os.makedirs(out, exist_ok=True)
    sheet = Image.new("RGB", (4 * (W * 2 + 8) + 8, 2 * (H * 2 + 8) + 8), (40, 40, 40))
    for i, fn in enumerate(SCENES):
        raw = fn()
        res, ink, paper, changed = resolve(raw, i)
        name = "scheme%d_%s.png" % (i + 1, NAMES[i].lower().replace(" ", "_"))
        print("%-32s pixels changed by the 2-colour rule: %d" % (name, changed))
        to_rgb(res).save(os.path.join(out, name))
        pv = preview(res, i).resize((W * 2, H * 2), Image.NEAREST)
        sheet.paste(pv, (8 + (i % 4) * (W * 2 + 8), 8 + (i // 4) * (H * 2 + 8)))
    if len(sys.argv) > 2:
        sheet.save(sys.argv[2])
