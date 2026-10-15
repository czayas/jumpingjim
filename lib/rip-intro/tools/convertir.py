#!/usr/bin/env python3
"""
Convierte una imagen PNG en una "lámina" para la intro del C64 (c64/rip_intro.a).

Uso:
  convertir.py imagen.png salida.bin --modo multi|hires --celdas ANCHOxALTO
               [--col N] [--fila N] [--vista vista.png]
  convertir.py --tablas tablas.a        (tablas del fundido, ver más abajo)

--celdas  tamaño en celdas de 8x8 (la imagen se escala a ese tamaño: en
          multicolor cada píxel es doble de ancho, así que ANCHO*4 x ALTO*8).
--col, --fila  posición en pantalla de la esquina superior izquierda
          (por omisión, centrada en 40x24).

Formato de la lámina (lo lee ri_show):
  byte 0  modo (0 hires, 1 multicolor)
  byte 1  columna, byte 2 fila, byte 3 ancho, byte 4 alto (en celdas)
  bitmap  ancho*alto*8 bytes, fila por fila, celda por celda
  pantalla ancho*alto bytes (colores de cada celda, nibble alto y bajo)
  color   ancho*alto bytes (solo multicolor: el tercer color de cada celda)
El fondo ($d021) es siempre negro.

La conversión multicolor es la misma que usaba Jumping Jim (v1.1.0) para el
logo de RIP, para que el resultado sea idéntico byte a byte.
"""
import argparse
import sys
from collections import Counter
from itertools import combinations

PEPTO = [(0, 0, 0), (255, 255, 255), (104, 55, 43), (112, 164, 178), (111, 61, 134),
         (88, 141, 67), (53, 40, 121), (184, 199, 111), (111, 79, 37), (67, 57, 0),
         (154, 103, 89), (68, 68, 68), (108, 108, 108), (154, 210, 132), (108, 94, 181),
         (149, 149, 149)]

# Escalera del fundido: cada color pasa a uno más oscuro. 5 niveles: 0 = original,
# 4 = negro (aplicar la escalera 4 veces lleva cualquier color al negro).
MAS_OSCURO = [0, 15, 9, 14, 6, 11, 0, 15, 2, 0, 8, 0, 11, 5, 4, 12]
NIVELES = 5


def dist(a, b):
    # distancia "redmean" entre colores RGB
    rm = (a[0] + b[0]) / 2.0
    dr, dg, db = a[0] - b[0], a[1] - b[1], a[2] - b[2]
    return (2 + rm / 256.0) * dr * dr + 4 * dg * dg + (2 + (255 - rm) / 256.0) * db * db


def nearest(rgb, allowed=range(16)):
    return min(allowed, key=lambda i: dist(rgb, PEPTO[i]))


def oscurecer(c, nivel):
    for _ in range(nivel):
        c = MAS_OSCURO[c]
    return c


def multicolor(img, w, h):
    """w, h en celdas. Devuelve bitmap, pantalla, color."""
    from PIL import Image
    W, H = w * 4, h * 8
    src = img.convert('RGB').resize((W, H), Image.LANCZOS)
    px = [[list(src.getpixel((x, y))) for x in range(W)] for y in range(H)]
    bm, scr, col = bytearray(), bytearray(), bytearray()
    for cy in range(h):
        for cx in range(w):
            cell = [(x, y) for y in range(cy * 8, cy * 8 + 8) for x in range(cx * 4, cx * 4 + 4)]
            cnt = Counter(nearest(tuple(px[y][x])) for x, y in cell)
            cands = [c for c, _ in cnt.most_common(6) if c != 0] or [1]
            best = None
            for combo in combinations(cands, min(3, len(cands))):
                pal = [0] + list(combo)
                e = sum(min(dist(tuple(px[y][x]), PEPTO[c]) for c in pal) for x, y in cell)
                if best is None or e < best[0]:
                    best = (e, pal)
            pal = best[1] + [0] * (4 - len(best[1]))
            codes = {}
            for y in range(cy * 8, cy * 8 + 8):
                for x in range(cx * 4, cx * 4 + 4):
                    old = px[y][x]
                    k = min(range(4), key=lambda i: dist(tuple(max(0, min(255, int(v))) for v in old),
                                                         PEPTO[pal[i]]))
                    codes[(x, y)] = k
                    newc = PEPTO[pal[k]]
                    err = [old[i] - newc[i] for i in range(3)]
                    for dx, dy, f in ((1, 0, 7 / 16), (-1, 1, 3 / 16), (0, 1, 5 / 16), (1, 1, 1 / 16)):
                        nx, ny = x + dx, y + dy
                        if cx * 4 <= nx < cx * 4 + 4 and ny < cy * 8 + 8:
                            for i in range(3):
                                px[ny][nx][i] += err[i] * f * 0.8
            for y in range(cy * 8, cy * 8 + 8):
                b = 0
                for x in range(cx * 4, cx * 4 + 4):
                    b = (b << 2) | codes[(x, y)]
                bm.append(b)
            scr.append((pal[1] << 4) | pal[2])
            col.append(pal[3])
    return bm, scr, col


