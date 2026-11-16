# Prerregistro de la prueba final

**Estado: CERRADO. Confirmado por el autor el 16-nov-2026** (respuestas en la sección 11). Queda
fechado por el commit `prerregistro prueba final` y su etiqueta de git `prerregistro-final`; sin
esa etiqueta el comando de la prueba final no corre. Desde ese commit no se cambia ni una coma
del código, de los datos ni de este texto. La única excepción es la adenda por error de programa
descrita en la sección 9, que se agrega al final con su propia etiqueta y no toca lo ya escrito.

Los rangos describen incertidumbre estadística; nada aquí es una recomendación financiera.

## 1. Qué es esta prueba y qué no es

- Es una evaluación **única** de los modelos de desarrollo sobre los datos desde 2020-01-01.
- Esos datos **no se usaron para elegir ni ajustar ningún modelo** (el código de desarrollo no
  puede cargarlos: `cargar_desarrollo` corta en 2020-01-01 y hay prueba).
- **No son datos nunca vistos (R2).** El análisis exploratorio (`reports/fase0.md`) y el caso
  «compra de dólares» ya mostraron la TRM de 2020 a 2026: el covid, el estrés de 2022 y la
  tendencia. El reporte final lo dirá con estas palabras y no la presentará como una muestra ciega.
- Las etiquetas de los episodios (covid 2020: 2020-02-20 a 2020-06-30; estrés 2022: 2022-06-01 a
  2022-12-31) se fijaron en la fase 0 mirando la serie. Solo sirven para mostrar resultados aparte.
- **La prueba final es el comando de la sección 10, corrido una vez, y nada más.** Llamar por
  separado a sus funciones (`cargar_prueba_final`, `correr_uno`, `confirmar`, `generar`) desde una
  consola o un cuaderno **no cuenta como prueba final**. Hacerlo antes de la corrida sería abrir
  los datos fuera del protocolo: no se hace, y si ocurriera se declara en el reporte.

## 2. Datos

- `data/processed/trm.csv` (1991-12-02 a 2026-11-14), `externas_diario.csv` y `tasas_diarias.csv`.
  Sus hashes están en la sección 10. **No se actualizan datos entre este prerregistro y la corrida.**
- **Tampoco se actualiza Python ni ninguna biblioteca** del entorno entre este prerregistro y la
  corrida: nada de instalar ni actualizar paquetes. El hash de entorno vigila las siete versiones
  de la sección 10; las demás dependencias tampoco se tocan.
- Orígenes de la prueba: desde el primer día de mercado de 2020 hasta el último que permite el
  embargo (63 observaciones en la corrida corta, 252 en la larga). Aproximadamente 1700 orígenes
  cortos y 1500 largos; el número exacto lo da la corrida.
- Ventana expansiva: en cada origen el modelo se estima solo con datos anteriores (desarrollo incluido).

## 3. Modelos (lista cerrada)

Entran los 17 de la corrida corta y los 15 de la larga: por la regla de C1 (estar en algún MCS o
superar a la base en algún horizonte en desarrollo) la cumplen todos los candidatos, y las líneas base
entran como referencia. Ninguno se agrega ni se quita después.

| modelo | reajuste | hiperparámetros (todos fijados antes; semilla 20240501) |
|---|---|---|
| caminata_aleatoria | 21 | sin parámetros |
| sim_hist_756 | 21 | ventana 756 |
| sim_hist_pond | 21 | toda la historia, λ = 0,994 |
| ewma_0.94 | 21 | λ = 0,94 |
| garch_t, gjr_t, egarch_t | 21 | (1,1) con t de Student, media cero, 4000 simulaciones, arranque en caliente, tolerancia de persistencia 1e-4 |
| gjr_skewt, egarch_skewt | 21 | igual, con t asimétrica de Hansen |
| fhs_ewma, fhs_gjr | 21 | residuos empíricos de toda la historia, 4000 simulaciones |
| markov_2 | 21 | 2 estados de varianza, normal, media cero, 4000 simulaciones |
| markov_3 | 63 | 3 estados de varianza, normal, media cero, 4000 simulaciones |
| reg_cuantiles | 21 | regresión lineal por cuantiles, 10 variables |
| lightgbm_cuantiles | 63 | 14 variables; 150 árboles, tasa 0,03, 7 hojas, mínimo 100 por hoja, submuestreo 0,8, λ = 5 |
| bootstrap_est, bootstrap_est_filtrado | 21 | bloques de Politis-White, 4000 simulaciones, EWMA 0,94 |

La definición exacta es el código (`src/laboratorio/backtest/catalogo.py` y los valores por
defecto de cada clase), que queda dentro del hash. Corrida larga: los mismos, sin `reg_cuantiles`
ni `lightgbm_cuantiles`.

«Reajuste» = cada cuántos orígenes (días de mercado) se vuelven a estimar los parámetros; entre
un reajuste y otro el modelo pronostica con los últimos parámetros y los datos del día.
`markov_2` se reajusta cada 21 y `markov_3` cada 63, igual en la corrida corta y en la larga y
igual que en desarrollo. La diferencia es de costo (cada estimación de `markov_3` tarda más de
2 segundos), no una elección hecha por resultados; `lightgbm_cuantiles` usa 63 por la misma razón.

