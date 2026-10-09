# Jumping Jim — especificación del juego (independiente de plataforma)

Este documento describe **qué hace** el juego, reconstruido por ingeniería inversa del
código Z80 original (`original/JumpingJim_v4.nex`). Es la referencia para cualquier port.
Las direcciones `$xxxx` remiten a la rutina/tabla del binario original. Todos los datos
numéricos están en `assets/jumpingjim.json` (generado por `tools/extract.py`).

## 1. Unidades y convenciones

- Pantalla lógica: **256×192 píxeles** (32×24 celdas de 8×8), como el ZX Spectrum.
- Coordenadas: `x` 0–255 (byte, **da la vuelta** de 255 a 0 para el jugador), `y` 0–191.
  La `y` de un objeto es la línea **sobre la que apoyan los pies** (el sprite de 16×16 se
  dibuja con su borde superior en `y-16`).
- Tiempo: todo avanza **1 vez por cuadro a 50 Hz**. Contadores en cuadros.
- Aritmética de 8 bits sin signo con desborde, salvo donde se indique "con signo".
- Colores: atributos del Spectrum `FLASH<<7 | BRIGHT<<6 | PAPER<<3 | INK`. Cada port los
  traduce a su paleta (ver `platforms/c64/tools/convert_c64.py` como ejemplo).

## 2. Estructura del nivel

- 7 pisos, índice 0 (suelo) a 6 (meta). `tables.floor_y = [184,160,136,112,88,64,40]`
  (fila de caracteres = y/8: 23,20,17,14,11,8,5).
- Cada piso es una franja de **3 líneas de píxeles** (líneas 0–2 de su fila de caracteres;
  las líneas 3–7 vacías). El piso 0 es macizo (8 líneas, sin hueco).
- Los pisos 1–6 tienen **un hueco** cada uno: `gap_start[c]` (0–255) y `gap_len[c]` px.
  El hueco se mueve `gap_speed[c]` px por actualización (con signo, ±1/±2) y da la vuelta.
  Píxel `x` está en el hueco si `(x - gap_start) mod 256 < gap_len`.
- **Prueba de hueco** (`$84DC`): un objeto en `x` con ancho `w` cae por el hueco si
  `(x + off - gap_start) mod 256 < (gap_len - w) mod 256`.
  Valores usados: caída del jugador `off=4,w=7`; cabeza al saltar `off=2,w=11`;
  enemigos `off=4,w=7`.

### Preparación de nivel (`$8BA7`)
1. `pal = (level-1) & 7` → `levels.palettes[pal]`: borde, 8 bandas de color de fondo (cada
   una 3 filas), color de cada piso, nombre ("NIGHT SKY"…) centrado en la fila 2
   (columna `name_col`).
2. `base = 0x2C - 2*min(level-1, 8)`.
3. Velocidades: `set = gap_speed_set_for_level[min(level-1,15)]`,
   `gap_speed[1..6] = gap_speed_sets[set]`.
4. Para c=1..6: `gap_start[c] = random()`, `gap_len[c] = gap_len_add[(level+c) mod 6] + base`.
5. Generar enemigos, colocar jugador, dibujar HUD, "GET READY!" (fila 1, col 11), música
   `level_music[(level-1) mod 12]`, esperar **130 cuadros**, borrar filas 1–2.

### Movimiento de huecos (`$85CC`)
Cada cuadro (si `level < 3`, sólo en cuadros pares del contador global) para c=1..6:
`gap_start[c] += gap_speed[c]`.

## 3. Jugador (`$86A9`)

Variables: `x, y, vy (con signo), state, floor, fall_count, timer, dir (0=der,1=izq),
anim, invuln, jump_frame, moving`.

Reaparición (`$8640`): `x=120, y=184, floor=0, state=0, invuln=90`.

Cada cuadro: si `invuln>0`, `invuln--`. Luego según `state`:

