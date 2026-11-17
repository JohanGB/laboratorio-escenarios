# Caso: compra de dólares para una meta — comprar hoy vs. compras escalonadas

Reporte generado por `python -m laboratorio.motor compra_dolares`. Los rangos describen
incertidumbre (histórica y simulada); no son pronóstico ni asesoría financiera. Cada cifra
termina en un código `#hash` que remite al apéndice con su fuente y su hash SHA-256. Bajo cada
bloque de cifras se dice qué evaluación fuera de muestra lo respalda, o «sin respaldo fuera de muestra».

**Antes de leer las cifras.** La probabilidad de que el Plan B supere el presupuesto depende del método: 25,5 % `#fd7ded8225` con las ventanas históricas, 31,5 % `#c75a7219bb` con el mismo motor remuestreando solo la flotación (análisis posterior) y 45,4 % `#8ace034dae` con el motor prerregistrado. La diferencia viene sobre todo de la deriva de la TRM que cada método supone (cuánto sube el dólar en promedio), no del azar de la simulación: el motor arrastra, amplificada, la depreciación de los años de banda cambiaria (sección 4). Ninguna de las tres cifras tiene respaldo fuera de muestra.

## Planteamiento

- Meta: 10.000 USD `#8397039538`. Plan A: comprarlos todos hoy. Plan B: 12 `#b3a2ac0f21` compras
  iguales, una cada 1 `#e8f3aef896` mes(es), la primera hoy.
- TRM de hoy (2026-11-14 `#a5fb52d5f6`): 3.316,70 COP/USD `#ac9d82649e`.
- Costo del Plan A (cierto): 33.167.000 COP `#bcc9c6d182`. Presupuesto: 34.825.350 COP `#9e8597da5c`
  (costo de comprar hoy más un margen de 5,0 % `#61136fa9f8`).
- Las cifras de meta, número de compras, margen y ventanas son valores ilustrativos del autor.

## 1. Escenarios deterministas del Plan B

La TRM sigue `TRM0·exp(g·m/12)`; g (logarítmica anual) toma los percentiles 5, 50 y 95 de la
variación anual observada desde la flotación. Diferencia = costo de B menos costo de A (positivo = B más caro).

| Escenario | Deriva anual g | Costo Plan B | Costo medio | Diferencia vs. A | ¿Se pasa del presupuesto? |
|---|---:|---:|---:|---:|---|
| Optimista | -0,1804 `#4f72a5af0e` | 30.576.089 COP `#74e6cef07d` | 3.057,61 COP/USD `#6c3fe66e33` | -2.590.911 COP `#af7626ded0` | No `#c20c4b5ae2` |
| Base | 0,0145 `#9055dd1622` | 33.388.447 COP `#4ecc594836` | 3.338,84 COP/USD `#4ef718cbbf` | 221.447 COP `#ff69fa5242` | No `#a0818850a9` |
| Estrés | 0,2566 `#4b75c3bec3` | 37.408.078 COP `#90f47bdfd2` | 3.740,81 COP/USD `#36e7807a2f` | 4.241.078 COP `#86d2b88bd7` | Sí `#746c357c7e` |

Respaldo: sin respaldo fuera de muestra (las derivas son supuestos; no es un pronóstico evaluado).

## 2. Reproducción histórica con nombre

Se aplican al Plan B, desde la TRM de hoy, los movimientos reales de cada ventana.

| Ventana | Inicio | Fin | TRM fin / TRM inicio | Costo Plan B | Diferencia vs. A | ¿Se pasa? |
|---|---|---|---:|---:|---:|---|
| Año 2015 | 2015-01-02 `#70cff49fb1` | 2015-12-02 `#88be7f0d0f` | 1,309 `#a2f36a27c8` | 37.574.195 COP `#4328d795ce` | 4.407.195 COP `#4796a6e03e` | Sí `#aa3d2d39c2` |
| Fin de 2022 | 2022-10-03 `#74bb16f98f` | 2023-09-03 `#b816d0365c` | 0,885 `#ecb3c57cf2` | 32.896.331 COP `#0aea3f60d0` | -270.669 COP `#0ec85949f2` | No `#e6f1919d87` |

Respaldo: sin respaldo fuera de muestra (repite dos episodios del pasado; no es un pronóstico).

## 3. Todas las ventanas históricas del régimen de flotación

Hay 6.243 `#397a9593d2` ventanas de inicio. La más barata empieza el 2009-02-25 `#eda09685c2`
y la más cara el 2008-06-19 `#b83b928b2b`. Se traslapan: equivalen a solo
29 `#181604e73f` ventanas sin traslape, así que los percentiles extremos
descansan en pocos episodios.

| Medida del Plan B | Valor | Diferencia vs. A |
|---|---:|---:|
| Costo esperado (media) | 33.660.196 COP `#eeb75ecf7b` | 493.196 COP `#36dfa5f819` |
| Mediana | 33.482.930 COP `#4bb0a8601f` | |
| Percentil 5 | 30.234.177 COP `#cd85d2879a` | |
| Percentil 95 | 38.822.363 COP `#aa745b31ec` | 5.655.363 COP `#ec552e8bb7` |
| Mínimo | 27.040.921 COP `#0d877ee4f5` | |
| Máximo | 43.559.893 COP `#d9066ae016` | |
| Probabilidad de superar el presupuesto | 25,5 % `#fd7ded8225` | |
| Probabilidad de salir más barato que comprar hoy | 44,0 % `#ab4c750b5d` | |

Respaldo: sin respaldo fuera de muestra (frecuencias del pasado con ventanas traslapadas; nunca se evaluó como pronóstico).

## 4. Monte Carlo por bloques

Se simulan 10.000 trayectorias de la TRM (semilla 20240501) con
`bootstrap_est_filtrado`, el motor fijado en el prerregistro antes de la prueba final. Es un bootstrap
estacionario (Politis-Romano): remuestrea por bloques de longitud media
25,2 días `#d0ce0a55a7` (Politis-White) los rendimientos diarios divididos por la volatilidad
de su momento, y los reescala con la volatilidad de hoy (0,739 % diario `#60af116737`), que
vuelve poco a poco a la de largo plazo (0,673 % diario `#9b37f64747`). La sensibilidad usa
`bootstrap_est` (los rendimientos tal cual, sin filtrar). El tiempo avanza en días con
TRM: la última compra cae a 217 días con TRM `#32ef644023` (el prerregistro decía «unos 230»;
la serie trae unas 20 observaciones por mes, no 21).

**Por qué toda la historia y no solo la flotación.** El remuestreo usa las
8.387 `#375fa7aa02` observaciones de la serie, desde 1991-12-02 `#a1606147c7` (banda cambiaria
incluida); la sección 3, en cambio, solo usa ventanas desde 1999-09-25 `#2650ef76b0`. Tres motivos:
(a) es exactamente el modelo que se evaluó en la prueba final: con otra muestra, las coberturas
medidas que se citan en la sección 5 no respaldarían estas cifras; (b) la banda aporta la
crisis de 1997-1999, uno de los pocos episodios de estrés que hay; (c) el motor remuestrea
choques ya divididos por la volatilidad de su época, así que el nivel de volatilidad de los
años de banda no se traslada a hoy: la escala la pone la volatilidad actual. En la sensibilidad
sin filtrar el motivo (c) no aplica. El motivo (c) vale para la volatilidad, no para la deriva:
ese mismo filtrado amplifica la depreciación de los años de banda (análisis posterior, al final
de esta sección).

**Lo que esa decisión cuesta: la deriva.** El promedio histórico de los choques (incluida la
depreciación sostenida de los años noventa) sí entra en las trayectorias, y en el motor entra
amplificado. La mediana simulada de la TRM a 252 días queda 9,2 % `#5751a6dc04` por encima
de la de hoy (4,9 % `#9cb2f0596c` en la sensibilidad sin filtrar y
2,3 % `#ab3d300e1f` en el análisis posterior solo con flotación), mientras que el escenario
base de la sección 1, que solo mira la flotación, supone una deriva logarítmica anual de
0,0145 `#9055dd1622`. Esa deriva empuja hacia arriba el costo esperado y la probabilidad de
superar el presupuesto frente a las ventanas históricas. No es una opinión del laboratorio sobre
hacia dónde va el dólar: es una propiedad del modelo evaluado, que se deja a la vista y no se
corrige aquí porque el motor quedó fijado antes de la prueba final.

