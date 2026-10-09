# Jumping Jim — Commodore 64

Port completo en ensamblador 6502 (ACME). Funciona en C64 PAL real o emulado (VICE).

## Compilar

Requisitos: `python3` (Pillow opcional, sólo para vistas previas), `acme`, `c1541` (VICE).

```sh
make          # build/jumpingjim.prg y build/jumpingjim.d64
make run      # abre en x64sc
make test     # build/test.prg con entrada automática (salta y camina sola)
```
En Manjaro: `sudo pacman -S acme vice` (o desde AUR si no está en los repos).

## Cargar en la máquina
`LOAD"*",8,1` y `RUN` (o arrastrar el .d64/.prg a VICE).

## Controles
- Teclado: **O/Z** izquierda, **P/X** derecha, **Q/ESPACIO** saltar, **ESPACIO/RETURN** empezar.
- Joystick en **puerto 2 o 1**: izquierda/derecha, arriba o fuego = saltar.

## Notas técnicas

- **Pantalla**: bitmap hires en el banco VIC 3 (`$E000` bitmap, `$C000` colores), modo
  24 filas con YSCROLL=7 → ventana de 256×192 centrada. Cada celda de 8×8 tiene dos
  colores, igual que los atributos del Spectrum, así que el aspecto es 1:1. Las 4 columnas
  laterales simulan el borde del Spectrum (y ocultan sprites con prioridad de fondo).
- **Sprites**: cada objeto = 2 sprites (base multicolor + contorno negro hires).
  Multiplexor por interrupciones de raster: 4 pares reutilizados verticalmente
  (jugador + 8 enemigos). Las copias espejadas están precalculadas (106 sprites,
  `$C400–$DE80`).
- **Pisos**: en lugar de rotar los 32 bytes de cada piso (el Next lo hace a 28 MHz), se
  pintan/borran sólo los píxeles de los bordes del hueco.
- **Sonido**: reproductor AY traducido a SID. Voz 1 y 2 = canales A y B (pulso), voz 3 =
  canal C (triángulo) compartida con batería y efectos (prioridad efecto > batería > música).
  Las envolventes de volumen se aproximan con ADSR. La voz digitalizada del título se
  reproduce por `$D418` a ~8 kHz (con el truco de offset DC para que suene en el 8580).
- **Sincronía Jim/pisos** (cambio respecto del original): Jim es arrastrado sólo en los
  cuadros en que los pisos realmente avanzan (en el original, en los niveles 1–2 iba al
  doble de velocidad que el hueco), también en la cima con los brazos en alto, y el hueco
  se dibuja con un cuadro de retraso para coincidir con el sprite.
- **Lógica**: traducida rutina por rutina del Z80; los comentarios llevan la dirección
  original (`; Z80 $86a9`).

## Mapa de memoria
| Rango | Uso |
|---|---|
| `$0801–$A8xx` | programa + datos (música, voz, logo precalculado, game over) |
| `$C000–$C3FF` | colores del bitmap + punteros de sprites |
| `$C400–$DE7F` | sprites (copiados al arrancar; I/O se apaga para escribir `$D000+`) |
| `$E000–$FF3F` | bitmap |
| `$FFFA–$FFFF` | vectores propios (KERNAL y BASIC desactivados) |
