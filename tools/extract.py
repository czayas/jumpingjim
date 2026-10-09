#!/usr/bin/env python3
"""Platform-neutral asset extractor for Jumping Jim.

Reads the original ZX Spectrum Next binary (original/JumpingJim_v4.nex) and
writes everything a port needs into assets/:

  assets/jumpingjim.json   all game tables, levels, music, sfx, logo, strings
  assets/font.bin          64 chars x 8 bytes (ASCII $20-$5F, 1bpp, MSB left)
  assets/sample_4bit.bin   title speech, packed 4-bit unsigned (high nibble first)
  assets/sample.wav        same speech as 8-bit WAV (for listening / other ports)
  assets/sprites/*.png     sprites as RGBA PNG (reference, human friendly)
  assets/screens/*.png     game-over screen, logo frames (reference)

Every number keeps the units of the original (pixels in a 256x192 screen,
frames at 50 Hz, AY periods for a 1.75 MHz AY-3-8912).  See docs/game-spec.md.

Usage:  python3 tools/extract.py [original/JumpingJim_v4.nex] [assets]
"""
import sys, os, json, struct, wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEX = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'original', 'JumpingJim_v4.nex')
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'assets')
os.makedirs(os.path.join(OUT, 'sprites'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'screens'), exist_ok=True)

raw = open(NEX, 'rb').read()
assert raw[:8] == b'NextV1R2', 'not a NEX v1.2 file'
MEM = raw[512:]                       # 16K bank 2 ($8000) + 16K bank 0 ($C000)

def m(a, n):
    return list(MEM[a - 0x8000:a - 0x8000 + n])

def cstr(a):
    s = bytearray()
    while MEM[a - 0x8000]:
        s.append(MEM[a - 0x8000]); a += 1
    return s.decode('ascii')

def s8(v):
    return v - 256 if v >= 128 else v

