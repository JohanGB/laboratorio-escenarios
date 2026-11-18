# Decisiones

Formato: fecha · decisión · alternativa descartada · motivo. Las decisiones previas a F1 siguen en
`docs/estado.md` y en los docstrings; se trasladan aquí en A1 (paso 3).

## 15-nov-2026 · F1 (cimientos)

- **Git sin conversión de fin de línea** (`core.autocrlf=false`, `.gitattributes: * -text`).
  Descartado: el valor por defecto de Windows. Motivo: cambiaría bytes al clonar y rompería los
  SHA-256 de `data/raw/` y el hash de código de las fichas.
- **`data/raw/` se versiona** (4,0 MB < 10 MB). `.playwright-mcp/` se ignora; borrarlo queda para A1.
- **Autor git genérico «analista»**, configurado solo en este repositorio. Motivo: privacidad.
- **N5, sin cambios en el código.** Cifras (desarrollo, 1991-12-02 a 2019-12-31):
  `dolar30` es NaN hasta el 2006-02-08 (la serie empieza el 2006-01-02, más 8 días de rezago y
  30 de ventana): 263 orígenes de 2005-2006 y 3216 filas de entrenamiento de 1992-2006. `pol90`
  es NaN hasta el 1998-05-14: 0 orígenes y 1344 filas de entrenamiento. `brent30`, `fed` y
  `fed90` no tienen NaN. La regresión por cuantiles no usa `dolar30`, `pol` ni `pol90`.
  LightGBM las usa con NaN nativo (aprende una rama por defecto para el faltante). El NaN de la
  fila t depende solo de si el dato ya estaba publicado en t, así que no hay información futura.
  Riesgo que queda: «falta el dato» se vuelve una señal de época (antes o después de 2006); es
  causal, pero puede confundirse con el régimen. Canario nuevo:
  `test_lightgbm_sin_fuga_con_series_externas_que_empiezan_tarde`.
- **R1: corrida larga aparte** (`FABRICAS_LARGOS`, `--largo`, `runs/backtest_largo/`, embargo de
  252: 3304 orígenes hasta el 2018-12-11). La corrida corta conserva sus 3493 orígenes (hay
  prueba). Entran caminata, simulaciones históricas, EWMA, GARCH/GJR/EGARCH y los dos bootstrap.
  Descartados: regresión por cuantiles y LightGBM, porque a 252 días entrenarían con ≈ n/252
  objetivos independientes, muy traslapados. Correrla queda para O3.
- **R4: `NIVELES_COLA`** con ambas colas (0,0025…0,025 y sus espejos). Descartado: solo la cola
  inferior. Motivo: la cola superior es el alza del dólar, ya subcubierta a h=1.
- **Bootstrap estacionario, dos variantes**:
  - *Simple*: rendimientos de toda la historia, banda incluida. Descartado: solo desde la
    flotación (1999-09-25). Motivo: conserva 1997-1999 como evento extremo y es coherente con
    «la banda no se excluye».
  - *Filtrado*: residuos z = r/σ_EWMA de toda la historia, reescalados con una volatilidad que
    parte de la del origen y vuelve a la de largo plazo con persistencia ρ estimada a 21 pasos
    (≈ 0,984 en 2018). Descartados: σ del origen constante hasta 252 días (sobreestima tras un
    choque) y una recursión GARCH aleatoria (duplicaría la agrupación de volatilidad que ya
    traen los bloques y es terreno de O1/FHS).
- **Longitud de bloque = máx(PW sobre la serie, PW sobre |serie|)**. Descartado: PW solo sobre
  la serie. Motivo: los rendimientos casi no tienen autocorrelación lineal (bloque ≈ 6-8) pero
  su volatilidad sí (|r|: 93-180). Con bloques de 7 días, la agrupación de volatilidad se pierde
  y las colas a 126-252 días salen estrechas. Tope: min(3√n, n/3).
- **Remuestreo circular** (Politis-Romano): un horizonte mayor que la historia disponible no falla.
- **Estos modelos nacen de mirar el desarrollo** (los hallazgos de la fase 2: cola superior
  subcubierta, IGARCH). Cuentan como búsqueda: el MCS (F2) y la corrección de Holm deben
  comparar el conjunto completo de candidatos, incluidos los dos bootstrap, no solo el ganador.

## 15-nov-2026 · O1 (GARCH estable y cola superior)
- **Arranque en caliente con respaldo en frío.** Se parte de los parámetros del reajuste anterior;
  si falla, se reintenta con los valores iniciales de `arch`. Descartado: solo caliente (un mal
  óptimo previo se arrastraría). La escala ×100 ya existía y no se tocó.