| Medida del Plan B | Monte Carlo (motor) | Sensibilidad (sin filtrar) | Ventanas históricas | Evaluación que la respalda |
|---|---:|---:|---:|---|
| Costo esperado (media) | 34.721.406 COP `#702b229397` | 33.998.678 COP `#fa52bfcde2` | 33.660.196 COP `#eeb75ecf7b` | sin respaldo fuera de muestra |
| Mediana | 34.463.192 COP `#1a112a5ca8` | 33.895.816 COP `#66525e9652` | 33.482.930 COP `#4bb0a8601f` | sin respaldo fuera de muestra |
| Percentil 5 | 30.078.346 COP `#bca23562cf` | 30.372.435 COP `#20cf50cda8` | 30.234.177 COP `#cd85d2879a` | sin respaldo fuera de muestra |
| Percentil 95 | 40.189.139 COP `#760ee96e28` | 38.397.630 COP `#60e4276de7` | 38.822.363 COP `#aa745b31ec` | sin respaldo fuera de muestra |
| Probabilidad de superar el presupuesto | 45,4 % `#8ace034dae` | 33,4 % `#dda8d22edf` | 25,5 % `#fd7ded8225` | sin respaldo fuera de muestra |
| Probabilidad de salir más barato que comprar hoy | 33,1 % `#85b8066e9b` | 36,8 % `#23a6449437` | 44,0 % `#ab4c750b5d` | sin respaldo fuera de muestra |

Diferencia frente al Plan A: costo esperado 1.554.406 COP `#2b981fec70`; percentil 95
7.022.139 COP `#3d14b4ee81`. Error estándar de Monte Carlo (solo por simular un número finito de
trayectorias; no mide el error del modelo): 30.981 COP `#1babdd36e2` en la media y
0,50 puntos porcentuales `#6c367e4404` en la probabilidad que más error tiene de las dos. Es un error
estándar, no una cota: el intervalo del 95 % es aproximadamente el doble a cada lado.

**Respaldo de estas cifras: indirecto.** Ninguna tiene una evaluación directa fuera de muestra.
El caso reparte la compra en 12 `#b3a2ac0f21` cuotas: la última cae a
217 días con TRM `#32ef644023` y la cifra que se reporta es el costo total, una suma sobre toda
la trayectoria. La prueba final no evalúa ni ese horizonte ni esa suma: evalúa el rendimiento
acumulado a 1, 5, 21, 63, 126 y 252 días, cada uno por separado. Dos límites: ese horizonte queda entre 126 y 252 días, que en la prueba final son solo descriptivos (cobertura medida del intervalo del 95 %: 0,992 `#261271976a` con 11 `#0954cae6d6` ventanas independientes y 0,932 `#e21c878bd1` con 5 `#f549e20b8c`); y
acertar cada horizonte por separado no garantiza acertar la trayectoria completa de la que
depende el costo total.

### Análisis posterior (no confirmatorio): el mismo bootstrap solo con la flotación

Este bloque no estaba en el prerregistro: se hizo después de ver la prueba final y las cifras de
arriba. No reemplaza al motor, que sigue siendo el principal, y no se usó para elegir nada.
Repite la simulación del motor con la misma semilla (20240501) y las mismas
10.000 trayectorias, y cambia una sola cosa: remuestrea solo las
6.459 `#4f977a8697` observaciones desde 1999-09-25 `#2650ef76b0` (el régimen de flotación). La
longitud de bloque y la volatilidad, la de hoy y la de largo plazo, son las del motor.

| Medida del Plan B | Motor prerregistrado (principal) | Solo flotación (análisis posterior) | Evaluación que la respalda |
|---|---:|---:|---|
| Mediana de la TRM a 252 días | 3.622,36 COP/USD `#f4f608d0ff` (9,2 % `#5751a6dc04` frente a hoy) | 3.394,28 COP/USD `#88d211c99b` (2,3 % `#ab3d300e1f` frente a hoy) | sin respaldo fuera de muestra |
| Costo esperado (media) | 34.721.406 COP `#702b229397` | 33.728.163 COP `#a34b98ffe6` | sin respaldo fuera de muestra |
| Mediana | 34.463.192 COP `#1a112a5ca8` | 33.468.544 COP `#5578a50e81` | sin respaldo fuera de muestra |
| Percentil 5 | 30.078.346 COP `#bca23562cf` | 29.603.213 COP `#3cc54e84f9` | sin respaldo fuera de muestra |
| Percentil 95 | 40.189.139 COP `#760ee96e28` | 38.705.262 COP `#4c375f1f27` | sin respaldo fuera de muestra |
| Probabilidad de superar el presupuesto | 45,4 % `#8ace034dae` | 31,5 % `#c75a7219bb` | sin respaldo fuera de muestra |
| Probabilidad de salir más barato que comprar hoy | 33,1 % `#85b8066e9b` | 45,5 % `#617b0cc621` | sin respaldo fuera de muestra |

**Causa de la diferencia.** Lo que cada tramo de la serie pone en el motor:

| Tramo de la serie | Peso en la muestra | Deriva anual observada | Volatilidad diaria | Rendimiento diario medio | Choque estandarizado medio | Aporte al choque medio de la serie | Equivalente diario en el motor |
|---|---:|---:|---:|---:|---:|---:|---:|
| Antes del 1999-09-25 `#2650ef76b0` (banda cambiaria) | 23,0 % `#d7759c2456` | 14,5 % por año `#b9d4a512e8` | 0,413 % diario `#0222a97e5f` | 0,0587 % diario `#96032ca422` | 0,179 `#1718e1c6d8` | 0,0412 `#7c62b8d36a` | 0,1208 % diario `#08df8ff3d6` |
| Desde el 1999-09-25 `#2650ef76b0` (flotación) | 77,0 % `#c6ac9baf8e` | 1,9 % por año `#a83b3fce3f` | 0,733 % diario `#96ca488430` | 0,0079 % diario `#49af4acbcc` | 0,016 `#d7a76ec089` | 0,0120 `#8da2c4b61f` | 0,0105 % diario `#23927de57c` |

«Choque estandarizado» = rendimiento del día dividido por la volatilidad de su momento (lo que
remuestrea el motor). «Equivalente diario en el motor» = ese choque medio multiplicado por la
volatilidad de largo plazo. La banda cambiaria es el 23,0 % `#d7759c2456` de las observaciones. En esos años la deriva de la TRM fue de 14,5 % por año `#b9d4a512e8` (desde la flotación, 1,9 % por año `#a83b3fce3f`) con una volatilidad de 0,413 % diario `#0222a97e5f` (desde la flotación, 0,733 % diario `#96ca488430`). El motor divide cada rendimiento por la volatilidad de su época y lo multiplica por la de hoy: un alza pequeña y constante en una época tranquila se convierte en un choque grande. Por eso los choques de la banda entran al motor como una depreciación de 0,1208 % diario `#08df8ff3d6`, 2,1 veces `#d2977f39ce` lo que de verdad se depreció (0,0587 % diario `#96032ca422`), y ese tramo pone 0,0412 `#7c62b8d36a` de los 0,0532 `#1ee79a939d` que vale el choque medio de toda la serie. La sensibilidad sin filtrar (los rendimientos tal cual) incluye la banda, pero no la amplifica.

**Qué significa.** No dice cuál de las dos cifras es la correcta. El motor supone que la
depreciación de los años de banda (un régimen de devaluación gradual que terminó el
1999-09-25 `#2650ef76b0`) puede repetirse y, además, la amplifica; la variante supone que no se repite.
Ninguna de las dos tiene respaldo fuera de muestra, y la variante solo con flotación no se evaluó
nunca: las coberturas de la sección 5 son del motor y no le aplican.

## 5. Abanico de la TRM y evaluación que lo respalda

![Abanico de la TRM proyectada](figs/compra_dolares_abanico.png)