def rgb332(c):
    r = (c >> 5) & 7; g = (c >> 2) & 7; b = c & 3
    b3 = (b << 1) | (1 if b else 0)
    return (r * 255 // 7, g * 255 // 7, b3 * 255 // 7)

TRANSPARENT = 0xE3
J = {'_about': 'Jumping Jim data extracted from the ZX Spectrum Next version. '
               'See docs/game-spec.md for the meaning of every field.'}

# ------------------------------------------------------------------ sprites
player = [m(0x965C + 256 * i, 256) for i in range(10)]
enemy = [m(0xA05C + 132 * i, 132) for i in range(48)]
drop = m(0xB91C, 256)
J['sprites'] = {
    'format': 'RGB332 bytes, row major, 0xE3 = transparent',
    'player': {'w': 16, 'h': 16, 'frames': player,
               'frame_names': ['walk0', 'walk1', 'walk2', 'walk3', 'idle', 'jump',
                               'stun0', 'stun1', 'dead', 'win']},
    'enemy': {'w': 12, 'h': 11, 'box_x': 2, 'box_y': 5,
              'index': 'variant*16 + kind*2 + frame (3 colour variants, 8 kinds, 2 frames)',
              'frames': enemy},
    'drop': {'w': 16, 'h': 16, 'frames': [drop]},
}

# ------------------------------------------------------------------ font / screens
font = m(0x9304, 512)
open(os.path.join(OUT, 'font.bin'), 'wb').write(bytes(font))
J['gameover'] = {
    'title_1bpp': {'w': 256, 'h': 16, 'data': m(0xBA1C, 512), 'pos_char': [0, 0], 'attr': 0x42},
    'picture_1bpp': {'w': 144, 'h': 144, 'data': m(0xBC1C, 2592), 'pos_char': [7, 2]},
    'picture_attr': {'w': 18, 'h': 18, 'data': m(0xC63C, 324),
                     'format': 'ZX Spectrum attributes (flash|bright|paper*8|ink)'},
}

# ------------------------------------------------------------------ levels
lev = m(0xE36E, 128)
names = m(0xE3EE, 104)
J['levels'] = {
    'note': 'palette index = (level-1) & 7; colours are Spectrum attributes',
    'palettes': [{
        'name': bytes(names[i*13+1:i*13+13]).rstrip(b'\0').decode(),
        'name_col': names[i*13],
        'border': lev[i*16],
        'band_attr': lev[i*16+1:i*16+9],     # 8 bands of 3 character rows
        'floor_attr': lev[i*16+9:i*16+16],   # floors 0..6
    } for i in range(8)],
}

J['tables'] = {
    'floor_y': m(0xE48A, 7),
    'floor_char_row': [y // 8 for y in m(0xE48A, 7)],
    'gap_speed_sets': [[s8(v) for v in m(0xE456 + 6*i, 6)] for i in range(6)],
    'gap_speed_set_for_level': m(0xE47A, 16),
    'gap_len_add': [s8(v) for v in m(0xE4C7, 6)],
    'enemy_speed': m(0xE4A1, 8),
    'level_music': m(0xE4CD, 12),
    'bob': m(0xE4D9, 32),
    'title_logo_level': m(0xE4F9, 240),
    'title_rainbow_attr': m(0xE4B7, 8),
    'border_rainbow': m(0xE4BF, 8),
}

# ------------------------------------------------------------------ sound
per = m(0xC780, 0x94)
J['sound'] = {
    'ay_clock_hz': 1750000,
    'note_periods': [per[2*i] | per[2*i+1] << 8 for i in range(0x4A)],
    'channel_start_volume': m(0xE4A9, 3),
    'channel_floor_volume': m(0xE4AC, 3),
    'drums': [{'frames': a, 'noise_period': b} for a, b in zip(m(0xE4AF, 4), m(0xE4B3, 4))],
    'tunes_note': 'rows of 4 bytes: noteA, noteB, noteC (0=off, 0xFF=hold, n=note index), drum',
    'tunes': [],
    'sfx': [],
}
mus = m(0xE314, 90)
for i in range(15):
    p = mus[i*6] | mus[i*6+1] << 8
    rows = mus[i*6+2]
    J['sound']['tunes'].append({'rows': rows, 'speed': mus[i*6+3], 'loop': mus[i*6+4],
                                'data': m(p, rows * 4)})
J['sound']['tune_ids'] = {'title': 2, 'level_complete': 3, 'game_over': 4}
sfx = m(0xE6C7, 30)
names_sfx = ['jump', 'climb', 'fall', 'death', 'stunned']
for i in range(5):
    e = sfx[i*6:i*6+6]
    d = e[2] | e[3] << 8
    J['sound']['sfx'].append({'name': names_sfx[i], 'period': e[0] | e[1] << 8,
                              'delta': d - 65536 if d >= 32768 else d,
                              'frames': e[4], 'noise': e[5]})
vt = m(0xF114, 64)
J['sound']['sample'] = {
    'file': 'sample_4bit.bin', 'wav': 'sample.wav', 'rate_hz_approx': 8000,
    'ay_volume_table': [vt[i*4:i*4+3] for i in range(16)],
    'note': 'each nibble n plays AY volumes ay_volume_table[n] on channels A,B,C',
}
smp = bytes(m(0xE6E5, 0xA2F))
open(os.path.join(OUT, 'sample_4bit.bin'), 'wb').write(smp)
AYV = [0, .0137, .0205, .0291, .0423, .0618, .0847, .1369, .1691, .2647,
       .3527, .4499, .5704, .6873, .8482, 1.0]
amp = [sum(AYV[v] for v in vt[i*4:i*4+3]) for i in range(16)]
mx = max(amp)
wv = wave.open(os.path.join(OUT, 'sample.wav'), 'wb')
wv.setnchannels(1); wv.setsampwidth(1); wv.setframerate(8000)
wv.writeframes(bytes(int(amp[n] / mx * 255) for b in smp for n in (b >> 4, b & 15)))
wv.close()

# ------------------------------------------------------------------ logo / text
segs = m(0xE5E9, 37 * 6)
J['title_logo'] = {
    'note': 'segment: x, y, length, direction (0 right,1 down,2 down-right,3 down-left), '
            'fly-in dx, dy (signed, shifted right by the logo level). Drawn 2 px thick into a 256x48 buffer.',
    'segments': [[segs[i*6], segs[i*6+1], segs[i*6+2], segs[i*6+3], s8(segs[i*6+4]), s8(segs[i*6+5])]
                 for i in range(37)],
}
J['strings'] = {k: cstr(a) for k, a in [
    ('score', 0x9024), ('level', 0x902B), ('two_spaces', 0x9035), ('get_ready', 0x9038),
    ('edition', 0x9043), ('hiscore', 0x905C), ('final_score', 0x9066), ('help_move', 0x9073),
    ('help_jump', 0x9087), ('help_joystick', 0x909B), ('hint1', 0x90AE), ('hint2', 0x90C5),
    ('press_fire', 0x90D8), ('level_complete', 0x90EC), ('subtitle', 0x9233)]}

json.dump(J, open(os.path.join(OUT, 'jumpingjim.json'), 'w'), indent=1)

# ------------------------------------------------------------------ reference PNGs
try:
    from PIL import Image
    def save_sprite(name, data, w, h):
        im = Image.new('RGBA', (w, h))
        for y in range(h):
            for x in range(w):
                c = data[y*w + x]
                im.putpixel((x, y), (0, 0, 0, 0) if c == TRANSPARENT else rgb332(c) + (255,))
        im.save(os.path.join(OUT, 'sprites', name + '.png'))
    for i, f in enumerate(player):
        save_sprite('player_%02d' % i, f, 16, 16)
    for i, f in enumerate(enemy):
        save_sprite('enemy_v%d_k%d_f%d' % (i // 16, (i % 16) // 2, i % 2), f, 12, 11)
    save_sprite('drop', drop, 16, 16)
    SPEC = [(0,0,0),(0,0,205),(205,0,0),(205,0,205),(0,205,0),(0,205,205),(205,205,0),(205,205,205)]
    SPECB = [(0,0,0),(0,0,255),(255,0,0),(255,0,255),(0,255,0),(0,255,255),(255,255,0),(255,255,255)]
    pic = J['gameover']['picture_1bpp']['data']; at = J['gameover']['picture_attr']['data']
    im = Image.new('RGB', (144, 144))
    for y in range(144):
        for x in range(144):
            a = at[(y//8)*18 + x//8]; P = SPECB if a & 64 else SPEC
            on = pic[y*18 + x//8] & (0x80 >> (x & 7))
            im.putpixel((x, y), P[a & 7] if on else P[(a >> 3) & 7])
    im.save(os.path.join(OUT, 'screens', 'gameover_face.png'))
    im = Image.new('L', (512, 64 * 8))
    for c in range(64):
        for y in range(8):
            for x in range(8):
                if font[c*8+y] & (0x80 >> x):
                    for a in range(4):
                        for b in range(4):
                            im.putpixel(((c % 16)*32 + x*4 + a, (c//16)*32 + y*4 + b), 255)
    im.crop((0, 0, 512, 128)).save(os.path.join(OUT, 'screens', 'font.png'))
except ImportError:
    print('Pillow not installed: PNG previews skipped')
print('assets written to', OUT)