- **Causa real de los fallos: tolerancia, no convergencia.** El arranque en frío reproduce los 38
  fallos de GARCH y 28 de GJR de la fase 2; todos los de GARCH eran `explosivo`: SLSQP converge a
  la frontera IGARCH con holgura ≈ 1e-5 (p. ej. α+β = 1,00001) y el código rechazaba > 1 + 1e-6.
  Decisión: tolerancia 1e-4 (`TOL_PERSISTENCIA`). Descartados: proyectar a α+β = 1 exacto
  (cambia parámetros que el optimizador sí eligió) y dejarlo como fallo (conserva parámetros
  viejos que también son IGARCH). Efecto: varianza a 252 pasos a lo sumo +2,5 %. Resultado
  (167 reajustes): GARCH 38 → 0, GJR 28 → 1, GJR-skewt 32 → 1, EGARCH 0 → 0 (los que quedan son
  `no_convergio`). El caliente solo, sin la tolerancia, apenas baja a 36 y 25. Persistencia = 1
  en todos los reajustes de GARCH/GJR: son IGARCH en la práctica, con α ≈ 0,18-0,20 (EWMA: 0,06).
  Cifras en reports/o1_convergencia.md. Los CSV de garch_t/gjr_t/egarch_t de la fase 2 quedan obsoletos:
  O3 debe correrlos con `--forzar`.
- **t asimétrica (`skewt` de Hansen, la de `arch`) para GJR y EGARCH.** Simulación por inversión
  de la CDF (`ppf`) con generador por origen. Persistencia del GJR-skewt reportada como α+γ/2+β
  (exacta solo con innovaciones simétricas; es un indicador).
- **FHS con dos filtros** (EWMA 0,94 y GJR-t), residuos empíricos de toda la historia (banda
  incluida, coherente con el bootstrap), sin renormalizar a varianza 1 (FHS clásica). h = 1
  exacto (σ·cuantil empírico); h > 1 trayectorias con la recursión del filtro. Descartado:
  ventana de residuos (otro hiperparámetro elegido mirando el desarrollo).
- **Búsqueda.** gjr_skewt, egarch_skewt, fhs_ewma y fhs_gjr nacen de mirar el desarrollo (cola
  superior subcubierta, IGARCH): el MCS de F2 los compara junto con todo el catálogo.

## 15-nov-2026 · O2 (Markov)
- **MarkovRegression de statsmodels, 2 y 3 estados de varianza, normal, media cero, r·100.**
  Filtro de Hamilton propio (igual a statsmodels, hay prueba) para pronosticar con parámetros
  fijos y verificar la causalidad. Estados ordenados por varianza en cada reajuste.
- **`maxiter=500`** (statsmodels trae 50): con 3 estados y 600 datos sintéticos no convergía con 50.
- **Reajuste:** 2 estados cada 21 (≈ 0,5-1,4 s por estimación); 3 estados cada 63 (7-15 s), por
  la regla de los 2 s de B2.
- **h = 1 exacto** (cuantiles de la mezcla de normales por bisección); h > 1 trayectorias de
  estado. Descartado: mezcla con las probabilidades proyectadas a h pasos (ignora que la varianza
  acumulada depende de la trayectoria).
- **Diagnóstico** (reports/o2_markov.md): el estado alto domina en 2008 y 2014-2015; con 2 estados
  separa sobre todo banda vs. flotación. Ambas variantes van al backtest; decide el MCS.

## 15-nov-2026 · F2 (pruebas que faltan)
- **ES desde la corrida (decisión A, confirmada por el autor).** El corredor pide en UNA llamada
  `NIVELES` + `NIVELES_COLA` + una rejilla de 25 puntos medios por cola (α = 0,025) y guarda
  `runs/backtest_desarrollo/cola/<modelo>.csv.gz` (c_<nivel>, es_inf, es_sup). Mismas
  simulaciones: la tabla principal y el CRPS no cambian (hay prueba). Error de la rejilla frente
  a la normal exacta < 0,5 %. Regresión por cuantiles y LightGBM: ES «no aplica» (un modelo por
  nivel, entrenados solo para los 11 niveles). Sin cola en la corrida larga.
- **Z2 de Acerbi-Székely solo a h = 1**, contra los umbrales del artículo (−0,70 al 5 %); sin
  p-valor exacto porque no se guardan las simulaciones.
- **Uniformidad del PIT: ji-cuadrado por casillas (decisión B; el autor delegó la elección).**
  Descartada: Kolmogorov-Smirnov sobre el PIT interpolado. Motivo: con 11 cuantiles el PIT no
  se conoce por debajo de 1 % ni por encima de 99 %, y KS dependería de cómo se rellenen las
  colas, que es justo lo que interesa. La ji-cuadrado es exacta a h = 1; a h > 1 usa n/h, fusiona
  casillas con < 5 esperadas y se marca «aproximada». El PIT interpolado queda para figuras.
- **MCS**: `arch.bootstrap.MCS`, α = 0,10, estadístico de rango, bootstrap estacionario, 5000
  réplicas, bloque máx(2h, 10), semilla fija, orígenes comunes. Compara todo el catálogo, líneas
  base incluidas. Columnas idénticas se calculan una vez (arch falla con varianza cero).
