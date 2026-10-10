# Jumping Jim — Commodore 64

Port completo en ensamblador 6502 (ACME). Funciona en C64 PAL real o emulado (VICE).

## Compilar

Requisitos: `python3` (Pillow opcional, sólo para vistas previas), `acme`, `c1541` (VICE).

```sh
make          # build/jumpingjim.prg y build/jumpingjim.d64
make run      # abre en x64sc
make test     # build/test.prg con entrada automática (salta y camina sola)
make promo    # build/promo.prg: piloto automático que juega solo (para grabar videos)
```
En Manjaro: `sudo pacman -S acme vice` (o desde AUR si no está en los repos).

## Cargar en la máquina
`LOAD"*",8,1` y `RUN` (o arrastrar el .d64/.prg a VICE).

## Presentación
Al arrancar se muestra el logo de **Retro Informática Paraguay** (bitmap multicolor de
68×192, convertido desde `assets/branding/rip_logo.png`) con fade in/out mediante tablas de
oscurecimiento de color; dura unos 3 s y el fuego lo saltea.

## Tabla de récords
Al terminar una partida, si el puntaje entra entre los 10 mejores se piden 3 iniciales
(izquierda/derecha cambian la letra, fuego confirma). La tabla se graba en el disco del que
se cargó el juego como `JJ.HISCORES` y se lee al arrancar. Sin disco (por ejemplo, un .prg
arrastrado a VICE) funciona igual pero no se conserva al apagar. En el título, tras ~12 s
sin tocar nada, se muestra la tabla.

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
  Las envolventes de volumen se aproximan con ADSR.
- **Sincronía Jim/pisos** (cambio respecto del original): Jim es arrastrado sólo en los
  cuadros en que los pisos realmente avanzan (en el original, en los niveles 1–2 iba al
  doble de velocidad que el hueco), también en la cima con los brazos en alto, y el hueco
  se dibuja con un cuadro de retraso para coincidir con el sprite.
- **Robot detenido sincronizado** (agregado): el robot (tipo 5) camina 64 cuadros y se
  detiene 64; mientras está detenido ahora viaja con el piso en vez de quedar fijo en la
  pantalla mientras el piso se le desliza debajo.
- **Efecto "transportador" (agregado): cuando un enemigo cae por el hueco del piso 1
  (en el original reaparece de golpe arriba), se hunde hacia el piso 0 desmaterializándose
  entre destellos y se rematerializa cerca del techo antes de seguir su caída al piso 5.
  Mientras dura no hace daño (igual que en el original). Usa los sprites 122–127 y el
  multiplexor permite cambiar la capa de contorno por destellos de colores.
- **Lógica**: traducida rutina por rutina del Z80; los comentarios llevan la dirección
  original (`; Z80 $86a9`).

## Mapa de memoria
| Rango | Uso |
|---|---|
| `$0801–$B9FF` | programa + datos (música, logo precalculado, game over, logo RIP) |
| `$C000–$C3FF` | colores del bitmap + punteros de sprites |
| `$C400–$DE7F` | sprites (copiados al arrancar; I/O se apaga para escribir `$D000+`) |
| `$E000–$FF3F` | bitmap |
| `$FFFA–$FFFF` | vectores propios (KERNAL y BASIC desactivados) |