def hires(img, w, h):
    """2 colores por celda de 8x8 (tinta y papel), con tramado dentro de la celda."""
    from PIL import Image
    W, H = w * 8, h * 8
    src = img.convert('RGB').resize((W, H), Image.LANCZOS)
    px = [[list(src.getpixel((x, y))) for x in range(W)] for y in range(H)]
    bm, scr = bytearray(), bytearray()
    for cy in range(h):
        for cx in range(w):
            cell = [(x, y) for y in range(cy * 8, cy * 8 + 8) for x in range(cx * 8, cx * 8 + 8)]
            cnt = Counter(nearest(tuple(px[y][x])) for x, y in cell)
            cands = [c for c, _ in cnt.most_common(5)]
            if len(cands) == 1:
                pal = [cands[0], cands[0]]
            else:
                best = None
                for combo in combinations(cands, 2):
                    e = sum(min(dist(tuple(px[y][x]), PEPTO[c]) for c in combo) for x, y in cell)
                    if best is None or e < best[0]:
                        best = (e, list(combo))
                pal = best[1]
            for y in range(cy * 8, cy * 8 + 8):
                b = 0
                for x in range(cx * 8, cx * 8 + 8):
                    old = px[y][x]
                    k = min(range(2), key=lambda i: dist(tuple(max(0, min(255, int(v))) for v in old),
                                                         PEPTO[pal[i]]))
                    b = (b << 1) | k
                    newc = PEPTO[pal[k]]
                    err = [old[i] - newc[i] for i in range(3)]
                    for dx, dy, f in ((1, 0, 7 / 16), (-1, 1, 3 / 16), (0, 1, 5 / 16), (1, 1, 1 / 16)):
                        nx, ny = x + dx, y + dy
                        if cx * 8 <= nx < cx * 8 + 8 and ny < cy * 8 + 8:
                            for i in range(3):
                                px[ny][nx][i] += err[i] * f * 0.8
                bm.append(b)
            scr.append((pal[1] << 4) | pal[0])          # bit 1 = tinta (nibble alto)
    return bm, scr


def vista(path, modo, w, h, bm, scr, col):
    from PIL import Image
    im = Image.new('RGB', (w * 8, h * 8))
    for cy in range(h):
        for cx in range(w):
            i = cy * w + cx
            for ln in range(8):
                b = bm[i * 8 + ln]
                if modo == 'multi':
                    pal = [0, scr[i] >> 4, scr[i] & 15, col[i]]
                    for p in range(4):
                        c = PEPTO[pal[(b >> (6 - 2 * p)) & 3]]
                        im.putpixel((cx * 8 + p * 2, cy * 8 + ln), c)
                        im.putpixel((cx * 8 + p * 2 + 1, cy * 8 + ln), c)
                else:
                    for p in range(8):
                        c = PEPTO[scr[i] >> 4 if b & (0x80 >> p) else scr[i] & 15]
                        im.putpixel((cx * 8 + p, cy * 8 + ln), c)
    im.resize((w * 24, h * 24), Image.NEAREST).save(path)


def tablas(path):
    """Tablas del fundido para el ensamblador: por cada nivel, el byte de
    pantalla oscurecido (256 bytes, los dos nibbles) y el color (16 bytes)."""
    out = ['; generado por tools/convertir.py --tablas: no editar', 'ri_fpant']
    for nv in range(NIVELES):
        for i in range(0, 256, 16):
            out.append('\t!byte ' + ','.join(
                '$%02x' % ((oscurecer(v >> 4, nv) << 4) | oscurecer(v & 15, nv))
                for v in range(i, i + 16)))
    out.append('ri_fcol')
    for nv in range(NIVELES):
        out.append('\t!byte ' + ','.join('$%02x' % oscurecer(v, nv) for v in range(16)))
    open(path, 'w').write('\n'.join(out) + '\n')


def main():
    ap = argparse.ArgumentParser(description='PNG -> lámina para la intro del C64')
    ap.add_argument('imagen', nargs='?')
    ap.add_argument('salida', nargs='?')
    ap.add_argument('--modo', choices=['multi', 'hires'], default='multi')
    ap.add_argument('--celdas', default='17x24')
    ap.add_argument('--col', type=int)
    ap.add_argument('--fila', type=int)
    ap.add_argument('--vista')
    ap.add_argument('--tablas')
    a = ap.parse_args()
    if a.tablas:
        tablas(a.tablas)
        if not a.imagen:
            return
    if not (a.imagen and a.salida):
        ap.error('faltan la imagen y la salida')
    from PIL import Image
    w, h = (int(v) for v in a.celdas.lower().split('x'))
    if not (1 <= w <= 40 and 1 <= h <= 25):
        sys.exit('tamaño fuera de la pantalla: %dx%d celdas' % (w, h))
    col = (40 - w) // 2 if a.col is None else a.col
    fila = (24 - h) // 2 if a.fila is None else a.fila
    if col + w > 40 or fila + h > 25:
        sys.exit('la imagen no entra en la pantalla en %d,%d' % (col, fila))
    img = Image.open(a.imagen)
    if a.modo == 'multi':
        bm, scr, cl = multicolor(img, w, h)
    else:
        bm, scr = hires(img, w, h)
        cl = b''
    data = bytes([1 if a.modo == 'multi' else 0, col, fila, w, h]) + bm + scr + cl
    open(a.salida, 'wb').write(data)
    if a.vista:
        vista(a.vista, a.modo, w, h, bm, scr, cl)
    print('%s: %s %dx%d celdas en %d,%d, %d bytes' % (a.salida, a.modo, w, h, col, fila, len(data)))


if __name__ == '__main__':
    main()