- **Acierto direccional solo a h = 1** (binomial y Pesaran-Timmermann), con la mediana como
  pronóstico; ceros descartados. En modelos de media cero que simulan, la mediana es ruido.
- **Horizontes largos**: cobertura 90 % y 95 % con Clopper-Pearson y n/h; descriptivo, sin MCS.
- **Alcance (decisión C)**: el reporte de fase 2 ya incluye las secciones nuevas (probado con
  datos sintéticos). O3 solo corre. El caché exige la tabla de cola: los modelos que pueden
  darla se vuelven a correr solos; aun así O3 debe usar `--forzar` por el cambio de O1.

## 15-nov-2026 · O3 (backtest completo)
- **Muestreo exacto de la t asimétrica** (dos lados de Hansen: |t| escalado por 1−λ o 1+λ) en
  lugar de invertir la CDF con `arch.SkewStudent.ppf`. Motivo: la inversión costaba ≈ 0,19 s por
  origen (≈ 40 min en la corrida larga, sobre el límite de 15); subir el paso de reajuste no
  servía porque el costo era simular. Misma distribución (prueba contra la ppf de `arch`).
  Ningún resultado previo usaba la versión vieja.
- **Ningún paso de reajuste cambió**: ningún modelo pasó de 15 min (máximo reg_cuantiles 10,6 min
  en la corta; markov_3 6,3 min en la larga). Corta y larga en paralelo (2 procesos, 4 núcleos):
  34 y 40 min. RAM: ≤ 190 MB por proceso, mínimo libre 0,58 GB de 8 (runs/o3_ram.log).
- El protocolo del reporte arma los pasos de reajuste desde los metadatos de cada corrida.

## 16-nov-2026 · F3 (conclusiones)
- **Regla del veredicto (N2).** Principal: MCS por horizonte; un horizonte tiene modelo útil solo
  si ninguna línea base queda en su MCS. Verificación: Diebold-Mariano contra la mejor línea base
  con Holm entre los horizontes de cada modelo (< 0,05). Descartado: usar el criterio por pares
  del resumen para concluir (premia al ganador de muchas pruebas). El criterio de descarte
  original no se tocó: el resumen lo sigue mostrando. Resultado: solo `lightgbm_cuantiles` a
  h = 1; `reg_cuantiles` (p_mcs = 0,063) es casi-acierto y no se rescata.
- **N4, LightGBM a 21 y 63.** Diagnóstico con el mismo esquema sin variables (aísla la
  estandarización) y la pérdida dentro/fuera de muestra: a 21 es sobreajuste; a 63, sobreajuste
  más estandarización (reports/f3_lightgbm.md). No se retoca el modelo: sería buscar en desarrollo.
- **Conclusiones en archivo aparte** (`reports/fase2_conclusiones.md`, con el hash de datos en la
  primera línea). El reporte las incluye solo si ese hash coincide con el de las corridas; si
  no, avisa que están obsoletas. Descartado: escribirlas dentro del código del reporte (quedarían
  pegadas a cifras viejas sin aviso).
- **Motor del caso: `bootstrap_est_filtrado` en todos sus horizontes**; el bootstrap simple queda
  como sensibilidad (a h = 1 se rechazan su VaR y su ES). Motivo: da trayectorias, está en el MCS
  a 5-63 y es el de cobertura más cercana a la nominal; no porque gane en CRPS. Pendiente de
  que el autor lo confirme en las preguntas del prerregistro (F4).
- **Fichas**: `lightgbm_cuantiles` (único que sobrevive) y `bootstrap_est_filtrado`. La segunda
  no sobrevive: se escribe porque es el motor del caso y sus límites deben quedar a la vista.

## 16-nov-2026 · F4 (prerregistro y código de la prueba final)
- **Candado en el cargador (R3).** `cargar_prueba_final` es la única función que entrega datos
  ≥ 2020 y antes verifica contra `docs/prerregistro.md` los hashes de `src/**/*.py`, de los tres
  CSV que usan los modelos y del entorno (versiones de Python y bibliotecas numéricas).
  Descartado: verificar solo en el comando (cualquier script podría saltárselo) y solo `trm.csv`
  (LightGBM y la regresión usan las series externas).
- **Corrida única**: `runs/prueba_final/HECHO.json` impide repetir; no existe `--forzar`. Una
  corrida interrumpida se reanuda (los modelos son deterministas).
- **Familia confirmatoria: una prueba por horizonte** (campeón del MCS de desarrollo contra la
  línea base de desarrollo; LightGBM a 1, EWMA a 5/21/63), DM unilateral con Holm entre las
  cuatro. Descartados: (a) solo h = 1 (deja tres horizontes sin criterio de éxito, que F4 pide);
  (b) exigir además estar en el MCS de la prueba final (con ≈ 27 ventanas a h = 63 casi nunca
  excluye a nadie; el MCS queda como descriptivo). Costo asumido: Holm multiplica por 4 el p de h = 1.
