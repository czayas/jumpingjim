# Guía para portar Jumping Jim a otra plataforma

## Flujo de datos

```
original/JumpingJim_v4.nex
        │  tools/extract.py           (una sola vez; ya está hecho y versionado)
        ▼
assets/  jumpingjim.json, font.bin, sample_4bit.bin, sample.wav, sprites/*.png, screens/*.png
        │  platforms/<plataforma>/tools/convert_<plataforma>.py
        ▼
platforms/<plataforma>/build/   datos en el formato nativo + binario final
```

Reglas:
1. **Nunca** leer el `.nex` desde un port: usar sólo `assets/`. Si falta un dato,
   agregarlo a `tools/extract.py` y regenerar con `make assets`.
2. La lógica sigue `docs/game-spec.md`. Mantener los nombres de variables y las
   referencias `$xxxx` a las rutinas originales en los comentarios facilita comparar.
3. Cada plataforma vive aislada en `platforms/<nombre>/` con su `Makefile`,
   `README.md`, `src/` y `tools/`. `build/` no se versiona.

## Pasos para una plataforma nueva

1. `mkdir -p platforms/<nombre>/{src,tools}` y copiar como plantilla el `Makefile` de C64.
2. Escribir `convert_<nombre>.py` leyendo `assets/jumpingjim.json`:
   - **Paleta**: mapear atributos Spectrum (ink/paper/bright) a los colores disponibles.
   - **Sprites**: vienen en RGB332 (0xE3 = transparente). Decidir cómo reducir colores y
     cómo espejar (el original espeja por hardware; en C64 se precalculan copias).
   - **Música**: convertir períodos AY a la unidad del chip destino
     (`f = 1750000 / (16*período)`). Las filas de las melodías son independientes del chip.
   - **Logo del título**: se puede dibujar en tiempo real con los segmentos o precalcular
     los 9 estados posibles (lo que hace C64).
3. Implementar en este orden (cada paso se puede probar solo): pantalla/texto → pisos y
   huecos → jugador → enemigos → colisiones → HUD → título → game over → sonido.
4. Agregar un objetivo en el `Makefile` raíz.

## Decisiones típicas por plataforma

| Tema | Spectrum Next original | Commodore 64 | Ideas para otras |
|---|---|---|---|
| Pantalla | ULA 256×192 + atributos | bitmap hires (color por celda = atributos) | Spectrum 48/128: igual que el original; MSX2/Amstrad: modo bitmap |
| Sprites | 128 sprites HW de 16×16, 256 colores | 8 sprites: multiplexor + 2 capas (multicolor + contorno hires) | software sprites con máscara |
| Espejado | por hardware | copias precalculadas | idem |
| Sonido | AY | SID (voz 3 = canal C + batería + efectos) | AY directo en MSX/CPC/Spectrum 128 |
| CPU | Z80 a 28 MHz | 6510 a 1 MHz (rotar los pisos se reemplazó por pintar sólo los bordes del hueco) | |

Candidatas naturales: ZX Spectrum 128K (casi directo: misma pantalla y chip AY),
Amstrad CPC y MSX (AY + Z80: reutiliza la música tal cual), Commander X16, NES.