Límites = percentiles 2,5 y 97,5 de las trayectorias del motor (la banda del 95 %), en los
horizontes que evaluó la prueba final. «Cobertura medida» = fracción de las veces, entre 2020 y
2026, en que la TRM real cayó dentro de la banda del 95 % del mismo modelo (lo ideal es 0,95).
El intervalo de confianza usa el n efectivo (ventanas sin traslape). La cobertura respalda los
límites de la banda, no la mediana: la mediana queda sin respaldo fuera de muestra y arrastra la deriva de la
sección 4.

| Horizonte (días con TRM) | Límite inferior | Mediana | Límite superior | Evaluación que la respalda | Advertencia |
|---:|---:|---:|---:|---|---|
| 1 | 3.269,72 COP/USD `#541f90666e` | 3.317,16 COP/USD `#cc8e090b93` | 3.372,33 COP/USD `#936ee02fff` | límites: prueba final, cobertura medida 0,950 `#596a548a9f` (n efectivo 1.564 `#8ed4be09f0`; intervalo de confianza 0,94 `#198851817d` a 0,96 `#3e92478beb`). Mediana: sin respaldo fuera de muestra | no hace falta |
| 5 | 3.198,56 COP/USD `#c740236e24` | 3.320,37 COP/USD `#f882ad467b` | 3.470,74 COP/USD `#bbc0f7abbb` | límites: prueba final, cobertura medida 0,961 `#c0b3c4334d` (n efectivo 313 `#b8217f3347`; intervalo de confianza 0,93 `#30d92cf8a8` a 0,98 `#c45bb97908`). Mediana: sin respaldo fuera de muestra | no hace falta |
| 21 | 3.083,83 COP/USD `#1e5b42ed4c` | 3.338,63 COP/USD `#4fda77a3ac` | 3.667,15 COP/USD `#e5dd4bdffc` | límites: prueba final, cobertura medida 0,968 `#451f44766a` (n efectivo 74 `#95595e43a8`; intervalo de confianza 0,91 `#0ba52be6fb` a 1,00 `#1937c307f3`). Mediana: sin respaldo fuera de muestra | no hace falta |
| 63 | 2.912,19 COP/USD `#c544f90b93` | 3.385,28 COP/USD `#0b46e0ec64` | 4.021,60 COP/USD `#c8b809a55d` | límites: prueba final, cobertura medida 0,960 `#b470e9eb43` (n efectivo 25 `#333f1fc8fe`; intervalo de confianza 0,80 `#74e483b946` a 1,00 `#3a25050041`). Mediana: sin respaldo fuera de muestra | **siempre**: solo 25 `#333f1fc8fe` ventanas independientes; que la cobertura nominal quepa en el intervalo no prueba que la banda esté bien calibrada |
| 126 | 2.798,08 COP/USD `#2160cade1d` | 3.457,93 COP/USD `#137af5dfc8` | 4.399,47 COP/USD `#61b9c14862` | límites: prueba final, descriptiva, cobertura medida 0,992 `#261271976a` (n efectivo 11 `#0954cae6d6`; intervalo de confianza 0,72 `#d056fc2c27` a 1,00 `#6885c4bc5a`). Mediana: sin respaldo fuera de muestra | **siempre**: solo 11 `#0954cae6d6` ventanas independientes; que la cobertura nominal quepa en el intervalo no prueba que la banda esté bien calibrada |
| 252 | 2.663,60 COP/USD `#7d4fd1e47e` | 3.622,36 COP/USD `#f4f608d0ff` | 5.056,59 COP/USD `#9f716920d9` | límites: prueba final, descriptiva, cobertura medida 0,932 `#e21c878bd1` (n efectivo 5 `#f549e20b8c`; intervalo de confianza 0,48 `#a77aa68fca` a 1,00 `#e03cb1472f`). Mediana: sin respaldo fuera de muestra | **siempre**: solo 5 `#f549e20b8c` ventanas independientes; que la cobertura nominal quepa en el intervalo no prueba que la banda esté bien calibrada |

**Modelo de referencia.** Solo a 1 día un modelo superó a su línea base en la prueba final: `lightgbm_cuantiles` (CRPS/base 0,977 `#78dfaf7397`, 1.564 `#bbaa9c983f` orígenes). Su cola superior quedó subcubierta en la prueba final: el VaR superior del 5 % se superó el 6,8 % `#95b74e1cbc` de los días y el del 1 % el 1,85 % `#2ee671614c` (Kupiec p = 0,002 `#2f175c3319` y 0,002 `#bcf7261da5`). Este caso no lo usa para simular ni calcula su banda: se cita como referencia de ese horizonte. En los demás horizontes ningún modelo se distinguió de las líneas base y no se cita ninguno.

### Análisis posterior (no confirmatorio): de qué lado de la banda quedó la TRM real

Este bloque no estaba en el prerregistro: se calculó después, con los mismos resultados de la
prueba final, y no confirma ni rechaza nada. La cobertura de la tabla anterior junta las dos
colas y no dice nada de la mediana. Aquí se cuenta, por horizonte, la proporción de veces que la
TRM real quedó por debajo de la mediana del motor (con una banda bien centrada sería
0,500 `#e026505876`) y fuera de cada límite (lo ideal es
0,025 `#ab871acd32` por lado). El intervalo de confianza es el de la
proporción bajo la mediana y usa las mismas ventanas independientes (n efectivo) de la cobertura.

| Horizonte (días con TRM) | Bajo la mediana del motor | Intervalo de confianza | Bajo el límite inferior | Sobre el límite superior | Ventanas independientes | Lectura |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 0,542 `#b3709ee772` | 0,517 `#8989555b8d` a 0,567 `#dc05564c30` | 0,025 `#3c79b823fa` | 0,025 `#04431aba22` | 1.564 `#8ed4be09f0` | la mitad queda fuera del intervalo: la TRM real quedó bajo la mediana más de lo esperado |
| 5 | 0,568 `#f0684375c3` | 0,512 `#1f35f90ea6` a 0,624 `#921d55f966` | 0,020 `#be1c54d4cc` | 0,019 `#37780f1a3c` | 313 `#b8217f3347` | la mitad queda fuera del intervalo: la TRM real quedó bajo la mediana más de lo esperado |
| 21 | 0,620 `#5a753b3377` | 0,501 `#57c6630a4d` a 0,732 `#ce5a0ad868` | 0,016 `#2f012924b0` | 0,016 `#198897ea55` | 74 `#95595e43a8` | la mitad queda fuera del intervalo: la TRM real quedó bajo la mediana más de lo esperado |
| 63 | 0,663 `#22f03ce406` | 0,465 `#1c268541d2` a 0,851 `#972fa45c17` | 0,029 `#16169c860e` | 0,012 `#5c8e552080` | 25 `#333f1fc8fe` | **indicio, no prueba**: solo 25 `#333f1fc8fe` ventanas independientes |
| 126 | 0,710 `#d952ae3e9c` | 0,390 `#e99d13f021` a 0,940 `#002516a7bd` | 0,007 `#2bba8c5c4b` | 0,001 `#53d9f16613` | 11 `#0954cae6d6` | **indicio, no prueba**: solo 11 `#0954cae6d6` ventanas independientes |
| 252 | 0,801 `#8909951c07` | 0,284 `#3bca3876a0` a 0,995 `#8e5402d1a9` | 0,068 `#86fa51018a` | 0,000 `#7628d6a0ce` | 5 `#f549e20b8c` | **indicio, no prueba**: solo 5 `#f549e20b8c` ventanas independientes |

En todos los horizontes la TRM real quedó bajo la mediana del motor más de la mitad de las veces. Es lo que se esperaría de una mediana corrida hacia arriba, como la que produce la deriva de la sección 4, pero un solo periodo de prueba no basta para atribuirlo solo a esa causa. **A 63, 126 y 252 días es un indicio, no una prueba**: con tan pocas ventanas independientes
casi cualquier proporción cabe en el intervalo. Estas proporciones describen al motor; no hay
medición equivalente para la variante solo con flotación de la sección 4.

## Limitaciones

- No se modela el rendimiento del dinero mientras espera (costo de oportunidad ni tasas COP/USD).
- La distribución histórica usa solo el pasado del régimen de flotación y supone que se
  repetirá; el Monte Carlo remuestrea choques ya ocurridos: ninguno de los dos contiene
  episodios más grandes que los vistos.