| state | significado | comportamiento |
|---|---|---|
| 0 | parado/caminando | *arrastre*: si floor≠0, `x += gap_speed[floor]` (el original lo hace en todos los cuadros aunque en niveles 1–2 los pisos se muevan en cuadros alternos; recomendado: sólo cuando los pisos avanzan). Izq/der: `x ∓= 3`, `moving=1`, `anim++`. Si floor≠0 y está sobre el hueco (off 4, w 7) → **cae**: state=1, vy=1, fall_count=1, borde arcoíris 30 cuadros, sfx *fall*. Si no cae y se pulsa salto → state=1, vy=−5, fall_count=0, sfx *jump*. |
| 1 | en el aire | izq/der `x ∓= 3`. `ny = y + vy`. Si vy<0: **cabeza** — para c=1..6 con `d = floor_y[c]+19`, si `y ≥ d > ny` y NO está bajo el hueco (off 2, w 11) → `ny = d, vy = 0`. Si vy≥0: **aterrizaje** — para c=0..6 con `d=floor_y[c]`, si `y < d ≤ ny`: si c≠0 y está sobre el hueco → atraviesa (`fall_count++`; la 1ª vez arcoíris + sfx *fall*); si no → **aterriza**. Si sigue en el aire: `y=ny`; en cuadros impares de `jump_frame` `vy++` (máx 6). |
| 2 | aturdido | arrastre + prueba de caída; `timer--`, a 0 → state 0. |
| 3 | muriendo | si `y<200`: `y += vy`, `vy++` (máx 7). `timer--`; a 0: `lives--`; sin vidas → fin de partida; si no, reaparece. |
| 4 | nivel completado | `timer--`; a 0 → siguiente nivel. *(Original: sin arrastre. Recomendado para ports: aplicar el arrastre también aquí.)* |

**Aterrizar en el piso c** (`$8825`): `y=floor_y[c]`, state 0, vy 0. Si `c > floor` anterior:
+10 puntos, sfx *climb*. Si c=6: state 4, timer 150, +`level`×100 puntos (BCD), texto
"LEVEL COMPLETE!" (fila 1, col 8), música 3. Si no y `fall_count>0`: aturdido,
`timer = 40 + 12*fall_count` (8 bits), sfx *stunned*.

Fotograma del sprite (`$8417`): aire→5, aturdido→6+((timer>>3)&1), muriendo→8,
nivel completo→9, caminando→(anim>>2)&3, quieto→4. Espejado si dir=1. Invisible si
`invuln & 4` (parpadeo).

## 4. Enemigos (`$88DA`, `$8975`)

Hasta 8. Registro: `state (0 libre,1 camina,2 cae), floor, x, y, speed (con signo),
kind|variant<<3, anim, yoff`.

**Generación**: `n = min(level+1, 8)`. Enemigo i (0..n−1): floor = `i mod 5 + 1`,
`y = floor_y[floor]`, `x = random() mod 240`, `kind = i`, `speed = enemy_speed[i]`,
`variant = (level+i) mod 3`, dirección aleatoria.

**Cada cuadro** (estado 1; si `level<3` sólo en cuadros pares, pero `anim++` siempre):
- kind 3: `yoff = bob[anim&31]`; kind 4: `yoff = 2*bob[anim&31]`;
- kind 6: `yoff = 10 + 2*((anim>>3)&1)`;
- kind 2 y 7: **persiguen** — si están en el piso del jugador y éste no muere,
  `speed = ±enemy_speed[kind]` hacia él;
- kind 5: si `anim & 0x40` no se mueve ese cuadro;
- movimiento: `x += speed`, rebota en 0 y 240 (invierte velocidad).
- Si su piso ≠ 0 y está sobre el hueco → state 2 y `floor--`; si llega a 0 reaparece
  arriba: `y = 8, floor = 5`.
- Estado 2: `y += 3` hasta `floor_y[floor]` → state 1.

Fotograma: `variant*16 + kind*2 + ((anim>>3)&1)`, espejado si speed<0. Se dibuja con
la caja de 16×16 en `(x, y - yoff - 16)` (el arte 12×11 ocupa x+2..x+13, y+5..y+15).

**Colisión** (`$8AA7`): si invuln=0 y state<3, para cada enemigo en estado 1:
`|y_j - (y_e - yoff)| < 8` y `|x_j - x_e| < 9` → state 3, timer 70, vy −6, sfx *death*.

## 5. Flujo del juego

