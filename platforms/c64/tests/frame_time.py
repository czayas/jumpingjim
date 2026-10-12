#!/usr/bin/env python3
"""
How much of each video frame does the game loop need?

Plays the 'levels' scenario (9 levels, autopilot) on PAL and on NTSC and notes
the raster line at which the game loop has finished its work and starts waiting
for the next frame. The frame starts at raster line 16 (top-of-frame interrupt).
A loop that does not finish in time skips a frame ("late frames").

usage: frame_time.py [prg] [labels]
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from run_tests import Vice, Game, load_labels, autopilot, FIRE  # noqa: E402

prg = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "build", "jumpingjim.prg")
lbl = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "build", "jumpingjim.lbl")
lab = load_labels(lbl)

for video, total in (("pal", 312), ("ntsc", 263)):
    starts, lines = [], []
    with Vice(prg, video=video) as v:
        g = Game(v, lab)

        def at_waitframe(vv):
            d011, d012 = vv.peek(0xD011, 2, bank=3)     # 3 = I/O
            lines.append((vv.frame, len(starts), ((d011 & 0x80) << 1) | d012))
        v.on(lab["setup_level"], lambda vv: starts.append(vv.frame))
        v.on(lab["waitframe"], at_waitframe)
        v.start(lab["irq_top"], lab["ri_end"], lab["input"])
        for frame in range(9000):
            g.refresh()
            if len(starts) == 10:
                break
            t = frame - starts[-1] if starts else -1
            inp = 0 if frame < 330 else FIRE if frame < 336 else (
                autopilot(g) if t > 10 else 0)
            if frame >= 336 and t == 420 and g.zp[lab["gstat"]] == 0 and g.pstate < 3:
                v.poke(lab["gstat"], 1)
            v.set_input(inp)
            v.next_frame()
    print("%s (%d raster lines per frame)" % (video.upper(), total))
    print("  level  enemies  average  worst   late frames")
    used = collections.defaultdict(list)
    frames = collections.defaultdict(set)
    for frame, level, line in lines:
        if level and frame - starts[level - 1] > 135:   # after GET READY
            used[level].append((line - 16) % total)
            frames[level].add(frame)
    for level in sorted(used):
        u, f = used[level], frames[level]
        span = max(f) - min(f) + 1
        print("  %5d  %7d  %6.0f%%  %4.0f%%   %d of %d" % (
            level, min(level + 1, 8), 100 * sum(u) / len(u) / total,
            100 * sorted(u)[int(len(u) * 0.95)] / total, span - len(u), span))