- **El motor del caso no se cambia a la vista de la prueba**: se publica su cobertura con n
  efectivo y, si 0,95 queda fuera del intervalo, el caso lo dice. Descartado: «si falla, otro
  motor» (sería elegir con la prueba final).
- **Lista cerrada = los 17 + 15 del catálogo**: todos cumplen la regla de C1.
- **Borrador, no prerregistro**: el texto vive en `docs/prerregistro_borrador.md` hasta que el autor
  responda las preguntas; con ese nombre el comando no corre. Al cerrar: renombrar, pegar la
  salida de `final --hashes` y commit `prerregistro prueba final`.
- `backtest/ejecucion.py`: la ejecución de un modelo salió de `__main__` para que desarrollo y
  prueba final usen el mismo código. El reporte final no incluye veredicto ni conclusiones libres.

## 16-nov-2026 · F4 (candados antes de cerrar el prerregistro)
- **Git como testigo del prerregistro.** `verificar_prerregistro` exige la etiqueta
  `prerregistro-final`, que `docs/prerregistro.md`, `src/` y `data/` sean iguales a ese commit y
  que `src/` y `data/` no tengan archivos sin versionar. Descartado: solo hashes (el prerregistro
  se podía editar junto con sus hashes sin dejar fecha).
- **Adenda = etiqueta nueva** `prerregistro-adenda-1`, `-2`… en un commit posterior; vale la
  última y `prerregistro-final` no se mueve ni se borra (decisión del autor al responder la
  pregunta 8). Descartado: mover la etiqueta original. El código exige numeración sin saltos y
  orden en la historia; con la prueba abierta, INICIADA.json detecta si la original se movió.
- **El caché de la prueba final solo vale con los mismos hashes** (código, entorno y datos) en el
  .json; si no, el modelo se repite. Descartado: fiarse de que existan los archivos.
- **INICIADA.json antes de leer datos** (hora, hashes, commits; las reanudaciones se agregan) y
  **HECHO.json con el SHA-256 de cada resultado**. La corrida no imprime cifras (ni segundos ni
  fallos): solo nombre y estado de cada modelo.
- **Fin de línea**: `*.py` y `docs/prerregistro*.md` con `eol=lf`; el resto sigue en `-text`
  (47 archivos versionados en CRLF y `data/raw/` cuyos bytes ya citan otros hashes). `hash_codigo`
  normaliza CRLF a LF. Descartado: `eol=lf` para todo.
- **El reporte final agrega** la advertencia de cobertura permanente a 63/126/252 con n efectivo,
  la línea de sensibilidad de h = 1 sin covid ni 2022 (descriptiva) y la nota de respaldo
  indirecto al caso (230 días, costo total). Va en el código porque este se congela al etiquetar.
- **Lectores sin candado** (grep de `src/`): la ruta de la prueba final solo lee los tres CSV del
  candado; `reportes/fase0.py` y `motor/datos.py` leen `trm.csv` completo y el motor agrega líneas
  a `data/supuestos/registro.jsonl` (correr el caso tras etiquetar bloquea la prueba). Declarado.

## 16-nov-2026 · F4 (cierre del prerregistro)
- **Prerregistro cerrado**: el autor respondió sí a las 8 preguntas (la 8 con la condición de las
  adendas como etiquetas nuevas). `docs/prerregistro_borrador.md` pasó a `docs/prerregistro.md`,
  commit `prerregistro prueba final`, etiqueta `prerregistro-final`. Desde aquí `src/`, `data/` y
  el prerregistro no se tocan hasta después de la corrida. La prueba final NO se ha corrido.

## 16-nov-2026 · F5 (Monte Carlo en el caso)
- **El motor del caso es el modelo evaluado, sin reescribir.** `motor/montecarlo.py` instancia
  `BootstrapEstacionario`, usa su `ajustar` y `trayectorias` y el mismo generador por origen; una
  prueba exige cuantiles idénticos a `pronosticar`. F5 no toca `modelos/`, `backtest/` ni
  `evaluacion/`. Descartado: un bootstrap propio del caso (no tendría evaluación).
- **Toda la historia, no solo flotación** (D1 pedía flotación). Motivo: es la muestra del modelo
  evaluado; con otra, las coberturas medidas no respaldarían las cifras. Costo declarado en el
  reporte: la deriva histórica entra en las trayectorias (mediana a 252 días por encima de hoy) y
  en el motor filtrado pesa más que en el simple. No se corrige: el motor quedó prerregistrado.
- **Meses → pasos desde los datos** (`historica.pasos_por_compra`: mediana de observaciones por
  ventana). La serie trae ≈ 20 observaciones por mes: la última compra cae a 217 días con TRM, no
  a los «unos 230» del prerregistro. Descartado: 21 pasos por mes (alargaría el horizonte ≈ 5 %).
