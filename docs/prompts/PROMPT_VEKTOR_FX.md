# PROMPT — Vektor FX · Laboratorio de Escenarios multidivisa (v1, 17-nov-2026)

> Pégalo en Claude Code desde la raíz del repositorio
> (`C:\Users\johan\Downloads\Life\IndeProjex\laboratorio-escenarios`). Guárdalo también como
> `PROMPT_VEKTOR_FX.md` en la raíz: a partir de hoy es el archivo que manda para el trabajo nuevo.

---

## 0. Contexto y reglas que no se negocian

Eres el desarrollador del proyecto. Lee primero, en este orden y nada más: `CLAUDE.md`,
`docs/estado.md`, la sección 1 y la 12 de `docs/prerregistro.md`, y el docstring de
`src/laboratorio/motor/montecarlo.py`. No leas `data/raw/` completo (usa `head`, conteos o resúmenes).

El proyecto ya terminó una prueba final prerregistrada sobre la TRM (USD/COP). Su conclusión es la
base de todo lo que sigue y **no se reinterpreta**:

- Solo a 1 día hay un modelo útil (`lightgbm_cuantiles`, CRPS/base 0,977, mejora ≈ 2 %) y sus colas
  quedan cortas.
- A 5, 21 y 63 días ningún modelo supera a su línea base; a 126 y 252 días todo es descriptivo.
- El motor del caso (`bootstrap_est_filtrado`) arrastra la deriva de la banda cambiaria
  amplificada ≈ 2,1 veces (F5b).

Objetivo de esta fase: convertir el laboratorio en **Vektor FX**, una herramienta que
(1) simula escenarios conjuntos para varias divisas contra el peso colombiano,
(2) pronostica solo donde la evidencia lo permite, (3) **apoya decisiones** comparando
estrategias, sin recomendarlas, y (4) lo muestra en una página web estática.

Reglas:

1. **Intocables.** No modifiques nada que cambie lo ya publicado: `docs/prerregistro.md`, las
   etiquetas `prerregistro-final`, `prerregistro-adenda-1` y `respaldo-prueba-final-v1`,
   `runs/prueba_final*/`, `runs/backtest_*/`, `data/raw/` existente y `data/respaldo/`. Lo nuevo
   va en archivos y carpetas nuevas. Si una tarea parece exigir tocarlos, detente y pregunta.
2. **Nombre público, no de paquete.** El paquete de Python sigue llamándose `laboratorio`
   (renombrarlo rompería importaciones, fichas y reproducciones). «Vektor FX» es el nombre del
   README, de la web y del repositorio; el subtítulo es «Laboratorio de Escenarios».
3. **«Asesorar» = comparar.** Ningún texto, figura o salida dice «compre», «recomendamos» ni
   «la mejor opción». Se dice «con tu tolerancia, estas estrategias cumplen; estas no» y siempre
   con el respaldo de la cifra. El aviso «No es asesoría financiera; los rangos describen
   incertidumbre estadística, no promesas» aparece en el README, en cada reporte y en la web.
4. **Cada cifra nueva** usa el sistema existente (`motor/cifras.py`): fuente + `#hash` + qué
   evaluación fuera de muestra la respalda o «sin respaldo fuera de muestra».
5. **Sin relleno de datos.** No se interpola ni se arrastra ningún valor (igual que en `limpieza.py`).
6. **Pruebas primero** en todo lo que toque números: escribe la prueba que falla, luego el código.
   `pytest -q -x` debe pasar al cerrar cada fase.
7. **Al cerrar cada fase:** actualiza `docs/estado.md` (máx. 15 líneas en total, reescribe en vez
   de añadir), registra decisiones en `docs/decisiones.md`, haz commit con un mensaje que empiece
   por el código de la fase (p. ej. `M1: …`) y **detente** con un resumen de 5 líneas para que yo
   revise. No encadenes fases sin mi visto bueno.
8. Si dudas entre dos lecturas razonables de una instrucción, elige la más conservadora
   estadísticamente, escríbela en `docs/decisiones.md` y sigue.

---

## M0. Higiene del repositorio (rápido; hazlo primero)

Problemas encontrados en la revisión:

