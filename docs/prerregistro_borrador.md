# Prerregistro de la prueba final — BORRADOR

**Estado: BORRADOR, sin confirmar por el autor (16-nov-2026).** Mientras este archivo se llame
`prerregistro_borrador.md`, el comando de la prueba final se niega a correr. Al confirmarlo se
renombra a `docs/prerregistro.md`, se recalculan los hashes de la sección 10, se hace el commit
`prerregistro prueba final` y a ese commit se le pone la etiqueta de git `prerregistro-final`
(sin la etiqueta el comando tampoco corre). Después de ese commit no se cambia ni una coma del
código, de los datos ni de este texto.

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

Provisionales, recalculados el 16-nov-2026 tras los últimos cambios de código (se vuelven a
calcular al cerrar con `python -m laboratorio.backtest final --hashes`; si nadie toca `src/` ni
los datos, salen iguales):

- `hash_codigo`: `a3c3ea0da8b84ba0da40297dd3e060ee85fcf52eee1cb43db5ed3a02243301c4`
- `hash_entorno`: `fd4c1314e5cc3e57`
- `hash_trm_csv`: `641393c5df0c869b`
- `hash_externas_diario_csv`: `c3cd56acdfdc01da`
- `hash_tasas_diarias_csv`: `5557495a88e94063`

Entorno: python 3.11.9, numpy 2.4.1, pandas 3.0.0, scipy 1.17.0, statsmodels 0.15.0, arch 9.0.0, lightgbm 4.7.0.

Cierre del prerregistro (una vez, cuando el autor responda la sección 11):

```
git mv docs/prerregistro_borrador.md docs/prerregistro.md
PYTHONPATH=src python -m laboratorio.backtest final --hashes     (y pegar aquí si algo cambió)
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

## 11. Preguntas para el autor (sí o no)

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
   sin mirar resultados parciales y se anote como adenda con el hash nuevo?