- **Sin variante con modelos** (decisión del autor): `lightgbm_cuantiles` solo se cita a h = 1
  (CRPS/base y su cola superior subcubierta); el caso no calcula su banda ni lo usa para simular.
- **Respaldo como dato con hash**: `data/respaldo/prueba_final.json` (`python -m laboratorio.motor
  respaldo`) resume la prueba final con `cobertura_motor`, `confirmar` y `pruebas_var`; entra en
  el hash de datos del caso. Sin archivo, todo dice «sin respaldo fuera de muestra».
  Descartado: leer `runs/**/*.csv.gz` en cada corrida (no están versionados).
- **Qué respalda qué**: la banda del 95 % de la TRM a 1/5/21/63/126/252 cita su cobertura medida
  y n efectivo (advertencia siempre a 63/126/252); el costo total y sus probabilidades quedan
  «sin respaldo fuera de muestra» con la frase de respaldo indirecto del prerregistro.
- **Semilla y trayectorias en la ficha**, no en el registro de supuestos (que no cambia).
- **Hash de la prueba final.** F5 modifica `src/`, así que el `hash_codigo` actual ya no coincide
  con el del prerregistro ni con el de los resultados. El de la prueba final se reproduce con
  `git checkout prerregistro-adenda-1` (y `python -m laboratorio.backtest final --hashes`); la
  prueba no se puede repetir (HECHO.json) y `final --verificar` fallará desde este commit: es lo esperado.

## 16-nov-2026 · F5b (análisis posterior: solo flotación)
- **Sensibilidad «análisis posterior (no confirmatorio)» al lado del motor**, que sigue siendo el
  principal. `montecarlo.simular(..., desde=)` remuestrea solo las observaciones desde
  `historica.desde` (1999-09-25); misma semilla (20240501) y mismas 10.000 trayectorias. No toca
  `modelos/`, `backtest/`, `evaluacion/` ni `reportes/`.
- **Solo cambia la muestra.** Bloque, σ̄, ρ y σ del origen son los del motor ajustado con toda la
  historia. Con 10.000 trayectorias: mediana de la TRM a 252 días +2,3 % (motor +9,2 %) y
  P(superar presupuesto) **31,5 %** (motor 45,4 %). Descartada: reajustar además bloque, σ̄ y ρ
  solo con la flotación, que da +2,5 % y **32,8 %**. Motivo de implementar una sola: la primera
  aísla una causa (la muestra) y la segunda mezcla dos (muestra y escala de volatilidad); la
  diferencia entre ambas (1,3 puntos) es pequeña frente a los 14 puntos que las separan del
  motor, y publicar dos variantes daría a elegir entre cifras, ninguna evaluada. La de 32,8 % se
  calculó en memoria y no queda en el código ni en el reporte.
- **Causa verificada con `data/processed/trm.csv`** (la hipótesis del autor se confirma): la banda
  es el 23,0 % de los rendimientos, con deriva de 14,5 % por año y volatilidad diaria de 0,413 %;
  la flotación, 1,9 % por año y 0,733 %. El choque estandarizado medio z = r/σ vale 0,179 en la
  banda y 0,016 en la flotación: la banda pone 0,041 de los 0,053 del conjunto. Reescalados con la
  volatilidad de largo plazo, los choques de la banda equivalen a 0,121 % diario, 2,1 veces su
  depreciación real (0,059 %). Las cifras van al reporte con hash (`causa.*`).
- **Las cifras del motor no cambian**: las 137 claves de la corrida versionada 200b84c2c1a1 dan lo
  mismo con el código nuevo (comprobado en memoria con 10.000 trayectorias). Corrida nueva =
  ficha nueva (cambian el hash de código y el de datos).

## 16-nov-2026 · F6 (revisión externa)
- **Bloqueante B1, corregido.** La sección 4 del caso decía que el filtrado impide que la banda se
  traslade a hoy. Vale para la volatilidad; la deriva de la banda entra amplificada y mueve la
  cifra principal de ≈ 31 % a 45 %. El texto ahora lo dice y remite al análisis posterior.
- **Bloqueante B2, corregido.** En la sección 5 la mediana aparecía en la misma fila que la
  cobertura medida, como si esta la respaldara. La cobertura respalda los límites; cada fila dice
  ahora «límites: prueba final…; Mediana: sin respaldo fuera de muestra».
