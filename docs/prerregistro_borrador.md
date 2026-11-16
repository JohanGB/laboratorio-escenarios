# Prerregistro de la prueba final — BORRADOR

**Estado: BORRADOR, sin confirmar por el autor (16-nov-2026).** Mientras este archivo se llame
`prerregistro_borrador.md`, el comando de la prueba final se niega a correr. Al confirmarlo se
renombra a `docs/prerregistro.md`, se recalculan los hashes de la sección 10 y se hace el commit
`prerregistro prueba final`. Después de ese commit no se cambia ni una coma del código ni de los datos.

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

## 2. Datos

- `data/processed/trm.csv` (1991-12-02 a 2026-11-14), `externas_diario.csv` y `tasas_diarias.csv`.
  Sus hashes están en la sección 10. **No se actualizan datos entre este prerregistro y la corrida.**
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
| markov_2, markov_3 | 21, 63 | 2 y 3 estados de varianza, normal, media cero, 4000 simulaciones |
| reg_cuantiles | 21 | regresión lineal por cuantiles, 10 variables |
| lightgbm_cuantiles | 63 | 14 variables; 150 árboles, tasa 0,03, 7 hojas, mínimo 100 por hoja, submuestreo 0,8, λ = 5 |
| bootstrap_est, bootstrap_est_filtrado | 21 | bloques de Politis-White, 4000 simulaciones, EWMA 0,94 |

La definición exacta es el código (`src/laboratorio/backtest/catalogo.py` y los valores por
defecto de cada clase), que queda dentro del hash. Corrida larga: los mismos, sin `reg_cuantiles`
ni `lightgbm_cuantiles`.

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

## 6. Motor del caso por horizonte

- El caso «compra de dólares» usa **`bootstrap_est_filtrado` en todos sus horizontes**, porque
  necesita trayectorias; `bootstrap_est` queda como análisis de sensibilidad.
- Donde la prueba confirmatoria tenga éxito, el campeón se cita como pronóstico de referencia de
  ese horizonte. Donde no, no se cita ningún modelo: solo el motor.
- **El motor no se cambia a la vista de los resultados.** Se publica la cobertura de su intervalo
  del 95 % en cada horizonte, con intervalo binomial exacto y n efectivo = n/h. Si 0,95 queda fuera
  de ese intervalo, el caso debe decirlo junto a cada cifra de ese horizonte.

## 7. Horizontes 126 y 252 (R5): solo descriptivos

De 2020 a 2026 caben unas 12 ventanas independientes de 126 días y unas 6 de 252. No hay
aprobado ni rechazado: se reporta la cobertura observada del 90 % y del 95 % con su intervalo
binomial. El caso lo dirá en cada cifra que dependa de esos horizontes.

## 8. Qué se publica pase lo que pase

`reports/prueba_final.md`, completo, con éxitos y fracasos:
declaraciones; las cuatro pruebas confirmatorias; la tabla del motor; por horizonte, CRPS y
coberturas de los 17 modelos, con covid 2020 y estrés 2022 aparte; VaR en dos colas; MCS;
Basilea; ES y Z2; PIT; acierto direccional; 126 y 252 con n efectivo. También los metadatos de
cada corrida (`runs/prueba_final/*.json`: tiempos, fallos de estimación, hashes) y el commit.
Después de la corrida no se ajusta nada; todo cálculo posterior se titula «análisis posterior
(no confirmatorio)».

## 9. Puertas revisadas

| puerta | cómo queda cerrada |
|---|---|
| Correr dos veces y quedarse con la mejor | `runs/prueba_final/HECHO.json` impide repetir; el comando no tiene opción de forzar |
| Cambiar el código tras ver algo | hash de `src/**/*.py`; si cambia un byte, el comando no carga los datos |
| Cambiar o actualizar los datos | hashes de los tres archivos |
| Otra versión de una biblioteca que mueva los números | hash del entorno (Python, numpy, pandas, scipy, statsmodels, arch, lightgbm) |
| Elegir la línea base o el campeón que convenga | fijados en la sección 5 y en el código |
| Elegir la métrica o el nivel de significancia | fijados en las secciones 4 y 5 |
| Rescatar un casi-acierto | regla escrita: es «no confirmado» |
| Cambiar de motor si le va mal | sección 6: no se cambia, se publica el límite |
| Quitar un modelo que falle al estimar | no se quita: conserva los parámetros anteriores y el número de fallos se publica |
| Redefinir los episodios | fechas fijas en `datos/limpieza.py` (dentro del hash) |
| Leer el reporte a conveniencia | el reporte solo contiene lo listado en la sección 8; sin sección de conclusiones libres |

Puertas que **no** se pueden cerrar y se declaran:
- Los datos ya fueron vistos en gráficos (sección 1).
- Si la corrida se cae por un error de programa, habrá que corregirlo y eso cambia el hash. En ese
  caso: no se abre ningún resultado parcial, la corrección se documenta como adenda a este
  prerregistro con el hash nuevo, y la corrida se reanuda.
- Poca potencia: ≈ 1700 días a h = 1, pero solo ≈ 27 ventanas independientes a h = 63. Un «no
  confirmado» a 21 o 63 días no prueba que el modelo sea inútil; solo que no hay evidencia.

## 10. Hashes, semilla y comando

Semilla de todos los modelos y del MCS: 20240501.

Provisionales (se recalculan al cerrar con `python -m laboratorio.backtest final --hashes`):

- `hash_codigo`: `62f98f3e3c8f84b630e7c25030bde3d07965ef2fb499435f0ea72a7a4ffc33cc`
- `hash_entorno`: `fd4c1314e5cc3e57`
- `hash_trm_csv`: `641393c5df0c869b`
- `hash_externas_diario_csv`: `c3cd56acdfdc01da`
- `hash_tasas_diarias_csv`: `5557495a88e94063`

Entorno: python 3.11.9, numpy 2.4.1, pandas 3.0.0, scipy 1.17.0, statsmodels 0.15.0, arch 9.0.0, lightgbm 4.7.0.

Comandos (y ningún otro):

```
PYTHONPATH=src python -m laboratorio.backtest final --verificar
PYTHONPATH=src python -m laboratorio.backtest final
```

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