- Los percentiles extremos dependen de pocos episodios (ver ventanas sin traslape).
- El costo total simulado no tiene evaluación directa fuera de muestra (sección 4).
- La TRM es la de la Superfinanciera (una fila por vigencia); el precio real de compra
  incluye comisiones y diferencial que no se modelan.

## Ficha de la corrida

- Corrida: `6506dbba3261`; caso `compra_dolares`; semilla: 20240501; trayectorias:
  10.000; motor `bootstrap_est_filtrado`, sensibilidad `bootstrap_est`.
- Hash de datos `f3d3d8e5e5dc4f8cae9d4c55634f7d42ab09cccc37bb2254bd829804a58076a5`
- Hash de supuestos `e26cfb6730179e94360fdf1f59c77945de48ea6950a79c7d7355c9e4abb2e912`
- Hash de código `6aed58e0b63462e136dfb0e30e79cc0d2e4f0dfa003d0b8a0a2771f69e397dfb`
- Hash de entrada `6506dbba326171b63516104206f071188f7f4d1b65634fa69197f91c051381f5`
- Hash de resultado `fd0721b819d7d3d52a3f6515eacbb9b05b3547c834581f0637939f979e2f203e`

## Apéndice: fuente y hash de cada cifra

| Cifra | Origen | Fuente / fórmula | Hash SHA-256 |
|---|---|---|---|
| `#9cb2f0596c` | calculo | 100 × (mediana de la TRM simulada a 252 pasos / TRM_hoy − 1), 10000 trayectorias de bootstrap_est (semilla 20240501, 252 pasos) | `9cb2f0596c651076dedef6489c8c28d32889458f14bc18ebcd81af17b13bad4f` |
| `#5751a6dc04` | calculo | 100 × (mediana de la TRM simulada a 252 pasos / TRM_hoy − 1), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `5751a6dc048dbcb8b71296f9b5975ed2039581195213c740e3f4ef8b2b5d536b` |
| `#ab3d300e1f` | calculo | 100 × (mediana de la TRM simulada a 252 pasos / TRM_hoy − 1), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos); análisis posterior (no confirmatorio): remuestrea solo las 6459 observaciones con fecha >= 1999-09-25, con el bloque y la volatilidad del motor | `ab3d300e1ffeab75b4c12947a3c9d2ef58e8aea91b638680aca3a37610d08e68` |
| `#60af116737` | calculo | 100 × desvío diario EWMA(0,94) en la última observación | `60af11673799490e6128da8fc025e57d5d3a47eb60c34372121545b27da2c5b2` |
| `#0222a97e5f` | calculo | 100 × desvío estándar del rendimiento logarítmico diario, observaciones con fecha anterior a desde (análisis posterior (no confirmatorio)) | `0222a97e5f90665fe84efc535755279f0bfc4a4a47d0453eabf2745a0352b3b5` |
| `#96ca488430` | calculo | 100 × desvío estándar del rendimiento logarítmico diario, observaciones con fecha igual o posterior a desde (análisis posterior (no confirmatorio)) | `96ca4884300e28a96021a8748fdf0f9956e4e2bdbe87890f30e65d13332451ad` |
| `#23a6449437` | calculo | 100 × fracción de trayectorias con costo < costo hoy, 10000 trayectorias de bootstrap_est (semilla 20240501, 252 pasos) | `23a644943705f6625996a9f23eefb9edc4d9afc6cbf1fc34e82b50490dad8a3b` |
| `#85b8066e9b` | calculo | 100 × fracción de trayectorias con costo < costo hoy, 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `85b8066e9b2eac37aff197128a5b104b6dcc9012bd96ba88b3292b15c801388c` |
| `#617b0cc621` | calculo | 100 × fracción de trayectorias con costo < costo hoy, 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos); análisis posterior (no confirmatorio): remuestrea solo las 6459 observaciones con fecha >= 1999-09-25, con el bloque y la volatilidad del motor | `617b0cc621dca5f4ef44ee425e20478534b3fe80f4be66dd249528c536b3ae19` |
| `#dda8d22edf` | calculo | 100 × fracción de trayectorias con costo > presupuesto, 10000 trayectorias de bootstrap_est (semilla 20240501, 252 pasos) | `dda8d22edf0a8a44971e6b5e67c0c50a3d4c74b0ea64da26686a0aabc8f05f26` |
| `#8ace034dae` | calculo | 100 × fracción de trayectorias con costo > presupuesto, 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `8ace034dae4618267502623a4aa38681845eb877f756a7a19744d32663c42a1b` |
| `#c75a7219bb` | calculo | 100 × fracción de trayectorias con costo > presupuesto, 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos); análisis posterior (no confirmatorio): remuestrea solo las 6459 observaciones con fecha >= 1999-09-25, con el bloque y la volatilidad del motor | `c75a7219bb19b4b16b1c565b2343811f792176bb7eca32c460025cd1ab30216f` |
| `#ab4c750b5d` | calculo | 100 × fracción de ventanas con costo < costo hoy | `ab4c750b5da2956d4e0811415cba2e6128675756d07c1040ed85387c6bfa3b50` |
| `#fd7ded8225` | calculo | 100 × fracción de ventanas con costo > presupuesto | `fd7ded8225cdc21d7d449139499f6a483c1f8f328f320a2074734d983c8da7d2` |
| `#08df8ff3d6` | calculo | 100 × media de z del tramo × desvío diario de largo plazo, observaciones con fecha anterior a desde (análisis posterior (no confirmatorio)) | `08df8ff3d610e0dbd2fd5d40db1ebfa4245bee5c95ed32b9833d9105885534d4` |
| `#23927de57c` | calculo | 100 × media de z del tramo × desvío diario de largo plazo, observaciones con fecha igual o posterior a desde (análisis posterior (no confirmatorio)) | `23927de57c9ba55153f6c92a752339b6e53a93d0e24f14418ccae5587391eb01` |
| `#96032ca422` | calculo | 100 × media del rendimiento logarítmico diario, observaciones con fecha anterior a desde (análisis posterior (no confirmatorio)) | `96032ca422875bdee93ced699d29d54dca443f12e8f2995536ce43d40b606361` |
| `#49af4acbcc` | calculo | 100 × media del rendimiento logarítmico diario, observaciones con fecha igual o posterior a desde (análisis posterior (no confirmatorio)) | `49af4acbccb45d32f5ef349b2b75b91ba76021bda4d49db9841da64f9de6cab4` |
| `#6c367e4404` | calculo | 100 × máximo de √(p(1−p)/trayectorias) entre las dos probabilidades, 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `6c367e44044e485962c05cbded0b5f559f6cc902ea5dba747fe1189d86eee0b8` |
| `#d7759c2456` | calculo | 100 × observaciones del tramo / observaciones con rendimiento, observaciones con fecha anterior a desde (análisis posterior (no confirmatorio)) | `d7759c2456716f4f5677c81c8274c3f385e91d6af5c8db13107644814ba0fb8c` |
| `#c6ac9baf8e` | calculo | 100 × observaciones del tramo / observaciones con rendimiento, observaciones con fecha igual o posterior a desde (análisis posterior (no confirmatorio)) | `c6ac9baf8e3a941d71c7aef71908aa6662a66ab3cb23f0d3862cf1a34a1a0699` |
| `#9b37f64747` | calculo | 100 × raíz de la media de r² en toda la historia | `9b37f647474a5dc060afe4f4d49c2f0fea13bbc6ee11f231cba2e8c4e0366f41` |
| `#b9d4a512e8` | calculo | 100 × suma de rendimientos logarítmicos / años de calendario, observaciones con fecha anterior a desde (análisis posterior (no confirmatorio)) | `b9d4a512e8581ec8a1d5e5a08f56b43af77b84c9b149d8f3d27a394a93132444` |
| `#a83b3fce3f` | calculo | 100 × suma de rendimientos logarítmicos / años de calendario, observaciones con fecha igual o posterior a desde (análisis posterior (no confirmatorio)) | `a83b3fce3f8d2df5e1c3a944579b998f90a61b8f66299ce4b2a35e75d73b39bb` |
| `#95b74e1cbc` | calculo | 100 × tasa de excesos del VaR | `95b74e1cbcbe8913dd0d63339632c45f9f9f7cdc966f662000b386f852242534` |
| `#2ee671614c` | calculo | 100 × tasa de excesos del VaR | `2ee671614c14d7e9634723ff46066a1982e112998262f1566161902ff659e2df` |
| `#a2f36a27c8` | calculo | TRM(inicio + horizonte) / TRM(inicio) | `a2f36a27c80cade8ffa6fee92d6966db3e333db4178c22398c89023a537fd72f` |
| `#ecb3c57cf2` | calculo | TRM(inicio + horizonte) / TRM(inicio) | `ecb3c57cf29270d201de3f17ce269daf27d36bfb36f2c17bdb2b26bdeabbfd02` |
| `#541f90666e` | calculo | TRM_hoy × exp(cuantil 0.025 del rendimiento acumulado a 1 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `541f90666e218484f9b23a9012030bffe2ebb9df5a61f9b171733ed75ed93cc2` |
| `#2160cade1d` | calculo | TRM_hoy × exp(cuantil 0.025 del rendimiento acumulado a 126 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `2160cade1de2c858e5cbd9d8afcdfed009b157c54a10ceff726a009b4d9f00c4` |
| `#1e5b42ed4c` | calculo | TRM_hoy × exp(cuantil 0.025 del rendimiento acumulado a 21 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `1e5b42ed4c7479039555061f49a47e60a426527659d5a3e754b8772c63407743` |
| `#7d4fd1e47e` | calculo | TRM_hoy × exp(cuantil 0.025 del rendimiento acumulado a 252 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `7d4fd1e47e6709866cd7acfff8f56bd0f797c40d9b1159b71390a965c232619c` |
| `#c740236e24` | calculo | TRM_hoy × exp(cuantil 0.025 del rendimiento acumulado a 5 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `c740236e24a74c7e89491de35806a9cb70dd068260f539ba8110fc05914b42ec` |
| `#c544f90b93` | calculo | TRM_hoy × exp(cuantil 0.025 del rendimiento acumulado a 63 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `c544f90b93b3d4efc0b6c3534cf492782a55614ce7267d37b9e29dae3419619c` |
| `#cc8e090b93` | calculo | TRM_hoy × exp(cuantil 0.5 del rendimiento acumulado a 1 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `cc8e090b938e5f276016d8e7572a8bf69e9fc56fed82b5eeba1252ca5c94470c` |
| `#137af5dfc8` | calculo | TRM_hoy × exp(cuantil 0.5 del rendimiento acumulado a 126 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `137af5dfc837925e016ac30f78c4d154875de211671d8bd86317ad3d6eb58cc8` |
| `#4fda77a3ac` | calculo | TRM_hoy × exp(cuantil 0.5 del rendimiento acumulado a 21 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `4fda77a3ac39a555c89da69e2ced5ef4e42519bc635548135bffb7ec201f9ea3` |
| `#f4f608d0ff` | calculo | TRM_hoy × exp(cuantil 0.5 del rendimiento acumulado a 252 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `f4f608d0ffacfad0f29e17e5a33e77f60cf5274f158ada56a4bf7252b31139a7` |
| `#f882ad467b` | calculo | TRM_hoy × exp(cuantil 0.5 del rendimiento acumulado a 5 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `f882ad467be1b8f208029c926f9e66f7e19371cadd37e49dae206dcdfb20d49c` |
| `#0b46e0ec64` | calculo | TRM_hoy × exp(cuantil 0.5 del rendimiento acumulado a 63 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `0b46e0ec640e24410fc819ef24e5dbdd540b9d74421b6e8b68aba7416285ef9c` |
| `#936ee02fff` | calculo | TRM_hoy × exp(cuantil 0.975 del rendimiento acumulado a 1 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `936ee02fff672e9bab12293fa61e58f7cc7d56fd00dab1f21b80871e4a400800` |
| `#61b9c14862` | calculo | TRM_hoy × exp(cuantil 0.975 del rendimiento acumulado a 126 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `61b9c148622d06f7f951a560cbdcb471f5cbe94dcbf2d82cf5a99cb574d4c64f` |
| `#e5dd4bdffc` | calculo | TRM_hoy × exp(cuantil 0.975 del rendimiento acumulado a 21 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `e5dd4bdffc717d5b1bf6187874af71c49e7d95a77b3f680729dd4caecb400346` |
| `#9f716920d9` | calculo | TRM_hoy × exp(cuantil 0.975 del rendimiento acumulado a 252 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `9f716920d9cc4feb3f88a871bbd6c5aa9f8036eea7b01deea6a093ec503c9e44` |
| `#bbc0f7abbb` | calculo | TRM_hoy × exp(cuantil 0.975 del rendimiento acumulado a 5 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `bbc0f7abbbe2837bb78df6e5947083c906333209cfd037cc11b8e2bbf348b3d1` |
| `#c8b809a55d` | calculo | TRM_hoy × exp(cuantil 0.975 del rendimiento acumulado a 63 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `c8b809a55d34073cf8ed24da7c108a41b33e1ecbfbefa3d0c08c732561e472cd` |
| `#88d211c99b` | calculo | TRM_hoy × exp(mediana del rendimiento acumulado a 252 pasos), 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos); análisis posterior (no confirmatorio): remuestrea solo las 6459 observaciones con fecha >= 1999-09-25, con el bloque y la volatilidad del motor | `88d211c99b18846ae899fc2e4d49d9b2298fd51cbf48d436c248a948a4dc07ae` |
| `#6c3fe66e33` | calculo | costo / meta_usd | `6c3fe66e33cb3ab867a5169fd8d92eb4bacba3393a9fdaec54af1908b03a7aad` |
| `#4ef718cbbf` | calculo | costo / meta_usd | `4ef718cbbf2447a74d60c0738e565b44863ba9a3b02c60cbe857a5d2d27eb723` |
| `#36e7807a2f` | calculo | costo / meta_usd | `36e7807a2f9dcdf5e60227814b2e621d3f059b63c6d6d9d6569fe391a3699a6a` |
| `#c20c4b5ae2` | calculo | costo > presupuesto | `c20c4b5ae2f93262a5e26d1029d82d4aa92edc65613e7129ac4379f209d815ef` |
| `#a0818850a9` | calculo | costo > presupuesto | `a0818850a967d8ec13a12d1b051d4388cb0e807871e019e79cde334083a45f54` |
| `#746c357c7e` | calculo | costo > presupuesto | `746c357c7e8030ed3f40305fdd58bcc392df96a9d136e7bc3c55b1a17d0ec0a8` |
| `#aa3d2d39c2` | calculo | costo > presupuesto | `aa3d2d39c29a1e1e35d3ea8d53a865f546a7e2b3dd1c1c01a18525255ccce8de` |
| `#e6f1919d87` | calculo | costo > presupuesto | `e6f1919d8744fe161fce2abdef6e4cf1fafd53985e2a1f8cea99e0614233f00b` |
| `#af7626ded0` | calculo | costo escalonado − costo hoy | `af7626ded0b0393852cf523ca6db0817ed07c22681c243a68adba1ed439a4e2f` |
| `#ff69fa5242` | calculo | costo escalonado − costo hoy | `ff69fa5242a5b376a90830a2e1d887b9df2926864f7bc775c1f7d9bdecd55194` |
| `#86d2b88bd7` | calculo | costo escalonado − costo hoy | `86d2b88bd752e6e3cafb03c773ff04b05262e628bbde7dfd5b8e5087608b0077` |
| `#4796a6e03e` | calculo | costo escalonado − costo hoy | `4796a6e03e909f700a67d8ebf3b95f96e8ff4fe39410c77e39ac536864bcb648` |
| `#0ec85949f2` | calculo | costo escalonado − costo hoy | `0ec85949f2ca379ea5c0d8a72749f255dd0678ffa5ac6de164f30b4d880cd6cd` |
| `#36dfa5f819` | calculo | costo esperado escalonado − costo hoy | `36dfa5f819e06c01ab3a532f90d09eefe817161cf926cbf44a011d75f4812694` |
| `#2b981fec70` | calculo | costo esperado simulado − costo hoy | `2b981fec705b53d52f3d9bce6d660bb0ec1a35bda2b93ee423b7731fa7fe399c` |
| `#9e8597da5c` | calculo | costo_hoy × (1 + margen/100) | `9e8597da5c7021daf7efb682d058be7efe9495c3dcb269d4f44c10dc9daa74b0` |
| `#1babdd36e2` | calculo | desvío del costo / √trayectorias, 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `1babdd36e287972e577ea16b0b2aa298322a413c061a65cced84690a1fb5cf98` |
| `#d2977f39ce` | calculo | equivalente diario en el motor / rendimiento diario medio | `d2977f39ceb1406baec311cacecd2a185b547f7a518ae781044520e46a83b6ab` |
| `#a5fb52d5f6` | calculo | fecha de la TRM de hoy | `a5fb52d5f6c99be5e5ca776dd85a16f84214b8c3090350c00dfb9152ae8382f6` |
| `#88be7f0d0f` | calculo | inicio + horizonte del plan | `88be7f0d0f15ce7b8baf20feb551703a7485694bbf798632054958e48d043734` |
| `#b816d0365c` | calculo | inicio + horizonte del plan | `b816d0365c319d929b7c991841e7271c30a79085ccfec23117d61f069e214552` |
| `#b83b928b2b` | calculo | inicio de la ventana de mayor costo | `b83b928b2bb60db154903a4fe7baa1985d64c80e90770815609c70c99271f180` |
| `#eda09685c2` | calculo | inicio de la ventana de menor costo | `eda09685c2ae227350bb424605f3ea6804227b55460e6783e493c91bbfd420a0` |
| `#d0ce0a55a7` | calculo | longitud media de bloque de Politis-White (máximo entre la serie y su valor absoluto), bootstrap_est_filtrado | `d0ce0a55a7a0eff1f5cfa6c1efe62aa07afb48f2f0117de6b374525cd12b3cef` |
| `#1718e1c6d8` | calculo | media de z = r / desvío EWMA(0,94) del día anterior, observaciones con fecha anterior a desde (análisis posterior (no confirmatorio)) | `1718e1c6d8f6edea860f2ecb9d265ac65ef9f0af65b410b2aa4a4909d775ad90` |
| `#d7a76ec089` | calculo | media de z = r / desvío EWMA(0,94) del día anterior, observaciones con fecha igual o posterior a desde (análisis posterior (no confirmatorio)) | `d7a76ec089e37b142974aa702f773781d33795cab26f10de5d7e87f3f32c9994` |
| `#eeb75ecf7b` | calculo | media del costo en todas las ventanas | `eeb75ecf7bf90947f607a43665f11d4b5f1f0fd58c94db47bb1632a98fc4c80d` |
| `#fa52bfcde2` | calculo | media del costo, 10000 trayectorias de bootstrap_est (semilla 20240501, 252 pasos) | `fa52bfcde2638785be04d32a5c99113168a3a0083cd13c6983a21ca1f1e2d1df` |
| `#702b229397` | calculo | media del costo, 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `702b229397ef5c6477f5cf8c53cc4ef8d0e2c8551af62d9d325acf4983a5d3d9` |
| `#a34b98ffe6` | calculo | media del costo, 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos); análisis posterior (no confirmatorio): remuestrea solo las 6459 observaciones con fecha >= 1999-09-25, con el bloque y la volatilidad del motor | `a34b98ffe6335a9a90ca7127b7d8267072210786c25b5c209945ba39b7d05842` |
| `#32ef644023` | calculo | mediana, en las ventanas históricas, de las observaciones entre el inicio y la última compra | `32ef64402361651612fcafa88d35519e05e594ad6cdf64a9dae5f1ad424347be` |
| `#181604e73f` | calculo | meses cubiertos / horizonte (ventanas sin traslape) | `181604e73ffafbd833606330eac16d80bb2aeec2a2c90c2fff2cba21e43fe118` |
| `#bcc9c6d182` | calculo | meta_usd × TRM_hoy | `bcc9c6d182f42b358cb4d5b1e1a5d97cb41ac5a5529c9e9c785e62521e66b0e7` |
| `#d9066ae016` | calculo | máximo del costo | `d9066ae016bd23a88844b437a20a2a5e58dd3075d272b1a260aeb9197ff7ae36` |
| `#0d877ee4f5` | calculo | mínimo del costo | `0d877ee4f5f1f6a6f3bc2ed50eed8d80a84cde1893ef65ba092e4267dab9accc` |
| `#397a9593d2` | calculo | número de fechas de inicio con ventana completa | `397a9593d212c419d51c53438b9f897bb2a437f576026404f0a6a85009801501` |
| `#4f977a8697` | calculo | observaciones de la serie con fecha >= desde y rendimiento | `4f977a869704665dba06566ae1722136988ee5a8e88973871e796e54330d7496` |
| `#cd85d2879a` | calculo | percentil 5 del costo | `cd85d2879a0362415a8fb863203021f2963c567390faab3e8bde38b9bb9749b1` |
| `#20cf50cda8` | calculo | percentil 5 del costo, 10000 trayectorias de bootstrap_est (semilla 20240501, 252 pasos) | `20cf50cda8b770123e1ffff98869966207385ffc7f176d1447a76dd9f8ab7cee` |
| `#bca23562cf` | calculo | percentil 5 del costo, 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `bca23562cf1f000284aa78f75c45142471b2b8b15f9266623f5e309007c8ba90` |
| `#3cc54e84f9` | calculo | percentil 5 del costo, 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos); análisis posterior (no confirmatorio): remuestrea solo las 6459 observaciones con fecha >= 1999-09-25, con el bloque y la volatilidad del motor | `3cc54e84f9238a91ccec4e7cab2ff5b111b9a217f650c5e14e80b00ea72c8c59` |
| `#4bb0a8601f` | calculo | percentil 50 (mediana) del costo | `4bb0a8601ffdbcebac527288b8fe2caa6700edca12d5c137c57f8184ad86451a` |
| `#66525e9652` | calculo | percentil 50 (mediana) del costo, 10000 trayectorias de bootstrap_est (semilla 20240501, 252 pasos) | `66525e9652e5bc54ca2b8126eb309626d5e327a51747e13ce1c81b4190dec40b` |
| `#1a112a5ca8` | calculo | percentil 50 (mediana) del costo, 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `1a112a5ca88c3dc6259fa60dd141255cea7f71a7bc811cfb9bafa1651b66ff90` |
| `#5578a50e81` | calculo | percentil 50 (mediana) del costo, 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos); análisis posterior (no confirmatorio): remuestrea solo las 6459 observaciones con fecha >= 1999-09-25, con el bloque y la volatilidad del motor | `5578a50e81a8b59cccac9e4f00131592be1f29d7f59516d81d6db5b4b57501aa` |
| `#aa745b31ec` | calculo | percentil 95 del costo | `aa745b31ec1fbfdb65c9432806ec940bfc74956f0ec8be86a94ff8de8aeae78e` |
| `#60e4276de7` | calculo | percentil 95 del costo, 10000 trayectorias de bootstrap_est (semilla 20240501, 252 pasos) | `60e4276de72e07ccb13c09e0486a4a42c5718c46572f07372a2b9bec43c5e584` |
| `#760ee96e28` | calculo | percentil 95 del costo, 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos) | `760ee96e287c0d233632296376326f40042fdb29232b9358dec50491a38c4efe` |
| `#4c375f1f27` | calculo | percentil 95 del costo, 10000 trayectorias de bootstrap_est_filtrado (semilla 20240501, 252 pasos); análisis posterior (no confirmatorio): remuestrea solo las 6459 observaciones con fecha >= 1999-09-25, con el bloque y la volatilidad del motor | `4c375f1f277caac846f57b0d8009f21f04b5a00df1b45baf8034f6acf38101a6` |
| `#ec552e8bb7` | calculo | percentil 95 escalonado − costo hoy | `ec552e8bb77adc4266db188dc8cf37d3256457ab7ce841353545a46b4def2d17` |
| `#3d14b4ee81` | calculo | percentil 95 simulado − costo hoy | `3d14b4ee81dd95434760c6a406e372bcc58a341fd44762d383ef90f11c0cd97b` |
| `#a1606147c7` | calculo | primera fecha de la serie | `a1606147c721020c679a016668896e06321feded5c50023049b4d910a8857f66` |
| `#1ee79a939d` | calculo | suma de los aportes de los tramos = media de z de toda la serie (análisis posterior (no confirmatorio)) | `1ee79a939d0c1f870c7592116019b0e214b6573da1513e89d4f4de0fd58931a3` |
| `#7c62b8d36a` | calculo | suma de z del tramo / observaciones de toda la serie, observaciones con fecha anterior a desde (análisis posterior (no confirmatorio)) | `7c62b8d36abdcfa7062bc6a2b721cbae7c4ecd8dcecbc6b6cbc502f8222542d0` |
| `#8da2c4b61f` | calculo | suma de z del tramo / observaciones de toda la serie, observaciones con fecha igual o posterior a desde (análisis posterior (no confirmatorio)) | `8da2c4b61f9da484256c24b345ffefeb171bc5269069aa0807e652d0d48f9899` |
| `#4328d795ce` | calculo | Σ (meta/n)·TRM_hoy·TRM(inicio+m_i)/TRM(inicio) | `4328d795ce8a7b129adc720b48e0d82358a543cb98c78c4f07c0e130c37c35be` |
| `#0aea3f60d0` | calculo | Σ (meta/n)·TRM_hoy·TRM(inicio+m_i)/TRM(inicio) | `0aea3f60d07d4e32720649ddebe75fd3580fc38d10a2c109df457eaa03525022` |
| `#74e6cef07d` | calculo | Σ (meta/n)·TRM_hoy·exp(g·m_i/12), m_i = i·intervalo | `74e6cef07d52f84497c5cc55d570e8ce4b1ddf5e135acf08a89e09546d8f3d08` |
| `#4ecc594836` | calculo | Σ (meta/n)·TRM_hoy·exp(g·m_i/12), m_i = i·intervalo | `4ecc594836c49cc675dcad898b06d65c15c01f9da34c7fbb4305c0817394f076` |
| `#90f47bdfd2` | calculo | Σ (meta/n)·TRM_hoy·exp(g·m_i/12), m_i = i·intervalo | `90f47bdfd2cfc554f54b9bf57c900e4505cf64845497b1c927dfad23c2ff2ae7` |
| `#375fa7aa02` | dato | processed/trm.csv#columna=trm;serie completa | `375fa7aa0246e099abc160f939cf5ec1cd48527a3267bfe6693904e32cfe1f5a` |
| `#ac9d82649e` | dato | processed/trm.csv#fecha=2026-11-14;columna=trm | `ac9d82649e85a0c41efb9bb796da93650898c8a971f2b2614f424c5ccf9a6497` |
| `#261271976a` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=126;campo=cobertura | `261271976a8a99e45c7d0686cea8b6d4b5307522d151a46f79cea4d49010faf1` |
| `#d056fc2c27` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=126;campo=ic_inf | `d056fc2c27b244ab4c84450efc9c732b13610b6c79cf4f7806df13ddad732ea2` |
| `#6885c4bc5a` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=126;campo=ic_sup | `6885c4bc5ad480eab26db6f034cfdd7b5f0f73d4a026e4c81bbcb77ae699f815` |
| `#0954cae6d6` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=126;campo=n_efectivo | `0954cae6d606014bce7d223cd97dfc7002f713ed074d1ea9f0fb747dbccb7931` |
| `#596a548a9f` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=1;campo=cobertura | `596a548a9fcc3314d4b01ae3f29afd5716bdf46219abe2106c4b8943c882ed3a` |
| `#198851817d` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=1;campo=ic_inf | `198851817db9cf3ba5e6542abad2ec1b60ef3c2a25c46a0b79fe3ef52341d320` |
| `#3e92478beb` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=1;campo=ic_sup | `3e92478beb2f6595f86a44c4fce3a82d7678417bd9320d56193dbaf5fd9e035a` |
| `#8ed4be09f0` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=1;campo=n_efectivo | `8ed4be09f0321f815a4051a47f43df5e40fafba7f640b1899d3a8d965e6abac8` |
| `#451f44766a` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=21;campo=cobertura | `451f44766a6db33dec54566bc609aad7d40a6730cefb9c73a9a3bb0078f9f121` |
| `#0ba52be6fb` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=21;campo=ic_inf | `0ba52be6fb652bb67b4e58a55bed029a92a55bc52589d14b9c1f121ee89925d5` |
| `#1937c307f3` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=21;campo=ic_sup | `1937c307f3931424bba9090df250bfa8cfedade70feef388a5bcdf213ee0c744` |
| `#95595e43a8` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=21;campo=n_efectivo | `95595e43a85012a893d306216416a7d6cf4fb0d26a80e419c264fec52e64c80f` |
| `#e21c878bd1` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=252;campo=cobertura | `e21c878bd175ccfb6a35c30ac56b7a7895b565ee477ac60af3456e72fe7fb6f8` |
| `#a77aa68fca` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=252;campo=ic_inf | `a77aa68fca27b5f2aa279ca5d76e1c74b4687e4459c2e4a1464021ac5cd03dea` |
| `#e03cb1472f` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=252;campo=ic_sup | `e03cb1472f9b4da5d94003b0c44dd355343f8b374e2e436bf2ef9d64cfc27cd3` |
| `#f549e20b8c` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=252;campo=n_efectivo | `f549e20b8cd14b459ed8cced0a973dd11f896399083087626dfaa9f349c264df` |
| `#c0b3c4334d` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=5;campo=cobertura | `c0b3c4334d09664ec7d5df87fdb00cb70d1bae271ca947fea0fe50c4ea8593c9` |
| `#30d92cf8a8` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=5;campo=ic_inf | `30d92cf8a8632cd30e16ff0a91b4644b5c1784de7fb030029a5f1ec0d27ce1a7` |
| `#c45bb97908` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=5;campo=ic_sup | `c45bb9790864011a48101021de9ec690a5dbd6e26f50d542b9a6f787175ccb12` |
| `#b8217f3347` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=5;campo=n_efectivo | `b8217f3347ffc09e696971b6dfa114f2a81afb7110a0262a86582861abb1446c` |
| `#b470e9eb43` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=63;campo=cobertura | `b470e9eb43d7d529db40fe1b39697a315f0ee308eb46e687847be7ff57c3a4aa` |
| `#74e483b946` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=63;campo=ic_inf | `74e483b9466cb7094b398b310e918c36688b14140c5a355890ca13e5b6f0dfb0` |
| `#3a25050041` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=63;campo=ic_sup | `3a2505004110fef73c61cd5130f89f3c4f1b35b39fe2818f5e7bd7aed0f62a45` |
| `#333f1fc8fe` | dato | respaldo/prueba_final.json#cobertura;motor=bootstrap_est_filtrado;h=63;campo=n_efectivo | `333f1fc8fe748c26dfcb380b21bd5d6b7802eb8801652888f350f66c37ba9f82` |
| `#bbaa9c983f` | dato | respaldo/prueba_final.json#confirmatorias;h=1;campo=n | `bbaa9c983f79254b6fc86faafa22e81eb043adf2951d2c6d22a9f34f904e631a` |
| `#78dfaf7397` | dato | respaldo/prueba_final.json#confirmatorias;h=1;campo=relativo | `78dfaf739732d1d508036f9c507f2ae920c566e1167ab12313ffd01b28b73047` |
| `#2bba8c5c4b` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=126;medida=bajo_inferior;campo=proporcion | `2bba8c5c4b64752063e407246c5de1da9081608c031904d05eb19645abc30965` |
| `#e99d13f021` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=126;medida=bajo_mediana;campo=ic_inf | `e99d13f021d73911d959554d62a3bb3a9d32a33da1d9799b0887b1cd2573973b` |
| `#002516a7bd` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=126;medida=bajo_mediana;campo=ic_sup | `002516a7bd78e4999569aa4900784d507ffa2c328f54288b03cf3648f35e2659` |
| `#d952ae3e9c` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=126;medida=bajo_mediana;campo=proporcion | `d952ae3e9cf2997b3a582aca84f3fd488c087bfdb2bfc474eedfba763315b80e` |
| `#53d9f16613` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=126;medida=sobre_superior;campo=proporcion | `53d9f16613f535715a75ad328ad2c7f9475d86163887c7c26d492286122339ed` |
| `#ab871acd32` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=1;medida=bajo_inferior;campo=esperado | `ab871acd32939c2146be9d62682e8391d37ce07c7bec7ecd1edf9c206f75a31c` |
| `#3c79b823fa` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=1;medida=bajo_inferior;campo=proporcion | `3c79b823fa5c63cd70610a683e1097720c0ca4a37c38ba2cdab68b35aa021080` |
| `#e026505876` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=1;medida=bajo_mediana;campo=esperado | `e0265058766e4fa9b9284308fd42bbff881e791aada011d8701a07ff112f19ec` |
| `#8989555b8d` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=1;medida=bajo_mediana;campo=ic_inf | `8989555b8d2b615799f8a8657933647422a6d18dfe4e8ea6f9feba511d5829e8` |
| `#dc05564c30` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=1;medida=bajo_mediana;campo=ic_sup | `dc05564c30d0c5d32bf3506860b8255dd8bdcd844c375a642d8696cf80668070` |
| `#b3709ee772` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=1;medida=bajo_mediana;campo=proporcion | `b3709ee7725a7ca6cc65259094afe0bc7020778961587b5e35b1538796776b99` |
| `#04431aba22` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=1;medida=sobre_superior;campo=proporcion | `04431aba22ddc7bbf465bff377329ac482e15f01692248e6df0e11deba63cd53` |
| `#2f012924b0` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=21;medida=bajo_inferior;campo=proporcion | `2f012924b0761a5c292720e892eaed8c1af5ca739467866b7e14e0a3a61bd05e` |
| `#57c6630a4d` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=21;medida=bajo_mediana;campo=ic_inf | `57c6630a4d3bc35d5e5264f7f3bf6934dc19293d7e4f6bfa3d2084e7140739de` |
| `#ce5a0ad868` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=21;medida=bajo_mediana;campo=ic_sup | `ce5a0ad868086e7f3be9aceff9b6d9aff6d601833dca6df664dfac211b1735e6` |
| `#5a753b3377` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=21;medida=bajo_mediana;campo=proporcion | `5a753b3377d01df4b70c0475a12e3a68658e04b03c03009aac8d78334b200a1c` |
| `#198897ea55` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=21;medida=sobre_superior;campo=proporcion | `198897ea556b73e97e20cf7bf547d76709e6289a1bee4a8708551bd16ccc9fe4` |
| `#86fa51018a` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=252;medida=bajo_inferior;campo=proporcion | `86fa51018a72832ed5f2b6b1aa29e3c7842806d0b481fff7659e974944a78231` |
| `#3bca3876a0` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=252;medida=bajo_mediana;campo=ic_inf | `3bca3876a05f51a14649638fe612ee26d8f7eb1553d3f428947d156db9136144` |
| `#8e5402d1a9` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=252;medida=bajo_mediana;campo=ic_sup | `8e5402d1a9adb9a48f19b7402fba81386a6395f38744fa6a905c85fe7cf1c11a` |
| `#8909951c07` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=252;medida=bajo_mediana;campo=proporcion | `8909951c0770b858a861fa0e6555502815f811ba31007dcc2f956197d39f156e` |
| `#7628d6a0ce` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=252;medida=sobre_superior;campo=proporcion | `7628d6a0ce6c5031d3f3cea59f17dc086001359795eb87192d456c58d878e752` |
| `#be1c54d4cc` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=5;medida=bajo_inferior;campo=proporcion | `be1c54d4ccec78fbb3eca4d9950da6cc152cfcb5c4c0968a887a9f2c3426a233` |
| `#1f35f90ea6` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=5;medida=bajo_mediana;campo=ic_inf | `1f35f90ea62953f1b3607ec7b35c11e064932918ad704e60eed88fbf5fd48fa1` |
| `#921d55f966` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=5;medida=bajo_mediana;campo=ic_sup | `921d55f9668b08618774408a1747f2937ed82a418fbcb18e6e2be9e1e9e4cdb8` |
| `#f0684375c3` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=5;medida=bajo_mediana;campo=proporcion | `f0684375c31e5fc4fe2049fdf34c3feb755b09b76704b5762c12da5930428641` |
| `#37780f1a3c` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=5;medida=sobre_superior;campo=proporcion | `37780f1a3c47a53d5704da581951dd067e1c164f9d358b813ddbf54d4ffa0c14` |
| `#16169c860e` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=63;medida=bajo_inferior;campo=proporcion | `16169c860ef48af823de9caff573db407d5e13bf188b11ea778126780e2e2cdb` |
| `#1c268541d2` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=63;medida=bajo_mediana;campo=ic_inf | `1c268541d2dcd668d13fa384f13b69ea95316700aa632e3b34e2c49d179357a6` |
| `#972fa45c17` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=63;medida=bajo_mediana;campo=ic_sup | `972fa45c1787ab10e1a49b3543f0350edd108b32b1156963021c96f7573a9ac9` |
| `#22f03ce406` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=63;medida=bajo_mediana;campo=proporcion | `22f03ce406c9eb665241dc0e89d0b9ec2fa9790c5579fa3a774b09544c61accf` |
| `#5c8e552080` | dato | respaldo/prueba_final.json#posterior;asimetria;motor=bootstrap_est_filtrado;h=63;medida=sobre_superior;campo=proporcion | `5c8e552080d386ab3d6971ec3170b369eea4da77a8b5f3511dccd1f0d9b63b59` |
| `#bcf7261da5` | dato | respaldo/prueba_final.json#var_h1;modelo=lightgbm_cuantiles;cola=sup 1 %;campo=p_kupiec | `bcf7261da5abf6cd2d7ed44ab446624b07a2212b131adb99d160fbf0cb99cdf3` |
| `#2f175c3319` | dato | respaldo/prueba_final.json#var_h1;modelo=lightgbm_cuantiles;cola=sup 5 %;campo=p_kupiec | `2f175c3319034e83c2b873d263830cd7ca9fc75b1d17492888319118a72658e2` |
| `#e8f3aef896` | supuesto | caso.intervalo_meses@v1 | `e8f3aef89601ce0e8df6a0a123d7c41fe964a14a55dcc39543348667e548b0f6` |
| `#8397039538` | supuesto | caso.meta_usd@v1 | `8397039538ed21d4d3ef2ee2a37b8de2af6dbf38b4bed9a013cd92b85959ab0d` |
| `#b3a2ac0f21` | supuesto | caso.n_compras@v1 | `b3a2ac0f2109f278f71f2d65004c8cfbfcc40fc1d5637f8b20e2c5978e6f11e7` |
| `#61136fa9f8` | supuesto | caso.presupuesto_margen_pct@v1 | `61136fa9f8245b920d937de94d6bffb8d6c215415b83e6fd10360958cacc2156` |
| `#2650ef76b0` | supuesto | historica.desde@v1 | `2650ef76b0af622383773d906804fc0537f0077d65db2ef0ae36187b960949c8` |
| `#70cff49fb1` | supuesto | historica.ventana.2015@v1 | `70cff49fb1706bed7f9ef876a595d27e1e81a47a62e80e07af83a7b6346677a2` |
| `#74bb16f98f` | supuesto | historica.ventana.fin_2022@v1 | `74bb16f98f15542d5937d1710a9459778cbc0c7fd09cdee34f833fdb5096adfd` |
| `#9055dd1622` | supuesto | trm.deriva_anual_log.base@v1 | `9055dd16227c7dd045926bb9fa285b40ffde0d7d40d766daf5afe925a24b3fcb` |
| `#4b75c3bec3` | supuesto | trm.deriva_anual_log.estres@v1 | `4b75c3bec392b3dd1ef07bc94ba97a4dd355925c0113579bf36608706fe48216` |
| `#4f72a5af0e` | supuesto | trm.deriva_anual_log.optimista@v1 | `4f72a5af0ee7416979e60dd0a488d14fe714dc2db2a590d6843ac7092415ca13` |