- **I1 publicado como análisis posterior (decisión del autor).** `motor/respaldo.asimetria_motor`
  cuenta, con los resultados de la prueba final, la proporción de veces que la TRM real quedó
  bajo la mediana del motor y fuera de cada límite, con el n efectivo y el intervalo binomial de
  `cobertura_n_efectivo`. Resultado: bajo la mediana 0,542/0,568/0,620/0,663/0,710/0,801 a
  1/5/21/63/126/252; a 252 días, 6,8 % bajo el límite inferior y 0,0 % sobre el superior. A 63,
  126 y 252 días el reporte lo llama indicio, no prueba. `data/respaldo/prueba_final.json` se
  regeneró: ningún valor anterior cambió (comprobado) y se agregó la sección `posterior`;
  cambia su SHA-256 y, con él, el hash de datos del caso. Descartado: escribirlo en
  `reportes/prueba_final.py` (ese reporte es solo lo prerregistrado).
- **I3 corregido**: la ficha de `bootstrap_est_filtrado` decía «falta la prueba final» y «no tiene
  opinión de dirección»; ahora trae las cifras de la prueba final, la deriva implícita y su causa.
- **I4 corregido**: «Error de Monte Carlo… a lo sumo ±» era un error estándar; el reporte lo llama
  así y aclara que no es una cota.
- **Frase inicial del reporte** (pedido del autor): las tres P(superar presupuesto), de menor a
  mayor, y que la diferencia viene sobre todo de la deriva que cada método supone.
- **Sin fugas halladas y coberturas reales**: los 82 SHA-256 de `HECHO.json` coinciden con los
  archivos locales, las 12 coberturas del respaldo se recomputan idénticas desde
  `runs/prueba_final*/` y `trm.csv` es el de la prueba final. Lo importante y lo menor que no se
  corrigió queda listado en `docs/estado.md`.

## 17-nov-2026 · M0 (higiene del repositorio, Vektor FX)
- **Prompt que manda**: `docs/prompts/PROMPT_VEKTOR_FX.md`. Los cuatro prompts anteriores se
  movieron con `git mv` a `docs/prompts/` sin editarlos (se citan entre sí por nombre, y siguen
  juntos). `CLAUDE.md` apunta a las rutas nuevas (hay prueba de que existen).
- **a. Instalación**: `pyproject.toml` con `[build-system]` (setuptools ≥ 61), `numpy` explícito,
  extra `dev = [pytest, hypothesis]` y paquetes bajo `src/`. `*.egg-info/` y `build/` ignorados.
  Ningún `.py` de `src/` cambió: `hash_codigo` no se mueve por M0.
- **b. Número de pruebas**: 372 (365 + 7 de `tests/test_higiene.py`). `test_readme_cita_el_numero_real_de_pruebas`
  compara el README con `pytest --collect-only -q`; cada fase que agregue pruebas debe
  actualizar el README o esa prueba falla (es lo buscado).
- **c. Entorno**: `requirements-prueba-final.txt` con las seis versiones de la §10 del
  prerregistro (Python 3.11.9 en comentario: pip no lo instala). Hay prueba de que coincide con
  la línea «Entorno:» del prerregistro. El README lo cita en «Reproducir la prueba final».
- **e. `runs/*.log` se quedan donde están.** `docs/decisiones.md` cita `runs/o3_ram.log`;
  moverlos rompería esa referencia sin ganar nada, y `runs/` no se ve en la portada. No se borran.
- **g. Datos de las pruebas (I7 cerrado)**: `tests/conftest.py` reconstruye `data/processed` al
  iniciar la sesión si falta cualquiera de sus 7 archivos, y detiene la sesión con un mensaje
  claro (código 4) si no hay `data/raw`. Se quitaron los saltos por falta de datos de seis
  módulos (los cinco de I7 y `test_datos.py`); hay prueba de que no vuelven. **Desviación del
  prompt**: este pide `python -m laboratorio.datos`, pero ese comando solo escribe
  `manifest.json` y `validacion.json`; `data/processed` lo genera `python -m
  laboratorio.datos.limpieza` (`limpiar`). Se usa esa función. Comprobado: borrando
  `data/processed`, la reconstrucción da los 7 archivos idénticos byte a byte.
- **h. Integración continua**: `.github/workflows/pruebas.yml` (Ubuntu, Python 3.11). Lectura
  conservadora: instala `.[dev]` **con `requirements-prueba-final.txt` como restricción**, para
  que las pruebas numéricas no cambien por versiones nuevas de las bibliotecas. Marcadas
  `lento` (> 30 s en la corrida local de 17-nov): `test_cuantiles::test_qr_con_variables…`
  (165 s) y `test_markov::test_calibrado_en_su_proceso_generador` (35 s). La verificación de
  hashes de la prueba final no entra en CI.
- **f. Licencia**: pendiente de la respuesta del autor; no se creó `LICENSE`.

