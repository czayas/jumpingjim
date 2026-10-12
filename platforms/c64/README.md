# Jumping Jim — Commodore 64

Complete port in 6502 assembly (ACME). Runs on a real PAL C64 or in an emulator (VICE).

## Building

Requirements: `python3` (Pillow), `acme`, `c1541` (VICE).

```sh
make          # build/jumpingjim.prg and build/jumpingjim.d64
make run      # opens it in x64sc
make test     # build/test.prg with scripted input (jumps and walks by itself)
make promo    # build/promo.prg: autopilot that plays on its own (for recording videos)
make check    # automated tests in headless VICE, compared with tests/ref-pal
```
On Manjaro/Arch:

```sh
# ACME is not in the Manjaro/Arch repositories: build it from source
git clone https://github.com/meonwax/acme
make -C acme/src && sudo cp acme/src/acme /usr/local/bin/
sudo pacman -S vice python-pillow    # VICE provides c1541 and x64sc
```
On Debian/Ubuntu: `sudo apt install acme vice` (VICE needs the C64 ROMs installed separately).

## Loading
`LOAD"*",8,1` and `RUN` (or drop the .d64/.prg onto VICE).

## Splash screen
On start-up the **Retro Informática Paraguay** logo is shown (a 68×192 multicolour bitmap
converted from `assets/branding/rip_logo.png`), faded in and out through colour-darkening
tables. It lasts about 3 s; fire skips it.

## High score table
At the end of a game, if the score makes the top 10, three initials are requested
(left/right change the letter, fire confirms). The table is saved as `JJ.HISCORES` on the
disk the game was loaded from and read back at start-up. Without a disk (for example a
.prg dropped onto VICE) it still works but is lost when the machine is switched off. On the
title screen the table is shown after ~12 s without input.

## Attract mode and credits
Without input, the title screen cycles: title (~12 s) → high score table (~8 s) →
credits (~8 s, with the animated logo) → title. Fire on any of them starts a game.

## Controls
- Keyboard: **O/Z** left, **P/X** right, **Q/SPACE** jump, **SPACE/RETURN** start.
- Joystick in **port 2 or 1**: left/right, up or fire = jump.
- **F1** on the title screen: extra effects (backgrounds, screen shake) on/off; on when
  the game starts.

## Technical notes

- **Screen**: hires bitmap in VIC bank 3 (`$E000` bitmap, `$C000` colours), 24-row mode
  with YSCROLL=7 → a centred 256×192 window. Each 8×8 cell has two colours, exactly like
  Spectrum attributes, so the look is 1:1. The 4 side columns emulate the Spectrum border
  (and hide sprites through background priority).
- **Sprites**: each object = 2 sprites (multicolour base + hires black outline).
  Raster-interrupt multiplexer: 4 pairs reused vertically (player + 8 enemies).
  Mirrored copies are precomputed (sprites at `$C400–$DFFF`).
- **Floors**: instead of rotating the 32 bytes of each floor (the Next does that at
  28 MHz), only the pixels at the edges of the gap are drawn/erased.
- **Sound**: the AY player translated to the SID. Voices 1 and 2 = channels A and B
  (pulse), voice 3 = channel C (triangle), shared with drums and effects (priority:
  effect > drum > music). Volume envelopes are approximated with ADSR. The digitised
  voice of the original title screen was dropped (it sounded harsh on the SID).
- **Jim/floor synchronisation** (change from the original): Jim is carried only on the
  frames in which the floors really advance (in the original, on levels 1–2 he moved at
  twice the speed of the gap), also on the top floor with his arms raised, and the gap is
  drawn one frame late to match the sprite.
- **Stopped robot in sync** (addition): the robot (kind 5) walks for 64 frames and stops
  for 64; while stopped it now travels with the floor instead of standing still on the
  screen while the floor slides beneath it.
- **"Transporter" effect** (addition): when an enemy falls through the floor-1 gap (in
  the original it simply reappears at the top), it sinks towards floor 0 dematerialising
  in sparkles and rematerialises near the ceiling before continuing its fall to floor 5.
  It is harmless meanwhile (as in the original). It uses sprites 122–127, and the
  multiplexer can replace the outline layer with coloured sparkles.
- **Level backgrounds** (addition, F1 on the title switches them off): one picture per
  colour scheme (`assets/backgrounds/scheme<N>_*.png`) fills rows 3-22 behind the floors.
  As on the rest of the screen each 8x8 cell has 2 colours, and under a floor line only
  one besides the floor's, so `convert_c64.py` checks the pictures against those limits.
  They are packed (about 9.5 KB for the eight) and unpacked straight into the bitmap when
  a level starts; the floors are drawn over them. Rows 0-2 (texts) and the ground stay as
  in the original. Without them (F1) the level looks exactly as in v1.0.1.
- **Packed data**: to make room, the title logo states and the sprites are packed too
  (`tools/lzpack.py`; routine `unpack`, which writes straight into place and can skip
  bytes, e.g. the side columns). The sprites are unpacked once at start-up; the logo
  every time its state changes. The two states shown most of the time stay unpacked so
  that the title runs as fast as in v1.0.1.
- **Screen shake and hops** (addition, F1 on the title switches them off): when Jim
  bumps his head the screen shakes 1 pixel for 6 frames; when he lands after a fall it
  shakes 2 pixels for 8 + 4 frames per floor fallen (up to 4 floors). Meanwhile every
  baddie hops (2 or 4 pixels) without stopping. The shake moves the whole picture up with
  YSCROLL (`$D011`, set in the top-of-frame interrupt together with the sprite buffer it
  belongs to) and the sprites with it; row 24, only seen while the screen is up, has the
  colour of the border. The hop is only drawn: positions and collisions are untouched, and
  the game logic is identical to v1.0.1 (see `docs/testing.md`).
- **Blinking text** (change from the original): "PRESS SPACE OR FIRE" blinks between
  yellow and invisible instead of the yellow inverse banner (the Spectrum FLASH attribute).
  This also fixes a stray banner: the title left its blinking row active while the high
  score table was being drawn, and sometimes a yellow bar stayed between two entries.
  Every new screen now stops the blinking row.
- **Instant start** (change from the original): the original freezes the game for 130
  frames on "GET READY!". Here play starts at once: the text stays for the same time while
  Jim blinks (invulnerable) and can already move.
- **Disk access**: the game runs with KERNAL and BASIC switched out. To read/write the
  table, the KERNAL's zero page is saved at start-up and temporarily restored
  (`kernal_enter`/`kernal_leave`) with the game's interrupts stopped.
- **Logic**: translated routine by routine from the Z80; comments carry the original
  address (`; Z80 $86a9`).

## Memory map
| Range | Use |
|---|---|
| `$0801–$B090` | program + data (music, packed logo, packed sprites, packed backgrounds, game over, RIP logo); `$B091–$BFFF` free (3.9 KB) |
| `$C000–$C3FF` | bitmap colours + sprite pointers |
| `$C400–$DFFF` | sprites (unpacked at start-up; I/O is switched off to write `$D000+`) |
| `$E000–$FF3F` | bitmap |
| `$FFFA–$FFFF` | own vectors (KERNAL and BASIC switched out) |