## 4. Métricas y pruebas

- Pérdida principal: CRPS aproximado con los 11 cuantiles del protocolo (1 % a 99 %).
- Diebold-Mariano unilateral, varianza HAC (Bartlett, h − 1 + ⌊4(n/100)^(2/9)⌋ rezagos), corrección de Harvey-Leybourne-Newbold.
- Holm para la familia de pruebas confirmatorias, α = 0,05.
- Descriptivas: MCS (α = 0,10, estadístico de rango, 5000 réplicas, bloque máx(2h, 10), semilla 20240501),
  Kupiec y Christoffersen al 1 % y 5 % en ambas colas (h = 1), semáforo de Basilea, ES al 97,5 % con
  Z2 de Acerbi-Székely (umbral −0,70), ji-cuadrado del PIT, acierto direccional y coberturas.

## 5. Hipótesis confirmatorias y criterio de éxito por horizonte

Una hipótesis por horizonte. El «campeón» es el candidato de menor CRPS en el MCS de desarrollo;
la línea base es la mejor de desarrollo en ese horizonte. Los dos quedan fijos aquí.

| h | campeón | línea base | en desarrollo (CRPS/base; p con Holm) | qué esperamos |
|---|---|---|---|---|
| 1 | lightgbm_cuantiles | sim_hist_pond | 0,963; p < 0,001 | éxito |
| 5 | ewma_0.94 | sim_hist_pond | 0,988; p = 0,158 | no confirmado |
| 21 | ewma_0.94 | sim_hist_pond | 0,964; p = 0,158 | no confirmado |
| 63 | ewma_0.94 | caminata_aleatoria | 0,976; p = 0,158 | no confirmado |

- **Éxito en h** = el CRPS medio del campeón es menor que el de la línea base **y** el p-valor de
  Diebold-Mariano, ajustado por Holm entre las cuatro pruebas, es menor que 0,05.
- Cualquier otro resultado es **«no confirmado»**. No hay casi-aciertos: p = 0,051 es no confirmado.
- Si h = 1 no se confirma, la conclusión de desarrollo («solo a 1 día hay un modelo útil») se
  retira y el proyecto dirá que ningún modelo supera a las reglas simples.
- «Éxito» solo dice que el error promedio fue menor. No dice que las colas estén bien calibradas
  ni que la mejora sea grande: el tamaño se publica al lado (en desarrollo fue 3,7 %).
- Que otro modelo distinto del campeón resulte mejor en la prueba final es un hallazgo
  **exploratorio**: se publica en las tablas descriptivas y no cambia ninguna conclusión.
- **Línea de sensibilidad para h = 1 (descriptiva).** Debajo de la tabla confirmatoria el reporte
  repite la comparación de h = 1 **sin los orígenes de covid 2020 ni de estrés 2022**: CRPS/base,
  p-valor de Diebold-Mariano sin Holm y n. Sirve para ver si el resultado a 1 día depende de esos
  dos episodios. **No cambia el veredicto en ningún sentido**: ni rescata un «no confirmado» ni
  anula un «éxito». Al quitar orígenes la serie queda con saltos y ese p-valor es aproximado.

## 6. Motor del caso por horizonte

- El caso «compra de dólares» usa **`bootstrap_est_filtrado` en todos sus horizontes**, porque
  necesita trayectorias; `bootstrap_est` queda como análisis de sensibilidad.
- Donde la prueba confirmatoria tenga éxito, el campeón se cita como pronóstico de referencia de
  ese horizonte. Donde no, no se cita ningún modelo: solo el motor.
- **El motor no se cambia a la vista de los resultados.** Se publica la cobertura de su intervalo
  del 95 % en cada horizonte, con intervalo binomial exacto y n efectivo = n/h.
- **Advertencia de cobertura en el caso.**
  - A **63, 126 y 252 días va siempre**, salga como salga la cobertura, junto a cada cifra del
    caso que dependa de ese horizonte y con su n efectivo: unas 27, 12 y 6 ventanas independientes
    (el número exacto lo da la corrida). Con tan pocas, que 0,95 «quepa» en el intervalo no
    prueba que el rango esté bien calibrado.
  - A 1, 5 y 21 días va solo si 0,95 queda fuera del intervalo.
- **El respaldo al caso es indirecto.** El caso reparte la compra en 12 cuotas mensuales: la
  última cae a unos **230 días hábiles** y la cifra que reporta es el **costo total**, una suma
  sobre toda la trayectoria. La prueba final no evalúa ni ese horizonte ni esa suma: evalúa el
  rendimiento acumulado a 1, 5, 21, 63, 126 y 252 días, cada uno por separado. Dos límites:
  230 días queda entre 126 y 252, que son solo descriptivos (sección 7); y acertar cada horizonte
  por separado no garantiza acertar la trayectoria completa de la que depende el costo total.
  El caso lo dirá con estas palabras.

