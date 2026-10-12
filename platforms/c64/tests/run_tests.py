#!/usr/bin/env python3
"""
Automated test scenarios for the Commodore 64 port (headless VICE).

  run_tests.py record  DIR [--prg P --labels L --video pal|ntsc]
        run every scenario and write to DIR, per scenario:
          <name>.trace.gz   game variables + screen checksum for every frame
          <name>.png        contact sheet of screenshots
          shots/<name>_<frame>.png
  run_tests.py compare DIR_A DIR_B [--ignore-screen]
        compare two recordings frame by frame and name the first difference
  run_tests.py check   DIR
        record into a temporary directory and compare with DIR (regression test)

The controls are scripted, or played by a small "autopilot" that only looks at
the game's own variables, so every run of a given binary is identical.
Requires VICE 3.5+ and python3 + Pillow (see tools/vice_harness.py).
"""
import argparse
import gzip
import hashlib
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "tools"))
from vice_harness import Vice, load_labels, contact_sheet  # noqa: E402

# bits of the game's `input` byte
RIGHT, LEFT, JUMP, START = 1, 2, 4, 8
FIRE = JUMP | START

# game variables recorded every frame: (label, length)
TRACE = [("level", 1), ("lives", 1), ("score", 3), ("hiscore", 3),
         ("px", 1), ("py", 1), ("pvy", 1), ("pstate", 1), ("pfloor", 1),
         ("pfall", 1), ("ptimer", 1), ("pdir", 1), ("panim", 1), ("pinv", 1),
         ("pjf", 1), ("pmoving", 1), ("gstat", 1), ("flash", 1),
         ("rndlo", 2), ("gapstart", 7), ("gaplen", 7), ("gapspd", 7),
         ("e_state", 8), ("e_floor", 8), ("e_x", 8), ("e_y", 8), ("e_spd", 8),
         ("e_kind", 8), ("e_anim", 8), ("e_yoff", 8), ("e_tp", 8),
         ("readyt", 1)]


class Game:
    """Reads the game state out of the emulated memory."""

    def __init__(self, vice, labels):
        self.v, self.lab = vice, labels
        self.floor_y = None

    def refresh(self):
        zp = self.v.peek(0, 0x100)
        lab = self.lab
        self.zp = zp
        self.px, self.py = zp[lab["px"]], zp[lab["py"]]
        self.pstate, self.pfloor = zp[lab["pstate"]], zp[lab["pfloor"]]
        self.gapstart = zp[lab["gapstart"]:lab["gapstart"] + 7]
        self.gaplen = zp[lab["gaplen"]:lab["gaplen"] + 7]
        self.gapspd = zp[lab["gapspd"]:lab["gapspd"] + 7]
        self.e_state = zp[lab["e_state"]:lab["e_state"] + 8]
        self.e_floor = zp[lab["e_floor"]:lab["e_floor"] + 8]
        self.e_x = zp[lab["e_x"]:lab["e_x"] + 8]
        if self.floor_y is None and self.v.frame > 5:     # program is loaded
            self.floor_y = list(self.v.peek(lab["floor_y"], 7))

    def trace(self):
        out = b""
        for name, length in TRACE:
            addr = self.lab[name]
            out += (self.zp[addr:addr + length] if addr + length <= 0x100
                    else self.v.peek(addr, length))
        return out


