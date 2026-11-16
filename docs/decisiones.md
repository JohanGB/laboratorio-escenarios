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
