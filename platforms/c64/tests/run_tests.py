#!/usr/bin/env python3
"""
Automated test scenarios for the Commodore 64 port (headless VICE).

  run_tests.py record  DIR [--prg P --labels L --video pal|ntsc]
        run every scenario and write to DIR, per scenario:
          <name>.trace.gz   game variables + screen checksum for every frame
          <name>.png        contact sheet of screenshots
          shots/<name>_<frame>.png
  run_tests.py compare DIR_A DIR_B [--ignore-screen]
        (frame 0 of every scenario is the first frame of the title screen)
        compare two recordings frame by frame and name the first difference
  run_tests.py check   DIR
        record into a temporary directory and compare with DIR (regression test)

  --clock frame  (default) one step = one video frame: the real behaviour,
                 timing included. Use it to check that nothing changed at all.
  --clock logic  one step = one game update, and the game's frame counter is
                 set to the update number. Levels 1-2 move the floors on even
                 frames, so in the real game a change of speed anywhere (a
                 slower screen set-up, a late frame) changes what happens
                 next; the logic clock removes that, so two versions with
                 different timing can be compared for the game logic alone.

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
    """No input: title, high score table, credits, title again."""
    for frame in range(1600):
        v.step()
        rec(frame, shot=frame in (40, 130, 300, 500, 700, 1050, 1450, 1590))


def scenario_play(v, g, rec):
    """Start a game and let the autopilot play: carefully for the first minute,
    then ignoring the baddies. After two minutes the remaining lives are taken
    away; then the initials are entered and the high score table is awaited."""
    over, back = [None], [None]

    def on_title(vv):
        if over[0] is not None and back[0] is None:
            back[0] = vv.now()
    v.on(g.lab["gameover"], lambda vv: over.__setitem__(0, vv.now()))
    v.on(g.lab["title"], on_title)
    for frame in range(12000):
        g.refresh()
        shot = False
        if frame < 330:
            inp = 0
        elif frame < 336:
            inp = FIRE                        # start the game (frame 0 = title)
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
        v.step()
        rec(frame, shot=shot)


def scenario_levels(v, g, rec):
    """Visit the first 9 levels (the 8 colour schemes and the first repeat):
    the autopilot plays with endless lives, and after 420 steps 'level
    complete' is forced."""
    starts = []

    def level_start(vv):
        starts.append(vv.now())
        vv.poke(g.lab["lives"], 3)            # cheat: never run out of lives
    v.on(g.lab["setup_level"], level_start)
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
            if t >= 420 and g.zp[g.lab["gstat"]] == 0 and g.pstate < 3:
                v.poke(g.lab["gstat"], 1)     # cheat: next level
        v.set_input(inp)
        v.step()
        rec(frame, shot=t in (60, 250))


SCENARIOS = [("attract", scenario_attract), ("play", scenario_play),
             ("levels", scenario_levels)]


def drawn(v, lab):
    """Everything the program has prepared to be shown: the 256x192 bitmap,
    its colours and the sprite list of the next frame (the side columns, the
    blinking row and the screen offset are left out: the interrupt changes
    them by time, not by the game logic)."""
    bitmap = v.peek(0xE000, 24 * 320)
    colours = bytearray(v.peek(0xC000, 24 * 40))
    flashrow = v.peek(lab["flashrow"])[0]
    out = bytearray()
    for r in range(24):
        out += bitmap[r * 320 + 32:r * 320 + 288]
        if r != flashrow:
            out += colours[r * 40 + 4:r * 40 + 36]
    n = v.peek(lab["dnB"])[0]
    sprites = v.peek(lab["bline"], 90)                 # bline .. bcol, 10 each
    for i in range(min(n, 10)):
        out += bytes(sprites[k * 10 + i] for k in (3, 4, 5, 6, 7, 8))   # x y msb pri ptr col
    out += bytes([n])
    return bytes(out)