## 7. Horizontes 126 y 252 (R5): solo descriptivos

De 2020 a 2026 caben unas 12 ventanas independientes de 126 días y unas 6 de 252. No hay
aprobado ni rechazado: se reporta la cobertura observada del 90 % y del 95 % con su intervalo
binomial. El caso lo dirá en cada cifra que dependa de esos horizontes.

## 8. Qué se publica pase lo que pase

`reports/prueba_final.md`, completo, con éxitos y fracasos:
declaraciones; las cuatro pruebas confirmatorias y la línea de sensibilidad de h = 1; la tabla
del motor con sus advertencias; por horizonte, CRPS y
coberturas de los 17 modelos, con covid 2020 y estrés 2022 aparte; VaR en dos colas; MCS;
Basilea; ES y Z2; PIT; acierto direccional; 126 y 252 con n efectivo. También los metadatos de
cada corrida (`runs/prueba_final/*.json`: tiempos, fallos de estimación, hashes), `INICIADA.json`
(cuándo se abrió la prueba y cada reanudación), `HECHO.json` (SHA-256 de cada archivo de
resultados) y el commit.
Después de la corrida no se ajusta nada; todo cálculo posterior se titula «análisis posterior
(no confirmatorio)».

## 9. Puertas revisadas

| puerta | cómo queda cerrada |
|---|---|
| Correr dos veces y quedarse con la mejor | mientras exista `runs/prueba_final/HECHO.json` el comando no repite y no tiene opción de forzar (borrarlo: ver abajo) |
| Cambiar el código tras ver algo | hash de `src/**/*.py` (igual con fin de línea de Windows o de Unix); si cambia un byte, el comando no carga los datos |
| Editar este prerregistro después de fecharlo | `docs/prerregistro.md` debe ser idéntico al del commit con la etiqueta `prerregistro-final` (o, si hubo adenda, al de la última `prerregistro-adenda-N`) |
| Mover o borrar la etiqueta para tapar un cambio | la original debe existir siempre; las adendas se numeran sin saltos y cada una va en un commit posterior; una vez abierta la prueba, `INICIADA.json` recuerda dónde estaba la original y el comando no corre si se movió |
| Código o datos distintos de los fechados | `src/` y `data/` deben ser idénticos a ese commit y no tener archivos sin versionar |
| Cambiar o actualizar los datos | hashes de los tres archivos |
| Otra versión de una biblioteca que mueva los números | hash del entorno (Python, numpy, pandas, scipy, statsmodels, arch, lightgbm); no se actualiza nada (sección 2) |
| Reanudar una corrida con resultados de otro código | un resultado guardado solo vale si tiene los mismos hashes de código, entorno y datos; si no, ese modelo se corre de nuevo |
| Abrir la prueba sin dejar rastro | `runs/prueba_final/INICIADA.json` se escribe antes de leer los datos: hora, hashes y commit; cada reanudación se agrega |
| Mirar cifras mientras corre | el comando solo imprime el nombre y el estado de cada modelo; las cifras salen juntas en el reporte |
| Cambiar un resultado después | `HECHO.json` guarda el SHA-256 de cada archivo de resultados y del reporte |
| Elegir la línea base o el campeón que convenga | fijados en la sección 5 y en el código |
| Elegir la métrica o el nivel de significancia | fijados en las secciones 4 y 5 |
| Rescatar un casi-acierto | regla escrita: es «no confirmado» |
| Cambiar de motor si le va mal | sección 6: no se cambia, se publica el límite |
| Quitar un modelo que falle al estimar | no se quita: conserva los parámetros anteriores y el número de fallos se publica |
| Redefinir los episodios | fechas fijas en `datos/limpieza.py` (dentro del hash) |
| Leer el reporte a conveniencia | el reporte solo contiene lo listado en la sección 8; sin sección de conclusiones libres |

Puertas que **no** se pueden cerrar y se declaran:
- Los datos ya fueron vistos en gráficos (sección 1).
- **Borrar `HECHO.json`.** Si alguien borra ese archivo (o `INICIADA.json`, o la carpeta de
  resultados), el comando vuelve a correr. El código no puede impedirlo. Compromiso: no se borran;
  los dos archivos entran a git en el primer commit posterior a la corrida, y el reporte publicado
  es el de esa única corrida.
- **Funciones sueltas y lectores sin candado.** El candado está en `cargar_prueba_final`, pero
  nada impide importar funciones y llamarlas a mano (sección 1: no cuenta como prueba final).
  Además, dos partes del proyecto leen `trm.csv` completo sin candado: el análisis exploratorio
  (`reportes/fase0.py`) y el motor del caso (`motor/datos.py`). Son los «datos ya vistos» de la
  sección 1; ninguna de las dos calcula pronósticos ni los evalúa. La tubería de datos crudos
  (`datos/`) lee `data/raw/` y no se vuelve a correr antes de la prueba.
- **No correr el caso entre la etiqueta y la prueba.** El motor del caso agrega líneas a
  `data/supuestos/registro.jsonl`; eso ensucia `data/` y el comando se negaría a correr.
