# Auditoría independiente de la prueba final y de sus afirmaciones

Fecha: 17-nov-2026. Auditor: Claude (sesión de Claude Code), a pedido del autor. Alcance: las
cuatro tareas del encargo (reimplementación, mutación, afirmaciones, fugas). **No se cambió nada
en `src/`, `runs/`, `data/` ni `reports/`; no se hizo commit.** Este archivo es lo único nuevo
dentro del repositorio.

Los rangos del proyecto describen incertidumbre estadística; esta auditoría no es asesoría financiera.

## Cómo reproducir

Los scripts de la auditoría están **fuera del repositorio**, en `C:\Users\johan\AppData\Local\Temp\auditoria\`
(una carpeta temporal: si se borra, este documento conserva los comandos y los resultados).

| script | qué hace | comando (desde esa carpeta) |
|---|---|---|
| `t1_reimplementacion.py` | Tarea 1. Solo numpy, pandas y scipy; **no importa nada de `src/`** | `python -I t1_reimplementacion.py <raíz del repo>` |
| `t2_mutaciones.py` | Tarea 2. Cada mutación en su propia copia; corre `pytest -q -x` | `python -I t2_mutaciones.py copia mut` |
| `t2_impacto.py` | Tarea 2. Qué habrían dado las confirmatorias con M07 y M11 (sin `src/`) | `python -I t2_impacto.py <raíz del repo>` |
| `t3_cifras_caso.py` | Tarea 3. Cifras con `#hash` del caso contra `resultado.json` y el respaldo | `python -I t3_cifras_caso.py <raíz> 6506dbba3261` |
| `t4_rezagos.py` | Tarea 4. Covariables externas recalculadas sin `src/` y comparadas con `src/` | `PYTHONIOENCODING=utf-8 python t4_rezagos.py <raíz>` |

`copia` es una copia completa del repositorio (con `data/processed` y los `.csv.gz`), hecha con
`cp -r` en el estado del commit `f8fbe16` sin cambios locales. La suite sin mutar pasa entera
en esa copia: **356 passed in 836 s**.

## Resumen

| tarea | resultado |
|---|---|
| 1. Reimplementación | **1.988 comparaciones, 0 diferencias** mayores que el redondeo publicado. Las cuatro confirmatorias, Holm, la sensibilidad de h = 1, coberturas con Clopper-Pearson y n/h, Kupiec, Christoffersen, Basilea, Z2, PIT (h = 1) y acierto direccional coinciden. |
| 2. Mutación | **12 mutaciones, 9 detectadas, 3 no detectadas**: quitar el rezago de publicación de las externas (M02), quitar el término h − 1 de los rezagos HAC (M07) y cambiar la línea base confirmatoria de h = 63 (M11). Ninguna de las tres estuvo activa en la corrida publicada (H1). |
| 3. Afirmaciones | Todas las cifras de `prueba_final.md` y las 222 cifras con `#hash` del caso tienen archivo y hash que las respaldan; la corrida del caso **se reproduce bit a bit**. Cuatro afirmaciones del README o de los reportes no tienen respaldo o lo contradicen (H2–H5). |
| 4. Fugas | **Ninguna fuga demostrada.** Las 6 covariables externas, recalculadas sin `src/` con solo datos de fecha ≤ origen − rezago, coinciden exactamente con las del código en los 1.564 orígenes. Quedan dudas sobre el calendario real de publicación (D1–D2). |

Ningún hallazgo cambia una cifra publicada ni un veredicto de la prueba final.

## Hallazgos, de más a menos grave

Gravedad: **alta** = podría cambiar un resultado; **media** = una garantía o una conclusión
publicada no está respaldada; **baja** = error de documentación o de trazabilidad.
Ninguno es «alto»: con la evidencia reunida, ningún resultado publicado está mal calculado.

### H1 (media). Tres errores realistas pasan la suite completa (356 de 356)

La garantía del README («356 pruebas automáticas, incluidas pruebas de fuga») no cubre:

1. **M02, sin rezago de publicación** (`caracteristicas.py:19`, todos los rezagos a 0). Es la única
   fuga de las probadas que nadie detecta. El canario (`test_sin_fuga.py:67-72`) solo corrompe
   datos con índice > t; nunca los externos con fecha en (f_t − rezago, f_t], que son justo los
   que el rezago debe excluir. Ninguna prueba fija `REZAGO_DIAS` ni comprueba que `construir`
   ignore el último dato externo. Con rezago 0, `lightgbm_cuantiles` y `reg_cuantiles` (el
   campeón de h = 1) usarían externos del mismo día del origen sin que falle nada.