| # | Problema | Qué hacer |
|---|---|---|
| a | `pip install -e ".[dev]"` del README falla en silencio: `pyproject.toml` no define el extra `dev` (pytest no se instala) | Añade `[project.optional-dependencies] dev = ["pytest", "hypothesis"]`, `numpy` explícito en dependencias y un `[build-system]` con setuptools ≥ 61 |
| b | El README dice 356 pruebas; `docs/estado.md` dice 365 | Corre la suite, usa el número real en ambos y añade una prueba que compare el número del README con `pytest --collect-only -q` (o elimina el número del README) |
| c | El entorno de la prueba final solo está en prosa (prerregistro §10) | Crea `requirements-prueba-final.txt` con las versiones exactas (python 3.11.9, numpy 2.4.1, pandas 3.0.0, scipy 1.17.0, statsmodels 0.15.0, arch 9.0.0, lightgbm 4.7.0) y cítalo en la sección «Reproducir la prueba final» del README |
| d | Cuatro `PROMPT_*.md` en la raíz ensucian la portada del repositorio | Muévelos con `git mv` a `docs/prompts/` y actualiza la ruta en `CLAUDE.md`. Este prompt nuevo también va ahí, una vez guardado |
| e | `runs/*.log` versionados (ruido) | Muévelos a `runs/logs/` o déjalos; no los borres de la historia. Decide y anótalo |
| f | Sin licencia | Pregúntame cuál (sugerencia: MIT para código, CC BY 4.0 para reportes) antes de crear `LICENSE` |
| g | Pendientes I7 de `docs/estado.md`: cinco módulos de prueba se saltan en silencio sin `data/processed` | Añade un `conftest.py` que, si falta `data/processed`, lo reconstruya desde `data/raw` una vez por sesión (`python -m laboratorio.datos`), o que falle con un mensaje claro si tampoco hay `raw`. Nunca un salto silencioso |
| h | Sin integración continua | Añade `.github/workflows/pruebas.yml` (Ubuntu, Python 3.11, instala `.[dev]`, reconstruye `data/processed`, corre `pytest -q -x -m "not lento"`). Marca como `lento` las pruebas de más de 30 s. La verificación de hashes de la prueba final NO va en CI (depende del entorno exacto) |

Criterio de terminado de M0: suite verde, README sin cifras desactualizadas, CI verde en GitHub.

---

## M1. Datos multidivisa

Divisas: EUR, MXN, JPY, CNY, CHF y BRL contra COP (más USD/COP, que ya existe).

**Fuente.** FRED (tasas H.10 de la Reserva Federal, mediodía de Nueva York), mismo formato que los
CSV de FRED que ya lee `lectores._leer_fred`:

| Divisa | Serie FRED | Unidad | Inicio aprox. |
|---|---|---|---|
| EUR | `DEXUSEU` | USD por EUR (¡invertida respecto a las demás!) | 1999 |
| MXN | `DEXMXUS` | MXN por USD | 1993 |
| JPY | `DEXJPUS` | JPY por USD | 1971 |
| CNY | `DEXCHUS` | CNY por USD (en tierra, no CNH) | 1981 |
| CHF | `DEXSZUS` | CHF por USD | 1971 |
| BRL | `DEXBZUS` | BRL por USD | 1995 |

Antes de descargar, comprueba en la página de cada serie que sigue actualizada a noviembre de
2026. Si alguna está descontinuada, **detente** y propón una fuente alterna (BCE para EUR, Banxico
para MXN, BCB para BRL) sin descargar nada todavía.

Pasos:

1. Descarga a `data/raw/` con el patrón existente `<nombre>_fred_<id>_<YYYYMMDD>.csv` y añade
   cada archivo a `data/raw/MANIFEST.csv` con URL, fecha, SHA-256, filas y rango. Los archivos
   existentes de `data/raw/` no se tocan.
2. **Cruce.** `X/COP = TRM × (USD por X)`. Para las series cotizadas «X por USD»,
   `USD por X = 1 / valor`; para `DEXUSEU`, el valor ya es USD por EUR. Escribe una prueba
   específica para la inversión del EUR.
3. **Alineación de fechas (decisión crítica, documéntala).** La TRM vigente en la fecha *t* se
   calcula con operaciones del día hábil anterior; H.10 es el precio del día *d* a mediodía en NY.
   No elijas la alineación a ojo: calcula la correlación entre los rendimientos de la TRM y los de
   `USD por X` con desfases −1, 0 y +1 (solo con datos anteriores a 2020-01-01) y elige el desfase
   de mayor correlación contemporánea **por razones de calendario**, no por ajuste fino.
   Regístralo como supuesto en `data/supuestos/registro.jsonl` y en `docs/supuestos.md`.
4. **Calendarios.** Festivos de Colombia y de EE. UU. difieren: une por fecha con *inner join*,
   sin relleno, y reporta cuántos días se pierden por divisa.