def autopilot(g, careful=True):
    """A simple player: walk under the gap above, jump, and once the head is
    through steer against the movement of the gap to land on solid floor.
    It flees from baddies on its floor and waits while one is right above;
    with careful=False it ignores them (and soon loses its lives)."""
    def near(floor):
        if not careful:
            return None
        for i in range(8):
            if g.e_state[i] == 1 and g.e_floor[i] == floor:
                d = (g.e_x[i] - g.px + 26) & 255
                if d < 52:
                    return d - 26
        return None

    f = g.pfloor
    if g.pstate == 1:                         # airborne
        if f >= 6 or g.py >= g.floor_y[f + 1] + 19:
            return 0                          # head not through yet
        if ((g.px + 4 - g.gapstart[f + 1]) & 255) >= g.gaplen[f + 1]:
            return 0                          # already over solid floor
        return LEFT if g.gapspd[f + 1] < 128 else RIGHT
    if g.pstate != 0:
        return 0
    d = near(f)
    if d is not None:
        return LEFT if d >= 0 else RIGHT
    if f >= 6 or near(f + 1) is not None:
        return 0
    gl, gs = g.gaplen[f + 1], g.gapstart[f + 1]
    head = (g.px + 2 - gs) & 255              # the game's own head test
    if 4 <= head < gl - 11 - 4:
        return JUMP
    dist = (gl // 2 + gs - g.px - 8) & 255    # towards the middle of the gap
    if dist < 4 or dist >= 0xFD:
        return 0
    step = 3 if dist < 128 else -3
    if f != 0:
        if ((g.px + step + 4 - g.gapstart[f]) & 255) < ((g.gaplen[f] - 7) & 255):
            return 0                          # would fall into our own gap
    return RIGHT if step > 0 else LEFT


# --------------------------------------------------------------- scenarios
def scenario_attract(v, g, rec):
    """No input: splash, title, high score table, credits, title again."""
    for frame in range(1700):
        v.next_frame()
        rec(frame, shot=frame in (40, 150, 215, 330, 600, 900, 1250, 1650))


def scenario_play(v, g, rec):
    """Start a game and let the autopilot play: carefully for the first minute,
    then ignoring the baddies. After two minutes the remaining lives are taken
    away; then the initials are entered and the high score table is awaited."""
    over, back = [None], [None]

    def on_title(vv):
        if over[0] is not None and back[0] is None:
            back[0] = vv.frame
    v.on(g.lab["gameover"], lambda vv: over.__setitem__(0, vv.frame))
    v.on(g.lab["title"], on_title)
    for frame in range(12000):
        g.refresh()
        shot = False
        if frame < 330:
            inp = 0
        elif frame < 336:
            inp = FIRE                        # start the game
        elif over[0] is None:
            inp = autopilot(g, careful=frame < 3300) if frame > 340 else 0
            if frame >= 6000 and frame % 250 == 0 and g.pstate < 3:
                # cheat: after two minutes, kill Jim the way a collision does
                v.poke(g.lab["pstate"], 3)
                v.poke(g.lab["ptimer"], 70)
                v.poke(g.lab["pvy"], 0xFA)
            shot = frame in (345, 420) or frame % 300 == 0
        elif back[0] is None:                 # game over, then the initials
            t = frame - over[0]
            inp = FIRE if (t > 200 and t % 50 < 5) else (
                RIGHT if (t > 200 and t % 50 == 25) else 0)
            shot = t in (5, 120, 190, 240, 340)
        else:                                 # back on the title screen
            t = frame - back[0]
            inp = 0
            shot = t in (100, 1000)
            if t > 1020:
                break
        v.set_input(inp)
        v.next_frame()
        rec(frame, shot=shot)


def scenario_levels(v, g, rec):
    """Visit the first 9 levels (the 8 colour schemes and the first repeat):
    the autopilot plays, and after 420 frames 'level complete' is forced."""
    starts = []
    v.on(g.lab["setup_level"], lambda vv: starts.append(vv.frame))
    for frame in range(9000):
        g.refresh()
        if len(starts) == 10:
            break
        t = frame - starts[-1] if starts else -1
        if frame < 330:
            inp = 0
        elif frame < 336:
            inp = FIRE
        else:
            inp = autopilot(g) if t > 10 else 0
            if t == 420 and g.zp[g.lab["gstat"]] == 0 and g.pstate < 3:
                v.poke(g.lab["gstat"], 1)     # cheat: next level
        v.set_input(inp)
        v.next_frame()
        rec(frame, shot=t in (60, 250))


SCENARIOS = [("attract", scenario_attract), ("play", scenario_play),
             ("levels", scenario_levels)]


# ----------------------------------------------------------------- driver
def record(outdir, prg, labels_file, video, only=None, emulator="x64sc"):
    lab = load_labels(labels_file)
    os.makedirs(os.path.join(outdir, "shots"), exist_ok=True)
    width = sum(n for _, n in TRACE)
    for name, func in SCENARIOS:
        if only and name not in only:
            continue
        rows, shots = [], []
        with Vice(prg, emulator=emulator, video=video) as v:
            g = Game(v, lab)
            v.start(lab["irq_top"], lab["ri_end"], lab["input"])

            def rec(frame, shot=False):
                g.refresh()
                img = v.screenshot()
                digest = hashlib.sha1(img.tobytes()).digest()[:6]
                rows.append(g.trace() + digest)
                if shot:
                    img.save(os.path.join(outdir, "shots",
                                          "%s_%05d.png" % (name, frame)))
                    shots.append(img)
            func(v, g, rec)
        with gzip.GzipFile(os.path.join(outdir, name + ".trace.gz"), "wb",
                           mtime=0) as f:
            f.write(b"".join(rows))
        if shots:
            contact_sheet(shots, columns=4).save(
                os.path.join(outdir, name + ".png"))
        print("%-8s %5d frames, %2d screenshots" % (name, len(rows), len(shots)))
    with open(os.path.join(outdir, "info.json"), "w") as f:
        json.dump({"video": video, "trace": TRACE, "row": width + 6}, f)


def compare(dir_a, dir_b, ignore_screen=False):
    info = json.load(open(os.path.join(dir_a, "info.json")))
    row, ok = info["row"], True
    for name, _ in SCENARIOS:
        fa = os.path.join(dir_a, name + ".trace.gz")
        fb = os.path.join(dir_b, name + ".trace.gz")
        if not (os.path.exists(fa) and os.path.exists(fb)):
            continue
        a, b = gzip.open(fa).read(), gzip.open(fb).read()
        na, nb = len(a) // row, len(b) // row
        result = None
        for frame in range(min(na, nb)):
            ra, rb = a[frame * row:(frame + 1) * row], b[frame * row:(frame + 1) * row]
            if ra == rb:
                continue
            pos = 0
            for var, length in info["trace"]:
                if ra[pos:pos + length] != rb[pos:pos + length]:
                    result = "frame %d: %s = %s vs %s" % (
                        frame, var, ra[pos:pos + length].hex(),
                        rb[pos:pos + length].hex())
                    break
                pos += length
            if result:
                break
            if not ignore_screen:
                result = "frame %d: same game state, different picture" % frame
                break
        if result is None and na != nb:
            result = "different length: %d vs %d frames" % (na, nb)
        print("%-8s %s" % (name, "identical (%d frames)" % na
                           if result is None else "DIFFERENT - " + result))
        ok = ok and result is None
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("mode", choices=["record", "compare", "check"])
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--prg", default=os.path.join(HERE, "..", "build", "jumpingjim.prg"))
    ap.add_argument("--labels", default=os.path.join(HERE, "..", "build", "jumpingjim.lbl"))
    ap.add_argument("--video", default="pal")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--ignore-screen", action="store_true")
    a = ap.parse_args()
    if a.mode == "record":
        record(a.dirs[0], a.prg, a.labels, a.video, a.only)
    elif a.mode == "compare":
        sys.exit(0 if compare(a.dirs[0], a.dirs[1], a.ignore_screen) else 1)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            video = json.load(open(os.path.join(a.dirs[0], "info.json")))["video"]
            record(tmp, a.prg, a.labels, video, a.only)
            sys.exit(0 if compare(a.dirs[0], tmp, a.ignore_screen) else 1)


if __name__ == "__main__":
    main()
