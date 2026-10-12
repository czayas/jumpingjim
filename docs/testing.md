# Automated testing

The ports are tested in the emulator without a screen, with scripted controls, so a
change can be compared **frame by frame** with the version that already works.

## How it works

`tools/vice_harness.py` starts VICE (`x64sc`, and later `xplus4`, `x128`, `xvic`,
`xpet`) in warp mode and drives it through VICE's *binary monitor*, a remote-control
connection built into VICE 3.5 and newer. Once per video frame the harness stops the
machine and can then:

- set the controls for that frame,
- read or write memory (game variables, cheats such as "next level"),
- grab the picture as a PNG.

Runs are fully repeatable: VICE's random RAM contents and random autostart delay are
switched off, and the controls are applied at exact frame boundaries. Two runs of the
same binary give identical memory and identical pictures on every frame.

The controls are injected by overwriting the game's `input` byte right after
`read_input` has stored it (label `ri_end`). VICE's own joystick injection is not used:
in VICE 3.7 it does not reach the emulated ports when running headless and it is applied
with a random delay. **The keyboard and joystick reading code itself is therefore not
covered by these tests.** Real key presses can be sent to the VICE window with `xdotool`
(this is how F1 on the title was tried), but the joystick has to be tried by hand.

Requirements: VICE 3.5+, `python3` with Pillow, and `xvfb-run` when there is no display
(`sudo pacman -S vice python-pillow xorg-server-xvfb`). With a display, VICE simply opens
a window while the test runs.

## Commodore 64

```sh
make -C platforms/c64 check       # play the scenarios, compare with the references
make -C platforms/c64 reference   # record the references again (after an intended change)
make -C platforms/c64 frametime   # CPU time used per frame, PAL and NTSC
```

`platforms/c64/tests/run_tests.py` has three scenarios. The start-up (RIP splash) is
skipped: step 0 of every scenario is the first frame of the title screen.

| Scenario | What it does |
|---|---|
| `attract` | no input: title, high score table, credits, title again (1600 steps) |
| `play` | starts a game; an autopilot plays (carefully for a minute, then ignoring the baddies); after two minutes the remaining lives are taken away; initials are entered; waits for the table |
| `levels` | visits levels 1 to 9 (the 8 colour schemes and the first repeat) with endless lives; the autopilot plays and "level complete" is forced after 420 steps |

For every step it records the game variables (player, gaps, enemies, score, random
seed...) and a checksum of the picture. `compare` names the first step and variable that
differ, or lists the steps whose picture differs while the game state is the same.

### Two clocks

- `--clock frame` (default): one step is one video frame, timing included. Any change in
  the code speed changes what happens next, because levels 1 and 2 move the floors on
  even frames only, and a slower screen set-up or one late frame shifts that. Use it to
  check that **nothing at all** changed (reference: `tests/ref-pal`).
- `--clock logic`: one step is one game update, and the game's frame counter is set to the
  update number. Timing no longer matters, so two versions that run at a different speed
  can be compared for their **game logic**. The picture checksum is then taken from
  memory (bitmap, colours and the sprite list of the next frame, leaving out the side
  columns and the blinking row, which the interrupt changes by time), not from VICE's
  half-drawn picture (reference: `tests/ref-pal-logic`).

```sh
cd platforms/c64
python3 tests/run_tests.py record /tmp/new --clock logic             # current build
python3 tests/run_tests.py compare tests/ref-pal-logic /tmp/new
python3 tests/run_tests.py compare tests/ref-pal-logic /tmp/new --ignore-screen
python3 tests/run_tests.py record /tmp/off --clock logic --fx-off    # effects off (F1)
python3 tests/run_tests.py record /tmp/ntsc --video ntsc             # also: paln
```

The picture checksums of the `frame` clock depend on the VICE version (the references
were recorded with VICE 3.7.1). Record the references again on your machine before
relying on them.

### Checks of the shake and the blinking text (branch v1.1.0-dev)

Compared with v1.0.1, logic clock, all three scenarios:

- game logic: identical (11,067 updates);
- effects off: identical pictures except the title (new F1 line, blinking text) and the
  high score table of the attract cycle (the stray banner is gone);
- effects on: the pictures differ in addition only in the 6 to 24 frames after a head
  bump or a fall.

### Checks of the backgrounds and the packed data (branch v1.1.0-dev)

- game logic: identical to v1.0.1 (logic clock, the three scenarios);
- effects off: same pictures as with the shake stage, i.e. the original levels;
- title and credits (logo unpacked on the fly): identical pictures to the previous stage;
- sprites after start-up (unpacked): byte for byte the same as v1.0.1;
- each of the eight backgrounds, read back from the C64 memory once the level is set up:
  0 pixels different from its master PNG (the floor lines left out);