2. **M07, HAC sin h − 1** (`pruebas.py:69`). Las pruebas de Diebold-Mariano pasan `rezagos`
   explícitos (0 o 1) y nunca usan el valor por defecto, que es el que usa la prueba final.
   Con la mutación, los p de Holm bajan de 0,493 a 0,315, 0,294 y 0,317 (h = 5, 21, 63). Esta vez
   no cambiaría ningún veredicto, pero el error infla la significancia justo donde hay traslape.
3. **M11, línea base de h = 63 cambiada** (`final.py:58`, `caminata_aleatoria` → `sim_hist_pond`).
   `test_prueba_final.py:590` solo exige que la base sea alguna línea base. Con la mutación, h = 63
   pasaría a CRPS/base 0,914 y p = 0,066 (Holm 0,198): sigue «no confirmado», pero la
   cifra publicada sería otra. Lo protege el candado por hash (`hash_codigo`) de cualquier corrida
   nueva; no lo protege ninguna prueba que lea la tabla de la sección 5 del prerregistro.

Las tres están **ausentes** del código que produjo los resultados: T1 reproduce los rezagos
publicados (7, 11, 27, 69) y la base `caminata_aleatoria`, y T4 confirma los rezagos de
publicación con los datos reales. Evidencia: `python -I t2_mutaciones.py copia mut
M02_sin_rezago_publicacion M07_hac_sin_h_menos_1 M11_base_confirmatoria_h63_cambiada` → `356 passed`
en cada una; impacto: `python -I t2_impacto.py <raíz>`.

### H2 (media). El README cita la cobertura de desarrollo del motor y omite que la prueba final la contradice

`README.md:26-27`: «A horizontes largos … los rangos del motor probablemente son estrechos
(cobertura nominal 95 %, observada 0,90 y 0,88 en desarrollo)». Las cifras son correctas
(`runs/backtest_largo/bootstrap_est_filtrado.csv.gz`: 0,904 y 0,880 a 126 y 252 días, n = 3.304),
pero la prueba final, que el README presenta como la evaluación que cuenta, midió lo contrario:
0,992 a 126 días y 0,932 a 252 (`data/respaldo/prueba_final.json`, campo
`cobertura.bootstrap_est_filtrado`, y `reports/prueba_final.md`, tabla «Motor del caso»), y
0,961, 0,968 y 0,960 a 5, 21 y 63 días. Con 11 y 5 ventanas independientes ninguna de las dos
mediciones prueba nada, pero la conclusión «probablemente estrechos» sale de la muestra de
desarrollo y se publica sin mencionar la medición posterior que no la apoya.

Evidencia: `python -I t1_reimplementacion.py <raíz>` imprime `motor h=126: cob 0.9920 …` y
`motor h=252: cob 0.9316 …`; para desarrollo:
`python -c "import pandas as pd,numpy as np; d=pd.read_csv('runs/backtest_largo/bootstrap_est_filtrado.csv.gz'); [print(h, np.mean((d[d.h==h].y>=d[d.h==h]['q_0.025'])&(d[d.h==h].y<=d[d.h==h]['q_0.975']))) for h in (126,252)]"`.

### H3 (baja). El comando de verificación que publican el README y el reporte falla en el estado actual del repositorio