# ----------------------------------------------------------------- driver
def record(outdir, prg, labels_file, video, only=None, emulator="x64sc", clock="frame",
           fx_off=False):
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
            # the start-up (RIP splash) is not compared: frame 0 of every
            # scenario is the first frame of the title screen, so versions
            # whose start-up takes a different time can still be compared
            v.run_to(lab["title"])
            g.floor_y = list(v.peek(lab["floor_y"], 7))
            if fx_off and "fx_on" in lab:
                v.poke(lab["fx_on"], 0)           # extra effects off (F1)
            if clock == "frame":
                v.step = v.next_frame
                v.now = lambda: v.frame - 1     # = index of the current step
            else:
                # one step = one game update, with the frame counter set to the
                # update number (see the module documentation)
                v.updates = 0
                v.step = lambda: v.next_update(lab["fcount"])
                v.now = lambda: v.updates - 1

            def rec(frame, shot=False):
                g.refresh()
                img = v.screenshot() if (shot or clock == "frame") else None
                if clock == "frame":
                    # the picture VICE has just finished drawing
                    digest = hashlib.sha1(img.tobytes()).digest()[:6]
                else:
                    # mid-frame, VICE's picture depends on timing: use what the
                    # program has in memory to be drawn instead
                    digest = hashlib.sha1(drawn(v, lab)).digest()[:6]
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
        json.dump({"video": video, "clock": clock, "trace": TRACE, "row": width + 6}, f)


# changed by the interrupt once per video frame, not by the game logic
IRQ_VARS = {"flash"}


def compare(dir_a, dir_b, ignore_screen=False):
    info = json.load(open(os.path.join(dir_a, "info.json")))
    row, ok = info["row"], True
    logic = info.get("clock") == "logic"
    for name, _ in SCENARIOS:
        fa = os.path.join(dir_a, name + ".trace.gz")
        fb = os.path.join(dir_b, name + ".trace.gz")
        if not (os.path.exists(fa) and os.path.exists(fb)):
            continue
        a, b = gzip.open(fa).read(), gzip.open(fb).read()
        na, nb = len(a) // row, len(b) // row
        result = None
        pic = []                              # frames: same state, other picture
        for frame in range(min(na, nb)):
            ra, rb = a[frame * row:(frame + 1) * row], b[frame * row:(frame + 1) * row]
            if ra == rb:
                continue
            pos = 0
            for var, length in info["trace"]:
                if logic and var in IRQ_VARS:
                    pos += length
                    continue
                if ra[pos:pos + length] != rb[pos:pos + length]:
                    result = "frame %d: %s = %s vs %s" % (
                        frame, var, ra[pos:pos + length].hex(),
                        rb[pos:pos + length].hex())
                    break
                pos += length
            if result:
                break
            if ra[-6:] != rb[-6:]:
                pic.append(frame)
        if result is None and pic and not ignore_screen:
            ranges, start = [], pic[0]
            for p0, p1 in zip(pic, pic[1:] + [None]):
                if p1 != p0 + 1:
                    ranges.append("%d-%d" % (start, p0) if p0 > start else str(start))
                    start = p1
            result = "same game state; the picture differs in %d frames: %s%s" % (
                len(pic), ", ".join(ranges[:12]), " ..." if len(ranges) > 12 else "")
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
    ap.add_argument("--clock", choices=["frame", "logic"], default="frame")
    ap.add_argument("--fx-off", action="store_true",
                    help="switch the extra effects off (as F1 on the title)")
    a = ap.parse_args()
    if a.mode == "record":
        record(a.dirs[0], a.prg, a.labels, a.video, a.only, clock=a.clock, fx_off=a.fx_off)
    elif a.mode == "compare":
        sys.exit(0 if compare(a.dirs[0], a.dirs[1], a.ignore_screen) else 1)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            info = json.load(open(os.path.join(a.dirs[0], "info.json")))
            record(tmp, a.prg, a.labels, info["video"], a.only,
                   clock=info.get("clock", "frame"))
            sys.exit(0 if compare(a.dirs[0], tmp, a.ignore_screen) else 1)


if __name__ == "__main__":
    main()