5. **Regímenes por divisa** (constantes editables en un módulo nuevo, como `FIN_BANDA` en
   `limpieza.py`), con fuente en un comentario:
   - CNY: tipo fijo hasta el 21-jul-2005; de ahí, flotación administrada.
   - CHF: piso de 1,20 por EUR del 6-sep-2011 al 15-ene-2015 (salto del 15-ene-2015 = episodio).
   - BRL: flotación desde el 18-ene-1999. MXN: flotación desde el 22-dic-1994.
   - EUR existe desde el 4-ene-1999.
   - COP: la banda hasta el 25-sep-1999 ya está declarada.
6. Salida: `data/processed/divisas.csv` (formato largo: `fecha, divisa, cop_por_unidad, ret_log,
   regimen`) generado por `python -m laboratorio.datos.limpieza`, más validaciones en
   `data/validacion.json` (positivos, sin duplicados, saltos > 8 % diarios listados para revisión
   manual, nunca borrados).
7. **Análisis exploratorio** en `reports/fase0_divisas.md` con como máximo tres figuras:
   niveles normalizados (base 100), volatilidad móvil por divisa y matriz de correlación de
   rendimientos en dos periodos (2005-2014 y 2015-2019). **No muestres ni resumas datos de
   2020-01-01 en adelante en este reporte**: así la prueba de M3 conserva un tramo sin ver para
   las divisas nuevas (ver M3).

Pruebas mínimas: lectura de cada CSV, inversión del EUR, cruce contra un valor calculado a mano,
ningún valor posterior a la fecha de descarga, el reporte no contiene fechas ≥ 2020-01-01.

---

## M2. Motor conjunto (simulación multidivisa)

El valor del multidivisa no es tener siete abanicos sueltos sino **preservar la correlación**
entre divisas: el riesgo de una canasta no es la suma de los riesgos.

Diseño obligatorio:

1. Simula **factores**, no cruces: rendimientos de la TRM y de cada `USD por X`. Los `X/COP`
   salen de multiplicar, así la triangulación es exacta en cada trayectoria (prueba:
   `EUR/COP ÷ USD/COP = USD por EUR` en todas las trayectorias, con tolerancia de máquina).
2. Bootstrap estacionario **por bloques con índices de fecha compartidos**: se sortea una sola
   secuencia de índices y se aplica a todas las series, lo que conserva correlación contemporánea
   y de corto plazo. Refactoriza `modelos/bootstrap.trayectorias` en dos funciones
   (`indices_bloques(...)` y la aplicación de índices) **sin cambiar ningún número**: añade una
   prueba de que, con una sola serie, la función conjunta reproduce bit a bit la salida actual de
   `trayectorias(x, largo, sims, bloque, rng, esc)` con la misma semilla.
3. Variante filtrada: cada serie se estandariza con su propia σ EWMA (z = r/σ) y se reescala con
   su propio σ del origen, como en `bootstrap_est_filtrado`. Longitud de bloque común: la de
   Politis-White de la TRM (decláralo; alternativa en sensibilidad: la mediana de las siete).
4. **Muestra común:** desde el inicio de flotación de todas las divisas incluidas en la corrida
   (con CNY, desde el 22-jul-2005). Eso significa que el motor conjunto **no** incluye la banda
   cambiaria colombiana y por tanto **no es** el motor evaluado en la prueba final. Etiquétalo
   así en todas sus salidas («motor conjunto, sin evaluación fuera de muestra hasta M3») y
   reporta, para la TRM, la diferencia frente al motor evaluado (ya sabemos por F5b que la
   deriva de la banda explica gran parte).
5. Módulo nuevo `src/laboratorio/motor/conjunto.py` con `simular_conjunto(vistas, divisas,
   motor, sims, semilla, largo, desde)` que devuelva un objeto con `acum` de forma
   `(largo, sims, n_divisas)` y los metadatos (bloque, σ, muestra, n). Nada de esto modifica
   `montecarlo.simular`.
6. Pruebas: triangulación; reproducción bit a bit con una serie; la correlación de Pearson de
   rendimientos diarios simulados está dentro de ±0,05 de la histórica de la muestra
   (10.000 trayectorias); semilla fija ⇒ resultado idéntico; ninguna fecha posterior al origen
   entra al remuestreo (prueba de fuga, como en `test_sin_fuga.py`).

---

## M3. Prerregistro multidivisa y evaluación (el corazón del rigor)

Las divisas nuevas son hipótesis nuevas. Sin esto, «probé siete divisas» se convierte en buscar
la que salga bien.