- Si la corrida se cae por un error de programa, habrá que corregirlo y eso cambia el hash. En ese
  caso: no se abre ningún resultado parcial; la corrección se documenta como adenda al final de
  este prerregistro con el hash nuevo; se hace un commit nuevo y a ese commit se le pone una
  **etiqueta nueva**, `prerregistro-adenda-1` (la siguiente sería `-2`, y así). **La etiqueta
  `prerregistro-final` no se mueve ni se borra**: el prerregistro original sigue fechado donde
  estaba. Luego la corrida se reanuda; los modelos que ya habían terminado con el código anterior
  se corren de nuevo y `INICIADA.json` anota la reanudación con su etiqueta y sus hashes.
- **Mover la etiqueta original antes de abrir la prueba.** Entre el cierre de este prerregistro y
  la primera corrida, el código no puede saber si alguien movió `prerregistro-final` (después sí:
  lo recuerda `INICIADA.json`). Compromiso: no se mueve; la historia de git la contradiría.
- Poca potencia: ≈ 1700 días a h = 1, pero solo ≈ 27 ventanas independientes a h = 63. Un «no
  confirmado» a 21 o 63 días no prueba que el modelo sea inútil; solo que no hay evidencia.

## 10. Hashes, semilla y comando

Semilla de todos los modelos y del MCS: 20240501.

Definitivos, calculados al cerrar (16-nov-2026) con `python -m laboratorio.backtest final --hashes`:

- `hash_codigo`: `3eb375386a72beb1365ab12bbc9060697464c83fa2a22c292189ff6920806336`
- `hash_entorno`: `fd4c1314e5cc3e57`
- `hash_trm_csv`: `641393c5df0c869b`
- `hash_externas_diario_csv`: `c3cd56acdfdc01da`
- `hash_tasas_diarias_csv`: `5557495a88e94063`

`hash_codigo` actualizado por la adenda 1 (sección 12), que cita el valor original; los otros cuatro no cambiaron.

Entorno: python 3.11.9, numpy 2.4.1, pandas 3.0.0, scipy 1.17.0, statsmodels 0.15.0, arch 9.0.0, lightgbm 4.7.0.

Cómo se cerró este prerregistro (hecho una vez, el 16-nov-2026, tras las respuestas de la sección 11):

```
git mv docs/prerregistro_borrador.md docs/prerregistro.md
PYTHONPATH=src python -m laboratorio.backtest final --hashes
git commit -am "prerregistro prueba final"
git tag prerregistro-final
```

Comandos de la prueba (y ningún otro):

```
PYTHONPATH=src python -m laboratorio.backtest final --verificar
PYTHONPATH=src python -m laboratorio.backtest final
```

Solo si hay una adenda (sección 9), con el texto de la adenda y los hashes nuevos ya escritos:

```
git commit -am "prerregistro prueba final: adenda 1"
git tag prerregistro-adenda-1
```

`--verificar` compara los cinco hashes y el estado de git sin leer ningún dato. El segundo comando
escribe `runs/prueba_final/INICIADA.json` antes de leer los datos, no imprime ninguna cifra
mientras corre y al terminar deja `reports/prueba_final.md` y `runs/prueba_final/HECHO.json`.

## 11. Preguntas al autor y sus respuestas

**Respondidas por el autor el 16-nov-2026:**

| pregunta | respuesta |
|---|---|
| 1. Datos ya vistos | sí |
| 2. Una sola vez | sí |
| 3. Cuatro pruebas, una por horizonte | sí |
| 4. Éxito pequeño | sí |
| 5. Motor del caso | sí |
| 6. Seis meses y un año, solo descriptivos | sí |
| 7. Datos congelados (y tampoco Python ni bibliotecas, sección 2) | sí |
| 8. Si el programa falla | sí, con una condición: «la adenda crea una etiqueta nueva (prerregistro-adenda-1, -2…) y la original no se mueve ni se borra» |

La condición de la pregunta 8 ya está en la sección 9 y en el código. Las preguntas, tal como se hicieron:

1. **Datos ya vistos.** ¿Aceptas que el reporte diga «datos no usados para elegir modelos, pero ya
   vistos en gráficos»? Ejemplo: ya vimos en las figuras cómo se movió el dólar en 2020; lo que
   nadie ha visto es si el rango que cada modelo daba para el día siguiente (digamos, de 3.960 a
   4.040 pesos con el dólar a 4.000) acertó o no.
2. **Una sola vez.** ¿Aceptas que la prueba se corra una única vez y se publique aunque salga mal?
   Ejemplo: si LightGBM resulta peor que la regla simple, el reporte dirá «no confirmado» y no se
   prueba otro ajuste para arreglarlo.
3. **Cuatro pruebas, una por horizonte.** ¿Aceptas estas cuatro y solo estas: LightGBM a 1 día, y
   EWMA a 5, 21 y 63 días, cada una contra su regla simple? Como son cuatro intentos, se exige
   evidencia más fuerte en cada uno (Holm). Esperamos éxito solo a 1 día.
