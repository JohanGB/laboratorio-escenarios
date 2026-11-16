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
