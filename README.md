# Jumping Jim

Juego de plataformas estilo *Jumping Jack*: subí los 7 pisos saltando por los huecos que
se desplazan, sin chocar contra el techo ni contra los enemigos. Originalmente hecho para
**ZX Spectrum Next** (generado con IA); este repositorio lo documenta y lo porta a otras
plataformas.

| Plataforma | Estado | Carpeta |
|---|---|---|
| ZX Spectrum Next (original) | binario de referencia | `original/` |
| Commodore 64 | ✅ completo | `platforms/c64/` |

## Estructura

```
original/        binario original (.nex) — fuente de verdad
tools/extract.py extrae TODOS los datos del .nex a formato neutral
assets/          datos neutrales: jumpingjim.json (tablas, niveles, música, efectos,
                 logo, textos), fuente, voz (4 bits y WAV), PNG de referencia
docs/            game-spec.md (reglas y lógica completas), porting-guide.md
platforms/<x>/   un port por plataforma: src/, tools/convert_<x>.py, Makefile, README
promo/           capturas y video promocionales (C64)
```

## Compilar

```sh
make            # todos los ports (hoy: C64)
make assets     # regenerar assets/ desde el .nex (sólo si cambia extract.py)
make c64
```

Para empezar un port nuevo leé `docs/porting-guide.md`.