4. **Éxito pequeño.** ¿Aceptas que «éxito» signifique solo «menor error promedio», aunque la mejora
   sea chica? Ejemplo: con el dólar a 4.000 pesos, el error típico de la regla simple a 1 día es de
   unos 15 pesos; la mejora de LightGBM en desarrollo (3,7 %) equivale a cerca de medio peso.
5. **Motor del caso.** ¿Aceptas que el caso use el bootstrap filtrado en todos los horizontes y que
   **no se cambie** aunque le vaya mal? Ejemplo: si el caso dice «en un año el dólar estaría entre
   3.400 y 5.000 pesos con 95 %» y la prueba muestra que rangos así acertaron 85 % de las veces, la
   cifra llevará esa advertencia al lado; no buscaremos otro motor.
6. **Seis meses y un año, solo descriptivos.** ¿Aceptas que a 126 y 252 días no haya «aprobado» ni
   «rechazado»? Ejemplo: de 2020 a 2026 solo caben unos 6 años completos; con 6 casos, acertar 5
   o 6 no distingue un rango bueno de uno malo.
7. **Datos congelados.** ¿Aceptas no actualizar la TRM hasta después de la prueba? Ejemplo: aunque
   mañana se publique la TRM de 4.050 pesos, no entra; si entrara, el comando se negaría a correr.
8. **Si el programa falla.** ¿Aceptas que, si la corrida se cae por un error de programa, se corrija
   sin mirar resultados parciales y se anote como adenda con el hash nuevo? (Al preguntarla se
   precisó: con un commit nuevo y su etiqueta.)

## 12. Adenda 1 (16-nov-2026): error de programa en el primer ajuste GARCH

**Qué pasó.** La primera corrida de la prueba final (abierta el 16-nov-2026; `INICIADA.json`) se
detuvo con `RuntimeError: la primera estimación GARCH no convergió` (`modelos/garch.py`) al estimar
`gjr_skewt`, el duodécimo modelo de la corrida corta. Habían terminado once modelos; no se generó
reporte ni `HECHO.json`. El registro de la consola no nombra el modelo; se dedujo del orden fijo
del catálogo.

**Causa.** En la prueba final cada modelo empieza sin parámetros: su primer ajuste es en frío
sobre toda la historia hasta el primer origen y, si no converge, el código no tenía a qué volver.
En desarrollo eso solo ocurrió el 2005-01-04, donde convergió; los demás ajustes arrancaron en
caliente. Con datos de desarrollo se comprobó que el arranque en frío de GJR con t asimétrica es
frágil: falla en 9 de los últimos 250 días de desarrollo y en 2 de los 167 reajustes (`gjr_t`,
en 1), siempre con SLSQP «Positive directional derivative for linesearch».
**Declaración:** con datos hasta 2019-12-31 ese ajuste en frío sí converge. La falla la
desencadenó la única observación de 2020 que entra en el primer ajuste (el rendimiento del primer
día de mercado de 2020). Lo único que se supo de 2020 es eso: que ese optimizador no convergió.

**Cómo se decidió.** Solo con el mensaje de error, el orden de los modelos y datos de desarrollo
(`cargar_desarrollo`). No se abrió ninguna cifra de la corrida abortada ni se leyó ningún dato
de 2020 en adelante. La corrección no depende de ningún resultado.

**Corrección (solo el primer ajuste de cada modelo GARCH, incluido el filtro de `fhs_gjr`).**
1. Arranque en frío de `arch`, como antes.
2. Si falla, la lista cerrada de vectores iniciales de abajo, en orden (rendimientos en %; orden
   de `arch`); gana el primero que converja y pase la validación de siempre.
3. Si nada sirve, lo mismo quitando la última observación, una a la vez, hasta 21 (solo datos
   anteriores, nunca posteriores).
4. Si aun así nada converge: error, el modelo no es estimable y haría falta una adenda 2.
El `.json` del modelo anota `primer_ajuste` (vector y recorte) solo si se usó esta regla. Los
ajustes siguientes siguen la regla prerregistrada (caliente → frío → conservar los anteriores).
Con datos de desarrollo, la lista rescata los 11 ajustes fallidos; V1 y V2 convergen en todos los
tipos probados; V3 de EGARCH a veces termina con ν > 200 o sin converger y la validación lo
rechaza. Todos tienen persistencia < 1 (hay prueba) y esta tabla es la del código (hay prueba):

| tipo | vector | ω | α | γ | β | ν | λ (solo skewt) |
|---|---|---|---|---|---|---|---|
| GARCH | V1 | 0,01 | 0,05 | — | 0,9 | 8 | 0 |
| GARCH | V2 | 0,005 | 0,1 | — | 0,89 | 5 | 0 |
| GARCH | V3 | 0,02 | 0,03 | — | 0,94 | 10 | 0 |
| GJR | V1 | 0,01 | 0,05 | 0,05 | 0,9 | 8 | 0 |
| GJR | V2 | 0,005 | 0,1 | 0 | 0,89 | 5 | 0 |
| GJR | V3 | 0,02 | 0,03 | 0,03 | 0,94 | 10 | 0 |
| EGARCH | V1 | 0 | 0,1 | -0,05 | 0,98 | 8 | 0 |
| EGARCH | V2 | 0 | 0,15 | 0 | 0,95 | 5 | 0 |
| EGARCH | V3 | 0 | 0,05 | -0,02 | 0,99 | 10 | 0 |