```
título → nueva partida (vidas 3, nivel 1, puntos 0)
  └─ bucle: preparar nivel → jugar
        nivel completado → level++, (cada 4 niveles +1 vida, máx 5)
        sin vidas → pantalla de GAME OVER → título
```
Bucle de juego (`$8CEA`): esperar cuadro → leer controles → mover huecos → jugador →
enemigos → colisiones → sprites → HUD si cambió.

**HUD** (fila 0): `SCORE 000000   LEVEL 01  ♥♥♥    ` — colores: col 0–11 amarillo,
12–24 cian, 25–31 rojo (corazones = carácter `#` de la fuente).

**Controles**: derecha P/X, izquierda O/Z, salto Q/ESPACIO, empezar ESPACIO/ENTER/fuego;
joystick: arriba o fuego = salto (fuego también empieza).

## 6. Pantallas

- **Título** (`$8D1C`): logo "JUMPING JIM" de 256×48 (filas 1–6) dibujado con los 37
  segmentos de `title_logo` (trazo de 2 px). Animación con `t = 0..239` (cíclico):
  `lv = title_logo_level[t]`; si lv<7 cada segmento se desplaza `(dx>>lv, dy>>lv)`
  (llegan volando); si lv=7 tiemblan 1 px: `dx = ((t>>2) + índice) & 1`. Colores
  arcoíris por columna desplazándose cada 4 cuadros (filas 1–7). En `t=42` suena la voz
  digitalizada y luego la música 2. Jim y un enemigo caminan por el suelo.
- **Game Over** (`$8EF7`): "GAME OVER" (16 px, rojo), cara llorando 144×144 en (col 7,
  fila 2), dos lágrimas animadas (sprite *drop*), puntuación final y récord; música 4;
  a los 150 cuadros "PRESS SPACE OR FIRE" parpadeando.
- **Borde arcoíris**: mientras `flash > 0` (30 cuadros al caer por un hueco), franjas de
  colores `border_rainbow` que se desplazan.

## 7. Sonido

- Chip original: AY-3-8912 a 1,75 MHz. Frecuencia = 1 750 000 / (16 × período).
- **Música** (`$80EA`): 15 melodías; filas de 4 bytes `A, B, C, batería`. Nota 0 = silencio,
  0xFF = mantener, n = `note_periods[n]`. Cada `speed` cuadros se lee una fila. Volumen al
  atacar `[13,13,10]`, baja 1 por cuadro hasta `[8,10,5]`. Batería: ruido en el canal C
  durante `drums[d].frames` cuadros.
- **Efectos**: `period` inicial, `delta` por cuadro, `frames`; tono o ruido en canal C.
- **Voz**: `sample_4bit.bin` (5214 muestras de 4 bits, ~8 kHz); cada nibble se reproduce
  como volúmenes AY de la tabla `ay_volume_table`. `sample.wav` es la versión lineal.

## 8. Números aleatorios

xorshift de 16 bits (semilla `0x2B7D`; en el título se incrementa cada cuadro para
variar la semilla). Sólo afecta posiciones iniciales de huecos y enemigos.

## 9. Diferencias con la descripción publicada en itch.io

La página de itch.io (roman126) describe los cambios de la **versión 2**; el binario
analizado es la **v4**. Esta especificación sigue al código de la v4. Diferencias:

| Descripción (v2) | Código v4 |
|---|---|
| La araña cambia de dirección al azar | Ningún enemigo cambia de dirección al azar; sólo rebotan en los bordes o persiguen (tipos 2 y 7) |
| Nivel 1: dos "blobs" verdes lentos | Nivel 1: enemigos de tipo 0 y 1 (distintos), variante de color `(nivel+i) mod 3` |
| Los niveles alternan entre tres melodías | 12 melodías de juego distintas (`level_music`), más título, nivel completado y game over |
| El borde parpadea al caer **y mientras está sentado** | El borde parpadea 30 cuadros al empezar a caer (no durante el aturdimiento) |

Coinciden: 8 tipos de enemigos, uno nuevo por nivel; robot que se detiene y arranca (tipo 5);
saltarines (tipos 3 y 4, este último salta el doble); niveles 1–2 a media velocidad; huecos
distintos por piso que se achican con el nivel; aturdimiento más largo según la altura de
la caída; silbido al caer y golpe al aterrizar; logo de palitos que se arma, tiembla y se
desarma con colores cíclicos.