## 17-nov-2026 · M0, ajustes del autor (nombre, licencia, flujo de ramas)
- **Nombre público: «Vektor FX»** (decisión del autor; ya era el de la ficha del portafolio), con
  título «Vektor FX — Laboratorio de Escenarios» (se aplica al README en M7) y repositorio
  sugerido `vektor-fx`. El paquete sigue siendo `laboratorio`. Prompt renombrado con `git mv` a
  `docs/prompts/PROMPT_VEKTOR_FX.md`. Se reemplazó el nombre anterior en `CLAUDE.md`,
  `docs/decisiones.md`, `docs/estado.md` y el prompt. Ningún archivo intocable lo mencionaba
  (`docs/prerregistro.md`, etiquetas, `runs/`): comprobado con `git grep` de las variantes con y
  sin tilde. `hash_codigo` sin cambios (cfb1ad53…, ningún `.py` de `src/` tocado).
- **Prompt, M1 paso 6**: el comando que genera `data/processed` es
  `python -m laboratorio.datos.limpieza` (desviación 4 de M0, aceptada por el autor).
- **Licencias**: `LICENSE` (MIT, Johan Esteban García Bautista, 2026) para código, pruebas y
  configuración; `LICENSE-docs` (CC BY 4.0, texto oficial de creativecommons.org sin cambios)
  para `reports/` y `docs/`. `data/raw/` conserva los términos de sus fuentes; el README lo dice y
  extiende lo mismo a `data/processed/` (derivado de raw). Sin decidir: `runs/`, `data/respaldo/`
  y `data/supuestos/` (salidas y supuestos; no están en ninguna de las dos listas del autor).
- **Flujo**: desde M0 cada fase va en su rama (`m0-higiene`, `m1-datos`, `m2-motor`…) con PR a
  `main`; se fusiona con merge commit (sin squash) solo con la CI en verde.