**Candado.** Reanudar con hashes distintos de los de la entrada anterior de `INICIADA.json` solo
se permite si la etiqueta vigente es una adenda nueva y su sección en este documento escribe cada
hash que cambió (con prueba sintética). El candado verifica contra la etiqueta de adenda más
reciente (con prueba sintética).

**Desarrollo idéntico.** Los 6 modelos afectados (`garch_t`, `gjr_t`, `egarch_t`, `gjr_skewt`,
`egarch_skewt`, `fhs_gjr`) se corrieron con datos de desarrollo con el código de
`prerregistro-final` (antes) y con el corregido (después). SHA-256 del CSV descomprimido (el
`.csv.gz` guarda la hora): antes = después = resultados archivados en `runs/backtest_desarrollo/`
y `runs/backtest_largo/`; `.json` sin `segundos`: antes = después. Cero diferencias.

| corrida | modelo | archivo | SHA-256 (CSV descomprimido) | antes = después = archivado |
|---|---|---|---|---|
| corta | garch_t | principal | `3ddc566617a8e53b2b7ed22f5ba442017b8ce2ca710b8836de24d126be7b9a22` | sí |
| corta | garch_t | cola | `f009593cc7c1f28944a69ab3ac03cf45f679add5a320c14a8166a20a179ceddc` | sí |
| corta | garch_t | .json sin `segundos` | `f9d7084723baaffe26686c397d5444972e35c4cfac4b71f861090d889c2b4295` | sí (antes = después) |
| corta | gjr_t | principal | `fcf460284458ced02bc34383775536e1ed771162f6d062dba1b6659632d95873` | sí |
| corta | gjr_t | cola | `8ec683ac005f4b62e3e8ddacb2ca2842a879a21ec07e8161c34554e491bb9709` | sí |
| corta | gjr_t | .json sin `segundos` | `65b7c073851806efeb9813dd953150fc32b7a404eefdfc782ecb5bdde5950ba9` | sí (antes = después) |
| corta | egarch_t | principal | `7f87e1b8209ca364a2817c2c3e09a092c9c31e66447d2789ecd98ae6eefca4db` | sí |
| corta | egarch_t | cola | `bbc3a6feea1b36902a443550bec62f852acfbac8d359ac7fb8d8079310db8cc1` | sí |
| corta | egarch_t | .json sin `segundos` | `8895909c6089a175515383d04c013a5b2f60e2ca9e379c38c424e6fbfd5132a3` | sí (antes = después) |
| corta | gjr_skewt | principal | `bc2ef041737684a17d19582f724f5d789fe108677c1c2748a070755400d18ee0` | sí |
| corta | gjr_skewt | cola | `9f4cf9a35a770c8531f5d09100b4ac710c5037ba3866a2fb7eb5e65ff1c91638` | sí |
| corta | gjr_skewt | .json sin `segundos` | `4424b47a5bcb2275ef4cc22e2caa20d373a7fc2d2c2f7f0ee92f3f78c9d70f6b` | sí (antes = después) |
| corta | egarch_skewt | principal | `29843c0295e89f1ce685f6ed212e07d67c3cd42bf10c8e94752929781e586d9f` | sí |
| corta | egarch_skewt | cola | `ea3ad39899f63aaf2c745eecac5fc0bf5f9f47fcfd77f3f682786a017f4680ae` | sí |
| corta | egarch_skewt | .json sin `segundos` | `28361851bccf378e2e8200bdff57b44caccdd422a2361cabb853944e7f05a0de` | sí (antes = después) |
| corta | fhs_gjr | principal | `8bb5231823c0d40e33ec9706d17380b06e48afd18c0e782075f64fd771d4cce1` | sí |
| corta | fhs_gjr | cola | `c9bbf0b09b3294d0056e0d91ba8b39347f56a6c3647314cd80da3d07e6bd14cc` | sí |
| corta | fhs_gjr | .json sin `segundos` | `90dd72167db72dcffaca6989dc31532aafe86874effdea139c907daab137c1b1` | sí (antes = después) |
| larga | garch_t | principal | `6b499b0deb271b5f57f49f83dddfc15d4287b3f8910f47a325d4db6faa12abfa` | sí |
| larga | garch_t | .json sin `segundos` | `62a3c39d3a62dd85b9292fa1a9c056001227a80e43ef3cc376bbdd963a40b222` | sí (antes = después) |
| larga | gjr_t | principal | `3f385cbebcd16872051aabb6440a8614a2ba9ffc65570810bb216a3015f2a77a` | sí |
| larga | gjr_t | .json sin `segundos` | `725f9590b7f124d15246dc22e6be309da1241009de06c73e159f6268743bc25e` | sí (antes = después) |
| larga | egarch_t | principal | `f00ec625de103c3daf84dff43e090ef7c8f2d6ddc41a5783be4d05af332a7a88` | sí |
| larga | egarch_t | .json sin `segundos` | `8db2351bbb33cc965353d79e2ea045f0b0f2479be9d4383a245af02c2db47ceb` | sí (antes = después) |
| larga | gjr_skewt | principal | `90f0ca6b096981aae568a06d0b5064c1b53349e31c31d6382c15ef2d5d8c47d3` | sí |
| larga | gjr_skewt | .json sin `segundos` | `59cd940185da270d875ca66fd7c0750cb13ba3329b8f64490280fad4b1e19618` | sí (antes = después) |
| larga | egarch_skewt | principal | `d06b01b8135c0e4da6bd6562b2cda80065306eaa14058a08252b88e31a9ad39a` | sí |
| larga | egarch_skewt | .json sin `segundos` | `3221da1302f03719a59576b52e8f6c020877aa6167c524a033a9796844df4c4e` | sí (antes = después) |
| larga | fhs_gjr | principal | `f54b0712a2f1e71cc64793c90cf044af4468036bab5c397b23c72c212b748a57` | sí |
| larga | fhs_gjr | .json sin `segundos` | `d748caf32319464e14ac5070764c531ec5cdba36922a677998eb2ad8146f9cac` | sí (antes = después) |

