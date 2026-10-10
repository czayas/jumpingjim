# Jumping Jim — Commodore 64

Complete port in 6502 assembly (ACME). Runs on a real PAL C64 or in an emulator (VICE).

## Building

Requirements: `python3` (Pillow), `acme`, `c1541` (VICE).

```sh
make          # build/jumpingjim.prg and build/jumpingjim.d64
make run      # opens it in x64sc
make test     # build/test.prg with scripted input (jumps and walks by itself)
make promo    # build/promo.prg: autopilot that plays on its own (for recording videos)
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

## Controls
- Keyboard: **O/Z** left, **P/X** right, **Q/SPACE** jump, **SPACE/RETURN** start.
- Joystick in **port 2 or 1**: left/right, up or fire = jump.

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
- **Disk access**: the game runs with KERNAL and BASIC switched out. To read/write the
  table, the KERNAL's zero page is saved at start-up and temporarily restored
  (`kernal_enter`/`kernal_leave`) with the game's interrupts stopped.
- **Logic**: translated routine by routine from the Z80; comments carry the original
  address (`; Z80 $86a9`).

## Memory map
| Range | Use |
|---|---|
| `$0801–$B9FF` | program + data (music, precomputed logo, game over, RIP logo) |
| `$C000–$C3FF` | bitmap colours + sprite pointers |
| `$C400–$DFFF` | sprites (copied at start-up; I/O is switched off to write `$D000+`) |
| `$E000–$FF3F` | bitmap |
| `$FFFA–$FFFF` | own vectors (KERNAL and BASIC switched out) |