- **Primera CI en rojo (PR #1)**: `test_backtest_infra::test_todo_modelo_del_catalogo…` falló con
  `LightGBMError: scikit-learn is required for lightgbm.sklearn`. Dependencia no declarada desde
  siempre (local estaba instalada). Se declara `scikit-learn` en `pyproject.toml` y se fija
  `scikit-learn==1.8.0` en `requirements-prueba-final.txt`, la del equipo de la prueba final
  (instalada el 26-ene-2026). No figura en el prerregistro ni en `hash_entorno`; se anota en el
  archivo. Ninguna restricción se relajó.

## 17-nov-2026 · Cierre de M0: licencias de resultados y scikit-learn fuera del hash de entorno
- **Licencias (decisión del autor)**: `runs/`, `data/respaldo/` y `data/supuestos/` quedan bajo
  CC BY 4.0, como los reportes (son resultados y supuestos del proyecto, no código). El README
  aclara que `runs/` y `data/respaldo/` derivan de datos públicos cuyas fuentes conservan sus
  términos.
- **scikit-learn en la prueba final**: la prueba final (16-nov-2026) se corrió con
  scikit-learn 1.8.0 (instalada el 26-ene-2026), que `lightgbm.LGBMRegressor` usa por debajo.
  Esa versión **no quedó dentro de `hash_entorno`**: `PAQUETES` de `backtest/final.py` no la
  incluye. No se cambia `PAQUETES`: tocar `src/` cambiaría `hash_codigo` y el prerregistro está
  cerrado. El registro de esa versión es `requirements-prueba-final.txt` (agregado después de la
  prueba, el 17-nov-2026; no es un hash prerregistrado).
- **Para M3**: el prerregistro multidivisa debe incluir `scikit-learn` en la lista de paquetes de
  su hash de entorno.

## 17-nov-2026 · M1 (datos multidivisa)
- **Series FRED vigentes**: las seis páginas decían «Updated: Nov 16, 2026» y último dato el
  2026-11-13; ninguna descontinuada. `curl` a la página de la serie fue rechazado por FRED; la
  comprobación se hizo con un lector web y la descarga con `fredgraph.csv` (como las series FRED
  existentes). Archivos nuevos en `data/raw/` con el patrón `<divisa>_fred_<id>_20261117.csv` y
  filas nuevas al final de `data/raw/MANIFEST.csv` (filas = líneas de datos, incluidas las vacías).
  Ningún archivo existente de `data/raw/` cambió.
- **Prueba final intacta**: con los archivos nuevos, `limpiar` produce `trm.csv`,
  `externas_diario.csv`, `tasas_diarias.csv`, `dtf.csv`, `ipc_mensual.csv` y `uvr_diaria.csv`
  idénticos byte a byte (comprobado con `cmp`): los hashes de datos de la prueba final no
  cambian. `construir_externas` elige archivos por prefijo, así que las series nuevas no entran.
  `hash_codigo` sí cambia (código nuevo en `src/`), como ya pasaba desde F5.
- **Alineación TRM–FRED (decisión crítica)**: desfase −1 en días de lunes a viernes (la TRM de *t*
  con H.10 del día hábil anterior). Criterio del prompt: correlación de rendimientos con desfases
  −1, 0 y +1, solo datos hasta el 31-dic-2019; el −1 gana en las seis divisas y en la media de
  |r|. El rendimiento se mide entre filas consecutivas de la unión, para que TRM y H.10 cubran el
  mismo intervalo. Para el yuan la correlación se mide desde el 2005-07-22 (con el tipo fijo su
  rendimiento es cero). Registrado en `data/supuestos/registro.jsonl` (`divisas.desfase_fred`, con
  los SHA-256 de los insumos) y en `docs/supuestos.md`.
- **Régimen de cada fila**: el de la divisa en la fecha de su precio H.10 (no en la de la TRM);
  la banda colombiana manda (`banda_cop`). Lectura conservadora: el cambio de régimen se fecha
  cuando el precio observado ya lo refleja.
- **USD incluido en `divisas.csv`** (filas = la TRM), para que el formato largo tenga las siete
  divisas y la triangulación se pueda comprobar en el mismo archivo.
- **Validación de `divisas.csv` en `data/validacion.json`** (clave `processed/divisas.csv`): la
  calcula `python -m laboratorio.datos` en memoria desde `data/raw` (misma función que la
  limpieza). `test_datos` ahora ignora las claves `processed/…` al comparar con `data/raw`, y
  comprueba unicidad por (fecha, divisa) en `divisas.csv`. 19 saltos > 8 %; ninguno se borra.
  *Corregido el 17-nov-2026*: la versión anterior decía «todos con causa conocida» y nombraba
  causas sin fuente (entre ellas, ninguna verificada para el real en 2002 ni para el yen en
  2020). Se quitó la atribución; las causas solo se escribirán con fuente citada.
- **Reporte `reports/fase0_divisas.md`**: lee los datos y descarta todo lo posterior al
  31-dic-2019 al cargarlos. Cada cifra lleva `#hash`; los insumos se hashean solo con las filas
  anteriores al corte, así que cambiar datos posteriores no cambia el reporte (hay prueba). El
  reporte no escribe ningún año desde 2020 (hay prueba con expresión regular). Tres figuras:
  niveles base 100, volatilidad móvil (63 obs.) y correlaciones 2005-2014 / 2015-2019.
- **Desviación menor**: `validacion.json` (salida de `python -m laboratorio.datos`) también lista
  saltos posteriores a 2019 (uno, de JPY/COP). Es un archivo de datos, no el
  reporte exploratorio; se deja así para que la revisión manual sea completa.
- **`data/raw/MANIFEST.csv`**: solo se añadieron seis filas al final, como pide M1 paso 1
  (`git diff`: 6 inserciones, 0 borrados). No entra en ningún hash de datos publicado.
- **Qué se vio de 2020 en adelante de las divisas nuevas (para declararlo en M3)**: al
  comprobar que las series siguen vivas, los cinco últimos valores de cada una (9 al 13 de
  noviembre de 2026) y la última línea de cada descarga; al revisar `validacion.json`, la lista
  de saltos > 8 %, que incluye uno solo posterior a 2019 (JPY/COP, 2020-03-10; su tamaño se
  vio y no se repite aquí); y los conteos de días perdidos de `limpieza.json`, que abarcan
  toda la serie. No se calculó ni se
  miró ninguna otra estadística, figura ni tabla de 2020 en adelante.

## 17-nov-2026 · Previos de M2 (revisión de M1 por el autor)
- **Reproducción de fichas** (corrección del autor al requisito de M5): la reproducción exacta
  se hace en el commit cuyo código tiene el `hash_codigo` de la ficha, con etiqueta
  `corrida-<id>`; en `main` se exige no regresión (tolerancia 0) solo para la ficha vigente
  `6506dbba3261`. Tabla y pruebas en `docs/reproduccion.md`. Ningún `ficha.json` se reescribe.
  - `d6f052613b7a` no tiene commit posible (creada antes del primer commit, `commit` nulo); la
    prueba de etiquetas la admite como única excepción, con esas dos condiciones comprobadas.
  - La prueba de etiquetas no se marca `lento` (tarda menos de 1 s): así corre en la CI y una
    ficha nueva sin etiqueta la rompe. La CI hace checkout con historial completo
    (`fetch-depth: 0`) para tener las etiquetas. La prueba de no regresión tarda unos 5 s y
    tampoco se marca.
- **Criterio de la alineación TRM–FRED**: se eligió el desfase con la mayor correlación **en
  valor absoluto** entre los rendimientos logarítmicos de la TRM (COP por USD) y de «USD por X».
  El signo negativo es el esperado: si el dólar sube frente al peso, también suele subir frente a
  la otra divisa, y entonces «USD por X» baja. Por eso las correlaciones con desfase −1 son
  negativas (EUR −0,231; MXN −0,291; CNY −0,201; CHF −0,110; BRL −0,378; cifras con `#hash` en
  `reports/fase0_divisas.md`, sección 2, datos hasta el 31-dic-2019). Yen: +0,047 con desfase
  −1 (`#0ca08c212f`, 6.670 pares).