**Resultados de la corrida abortada.** Movidos sin abrir a `runs/prueba_final_abortada_1/`, con
el registro de la consola (`registro.log`). Los `.csv.gz` no entran a git (`.gitignore`); quedan
fechados por esta tabla. Tras la corrida nueva, el CSV descomprimido de cada uno de estos modelos
debe coincidir con el de la corrida nueva; si no, se detiene todo. `INICIADA.json` se queda en
`runs/prueba_final/` (sección 9): la reanudación se anota ahí. Todos los modelos se corren de nuevo
porque cambió `hash_codigo`.

| archivo | SHA-256 del archivo | SHA-256 del CSV descomprimido |
|---|---|---|
| bootstrap_est.csv.gz | `900aca2720d42b99fb620e4fde60c36cdac83589ad975b0c4343767541991b55` | `f32e7a6dd0b1aeb6d715aa3f9121bb741abc5761134701fe323f9ea0995e284b` |
| bootstrap_est.json | `c55e3a5e182798a92b62bafb9c65b0c5173e0373e8a0e0d1c76bda17946faf82` | — |
| bootstrap_est_filtrado.csv.gz | `9f321ef39df5c183760723f7d22f148f89b8f3724d19376d996fc1d7e23b4842` | `b41570bba4b906dd8e6e5cc58d36eb56c758f7c2d8c452e4c99145c1131a9a1f` |
| bootstrap_est_filtrado.json | `9cb0fe3648abee503bec3f449c41ed2e7330e644ca80fa617e46778e51c6cb64` | — |
| caminata_aleatoria.csv.gz | `a1a6f06c9b6d16328bb90e6e81a3871dec6f16015e051cdb769b0e378ecd9cd3` | `2dd89687a3cac34557587a739037a4df92fa29178068432d10ef9a51aa82d6a0` |
| caminata_aleatoria.json | `1cfa44a5203f1d6bce06376fb5413d07f07233e47d21b5c6676b8c2c51045a4f` | — |
| cola/bootstrap_est.csv.gz | `6b373eac0a80c9a1d279760d1ea5129edea8db5ecfc1a1e306b9622d83a4aeff` | `641460fd4b4e18b3031c9f345c4da9575be0ba888eec8d61031ef04b082fa849` |
| cola/bootstrap_est_filtrado.csv.gz | `45c15ecf4cccc44c849b0b54e28538fea84b2bf16291b8c8187eacf7b567edd1` | `1fdc5374ce56cc86413804e9c6febfad27c9b0b7723546556f8a0c5d0154cfc4` |
| cola/caminata_aleatoria.csv.gz | `0da81a2327abe8ec51c62f672165d210a336e182d382868bbeaac0ceb487571b` | `053e991c9c07e9253f6d9a04f2b0620d6b534e5f55745838002b48132f7b1e3b` |
| cola/egarch_t.csv.gz | `73e7c879e0251a023e96644b387184f0f753cb9f6a6323ad40b69d8cd5e5dc4f` | `86cd451463806d68c0a540355535ce620100449930c0142c637e50fd47da9908` |
| cola/ewma_0.94.csv.gz | `3782730990615ac83c6eb9607efd5f28306711bfe7d5817669503a9db4775f8e` | `5cf289a366850965850b3f18640995c30cf3a1011dd28ca1fc906e04e696079e` |
| cola/garch_t.csv.gz | `468ad5efa6960729fad6cce452f367c0f7f5f967fbeac07f43009286b8427ce8` | `89a3dd1bc21f7c100b28a6c4c554d29f387225584d2bc98fc3999b89fa891e46` |
| cola/gjr_t.csv.gz | `7a694807d7333d4a4418e5cc02f3108e7b3a4ec2d858339c05866b2f52f26a9a` | `d3beb73a815e31a38dd5124c67a132f543c06202760471a6339954a2fab5af4f` |
| cola/sim_hist_756.csv.gz | `21d72569a490ec18b86e56b775bb517a2aa1499a409154b3e474d94618373358` | `c226faf63719982220aa04594222e982cda855257b62ccab13c344cc85164707` |
| cola/sim_hist_pond.csv.gz | `3aefdaeff4595027314156784d59ae717a6f778a68c900c86168df09caa64106` | `686c455cea41df2285482a83e82a024f1f24994100d02705ceb773ad153080ff` |
| egarch_t.csv.gz | `71c0c483900ed5cbfdf81337ff5383d9641c026de3eada6d117b75a800b26d02` | `4f3122e028e5db0714933dadd5df42f1a0215482af775ae6bc804ef1895381ad` |
| egarch_t.json | `a355accee8423c7bcbcce1f22ef0ee2d97a3bff2c06f985550dbf274deab1a5e` | — |
| ewma_0.94.csv.gz | `27a1182027f934bec62540360caaaeea1a9dd992a9b1be234f797cb181651a73` | `de3e79f83df0d9ca415b8bab6c89321e869a1ca6124401326e7557c25cb6dba7` |
| ewma_0.94.json | `6bafa1e9acc276b447fe3dd55d2545b9823c982dbb3d5e7bf4639d37ba0ec335` | — |
| garch_t.csv.gz | `be7ba55af0849ecffca491a9b2f71abaac4c790dcac3600fa26b1ec0ef4c2abf` | `63f740f239b5f96655465e5bce1ebcd4f11af303a26219992cf3384643c6c838` |
| garch_t.json | `d9b7faa13665a70092b6604103e7a8b15dd003d3d677c8653770b09f63f41ef1` | — |
| gjr_t.csv.gz | `08392e4a7b5083a8895efb102164176dea3754374844be2e6298cda117640fe2` | `ee2f6f46161a3561dfcd2c643f54e21e145d35c49c1f14ed7bce1472d269adf1` |
| gjr_t.json | `5c60ff657db53ee5168303eb1879856b0e10f7fe8ed055618c6440df81d69c75` | — |
| lightgbm_cuantiles.csv.gz | `83bc8bdecd63b76e35be6d33813d4655278544346f45772312d216c3d518eb70` | `40e095321475ff8e3628d62730952b52fb69ad90d640c04d13c4f2e8ae278a6c` |
| lightgbm_cuantiles.json | `4df1cc7ed7a51583daa5591a7c20ddb2a548daed69bdc48d0e0d426aaae90a5e` | — |
| reg_cuantiles.csv.gz | `d44d8b25aeaa7f346a79d6a2d276541dca3077839f2a35b6be71323f2c2e575e` | `2a16e4dbe22aa4136214846047d54857072872787b01e2f114b99fe356d8a68f` |
| reg_cuantiles.json | `2592d9bfccfa91e7ad5448d32535e88fb2dff57b2a6838198a7bc6282468db14` | — |
| sim_hist_756.csv.gz | `576f4d2be8f90226dfd2bad91ed2529d60a1cf872b823acaa9ada7a12b089aab` | `ecaa0aaf22f92f42d2c561f9d90b581e98b3b1a325a5c52ea58b7ec37c6b2611` |
| sim_hist_756.json | `957764721a687bb2e3a5953f8200daf32208a59ddc39e75fb4dc5b753cc90fa7` | — |
| sim_hist_pond.csv.gz | `2258a547388fb7b9727a9ebfb95eee5f047762e3c3d71f9fb39558dd9a8cc8a2` | `8a60634fd25c3c1cb8e8d37d931f904160afa1a813a2f31e0d6d052dede4d787` |
| sim_hist_pond.json | `131129c5ee67d9a92fc1833d19b3af8ca27cc7a2b1c9d3d33961612f0831dd50` | — |
| registro.log | `81b1759cb511b4203406b61c3b1662eb3db0b17641b29e20b48012e45f3683ea` | — |

**Hashes.** `hash_codigo` original (sección 10 al fechar `prerregistro-final`):
`a3c3ea0da8b84ba0da40297dd3e060ee85fcf52eee1cb43db5ed3a02243301c4`. `hash_codigo` nuevo, ya escrito en la sección 10: `3eb375386a72beb1365ab12bbc9060697464c83fa2a22c292189ff6920806336`.
`hash_entorno` y los tres hashes de datos no cambian. La línea de `hash_codigo` de la sección 10 se
editó (sin claves repetidas), con autorización del autor, y debajo se agregó una frase que remite
a esta sección; son los únicos cambios fuera de ella.

**Etiqueta.** Commit «prerregistro prueba final: adenda 1» con la etiqueta nueva
`prerregistro-adenda-1`. `prerregistro-final` no se mueve ni se borra.
