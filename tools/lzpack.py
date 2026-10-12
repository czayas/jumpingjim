#!/usr/bin/env python3
"""
Small LZ77 packer for the 6502 ports (decompressor: platforms/c64/src, 'unpack').

Format, chosen for a short and fast 6502 decompressor:
  t = 0          end of data
  t = 1..127     t literal bytes follow
  t = 128        skip: the next byte (1..255) says how many output bytes to
                 leave as they are (the destination advances, nothing is written)
  t = 129..191   copy t - 126 bytes (3..65) from 'offset' bytes back in the
                 output; a 2-byte little-endian offset (1..65535) follows
  t = 192..255   fill: t - 189 bytes (3..66) with the value in the next byte
                 (runs of one value are common in pictures, and the 6502 fills
                 faster than it copies)

Skipping lets one stream fill a part of the screen that is not contiguous in
memory (e.g. the 32 middle columns of each bitmap row) without a buffer.

The output is written as a byte string; the decompressor needs nothing but the
data and the destination address (no buffer), so it can unpack straight into
the bitmap.

usage as a module:  pack(data, skip=None) -> bytes,  unpack(packed, base=None)
(skip: a sequence of booleans, True = leave that output byte untouched)
"""
import sys

MIN_MATCH, MAX_MATCH, MAX_LIT, MAX_FILL = 3, 65, 127, 66


def pack(data, skip=None, window=8192):
    data = bytes(data)
    n = len(data)
    skip = [False] * n if skip is None else list(skip)
    out = bytearray()
    lit = bytearray()
    heads = {}                      # 3-byte prefix -> list of positions
    i = 0

    def flush():
        nonlocal lit
        while lit:
            chunk = lit[:MAX_LIT]
            out.append(len(chunk))
            out.extend(chunk)
            lit = lit[MAX_LIT:]

    def add(pos):
        if pos + 3 <= n and not any(skip[pos:pos + 3]):
            heads.setdefault(data[pos:pos + 3], []).append(pos)

    while i < n:
        if skip[i]:
            flush()
            j = i
            while j < n and skip[j] and j - i < 255:
                j += 1
            out += bytes([128, j - i])
            i = j
            continue
        run = 1
        while run < MAX_FILL and i + run < n and not skip[i + run] and data[i + run] == data[i]:
            run += 1
        best_len, best_off = 0, 0
        if i + MIN_MATCH <= n and not any(skip[i:i + 3]):
            for p in reversed(heads.get(data[i:i + 3], [])):
                if i - p > window:
                    break
                ln = 3
                while (ln < MAX_MATCH and i + ln < n and not skip[i + ln]
                       and not skip[p + ln] and data[p + ln] == data[i + ln]):
                    ln += 1
                if ln > best_len:
                    best_len, best_off = ln, i - p
                    if ln == MAX_MATCH:
                        break
        if run >= 3 and run >= best_len:
            flush()
            out += bytes([189 + run, data[i]])
            for k in range(run):
                add(i + k)
            i += run
        elif best_len >= MIN_MATCH:
            flush()
            out.append(126 + best_len)
            out += bytes([best_off & 255, best_off >> 8])
            for k in range(best_len):
                add(i + k)
            i += best_len
        else:
            lit.append(data[i])
            add(i)
            i += 1
    flush()
    out.append(0)
    return bytes(out)


def unpack(packed, base=None):
    """Unpack into a copy of `base` (bytes left by skips keep their value)."""
    out = bytearray(base) if base is not None else bytearray()
    pos, i = 0, 0
    while True:
        t = packed[i]
        i += 1
        if t == 0:
            return bytes(out[:max(pos, 0)] if base is None else out)
        if t < 128:
            put = packed[i:i + t]
            i += t
        elif t == 128:
            if base is None:
                out += bytes(packed[i])
            pos += packed[i]
            i += 1
            continue
        elif t >= 192:
            put = bytes([packed[i]]) * (t - 189)
            i += 1
        else:
            ln, off = t - 126, packed[i] | (packed[i + 1] << 8)
            i += 2
            put = bytearray()
            for k in range(ln):
                src = pos + k - off
                put.append(put[src - pos] if src >= pos else out[src])
        if len(out) < pos + len(put):
            out += bytes(pos + len(put) - len(out))
        out[pos:pos + len(put)] = put
        pos += len(put)


if __name__ == "__main__":
    for path in sys.argv[1:]:
        raw = open(path, "rb").read()
        p = pack(raw)
        assert unpack(p) == raw
        print("%-40s %6d -> %6d" % (path, len(raw), len(p)))