**Problema que debes declarar, no esconder:** el periodo 2020-2026 de USD/COP ya se vio, y
`X/COP = TRM × USD por X`, así que la mitad de cada cruce ya es conocida. Por eso:

1. **Prerregistro nuevo e independiente**: `docs/prerregistro_multidivisa.md` y etiqueta
   `prerregistro-multidivisa`. Reutiliza el mecanismo de candado de `backtest/final.py`
   (hashes de código, datos y entorno —el de entorno incluye `scikit-learn`, que el original no
   cubría—; INICIADA/HECHO con SHA-256; corrida única), extrayendo lo
   común a una función sin cambiar el comportamiento de la prueba final original (sus pruebas
   deben seguir pasando). Constantes nuevas en un módulo nuevo, p. ej. `backtest/final_divisas.py`.
2. **Evaluación retrospectiva (2020-2026), declarada como «parcialmente vista».** Se evalúan las
   seis divisas nuevas; USD/COP no se vuelve a evaluar.
3. **Evaluación prospectiva (la que de verdad no se ha visto).** Comando
   `python -m laboratorio.pronostico sellar` que, con los datos al día, escribe en
   `pronosticos/AAAA-MM-DD.json` los cuantiles de cada divisa y horizonte, con hashes de código y
   datos, y hace commit. `python -m laboratorio.pronostico evaluar` puntúa solo los pronósticos
   cuyo horizonte ya venció. Los pronósticos sellados no se editan nunca (prueba que lo verifique
   con el historial de git). Prerregistra cuándo se evaluará (p. ej. a 63 días con ≥ 40 sellos
   semanales) y acepta que a 252 días no habrá resultado durante más de un año.
4. **Catálogo reducido y cerrado** (correr los 17 modelos × 7 divisas es caro y multiplica las
   comparaciones): `caminata_aleatoria`, `sim_hist_pond`, `ewma_0.94`, `bootstrap_est`,
   `bootstrap_est_filtrado`, `gjr_t` y `lightgbm_cuantiles`. El desarrollo de las divisas nuevas
   usa datos < 2020-01-01, con el mismo protocolo de `backtest/particion.py` (origen móvil desde
   2005-01-03 o desde el inicio de flotación si es posterior, reajuste 21, embargo = h_max).
5. **Hipótesis confirmatorias** (escríbelas antes de abrir los datos):
   - H_d (una por divisa nueva, h = 1): `lightgbm_cuantiles` tiene menor CRPS que
     `sim_hist_pond` (Diebold-Mariano unilateral, HAC con h − 1).
   - Las seis forman **una familia: Holm, α = 0,05**.
   - Para el motor conjunto: cobertura del 95 % de una canasta fija (p. ej. 1/3 USD, 1/3 EUR,
     1/3 MXN, en COP) a 21 y 63 días, con su n efectivo y la advertencia de pocas ventanas.
   - Escribe también qué se espera que **no** salga: EUR, CHF y JPY son monedas de reserva o
     refugio y pueden comportarse distinto a MXN y BRL; un resultado mixto no es un fracaso.
6. **Qué se publica pase lo que pase** (copia la estructura de la sección 8 del prerregistro
   original): las seis comparaciones, coberturas y PIT, aunque no confirmen nada.
7. Prueba de fuga obligatoria: durante el desarrollo, ningún dato ≥ 2020-01-01 de las divisas
   nuevas existe en memoria (igual que `cargar_desarrollo`).

Antes de cerrar el prerregistro, **detente** y muéstrame el borrador con las preguntas abiertas
(como hiciste en la sección 11 del prerregistro original). No corras la prueba sin mi «sí».

---

## M4. Pronóstico con semáforo de evidencia

1. `src/laboratorio/motor/evidencia.py`: una tabla divisa × horizonte con tres estados, calculados
   (no escritos a mano) a partir de `data/respaldo/` y del respaldo nuevo de M3:
   - **Respaldado**: hipótesis confirmatoria aprobada con Holm.
   - **Descriptivo**: cobertura evaluada pero sin prueba confirmatoria o con n efectivo < 30.
   - **Sin respaldo fuera de muestra**.
2. El **pronóstico central** (mediana y percentiles 5-95) a 1 día se muestra **solo** en las
   casillas «Respaldado». En las demás, solo el rango de escenarios con su etiqueta.
3. Toda salida que muestre un número lleva el color y el texto del semáforo. Prueba: ninguna
   casilla «Sin respaldo» produce un pronóstico central.

---

## M5. Apoyo a decisiones (lo que el usuario llama «asesoría»)

