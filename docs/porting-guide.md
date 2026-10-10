# Porting Jumping Jim to another platform

## Data flow

```
original/JumpingJim_v4.nex
        │  tools/extract.py           (run once; already done and committed)
        ▼
assets/  jumpingjim.json, font.bin, sample_4bit.bin, sample.wav, sprites/*.png, screens/*.png,
         branding/rip_logo.png
        │  platforms/<platform>/tools/convert_<platform>.py
        ▼
platforms/<platform>/build/   data in the native format + final binary
```

Rules:
1. **Never** read the `.nex` from a port: use `assets/` only. If something is missing,
   add it to `tools/extract.py` and regenerate with `make assets`.
2. The logic follows `docs/game-spec.md`. Keeping the variable names and the `$xxxx`
   references to the original routines in comments makes comparison easy.
3. Each platform lives on its own in `platforms/<name>/` with its `Makefile`,
   `README.md`, `src/` and `tools/`. `build/` is not committed.

## Steps for a new platform

1. `mkdir -p platforms/<name>/{src,tools}` and copy the C64 `Makefile` as a template.
2. Write `convert_<name>.py`, reading `assets/jumpingjim.json`:
   - **Palette**: map Spectrum attributes (ink/paper/bright) to the available colours.
   - **Sprites**: stored as RGB332 (0xE3 = transparent). Decide how to reduce colours and
     how to mirror them (the original mirrors in hardware; the C64 uses precomputed copies).
   - **Music**: convert AY periods to the target chip's units
     (`f = 1750000 / (16*period)`). The tune rows themselves are chip independent.
   - **Title logo**: draw it in real time from the segments, or precompute the 9 possible
     states (what the C64 does).
3. Implement in this order (each step can be tested on its own): screen/text → floors and
   gaps → player → enemies → collisions → HUD → title → game over → sound.
4. Add a target to the root `Makefile` and a `dist` target to the platform `Makefile`.

## Typical per-platform decisions

| Topic | Original Spectrum Next | Commodore 64 | Ideas for others |
|---|---|---|---|
| Screen | ULA 256×192 + attributes | hires bitmap (per-cell colour = attributes) | Spectrum 48/128: same as the original; MSX2/Amstrad: bitmap mode |
| Sprites | 128 hardware 16×16 sprites, 256 colours | 8 sprites: multiplexer + 2 layers (multicolour + hires outline) | masked software sprites |
| Mirroring | in hardware | precomputed copies | same |
| Sound | AY | SID (voice 3 = channel C + drums + effects) | AY directly on MSX/CPC/Spectrum 128 |
| CPU | Z80 at 28 MHz | 6510 at 1 MHz (rotating the floors was replaced by drawing only the gap edges) | |

Natural candidates: ZX Spectrum 128K (almost direct: same screen and AY chip),
Amstrad CPC and MSX (AY + Z80: the music can be reused as is), Commander X16, NES.