- title speed: 467 loop iterations in the first 590 frames (v1.0.1: 470);
- loading from the .d64 with true drive emulation and saving `JJ.HISCORES`: works.

### Checks of PAL / NTSC / PAL-N (branch v1.1.0-dev)

- detection (`tv_sys` read back after start-up): PAL 0, NTSC 1, old NTSC 1, PAL-N 2;
- game ticks per second (counted from `fcount`): PAL 50.12, NTSC 49.86, old NTSC 50.83,
  PAL-N 50.47;
- tuning (SID frequency in use against the AY frequency of each note): within 1.4 cents
  on PAL and NTSC, 2.4 cents on PAL-N;
- game logic and pictures with the logic clock on NTSC, old NTSC and PAL-N: identical to
  PAL, except the credits line that names the system;
- game updates per second reached with 2 to 8 baddies (`make frametime`):

| Level | Enemies | PAL CPU | PAL updates/s | NTSC CPU | NTSC updates/s |
|---|---|---|---|---|---|
| 1 | 2 | 27 % | 50.1 | 31 % | 49.9 |
| 2 | 3 | 32 % | 50.1 | 36 % | 49.9 |
| 3 | 4 | 44 % | 50.1 | 49 % | 49.9 |
| 4 | 5 | 54 % | 50.1 | 60 % | 49.7 |
| 5 | 6 | 64 % | 49.9 | 70 % | 49.7 |
| 6 | 7 | 72 % | 49.9 | 84 % | 49.7 |
| 7 | 8 | 79 % | 49.9 | 90 % | 49.9 |
| 8 | 8 | 76 % | 49.9 | 83 % | 49.5 |
| 9 | 8 | 81 % | 49.9 | 91 % | 49.7 |

(Ideal: 50.1 on PAL, 49.9 on NTSC. "CPU" is the average share of a frame the game loop
needs.)

## Baseline measurements, v1.0.1

(The shake adds about 1 to 2 % of a frame to the game loop.)

### Video standards

The game was written for PAL. It also starts and plays on NTSC and PAL-N (Drean) with no
visible fault in the three scenarios, but the game logic runs once per video frame:

| Standard | Frames per second | Game and music speed | Pitch of the music |
|---|---|---|---|
| PAL | 50.12 | as designed | as designed |
| NTSC | 59.83 | 19 % faster | 3.8 % sharp (about 2/3 of a semitone) |
| PAL-N | 50.47 | 0.7 % faster | 3.9 % sharp |

(The speed follows from the frame rate; the pitch from the clock of each machine,
because the SID frequency table was computed for the PAL clock. The sound itself is not
checked by the tests.)

### CPU time per frame

Share of the frame used by the game loop (from the top-of-frame interrupt until it
starts waiting for the next frame), `levels` scenario:

| Level | Enemies | PAL average | PAL late frames | NTSC average | NTSC late frames |
|---|---|---|---|---|---|
| 1 | 2 | 26 % | 0 of 263 | 33 % | 0 of 283 |
| 2 | 3 | 32 % | 0 of 1068 | 35 % | 1 of 190 |
| 3 | 4 | 45 % | 0 of 283 | 51 % | 2 of 283 |
| 4 | 5 | 55 % | 1 of 429 | 61 % | 4 of 361 |
| 5 | 6 | 61 % | 2 of 283 | 71 % | 10 of 691 |
| 6 | 7 | 75 % | 6 of 345 | 83 % | 6 of 375 |
| 7 | 8 | 79 % | 6 of 364 | 94 % | 4 of 283 |
| 8 | 8 | 80 % | 3 of 283 | 88 % | 5 of 379 |
| 9 | 8 | 80 % | 5 of 283 | 93 % | 2 of 283 |

A "late frame" is a frame in which the loop did not finish and the game skipped one
update. Each enemy costs roughly 9 % of a PAL frame. An NTSC frame has 13 % fewer CPU
cycles, so there is little room left there with eight enemies.

### Memory map

| Range | Size | Contents |
|---|---|---|
| `$0801–$2899` | 8.3 KB | code |
| `$289A–$2F47` | 1.7 KB | texts, tables, sprite multiplexer buffers |
| `$2F48–$3147` | 0.5 KB | font |
| `$3148–$427B` | 4.3 KB | game over colours, RIP logo |
| `$427C–$5D7B` | 6.8 KB | music |
| `$5D7C–$69FF` | 3.1 KB | game over picture |
| `$6A00–$9FFF` | 13.5 KB | title logo, 9 precomputed states |
| `$A000–$BBFF` | 7.0 KB | sprites (copied to `$C400` at start-up, unused afterwards) |
| `$BC00–$BFFF` | 1.0 KB | **free** |
