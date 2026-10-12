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
covered by these tests** and has to be tried by hand.

Requirements: VICE 3.5+, `python3` with Pillow, and `xvfb-run` when there is no display
(`sudo pacman -S vice python-pillow xorg-server-xvfb`). With a display, VICE simply opens
a window while the test runs.

## Commodore 64

```sh
make -C platforms/c64 check       # play the scenarios, compare with tests/ref-pal
make -C platforms/c64 reference   # record tests/ref-pal again (after an intended change)
make -C platforms/c64 frametime   # CPU time used per frame, PAL and NTSC
```

`platforms/c64/tests/run_tests.py` has three scenarios:

| Scenario | What it does | Frames |
|---|---|---|
| `attract` | no input: splash, title, high score table, credits, title | 1700 |
| `play` | starts a game; an autopilot plays (carefully for a minute, then ignoring the baddies); after two minutes the remaining lives are taken away; initials are entered; waits for the table | ~7700 |
| `levels` | visits levels 1 to 9 (the 8 colour schemes and the first repeat); the autopilot plays and "level complete" is forced after 420 frames | ~5200 |

For every frame it records the game variables (player, gaps, enemies, score, random
seed...) and a checksum of the picture. `compare` names the first frame and variable that
differ; `--ignore-screen` compares the game logic only, which is the right check for a
change that is meant to alter the picture but not the behaviour.

```sh
cd platforms/c64
python3 tests/run_tests.py record /tmp/new                      # current build
python3 tests/run_tests.py compare tests/ref-pal /tmp/new       # everything
python3 tests/run_tests.py compare tests/ref-pal /tmp/new --ignore-screen
python3 tests/run_tests.py record /tmp/ntsc --video ntsc        # also: paln
```

`tests/ref-pal/` holds the reference of **v1.0.1** on PAL (traces and contact sheets).
The picture checksums depend on the VICE version (recorded with VICE 3.7.1); the game
variables should not. Record the reference again on your machine before relying on the
picture comparison.

## Baseline measurements, v1.0.1

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
