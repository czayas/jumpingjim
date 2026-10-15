# Especificación de la intro de RIP

Lo que tiene que hacer la intro en cualquier máquina, para que se vea igual. La versión
de referencia es la del Commodore 64 (`c64/rip_intro.a`), que reproduce la intro de
*Jumping Jim* v1.1.0.

## Imagen

- El logo (`assets/rip_logo.png`, 209x296) se escala a **136x192 píxeles** (en el C64,
  68x192 en multicolor: 17x24 celdas de 4x8) y se centra en una pantalla de 256x192 sobre
  fondo negro (en el C64, columnas 11 a 27 de 40; la ventana de 24 filas).
- El fondo, el borde y todo lo que no es el logo son negros durante toda la intro.

## Fundido

- **5 niveles**: 0 = colores originales, 4 = todo negro. Cada nivel se obtiene aplicando
  la escalera "un color más oscuro" las veces que indica el nivel. En la paleta del C64:

  | Color | 0 negro | 1 blanco | 2 rojo | 3 cian | 4 violeta | 5 verde | 6 azul | 7 amarillo |
  |---|---|---|---|---|---|---|---|---|
  | pasa a | 0 | 15 | 9 | 14 | 6 | 11 | 0 | 15 |

  | Color | 8 naranja | 9 marrón | 10 rosa | 11 gris oscuro | 12 gris | 13 verde claro | 14 azul claro | 15 gris claro |
  |---|---|---|---|---|---|---|---|---|
  | pasa a | 2 | 0 | 8 | 0 | 11 | 5 | 4 | 12 |

  En otras máquinas: una escalera equivalente con su paleta, en 4 pasos hasta el negro.
- **Entrada**: niveles 4, 3, 2, 1, 0. **Salida**: 1, 2, 3, 4.
- **Cada paso dura 5 tics** (1/10 s) desde que empieza a escribirse.
- **Barrido**: cada nivel se escribe fila por fila de arriba abajo, más despacio que el
  haz de la pantalla (en el C64 tarda casi dos cuadros), así que el cambio "baja" por la
  imagen. Es parte del efecto: una versión que cambie todo de golpe se ve más brusca.
- **A pleno**: 110 tics (2,2 s). En total, unos 2,9 s.

## Tiempo

- **Tic** = 1/50 s. En máquinas de 60 Hz se saltea 1 de cada 6 cuadros.
- En el C64 cada tic empieza en la línea 18 del haz más 35 ciclos (línea 20, ciclo 58:
  donde empezaba Jumping Jim), por encima de la imagen.

## Controles

- **Disparo** (cualquier joystick), **ESPACIO** o **RETURN** durante la espera a pleno:
  pasa enseguida al fundido de salida. Durante el fundido de entrada no se saltea.
- Al final se espera a que se suelte, para que el juego no lo tome como "empezar".

## Formato de las láminas (C64)

`tools/convertir.py` escribe: 5 bytes de cabecera (modo 0 hires / 1 multicolor,
columna, fila, ancho, alto en celdas), el bitmap (8 bytes por celda, fila por fila),
los colores de pantalla (1 byte por celda) y, en multicolor, la RAM de color (1 byte por
celda). El fondo ($d021) es negro.
