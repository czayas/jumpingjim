#!/usr/bin/env python3
"""Convert the platform-neutral Jumping Jim assets (assets/, made by
tools/extract.py) into Commodore 64 formats for the 6502 port.
Usage: convert_c64.py <assets dir> <build dir>"""
import sys, os, math
from collections import Counter

import json
ASSETS, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
J = json.load(open(os.path.join(ASSETS, 'jumpingjim.json')))
T = J['tables']; SND = J['sound']

def w(name, data):
    open(os.path.join(OUT, name), 'wb').write(bytes(data))

# ---------------------------------------------------------------- palettes
PEPTO = [(0,0,0),(255,255,255),(104,55,43),(112,164,178),(111,61,134),
         (88,141,67),(53,40,121),(184,199,111),(111,79,37),(67,57,0),
         (154,103,89),(68,68,68),(108,108,108),(154,210,132),(108,94,181),
         (149,149,149)]

def next_rgb(c):
    r = (c >> 5) & 7; g = (c >> 2) & 7; b = c & 3
    b3 = (b << 1) | (1 if b else 0)
    return (r * 255 // 7, g * 255 // 7, b3 * 255 // 7)

def dist(a, b):
    # 'redmean' perceptual rgb distance
    rm = (a[0] + b[0]) / 2.0
    dr, dg, db = a[0]-b[0], a[1]-b[1], a[2]-b[2]
    return (2 + rm/256.0)*dr*dr + 4*dg*dg + (2 + (255-rm)/256.0)*db*db

def nearest(rgb, allowed=range(16)):
    return min(allowed, key=lambda i: dist(rgb, PEPTO[i]))

# Spectrum colour -> C64 colour
SPEC_N = [0, 6, 2, 4, 5, 3, 7, 15]
SPEC_B = [0, 14, 10, 4, 13, 3, 7, 1]

def spec_ink(a):
    return (SPEC_B if a & 0x40 else SPEC_N)[a & 7]

def spec_paper(a):
    return (SPEC_B if a & 0x40 else SPEC_N)[(a >> 3) & 7]

def attr2c64(a):
    return (spec_ink(a) << 4) | spec_paper(a)

# ---------------------------------------------------------------- sprites
TRANS = 0xE3
def player_pat(i):
    return list(J['sprites']['player']['frames'][i])

def enemy_pat(i):
    p = [TRANS] * 256
    src = J['sprites']['enemy']['frames'][i]
    for r in range(11):
        p[(5 + r) * 16 + 2:(5 + r) * 16 + 14] = src[r * 12:r * 12 + 12]
    return p

def mirror(p):
    out = []
    for y in range(16):
        out += p[y * 16:y * 16 + 16][::-1]
    return out

MC0 = 1      # $D025 shared: white
MC1 = 10     # $D026 shared: light red (skin tone of Jim)

def convert_layers(pats, indivs, row0, nrows, mc1):
    """pats: list of 16x16 Next patterns sharing one shape (colour variants),
    indivs: c64 colour per variant.  Returns (base MC sprite, overlay)."""
    base = bytearray(64); over = bytearray(64)
    for sy in range(nrows):
        y = row0 + sy
        for x in range(16):
            if pats[0][y * 16 + x] == 0x00:
                over[sy * 3 + x // 8] |= 0x80 >> (x % 8)
        for j in range(8):
            votes = Counter()
            for v, p in enumerate(pats):
                mc = main_colour(p)
                for c in (p[y*16+2*j], p[y*16+2*j+1]):
                    if c in (TRANS, 0x00):
                        continue
                    if c == mc:
                        votes[2] += 1.01
                        continue
                    rgb = next_rgb(c)
                    code = min((1, 2, 3), key=lambda k: dist(rgb, PEPTO[{1: MC0, 2: indivs[v], 3: mc1}[k]]))
                    votes[code] += 1
            if not votes:
                continue
            bcode = votes.most_common(1)[0][0]
            bx = 2 * j
            base[sy * 3 + bx // 8] |= bcode << (6 - (bx % 8))
    return base, over

def main_colour(p):
    cnt = Counter(c for c in p if c not in (TRANS, 0x00, 0xFF))
    if not cnt:
        return 0xFF
    return cnt.most_common(1)[0][0]

def best_indiv(pats, mc1):
    best = None
    for col in range(16):
        if col in (0, MC0, mc1):
            continue
        err = 0
        for p in pats:
            for c in p:
                if c in (TRANS, 0):
                    continue
                rgb = next_rgb(c)
                err += min(dist(rgb, PEPTO[k]) for k in (col, MC0, mc1))
        if best is None or err < best[0]:
            best = (err, col)
    return best[1]

players = [player_pat(i) for i in range(10)]
enemies = [enemy_pat(i) for i in range(48)]
drop = list(J['sprites']['drop']['frames'][0])

# choose shared MC1 colour minimising total error
def total_err(mc1):
    e = 0
    for p in players + enemies + [drop]:
        cols = set(c for c in p if c not in (TRANS, 0))
        e += min(sum(min(dist(next_rgb(c), PEPTO[k]) for k in (ind, MC0, mc1))
                     for c in p if c not in (TRANS, 0))
                 for ind in range(2, 16))
    return e
if os.environ.get('PICK_MC1'):
    for k in range(2, 16):
        print(k, total_err(k))
MC1 = int(os.environ.get('MC1', MC1))

player_col = int(os.environ.get('PCOL', 8))
drop_col = best_indiv([drop], MC1)

# enemy: index = variant*16 + kind*2 + frame
enemy_cols = [[0]*3 for _ in range(8)]
for k in range(8):
    for v in range(3):
        enemy_cols[k][v] = nearest(next_rgb(main_colour(enemies[v*16+k*2])), [c for c in range(1, 16) if c != MC1])

SPR = {}          # slot -> 64 bytes
for f in range(10):
    for d in range(2):
        p = players[f] if d == 0 else mirror(players[f])
        b, o = convert_layers([p], [player_col], 0, 16, MC1)
        s = 16 + (f * 2 + d) * 2
        SPR[s], SPR[s + 1] = b, o
for k in range(8):
    for a in range(2):
        for d in range(2):
            pats = [enemies[v * 16 + k * 2 + a] for v in range(3)]
            if d:
                pats = [mirror(p) for p in pats]
            b, o = convert_layers(pats, enemy_cols[k], 5, 11, MC1)
            s = 56 + ((k * 2 + a) * 2 + d) * 2
            SPR[s], SPR[s + 1] = b, o
b, o = convert_layers([drop], [drop_col], 0, 16, MC1)
SPR[120], SPR[121] = b, o
# transporter effect: 122 = blank, 123-126 = sparkle frames, 127 = sparse sparkle
import random
rnd = random.Random(1701)
SPR[122] = bytearray(64)
def sparkle(density):
    sp = bytearray(64)
    for y in range(11):
        for x in range(2, 14):
            if rnd.random() < density * (1.0 if 4 <= x <= 11 else 0.5):
                sp[y*3 + x//8] |= 0x80 >> (x % 8)
    return sp
for k in range(4):
    SPR[123 + k] = sparkle(0.35)
SPR[127] = sparkle(0.12)
blob = bytearray()
for s in range(16, 128):
    blob += SPR.get(s, bytearray(64))
w('sprites.bin', blob)

# ---------------------------------------------------------------- preview
try:
    from PIL import Image
    S = 4
    im = Image.new('RGB', (16 * 24 * S // 2, 8 * 24 * S), (20, 20, 60))
    def draw(slot, ox, oy, col):
        b, o = SPR[slot], SPR[slot + 1]
        for y in range(21):
            for j in range(12):
                code = (b[y*3 + j//4] >> (6 - 2*(j % 4))) & 3
                if code:
                    c = PEPTO[{1: MC0, 2: col, 3: MC1}[code]]
                    for xx in range(2):
                        for a in range(S):
                            for bb in range(S):
                                im.putpixel((ox+(2*j+xx)*S+a, oy+y*S+bb), c)
            for x in range(24):
                if o[y*3 + x//8] & (0x80 >> (x % 8)):
                    for a in range(S):
                        for bb in range(S):
                            im.putpixel((ox+x*S+a, oy+y*S+bb), (0, 0, 0))
    n = 0
    for f in range(10):
        for d in range(2):
            draw(16 + (f*2+d)*2, (n % 8) * 24 * S, (n // 8) * 24 * S, player_col); n += 1
    n = 24
    for k in range(8):
        for a in range(2):
            for v in range(3):
                pass
    for k in range(8):
        for a in range(2):
            draw(56 + ((k*2+a)*2)*2, (n % 8)*24*S, (n//8)*24*S, enemy_cols[k][0]); n += 1
    draw(120, (n % 8)*24*S, (n//8)*24*S, drop_col)
    im.save(os.path.join(OUT, 'preview_sprites.png'))
except ImportError:
    pass

# ---------------------------------------------------------------- font
w('font.bin', open(os.path.join(ASSETS, 'font.bin'), 'rb').read())

# ---------------------------------------------------------------- colours / tables
def asm_bytes(name, vals):
    s = name + '\n'
    for i in range(0, len(vals), 16):
        s += '\t!byte ' + ','.join('$%02x' % (v & 0xFF) for v in vals[i:i+16]) + '\n'
    return s

A = '; generated by convert.py - do not edit\n'
A += 'PLAYER_COL = %d\nDROP_COL = %d\nSPR_MC0 = %d\nSPR_MC1 = %d\n' % (player_col, drop_col, MC0, MC1)
A += asm_bytes('enemy_cols', [enemy_cols[k][v] for v in range(3) for k in range(8)])

PALS = J['levels']['palettes']
A += asm_bytes('lev_border', [SPEC_N[p['border'] & 7] for p in PALS])
A += asm_bytes('lev_band', [attr2c64(a) for p in PALS for a in p['band_attr']])
A += asm_bytes('lev_floor', [attr2c64(a) for p in PALS for a in p['floor_attr']])
nm = []
for p in PALS:
    nm.append(p['name_col'])
    nm += list(p['name'].encode().ljust(12, b'\0'))
A += asm_bytes('pal_names', nm)
A += asm_bytes('spd_sets', [v for row in T['gap_speed_sets'] for v in row])
for nme, key in [('spd_idx', 'gap_speed_set_for_level'), ('floor_y', 'floor_y'),
                 ('enemy_spd', 'enemy_speed'), ('gap_add', 'gap_len_add'),
                 ('lev_music', 'level_music'), ('bob_tab', 'bob'), ('title_lv', 'title_logo_level')]:
    A += asm_bytes(nme, T[key])
A += asm_bytes('rainbow_ink', [attr2c64(x) & 0xF0 for x in T['title_rainbow_attr']])
A += asm_bytes('flash_border_b', [SPEC_B[x & 7] for x in T['border_rainbow']])

# ---------------------------------------------------------------- sound
CLK_AY = 1750000.0
PAL = 985248.0
def sidf(period):
    if period == 0:
        return 0
    f = CLK_AY / (16.0 * period)
    return min(0xFFFF, int(round(f * 16777216.0 / PAL)))
def sidnoise(np_):
    np_ = np_ & 0x1F or 1
    f = CLK_AY / (16.0 * np_)
    return min(0xFFFF, int(round(f * 1048576.0 / PAL)))

nf = [sidf(p) for p in SND['note_periods']]
A += asm_bytes('note_lo', [x & 0xFF for x in nf])
A += asm_bytes('note_hi', [x >> 8 for x in nf])

mlo, mhi, mrows, mspeed, mloop = [], [], [], [], []
off = 0
blob = bytearray()
for t in SND['tunes']:
    mlo.append(off & 0xFF); mhi.append(off >> 8)
    mrows.append(t['rows']); mspeed.append(t['speed']); mloop.append(t['loop'])
    blob += bytes(t['data']); off += len(t['data'])
w('music.bin', blob)
A += asm_bytes('mus_lo', mlo) + asm_bytes('mus_hi', mhi)
A += asm_bytes('mus_rows', mrows) + asm_bytes('mus_speed', mspeed) + asm_bytes('mus_loop', mloop)
A += asm_bytes('drum_len', [d['frames'] for d in SND['drums']])
dnf = [sidnoise(d['noise_period']) if d['noise_period'] else 0 for d in SND['drums']]
A += asm_bytes('drum_lo', [x & 0xFF for x in dnf]) + asm_bytes('drum_hi', [x >> 8 for x in dnf])

# sound effects: precompute one SID frequency per frame
seq_lo, seq_hi, sfx_start, sfx_len, sfx_type = [], [], [], [], []
for e in SND['sfx']:
    p, dlt, n, typ = e['period'], e['delta'], e['frames'], e['noise']
    sfx_start.append(len(seq_lo)); sfx_len.append(n); sfx_type.append(typ)
    for k in range(n):
        f = sidf(p & 0xFFFF) if typ == 0 else sidnoise(p & 0x1F)
        seq_lo.append(f & 0xFF); seq_hi.append(f >> 8)
        p = (p + dlt) & 0xFFFF
A += asm_bytes('sfx_start', sfx_start) + asm_bytes('sfx_len', sfx_len) + asm_bytes('sfx_type', sfx_type)
A += asm_bytes('sfx_lo', seq_lo) + asm_bytes('sfx_hi', seq_hi)

# speech sample -> 4 bit linear values for $d418
AYV = [0,0.0137,0.0205,0.0291,0.0423,0.0618,0.0847,0.1369,0.1691,0.2647,
       0.3527,0.4499,0.5704,0.6873,0.8482,1.0]
amp = [sum(AYV[v] for v in row) for row in SND['sample']['ay_volume_table']]
mx = max(amp)
lin = [int(round(a / mx * 15)) for a in amp]
smp = open(os.path.join(ASSETS, SND['sample']['file']), 'rb').read()
out = bytearray((lin[b >> 4] << 4) | lin[b & 15] for b in smp)
w('sample.bin', out)
A += 'SAMPLE_LEN = %d\n' % len(out)

# ---------------------------------------------------------------- pictures
def lines_to_cells(lines, ncols):
    """lines: list of rows of ncols bytes (8*k lines) -> C64 cell order"""
    out = bytearray()
    for r in range(len(lines) // 8):
        for c in range(ncols):
            for l in range(8):
                out.append(lines[r*8+l][c])
    return out

go = J['gameover']['title_1bpp']['data']
w('gameover_title.bin', lines_to_cells([go[i*32:i*32+32] for i in range(16)], 32))
pic = J['gameover']['picture_1bpp']['data']
w('gameover_pic.bin', lines_to_cells([pic[i*18:i*18+18] for i in range(144)], 18))
w('gameover_attr.bin', [attr2c64(a) for a in J['gameover']['picture_attr']['data']])

# ---------------------------------------------------------------- title logo
SEGS = J['title_logo']['segments']
def sra(v, n):
    v = v - 256 if v >= 128 else v
    return (v >> n) & 0xFF
def logo_state(lv, phase):
    buf = bytearray(48 * 32)
    for i in range(37):
        s = list(SEGS[i]); s[4] &= 0xFF; s[5] &= 0xFF
        idx = i + 1
        if lv < 7:
            d0, e0 = sra(s[4], lv), sra(s[5], lv)
        else:
            d0, e0 = (phase + idx) & 1, 0
        x0 = (s[0] + d0) & 0xFF; y0 = (s[1] + e0) & 0xFF
        for c in range(2):
            d, e = x0, y0
            if s[3] == 0:
                if c & 1: e = (e + 1) & 0xFF
            else:
                if c & 1: d = (d + 1) & 0xFF
            for k in range(s[2] + 1):
                if e < 0x30:
                    buf[e * 32 + (d >> 3)] |= 0x80 >> (d & 7)
                if s[3] == 0: d = (d + 1) & 0xFF
                elif s[3] == 1: e = (e + 1) & 0xFF
                elif s[3] == 2: d = (d + 1) & 0xFF; e = (e + 1) & 0xFF
                else: d = (d - 1) & 0xFF; e = (e + 1) & 0xFF
    return buf
states = []
blob = bytearray()
for lv in range(7):
    states.append(logo_state(lv, 0))
states.append(logo_state(7, 0)); states.append(logo_state(7, 1))
for st in states:
    blob += lines_to_cells([st[i*32:i*32+32] for i in range(48)], 32)
w('logo.bin', blob)
LOGO_CELLS = bytes(blob)     # packed further below (logo.pk)
try:
    from PIL import Image
    im = Image.new('L', (256, 48 * 9 + 9 * 4))
    for k, st in enumerate(states):
        for y in range(48):
            for x in range(256):
                if st[y*32 + x//8] & (0x80 >> (x & 7)):
                    im.putpixel((x, k * 52 + y), 255)
    im.save(os.path.join(OUT, 'preview_logo.png'))
except ImportError:
    pass

open(os.path.join(OUT, 'tables.a'), 'w').write(A)
print('player col', player_col, 'drop col', drop_col, 'MC1', MC1)
print('enemy cols', enemy_cols)

# ---------------------------------------------------------------- RIP splash logo
# Multicolour bitmap, 17 cells (68 double-wide pixels) x 24 rows, background black.
def convert_rip(path):
    from PIL import Image
    from itertools import combinations
    src = Image.open(path).convert('RGB').resize((68, 192), Image.LANCZOS)
    W, H = 68, 192
    px = [[list(src.getpixel((x, y))) for x in range(W)] for y in range(H)]
    bm = bytearray(); scr = bytearray(); col = bytearray()
    for cy in range(H // 8):
        for cx in range(W // 4):
            cell = [(x, y) for y in range(cy*8, cy*8+8) for x in range(cx*4, cx*4+4)]
            # candidate colours: nearest palette colour of each pixel
            cnt = Counter(nearest(tuple(px[y][x])) for x, y in cell)
            cands = [c for c, _ in cnt.most_common(6) if c != 0] or [1]
            best = None
            for combo in combinations(cands, min(3, len(cands))):
                pal = [0] + list(combo)
                e = sum(min(dist(tuple(px[y][x]), PEPTO[c]) for c in pal) for x, y in cell)
                if best is None or e < best[0]:
                    best = (e, pal)
            pal = best[1] + [0] * (4 - len(best[1]))
            # Floyd-Steinberg inside the cell's 4 colours
            codes = {}
            for y in range(cy*8, cy*8+8):
                for x in range(cx*4, cx*4+4):
                    old = px[y][x]
                    k = min(range(4), key=lambda i: dist(tuple(max(0, min(255, int(v))) for v in old), PEPTO[pal[i]]))
                    codes[(x, y)] = k
                    newc = PEPTO[pal[k]]
                    err = [old[i] - newc[i] for i in range(3)]
                    for dx, dy, f in ((1, 0, 7/16), (-1, 1, 3/16), (0, 1, 5/16), (1, 1, 1/16)):
                        nx, ny = x + dx, y + dy
                        if cx*4 <= nx < cx*4+4 and ny < cy*8+8:
                            for i in range(3):
                                px[ny][nx][i] += err[i] * f * 0.8
            for y in range(cy*8, cy*8+8):
                b = 0
                for x in range(cx*4, cx*4+4):
                    b = (b << 2) | codes[(x, y)]
                bm.append(b)
            scr.append((pal[1] << 4) | pal[2])
            col.append(pal[3])
    w('rip_bitmap.bin', bm); w('rip_screen.bin', scr); w('rip_color.bin', col)
    try:
        prev = Image.new('RGB', (W * 2, H))
        for cy in range(H // 8):
            for cx in range(W // 4):
                i = cy * (W // 4) + cx
                pal = [0, scr[i] >> 4, scr[i] & 15, col[i]]
                for l in range(8):
                    b = bm[i * 8 + l]
                    for p in range(4):
                        c = PEPTO[pal[(b >> (6 - 2*p)) & 3]]
                        X = (cx*4 + p) * 2
                        prev.putpixel((X, cy*8 + l), c); prev.putpixel((X + 1, cy*8 + l), c)
        prev.resize((W * 6, H * 3), Image.NEAREST).save(os.path.join(OUT, 'preview_rip.png'))
    except Exception as ex:
        print('preview failed', ex)

convert_rip(os.path.join(ASSETS, 'branding', 'rip_logo.png'))

# fade-to-black chains for the splash (each colour -> a darker one)
DARKER = [0, 15, 9, 14, 6, 11, 0, 15, 2, 0, 8, 0, 11, 5, 4, 12]
fade = []
for L in range(5):
    for c in range(16):
        v = c
        for _ in range(L):
            v = DARKER[v]
        fade.append(v)
open(os.path.join(OUT, 'tables.a'), 'a').write(asm_bytes('fadetab', fade))

# ---------------------------------------------------------------- packed data
# Title logo states and level backgrounds, packed with tools/lzpack.py and
# unpacked by the game (routine 'unpack') straight into the bitmap: whole
# 320-byte bitmap rows / 40-byte colour rows, with the side columns skipped.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'tools'))
from lzpack import pack, unpack

def bitmap_rows(rows):
    """rows: list of 256-byte middle parts or None (= skip the whole row)."""
    data, skip = bytearray(), []
    for r in rows:
        if r is None:
            data += bytes(320); skip += [True] * 320
        else:
            data += bytes(32) + bytes(r) + bytes(32)
            skip += [True] * 32 + [False] * 256 + [True] * 32
    return data, skip

def colour_rows(rows):
    data, skip = bytearray(), []
    for r in rows:
        data += bytes(4) + bytes(r) + bytes(4)
        skip += [True] * 4 + [False] * 32 + [True] * 4
    return data, skip

def packed(data, skip, what):
    p = pack(data, skip)
    chk = unpack(p, bytes(len(data)))
    assert all(chk[k] == data[k] for k in range(len(data)) if not skip[k]), what
    return p

# title logo, 6 bitmap rows (rows 1-6) per state: the 7 'flying' states are
# packed; the 2 'wiggle' states (shown 170 frames of every 240, alternating
# every 4) stay as plain 1536-byte blocks, as fast to copy as before
logo_pk, logo_tab = bytearray(), []
for k in range(7):
    st = LOGO_CELLS[k * 1536:(k + 1) * 1536]
    logo_tab.append(len(logo_pk))
    logo_pk += packed(*bitmap_rows([st[r * 256:(r + 1) * 256] for r in range(6)]), 'logo')
w('logo.pk', logo_pk)
w('logo_raw.bin', LOGO_CELLS[7 * 1536:9 * 1536])

# sprites: unpacked once at start-up to $C400-$DFFF
spr = open(os.path.join(OUT, 'sprites.bin'), 'rb').read()
w('sprites.pk', packed(spr, [False] * len(spr), 'sprites'))

# level backgrounds (assets/backgrounds/scheme<N>_*.png, see
# tools/backgrounds/): rows 3-22. Each 8x8 cell may hold 2 colours; under a
# floor line (rows 5, 8 ... 20) only one, as the cell's other colour is the
# floor's. Rows 0-2 (texts) and 23 (ground) are not part of the background.
FLOOR_ROWS = [23, 20, 17, 14, 11, 8, 5]
def load_background(scheme, pal):
    from PIL import Image
    import glob
    path = glob.glob(os.path.join(ASSETS, 'backgrounds', 'scheme%d_*.png' % (scheme + 1)))
    if not path:
        return None
    im = Image.open(path[0]).convert('RGB')
    assert im.size == (256, 192), path[0]
    px = im.load()
    cache = {}
    def idx(x, y):
        c = px[x, y]
        if c not in cache:
            cache[c] = nearest(c)
        return cache[c]
    bm_rows, col_rows = [], []
    for r in range(3, 23):
        cols, bits = [], bytearray()
        for c in range(32):
            if r in FLOOR_ROWS:
                fl = FLOOR_ROWS.index(r)
                vals = {idx(c * 8 + x, r * 8 + y) for y in range(3, 8) for x in range(8)}
                if len(vals) != 1:
                    sys.exit('%s: cell %d,%d under a floor line has %d colours (1 allowed)'
                             % (path[0], c, r, len(vals)))
                ink = attr2c64(pal['floor_attr'][fl]) >> 4
                cols.append((ink << 4) | vals.pop())
            else:
                cnt = Counter(idx(c * 8 + x, r * 8 + y) for y in range(8) for x in range(8))
                if len(cnt) > 2:
                    sys.exit('%s: cell %d,%d has %d colours (2 allowed)' % (path[0], c, r, len(cnt)))
                order = [v for v, _ in cnt.most_common()]
                paper, ink = order[0], order[-1]
                cols.append((ink << 4) | paper)
                for y in range(8):
                    b = 0
                    for x in range(8):
                        b = (b << 1) | (1 if ink != paper and idx(c * 8 + x, r * 8 + y) == ink else 0)
                    bits.append(b)
        bm_rows.append(None if r in FLOOR_ROWS else bits)
        col_rows.append(cols)
    return (packed(*bitmap_rows(bm_rows), path[0]), packed(*colour_rows(col_rows), path[0]))

bg_pk, bg_tab = bytearray(), []
for scheme, pal in enumerate(PALS):
    bg = load_background(scheme, pal)
    if bg is None:
        sys.exit('missing assets/backgrounds/scheme%d_*.png' % (scheme + 1))
    for part in bg:
        bg_tab.append(len(bg_pk))
        bg_pk += part
w('bg.pk', bg_pk)
open(os.path.join(OUT, 'tables.a'), 'a').write(
    'logo_tab\n\t!word ' + ','.join('logo_pk+%d' % o for o in logo_tab) + '\n' +
    'bg_tab   ; bitmap, colours for each colour scheme\n\t!word ' +
    ','.join('bg_pk+%d' % o for o in bg_tab) + '\n')
print('packed: logo %d bytes + 3072 plain (was %d), sprites %d (was %d), backgrounds %d' % (
    len(logo_pk), len(LOGO_CELLS), os.path.getsize(os.path.join(OUT, 'sprites.pk')), len(spr), len(bg_pk)))