`README.md:59` («`final --verificar` # comprueba hashes y etiquetas») y la sección «Reproducir» de
`reports/prueba_final.md` lo dan como la forma de comprobar la prueba. En `HEAD` (`f8fbe16`) falla:

```
PYTHONPATH=src python -m laboratorio.backtest final --verificar
RuntimeError: los hashes no coinciden con el prerregistro; NO se corre nada:
  hash_codigo: prerregistro 3eb37538… ≠ actual cfb1ad53…
```

Causa: `hash_codigo` cubre todo `src/**/*.py`, y después de la prueba cambiaron
`src/laboratorio/motor/` (caso, F5 y F6: `git diff --stat prerregistro-adenda-1 HEAD -- src`).
Es el candado funcionando como se diseñó, no una alteración de resultados: en un clon con
`git checkout prerregistro-adenda-1` y `data/processed` copiado, `--verificar` pasa y muestra los
cinco hashes del prerregistro. Lo que falta es decirlo: el comando solo vale en el commit etiquetado.

### H4 (baja). El reporte final atribuye los horizontes 126 y 252 a la carpeta de desarrollo

`reports/prueba_final.md`, sección «Horizontes largos»: «Corrida aparte (runs/backtest_largo/)».
Los números de esa tabla salen de `runs/prueba_final_largo/` (la reimplementación los recalcula
desde ahí y coinciden todos; `runs/backtest_largo/` da otros, p. ej. n = 3.304 en vez
de 1.375). El texto está fijo en `src/laboratorio/reportes/pruebas_f2.py:204`, escrito para el
reporte de desarrollo y reutilizado. Un lector puede creer que 126/252 vienen del desarrollo.

### H5 (baja). La ficha del caso apunta a un commit que no contiene su código

`runs/6506dbba3261/ficha.json`: `"commit": "037f784…"`, `"hash_codigo": "6aed58e0…"`. El
código de `037f784` tiene otro hash; `6aed58e0…` es el de `d4c6f25` (el commit siguiente, que
añadió F5b/F6 y la propia corrida). La corrida se hizo con cambios sin commit. El hash de código
sí identifica el código correcto, y la ficha declara el commit como «informativo», así que no
se pierde la trazabilidad; pero quien siga el campo `commit` llega a otro código.

Evidencia (en un clon, sin tocar el repo):
`for c in 037f784 d4c6f25; do git checkout -q $c; PYTHONPATH=src python -c "from laboratorio.motor.ficha import hash_codigo; print('$c', hash_codigo('src/laboratorio'))"; done`
→ `037f784 eb779fe2…`, `d4c6f25 6aed58e0…`.

### H6 (baja, metodológica). El intervalo de cobertura redondea los aciertos y a 252 días los cuenta como 5 de 5

`src/laboratorio/evaluacion/cobertura.py:40-43`: k = round(cobertura · n_ef). A 252 días el motor
cubrió 0,932 (4,66 de 5 ventanas), pero el intervalo publicado (0,48 – 1,00) es el de 5/5; con
k = 4 sería 0,28 – 0,99. A 126 días pasa lo mismo (0,992 → 11/11). El prerregistro dice
«intervalo binomial exacto y n efectivo = n/h» sin fijar el redondeo; el código lo documenta.
No cambia ningún «compatible» (0,95 cae en los dos intervalos), pero el intervalo publicado
parece más favorable de lo que la cobertura observada permite. Evidencia: `t1` reproduce el
intervalo publicado con el mismo redondeo; `scipy.stats.beta.ppf([0.025, 0.975], [4, 5], [2, 1])`
da el de k = 4.

## Tarea 1 — Reimplementación independiente

`t1_reimplementacion.py` lee los `.csv.gz` de `runs/prueba_final/` y `runs/prueba_final_largo/`,
las tablas de cola y `data/processed/trm.csv`, y calcula todo desde las definiciones:

- **Objetivo**: y = ln TRM(origen + h) − ln TRM(origen) desde `trm.csv`; coincide en los 17 + 15
  modelos (error máximo < 1e-9) y las fechas de origen están alineadas. Todos los modelos tienen
  los mismos (origen, h). Embargo: último origen corto = índice 8.323 = n − 1 − 63; largo =
  8.134 = n − 1 − 252; primer origen 2020-01-03.
- **Pinball** por nivel y **CRPS** = 2 ∫ pinball dτ por trapecios sobre los 11 niveles.
- **Diebold-Mariano** con HAC de Bartlett, h − 1 + ⌊4(n/100)^(2/9)⌋ rezagos (7, 11, 27 y 69),
  corrección HLN y t con n − 1 g.l.; **Holm** escrito como bucle propio.
- **Cobertura** con n_ef = round(n/h) e intervalo de **Clopper-Pearson** (`scipy.stats.beta`).
- **Kupiec**, **Christoffersen** (independencia y condicional), **Basilea** (ventanas de 250),
  **Z2** de Acerbi-Székely, **PIT** a h = 1 (12 casillas, χ² con 11 g.l.) y acierto direccional
  binomial.

Recalculado (coincide con `reports/prueba_final.md` y con `data/respaldo/prueba_final.json`):

| h | campeón vs. base | CRPS ×100 | CRPS/base | t (HLN) | p | p Holm | rezagos | veredicto |
|---|---|---|---|---|---|---|---|---|
| 1 | lightgbm_cuantiles vs. sim_hist_pond | 0,4436 / 0,4538 | 0,9774 | −3,546 | 0,00020 | 0,00081 | 7 | éxito |
| 5 | ewma_0.94 vs. sim_hist_pond | 1,1123 / 1,1190 | 0,9940 | −0,977 | 0,164 | 0,493 | 11 | no confirmado |
| 21 | ewma_0.94 vs. sim_hist_pond | 2,3083 / 2,3494 | 0,9825 | −0,960 | 0,169 | 0,493 | 27 | no confirmado |
| 63 | ewma_0.94 vs. caminata_aleatoria | 3,7695 / 3,7866 | 0,9955 | −0,251 | 0,401 | 0,493 | 69 | no confirmado |

Comparaciones: 1.988 (confirmatorias, sensibilidad, motor, 17 modelos × 4 horizontes × CRPS y
3 coberturas, episodios, 68 filas de VaR, Basilea, Z2, PIT, dirección, 60 filas de horizontes
largos y el respaldo). **Diferencias mayores que el redondeo: 0.**

Comprobaciones adicionales (no publicadas; solo robustez):
- Si el CRPS se aproxima con pesos iguales (2 × media simple de las 11 pérdidas) en vez de
  trapecios, el veredicto no cambia: p de Holm = 0,006 a h = 1 y > 0,2 en los demás.
- Pinball medio ×100 a h = 1: `lightgbm_cuantiles` 0,1334 frente a `sim_hist_pond` 0,1382.
- Con n completo en vez de n/h, el intervalo del motor a 63 días sería 0,949 – 0,969 en vez de
  0,80 – 1,00: el n efectivo está bien aplicado y es lo que hace «compatibles» casi todas las coberturas largas.

No verificado de forma independiente: el MCS (bootstrap de 5.000 réplicas), Pesaran-Timmermann y
el PIT a h > 1 (con fusión de casillas). Se dan por respaldados solo por el código y los CSV.

Integridad de archivos: los 82 SHA-256 de `runs/prueba_final/HECHO.json` coinciden con los
archivos actuales; el SHA-256 de `HECHO.json` (`6ef88d12…`) es el que guarda el respaldo. Las
tablas de la adenda 1 también se cumplen: los 32 archivos de `runs/prueba_final_abortada_1/`
tienen el hash publicado, el CSV descomprimido de cada modelo abortado es idéntico al de la
corrida nueva, y los 18 CSV de «desarrollo idéntico» coinciden con los archivados.

## Tarea 2 — Mutación

Cada mutación se aplicó en una copia nueva de `copia` (que no se modifica). Se corrió
`python -m pytest -q -x -p no:cacheprovider` y luego se borró la copia. «Detectada» = al menos
una prueba falla. Registro completo en `mut/resumen.tsv` y `mut/<id>.log`.

| id | error simulado | archivo | resultado | prueba que la detecta |
|---|---|---|---|---|
| M01 | embargo corto: último origen = corte − h_max (un día de más) | `evaluacion/origen_movil.py:34` | detectada | `test_backtest_infra::test_corredor_ningun_ajuste_ni_pronostico_ve_el_futuro…` |
| M02 | sin rezago de publicación de las externas | `modelos/caracteristicas.py:19` | **NO detectada** (356 passed) | — |
| M03 | fuga de un día: `Vista.hasta(t)` entrega t + 1 | `backtest/datos.py:38` | detectada | `test_backtest_infra::test_vista_hasta_recorta_todo…` |
| M04 | ventana mal alineada: y del origen + 1 | `backtest/corredor.py:85` | detectada | `test_backtest_infra::test_corredor_ningun_ajuste…` |
| M05 | Holm sin máximo acumulado (no monótono) | `evaluacion/pruebas.py:119` | detectada | `test_veredicto_f3::test_holm_a_mano` |
| M06 | n efectivo sin dividir por h | `evaluacion/cobertura.py:40` | detectada | `test_montecarlo::test_asimetria_cuenta_a_cada_lado…` |
| M07 | HAC sin el término h − 1 en los rezagos | `evaluacion/pruebas.py:69` | **NO detectada** (356 passed) | — |
| M08 | reajuste con datos de todo el bloque (hasta 20 días de futuro) | `backtest/corredor.py:73` | detectada | `test_backtest_infra::test_corredor_ningun_ajuste…` |
| M09 | Diebold-Mariano unilateral en la cola equivocada | `evaluacion/pruebas.py:99` | detectada | `test_pruebas_estadisticas::test_diebold_mariano_sin_rezagos` |
| M10 | Clopper-Pearson al 90 % en vez de al 95 % | `evaluacion/cobertura.py:42-43` | detectada | `test_montecarlo::test_asimetria_cuenta_a_cada_lado…` |
| M11 | línea base confirmatoria de h = 63 cambiada | `backtest/final.py:58` | **NO detectada** (356 passed) | — (solo el candado por hash) |
| M12 | corrección HLN calculada con h = 1 | `evaluacion/pruebas.py:96` | detectada | `test_pruebas_estadisticas::test_diebold_mariano_con_un_rezago_bartlett` |

Observaciones:
- M06 y M10 los detectó primero una prueba del **caso** (`test_montecarlo`). Con `-x` la corrida
  se detiene ahí, antes de llegar a `test_pruebas_f2.py:174` (Clopper-Pearson a mano). Por
  orden alfabético no se sabe si esa prueba también las habría detectado; no se comprobó.
- Las fugas en el ajuste (M03, M08) y en la alineación (M01, M04) las detecta una sola prueba
  con un modelo espía. Está bien diseñada, pero es un único punto de falla.
- Impacto de las no detectadas sobre la prueba final (`t2_impacto.py`): M07 → p de Holm 0,315 /
  0,294 / 0,317 a 5 / 21 / 63; M11 → h = 63 CRPS/base 0,914, Holm 0,198. Ningún veredicto
  cambia. M02 no se puede cuantificar sin volver a correr la prueba, y eso no se hizo.

## Tarea 3 — Afirmaciones y su respaldo

Hashes de referencia: `HECHO.json` (SHA-256 de cada resultado; su propio SHA-256 es `6ef88d12…`),
`reports/prueba_final.md` (`e0716de2…`, registrado en `HECHO.json`), `data/respaldo/prueba_final.json`
(`eabb756d…`, el que cita la ficha del caso), `runs/6506dbba3261/resultado.json`
(`bbdff902…`; `hash_resultado` de la ficha `fd0721b8…`).

**La corrida del caso se reproduce bit a bit.** En un clon en `f8fbe16` con `data/processed`
copiado: `PYTHONPATH=src python -m laboratorio.motor compra_dolares --trayectorias 10000 --semilla 20240501`
da `hash resultado fd0721b8…` (el de la ficha) y un `reports/compra_dolares.md` idéntico byte a byte al publicado.

### README.md

| # | afirmación | respaldo (archivo · hash) | estado |
|---|---|---|---|
| R1 | 17 modelos, origen móvil | `HECHO.json` («modelos», 17) · `6ef88d12…` | respaldada |
| R2 | «sin fugas de información» | código + pruebas; T4 no halla fuga | respaldo parcial: ver H1 y D1 |
| R3 | prueba final corrida «una sola vez» | `INICIADA.json` (1 apertura + 1 reanudación tras la adenda) · `c5e1f67c…` | respaldada, con la corrida abortada declarada |
| R4 | h = 1: CRPS/base 0,977; p de Holm < 0,001; confirmada | `prueba_final.md` · `e0716de2…`; respaldo `confirmatorias.1` | respaldada (T1) |
| R5 | mejora ≈ 2 % | 1 − 0,9774 = 2,3 % | respaldada |
| R6 | 5, 21, 63: no confirmada, p de Holm 0,493 | ídem | respaldada (T1) |
| R7 | 126 y 252: 11 y 5 ventanas independientes | respaldo `cobertura.*.n_efectivo` | respaldada |
| R8 | a 1 día «sus colas quedan cortas» | VaR sup. 5 % y 1 %: Kupiec p = 0,002 y 0,002 (respaldo `var_h1`) | respaldada para la cola superior; la inferior al 1 % no se rechaza (p = 0,128) |
| R9 | «a horizontes largos ningún modelo supera a una línea base simple» | MCS de 5, 21 y 63 (descriptivo): las líneas base quedan dentro | respaldo parcial: a 5–63 solo se probó EWMA; a 126 y 252 no hay ninguna prueba de comparación |
| R10 | rangos del motor «probablemente estrechos» (0,90 y 0,88 en desarrollo) | `runs/backtest_largo/` (desarrollo) | contradicha por la prueba final: **H2** |
| R11 | datos de prueba ya vistos, declarado | `prueba_final.md`, «Declaraciones» | respaldada |
| R12 | 25,5 %, 31,5 %, 45,4 % | `resultado.json` (`dist.prob_superar`, `flot.prob_superar`, `mc.prob_superar`) · `bbdff902…` | respaldada y reproducida |
| R13 | «amplificada unas 2,1 veces» | `causa.antes.factor` = 2,057 | respaldada |
| R14 | banda 1991-1999 = 23 % de los datos | `causa.antes.peso` = 22,98 | respaldada |
| R15 | las tres cifras difieren «sobre todo por la deriva» | tabla «Causa de la diferencia» del caso | interpretación sin prueba directa: **D4** |
| R16 | el comando no corre si cambia código, entorno o datos | demostrado: en HEAD se niega (H3) | respaldada |
| R17 | resultados parciales de la corrida abortada no se abrieron | — | sin respaldo posible (D5); sí se verificó que coinciden con la corrida nueva |
| R18 | cada cifra del caso termina en `#hash` | 222 cifras con `#hash`, 179 filas de apéndice; `t3` | respaldada |
| R19 | 356 pruebas, incluidas de fuga | `pytest --collect-only`: 356 | respaldada; su alcance: T2 |
| R20 | `final --verificar` comprueba hashes y etiquetas | falla en HEAD | **H3** |
| R21 | SHA-256 de los `.csv.gz` «ver docs/decisiones.md» | están en `HECHO.json`; `decisiones.md:267` solo dice que coinciden | respaldo indirecto |
| R22 | flotación de 27 años | 1999-09-25 a 2026-11-14 (`limpieza.py: FIN_BANDA`) | respaldada |
| R23 | externas y tasas entran por rezago; revisiones no modeladas | `caracteristicas.py: REZAGO_DIAS`; T4 | respaldada; ver D1–D2 |

### reports/prueba_final.md (SHA-256 `e0716de2…`, en `HECHO.json`)

| sección | respaldo | estado |
|---|---|---|
| Declaraciones: orígenes 2020-01-03 a 2026-08-12, 1.564; hashes | CSV de `runs/prueba_final/` (SHA en `HECHO.json`); `INICIADA.json` | respaldada |
| «Cada modelo se estimó solo con datos anteriores a cada origen» | `corredor.py:73-74` y `test_backtest_infra.py:62` | respaldada (en rigor «hasta el origen», incluido) |
| Confirmatorias y sensibilidad de h = 1 | CSV · T1 | respaldada |
| Motor por horizonte | CSV corto y largo · T1; respaldo `cobertura` | respaldada; «unos 230 días hábiles» lo corrige el caso (217) |
| Tablas por horizonte y por episodio | CSV · T1 | respaldada |
| VaR, Basilea, ES/Z2, PIT h = 1, dirección (binomial) | CSV y `cola/` · T1 | respaldada |
| MCS, Pesaran-Timmermann, PIT h > 1 | CSV + código | sin verificación independiente |
| Horizontes largos | `runs/prueba_final_largo/` · T1 | cifras respaldadas; la carpeta citada es otra: **H4** |
| «Reproducir» | — | falla en HEAD: **H3** |

### reports/compra_dolares.md (corrida `6506dbba3261`)

| bloque | respaldo | estado |
|---|---|---|
| 222 cifras con `#hash` (secciones 1-5, causa, asimetría) | `resultado.json` · `bbdff902…`; datos de la prueba final en el respaldo · `eabb756d…` | respaldadas (`t3`: todas encontradas con la precisión publicada) y reproducidas bit a bit |
| Coberturas e intervalos del abanico | respaldo `cobertura.bootstrap_est_filtrado` | respaldadas (T1 las recalcula desde los CSV) |
| Asimetría (bajo la mediana, fuera de los límites) | respaldo `posterior.asimetria` | respaldada (T1) |
| «(a) es exactamente el modelo que se evaluó» | `motor/montecarlo.py` importa `BootstrapEstacionario` de `modelos/bootstrap.py` | respaldada |
| «lo que se esperaría de una mediana corrida hacia arriba» | — | interpretación declarada como tal |
| Ficha: `commit` | `037f784` no contiene ese código | **H5** |

## Tarea 4 — Búsqueda de fugas (revisión a mano)

**TRM.** `datos/lectores.py:28` toma `VIGENCIADESDE` como fecha: la fila t es la TRM vigente
desde f_t, calculada con las operaciones del día hábil anterior. El objetivo es
ln TRM(t + h) − ln TRM(t) (`backtest/datos.py:42-47`); la TRM de t + 1 depende de las
operaciones del día f_t, posteriores a todo lo que el modelo ve en t. `Vista.hasta(t)` recorta
TRM, rendimientos y externas a t (`datos.py:35-40`); el corredor ajusta con `hasta(reajuste)` y
pronostica con `hasta(último origen del bloque)` (`corredor.py:73-74`), y cada modelo indexa en
su origen (canario `test_sin_fuga.py:76-88`; M03, M04 y M08 lo confirman).

**Covariables externas** (`modelos/caracteristicas.py:19,34-42,60-69`): se toma el último valor
con fecha ≤ f_t − rezago (brent 3 días, dólar amplio 8, fed funds 2, tasa de política 1) y, para
las variaciones, el de f_t − rezago − 30 (o − 90). `t4_rezagos.py` lo recalcula **sin `src/`**
para todos los orígenes ≥ 2020 y compara con `construir` aplicado a la vista **completa** (datos
hasta 2026-11-14): diferencia máxima **0,0** en las seis columnas. En la prueba final, el dato
externo más reciente que entra en un origen tiene al menos 3, 8, 2 y 1 días. Ningún dato
posterior al corte de publicación entra.

**Tasa de política** (`datos/limpieza.py:123-132`): la serie diaria de BanRep cambia en la fecha
de vigencia, no en la del anuncio (p. ej. 3,75 % desde 2020-03-30, lunes siguiente a la junta del
27); con rezago de 1 día el valor usado ya era público. Los valores publicados por adelantado se
cortan en la fecha de descarga (`_hasta`).

**Otras vías revisadas, sin fuga:** las etiquetas de episodio (`estres`) solo estratifican; ningún
modelo las usa (`grep` en `modelos/`). La bandera `banda` es una fecha de política conocida. La
purga del entrenamiento de cuantiles es implícita: `vista.objetivo(h)` sobre `hasta(t0)` es NaN
cuando s + h > t0 (`cuantiles.py:67-69`). `cargar_desarrollo` corta en 2020-01-01 y hay prueba
con los datos reales (`test_backtest_infra.py:108`).

## Dudas (no demostradas; no son hallazgos)

- **D1. Calendario real de publicación de las externas.** Los rezagos del código coinciden
  exactamente con la antigüedad del último dato en la descarga del sábado 2026-11-14 (brent
  2026-11-11 = 3 días, dólar amplio 2026-11-06 = 8, fed funds 2026-11-12 = 2). Una sola foto, un
  sábado, no da el peor caso de un día hábil. Sin conexión no pude verificar el calendario de la
  EIA (brent) ni el de la Reserva Federal (H.10: si el lunes es festivo en EE. UU., sale el martes
  por la tarde, después de la sesión que fija la TRM siguiente). Si hubo desfase, sería de horas o
  de un día y sobre variaciones de 30 o 90 días: casi sin contenido para predecir el día siguiente.
- **D2. Revisiones.** FRED entrega la última versión de cada serie, no la que existía en cada
  origen. El README lo declara («sus revisiones no se modelan»). No se pudo medir su efecto.
- **D3. MCS, Pesaran-Timmermann y PIT a h > 1** no se reimplementaron.
- **D4. «Sobre todo por la deriva»** (README y caso): la variante solo con flotación cambia la
  muestra entera, no solo la deriva; ninguna corrida aísla la deriva (p. ej., choques centrados).
  La atribución es plausible, no probada.
- **D5. Corrida abortada.** Que sus resultados no se abrieran no se puede demostrar con archivos.
  Sí se comprobó que son idénticos a los de la corrida nueva, así que abrirlos no habría dado
  ninguna ventaja sobre los resultados publicados.
- **D6. Diebold-Mariano a 63 días.** Con ≈ 25 ventanas independientes y 69 rezagos, el p-valor
  asintótico es aproximado. No cambia nada (p = 0,40), pero la prueba tiene muy poca potencia
  allí, como el prerregistro ya advierte.