Generaliza `motor/casos/compra_dolares.py` sin romperlo (sus pruebas y la reproducción de las
fichas `runs/6506dbba3261` y `runs/200b84c2c1a1` deben seguir dando «COINCIDE»).

1. **Caso 2 nuevo, `pagos_multidivisa`:** una canasta de obligaciones futuras en varias divisas
   (ejemplo ilustrativo del autor: 4.000 EUR, 20.000 CNY y 3.000 USD a pagar en 6 meses).
   Estrategias comparadas:
   - Comprar todo hoy (costo cierto).
   - Comprar en cuotas mensuales.
   - Mixto: X % hoy y el resto en cuotas (X ∈ {25, 50, 75}).
   - Cobertura con contrato a plazo (*forward*): su precio por paridad de tasas requiere las tasas
     de cada país, que no están en los datos. Entra como **supuesto ilustrativo** (prima anual
     editable por divisa, registrada en `data/supuestos/`) y la salida lo dice explícitamente.
2. **Perfil de tolerancia:** el usuario fija un presupuesto y una probabilidad máxima aceptable
   de superarlo (p. ej. 10 %). La salida es una tabla: estrategia, costo mediano, percentil 95,
   P(superar presupuesto) con su respaldo, y «cumple / no cumple tu tolerancia». Ordena por
   P(superar) pero **no marques ganador**.
3. **Las tres cifras, siempre juntas.** Como en el caso 1, cada probabilidad se publica con las
   variantes disponibles (ventanas históricas, motor conjunto, motor conjunto solo flotación) y
   la explicación de por qué difieren. Nunca una sola.
4. Valores de meta, fechas y montos: supuestos ilustrativos del autor, con la etiqueta
   `ILUSTRATIVO` que ya usa el caso 1.
5. Reporte `reports/pagos_multidivisa.md` generado por
   `python -m laboratorio.motor pagos_multidivisa`, con ficha reproducible en `runs/`.

---

## M6. Página web estática (Vektor FX)

Sigue la sección 9 de `docs/prompts/PROMPT_FINANZAS.md` (tres paneles: Supuestos, Resultado,
Explicación; máximo tres gráficas por vista; pensada primero para celular).

1. `python -m laboratorio.web` genera `web/datos.json` (solo cuantiles y resúmenes, nunca las
   10.000 trayectorias) y una página `web/index.html` autocontenida (HTML + CSS + JS en un archivo,
   sin servidor). Publicación con GitHub Pages desde `web/`.
2. **Vista principal (menos es más):** selector de divisa y de horizonte, un solo gráfico central
   (abanico 50 % y 95 % con la mediana), el semáforo de evidencia y el aviso legal visible sin
   desplazarse.
3. **Pestaña «Comparar estrategias»:** controles de presupuesto y tolerancia; histograma o
   gráfico de densidad de costos por estrategia con el presupuesto como línea vertical; la tabla
   de M5.
4. **Pestaña «Cómo se mueven juntas»:** mapa de calor de correlaciones con selector de periodo.
5. **Pestaña «Qué tan confiable es»:** el semáforo completo y un enlace a cada reporte y
   prerregistro.
6. Paleta accesible para daltonismo, sin rojo/verde como único código; textos en español; cifras
   con coma decimal. Revisa la página en un navegador a 375 px y a 1280 px y corrige lo que se
   corte antes de dar la fase por terminada.

---

## M7. README y presentación del portafolio

1. Título: «Vektor FX — Laboratorio de Escenarios». Primera línea: qué pregunta responde
   (¿qué rango de resultados es razonable para varias divisas y qué tan confiable es ese rango?).
2. Conserva intactas las secciones «El resultado, sin adornos», «La cifra que más cuidado merece»
   y «Cómo se garantiza que no se hizo trampa»; añade debajo los resultados de M3 (sean los que
   sean) y el estado de la evaluación prospectiva.
3. Captura de la web y enlace a GitHub Pages en la parte superior.
4. Actualiza `docs/uso_de_ia.md` con lo hecho en estas fases.
5. Renombrar el repositorio en GitHub (`vektor-fx`) es decisión mía: pregúntame al final, no lo
   hagas tú.

---

## Orden y puntos de parada

M0 → (parada) → M1 → (parada) → M2 → (parada) → M3 borrador → (parada obligatoria antes de cerrar
el prerregistro) → M3 corrida → (parada) → M4 → M5 → (parada) → M6 → (parada) → M7.

En cada parada entrega: qué cambió (archivos), resultado de `pytest -q -x`, decisiones nuevas y
lo que queda pendiente. Si una cifra nueva contradice algo publicado, dilo primero.
