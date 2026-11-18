# PROMPT DE CONTINUACIÓN — Laboratorio de Escenarios (desde el 14-nov-2026)

Este archivo complementa a `PROMPT_FINANZAS.md` (especificación completa) y a `docs/estado.md`
(estado vivo). Está dividido en **sesiones**. En cada sesión de Claude Code se pega solo el
mensaje corto de esa sesión; el mensaje indica qué sección de este archivo leer. No leas el
archivo entero si la sesión no lo pide.

---

## 0. Reglas comunes a todas las sesiones

1. Lee primero `docs/estado.md` y luego SOLO la sección de este archivo que indique el mensaje.
2. **La prueba final (datos desde 2020-01-01) no se toca** hasta la sesión C2. Ningún modelo,
   umbral, característica ni hiperparámetro puede elegirse mirando esos datos.
   `cargar_desarrollo` debe seguir fallando si ve fechas ≥ corte.
3. Cada modelo nuevo se agrega a `FABRICAS` en `backtest/catalogo.py` **y** al canario
   anti-fuga `tests/test_sin_fuga.py`.
4. Antes de dar una tarea por terminada: `pytest -q -x` en verde y `docs/estado.md` actualizado
   (máx. 15 líneas; reemplaza lo viejo, no lo acumules).
5. Dudas menores: decide, regístralo en `docs/decisiones.md` (fecha, decisión, alternativa
   descartada, motivo) y sigue. Dudas que cambian resultados: detente y pregunta.
6. Nunca leas `data/raw/` completo ni archivos `runs/**/*.csv.gz` enteros: usa resúmenes.
7. Todo en español. Ninguna salida es asesoría financiera; los rangos describen incertidumbre.
8. No cambies las constantes de `backtest/particion.py`. Si una tarea lo exige, pregunta.

---

## 1. Diagnóstico (lo que hay y lo que falta)

**Hecho y verificado:**
- Fase 0: datos con manifiesto SHA-256 (TRM Superfinanciera y Banrep, IPC DANE, SUAMECA con
  16 series, Brent, dólar amplio y fed funds de FRED), limpieza, validación y EDA con regímenes.
- Fase 1 (parcial): supuestos encadenados por hash, ficha de corrida reproducible, cifras
  rastreables, caso «compra de dólares» con escenarios deterministas, reproducción histórica y
  distribución empírica de todas las ventanas de flotación.
- Fase 2 (parcial): protocolo de backtesting aprobado (origen móvil desde 2005, purga, embargo,
  prueba final reservada), escalones 1, 2 y 4 de la escalera, pinball, CRPS, puntaje de
  intervalo, cobertura, Kupiec, Christoffersen, Diebold-Mariano con HLN, reporte por régimen.

**Hallazgos del backtest de desarrollo que condicionan lo que sigue:**
- H1. Todos los candidatos superan a la mejor línea base **solo a 1 día**. A 5, 21 y 63 días
  ninguno lo logra con significancia (EWMA queda cerca: p = 0,053 y 0,056).
- H2. La **cola superior** (alzas del dólar) está subcubierta a 1 día en casi todos los
  modelos (violaciones del VaR superior al 5 % entre 5,7 % y 7,1 %). Es justo la cola que
  importa en el caso de compra de dólares.
- H3. En estrés, a 63 días, la cobertura del 95 % cae a 0,49–0,79 en todos los modelos.
- H4. GARCH y GJR no convergieron en 38 y 28 de 167 reajustes y la persistencia queda ≈ 1.
- H5. El índice del dólar de FRED empieza en 2006-01-02, pero el desarrollo empieza en
  2005-01-03: hay que confirmar cómo se trató ese año en las características.

**Falta (por fase de `PROMPT_FINANZAS.md`):**
- Fase 2: escalón 3 (cambio de régimen de Markov), Model Confidence Set, semáforo de Basilea,
  Expected Shortfall con Acerbi-Székely, VaR al 95 % y 99 % reportado en ambas colas, diagramas
  PIT, acierto direccional como diagnóstico, *model cards*, prerregistro y prueba final.
- Fase 1: Monte Carlo con bootstrap por bloques, valores de Shapley con cascada, comparador
  de escenarios A vs. B.
- Fase 3: caso hipoteca UVR vs. pesos, página web estática.
- Fase 4 (después): deep learning en Kaggle/Colab, combinación de pronósticos, caso pyme.
- Estándar del repositorio: `README.md`, `docs/decisiones.md`, `docs/supuestos.md`,
  `docs/uso_de_ia.md`, `models/model_cards/`, `.gitignore`, repositorio git. Limpiar
  `.playwright-mcp/` (capturas de la descarga de datos; no son parte del proyecto).

---

## 2. Orden de sesiones

| Sesión | Tarea | Modelo · esfuerzo | Modo plan |
|---|---|---|---|
| A1 | Orden de la casa: git, `.gitignore`, documentos base, H5 | sonnet · medium | No |
| B1 | Corregir GARCH (H4) y agregar candidatos para la cola superior (H2) | opus · high | Sí |
| B2 | Escalón 3: cambio de régimen de Markov | sonnet · medium | No |
| B3 | Pruebas que faltan: MCS, Basilea, ES/Acerbi-Székely, PIT, dirección | opus · high | Sí |
| B4 | Correr backtest completo, reporte de fase 2 y *model cards* | sonnet · medium | No |
| C1 | Prerregistro de la prueba final | fable · high (u opus · high) | Sí |
| C2 | Ejecutar la prueba final una sola vez | sonnet · medium | No |
| D1 | Monte Carlo por bloques en el motor y en el caso 1 | opus · high | Sí |
| D2 | Shapley exacto, cascada y comparador | opus · high | Sí |
| E1 | Caso hipoteca UVR vs. pesos | opus · high | Sí |
| F1 | Página web estática | sonnet · medium | No |
| G1 | Revisión final de fases 1–3 | fable · high (u opus · high) | Sí |

Entre sesiones: `/clear`. Si una sesión se alarga, `/compact` antes de que el contexto pase
de la mitad.

---

## A1. Orden de la casa

1. `git init`, rama `main`. `.gitignore` con: `__pycache__/`, `.pytest_cache/`,
   `.playwright-mcp/`, `runs/**/*.csv.gz`, `data/processed/`, `*.xlsx` dentro de
   `.playwright-mcp/`. **`data/raw/` sí se versiona solo si pesa menos de 10 MB en total**;
   si pesa más, se ignora y el manifiesto basta para reconstruirlo (anótalo en decisiones).
2. Borra `.playwright-mcp/` después de confirmar que `data/raw/trm_banrep_20261114.xlsx` y
   el archivo del mismo nombre ahí tienen el mismo SHA-256 (si difieren, detente y avisa).
3. Crea `docs/decisiones.md` con las decisiones que ya están en `docs/estado.md` y en los
   docstrings (régimen de banda hasta 24-sep-1999, periodos de estrés, corte 2020-01-01,
   reajuste 21/63, z normalizada con EWMA 0,94, QR sin niveles, hash de código por contenido).
4. Crea `docs/supuestos.md` generado desde `data/supuestos/registro.jsonl` (tabla legible,
   un comando para regenerarlo; no se edita a mano).
5. Crea `docs/uso_de_ia.md`: qué hizo la IA, qué revisó el autor, qué no se delegó.
6. `MANIFEST.csv` tiene vacíos el SHA-256 y las filas de los tres archivos de FRED, aunque
   `data/manifest.json` sí los tiene: deja una sola fuente de verdad (el JSON) y que el CSV
   se genere desde él, o elimina el CSV. Agrega una prueba que verifique que los hashes del
   manifiesto coinciden con los archivos.
7. H5: revisa en `modelos/caracteristicas.py` cómo se trata `dolar30` antes de 2006-01-02.
   Reporta cuántos orígenes afectados hay y qué valor reciben. Si se rellenan con algo que
   use información futura, corrígelo y agrega el caso al canario anti-fuga.
8. `README.md` corto: qué es, cómo instalar, los tres comandos principales, aviso de que no
   es asesoría financiera.
9. Primer commit.

**Termina cuando:** `git status` limpio, pruebas en verde, H5 respondido con cifras.

---

## B1. GARCH estable y candidatos para la cola superior

**GARCH (H4):**
- Estima sobre rendimientos en puntos porcentuales (×100), que es la escala recomendada por
  `arch`, y usa los parámetros del reajuste anterior como valores iniciales.
- Reporta fallos antes y después. Si la persistencia sigue ≈ 1, documenta que el modelo
  aceptado es en la práctica IGARCH y compáralo con EWMA (que es un IGARCH sin estimar).

**Cola superior (H2).** Agrega como candidatos nuevos, sin tocar los existentes:
1. GJR y EGARCH con **t asimétrica** (`skewt` de `arch`).
2. **Simulación histórica filtrada** (FHS): residuos estandarizados por EWMA 0,94 y por
   GJR-t, remuestreados y reescalados con la volatilidad del origen.
Para h > 1, simula trayectorias (no escales por √h), con semilla fija.

**Regla de rigor:** estos modelos nacen de mirar el desarrollo, no la prueba final. Eso es
válido, pero cuenta como búsqueda: queda registrado en `docs/decisiones.md` y el MCS de la
sesión B3 los compara a todos juntos para no premiar el azar de probar muchos.

**Termina cuando:** pruebas unitarias de cada modelo (cuantiles no cruzados, semilla
reproducible, con volatilidad constante FHS coincide con la simulación histórica escalada) y
canario anti-fuga ampliado. No corras todavía el backtest completo: eso es B4.

---

## B2. Escalón 3: cambio de régimen de Markov

- `MarkovRegression` de statsmodels con 2 estados de varianza (y 3 como variante), media
  cero, sobre rendimientos ×100.
- Distribución de pronóstico: mezcla según las probabilidades de estado proyectadas con la
  matriz de transición; para h > 1, simulación de trayectorias de estado.
- Reajuste cada 63 orígenes si cada estimación tarda más de 2 s.
- Reporta probabilidades filtradas de estado alto en los periodos de estrés etiquetados
  (diagnóstico: el estado alto debería dominar en 2008 y 2014–2015).

**Termina cuando:** pruebas unitarias, canario anti-fuga y una figura de diagnóstico.

---

## B3. Pruebas que faltan (módulo `evaluacion/`, sin dependencias del dominio)

1. **Model Confidence Set** (Hansen, Lunde y Nason) por horizonte sobre la pérdida CRPS,
   con `arch.bootstrap.MCS`, bootstrap por bloques, α = 0,10. Reporta el conjunto superior.
2. **VaR al 95 % y 99 % en ambas colas** (la inferior es caída del dólar, la superior alza),
   con Kupiec y Christoffersen, como ya existe a 1 día.
3. **Semáforo de Basilea** sobre el VaR al 99 % a 1 día en ventanas móviles de 250
   observaciones: verde 0–4 excepciones, amarillo 5–9, rojo 10 o más. Reporta el porcentaje
   de ventanas en cada zona.
4. **Expected Shortfall** al 97,5 % y prueba Z2 de **Acerbi-Székely**. Para modelos que
   simulan, el ES sale de las simulaciones; para los de cuantiles, de una rejilla densa de
   cola (agrega niveles 0,0025–0,025). Si un modelo no puede dar un ES defendible, se
   declara «no aplica» con el motivo.
5. **PIT** por horizonte (aproximado por interpolación entre cuantiles) y una prueba de
   uniformidad. Máximo 3 figuras por vista del reporte.
6. **Acierto direccional** como diagnóstico, contra 50 % (prueba binomial) y con la prueba
   de Pesaran-Timmermann. Se reporta, no se optimiza.
7. Cada prueba se verifica contra un cálculo a mano o un caso con respuesta conocida, como
   ya se hizo con Kupiec y Diebold-Mariano.

**Termina cuando:** cada función tiene prueba con resultado conocido.

---

## B4. Backtest completo, reporte y *model cards*

1. `python -m laboratorio.backtest correr` con todos los modelos (incluidos los de B1 y B2).
   Como hay más modelos y niveles de cola, vigila tiempo y RAM (8 GB): si un modelo pasa de
   15 minutos, sube su paso de reajuste y anótalo.
2. Regenera `reports/fase2.md` con: resumen, MCS por horizonte, VaR/ES/Basilea, PIT,
   régimen y estrés. Mantén el criterio de descarte fijado: no lo cambies a la vista de los
   resultados.
3. Sección de conclusiones honestas: qué horizonte tiene un modelo útil y cuál no. Si a 21 y
   63 días nada supera a la simulación histórica, se dice así y el motor usa bootstrap por
   bloques en esos horizontes.
4. `models/model_cards/<modelo>.md` por cada modelo que sobreviva al menos en un horizonte:
   datos, supuestos, métricas, cuándo falla (con el régimen y el periodo), cuándo no usarlo.

**Termina cuando:** el reporte se regenera con un comando y cada cifra trae el hash de datos.

---

## C1. Prerregistro de la prueba final

Escribe `docs/prerregistro.md` **antes** de tocar los datos desde 2020. Debe fijar:
- Lista cerrada de modelos que entran (los que estén en el MCS o superen a la base en algún
  horizonte en desarrollo) y sus hiperparámetros exactos.
- Métricas, pruebas, niveles de significancia y el criterio de éxito por horizonte.
- Qué se publicará pase lo que pase (incluidos los fracasos).
- Hash del código (contenido de `src/**/*.py`), hash de `trm.csv` y semilla.
- Commit de git con el mensaje `prerregistro prueba final`.

Revisa el documento buscando cualquier puerta para ajustar después. Pide confirmación al
autor antes de cerrarlo.

---

## C2. Prueba final (una sola vez)

1. Verifica que el hash del código y de los datos coincide con el prerregistro. Si no
   coincide, detente.
2. Corre la evaluación desde 2020-01-01 hasta el último origen que permita el embargo.
3. Escribe `reports/prueba_final.md` con exactamente lo prerregistrado, incluyendo covid 2020
   y estrés 2022 por separado.
4. **Después de esta corrida no se ajusta nada.** Cualquier cambio posterior se etiqueta
   «análisis posterior (no confirmatorio)».

---

## D1. Monte Carlo por bloques

1. Bootstrap estacionario de Politis-Romano con longitud media de bloque de Politis-White,
   sobre rendimientos del régimen de flotación, semilla fija, 10.000 trayectorias por defecto.
2. Variante con los modelos que pasaron la prueba final en horizontes cortos (si alguno pasó).
3. Integra al caso «compra de dólares»: costo esperado, P5, P50, P95, P(superar presupuesto)
   y P(salir más barato que comprar hoy), junto a la distribución empírica que ya existe.
4. Invariantes con prueba: con volatilidad cero el Monte Carlo coincide con el determinista;
   misma semilla da el mismo hash de resultado; con bloques de longitud 1 se recupera el
   bootstrap simple.
5. Gráfica de abanico (*fan chart*) de la TRM proyectada.

---

## D2. Shapley, cascada y comparador

1. Valores de Shapley **exactos** para la diferencia de resultado entre dos escenarios
   (con k supuestos que cambian, 2^k evaluaciones; si k > 10, detente y pregunta).
2. Prueba: la suma de aportes es igual a la diferencia total (eficiencia de Shapley).
3. Cascada (*waterfall*) con los aportes, ordenados por magnitud.
4. Comparador A vs. B: tabla de supuestos que difieren (valor, versión, fuente) y la cascada.
5. Comando: `python -m laboratorio.motor comparar <ficha_A> <ficha_B>`.

---

## E1. Caso hipoteca UVR vs. pesos a tasa fija

1. **Verifica en fuente oficial** del Banco de la República la metodología de cálculo de la
   UVR y cítala en `docs/decisiones.md` con enlace y fecha de consulta. Comprueba que tu
   cálculo reproduce la UVR publicada en `data/processed/uvr_diaria.csv` (error máximo a
   definir y reportar).
2. Proyecta cuota y saldo de ambos créditos bajo los escenarios deterministas, la
   reproducción histórica y Monte Carlo de inflación (bootstrap por bloques del IPC mensual).
3. Calcula la **inflación de equilibrio**: la inflación constante a partir de la cual la UVR
   sale más cara que la tasa fija, en valor presente y en total pagado.
4. Supuestos ilustrativos (monto, plazo, tasas) como versiones nuevas del registro.
5. Invariantes: la suma de abonos a capital es igual al monto; con inflación cero la UVR no
   cambia; saldo final cero.
6. Reporte `reports/hipoteca_uvr.md` con cifras rastreables y limitaciones.

---

## F1. Página web estática

- HTML, CSS y JavaScript sin servidor, lista para GitHub Pages. Los resultados se precalculan
  en Python y se exportan como JSON; la página no recalcula modelos.
- Tres paneles: **Supuestos** (con fuente visible), **Resultado** (abanico) y
  **Explicación** (cascada Shapley). Máximo tres gráficas por vista, pensada para celular.
- Selector de caso (dólares, hipoteca) y línea de tiempo de versiones del escenario.
- Aviso visible: no es asesoría financiera; los rangos describen incertidumbre.
- Revisa la página en un navegador a 375 px y a 1280 px de ancho antes de terminar.

---

## G1. Revisión final

Revisa como un evaluador externo: fugas de información, cifras sin hash, coberturas
publicadas sin su medición real, afirmaciones que el reporte no respalda, pruebas que no
prueban nada. Entrega una lista priorizada (bloqueante, importante, menor) y corrige solo
lo bloqueante. Actualiza `README.md` y `docs/estado.md`.

---

## 3. Fuera de este prompt (fase 4, después)

Deep learning probabilístico (N-HiTS o TFT) en Kaggle/Colab, combinación de pronósticos y
caso pyme importadora. Requiere su propio prompt cuando la fase 3 esté cerrada. El riesgo
país (EMBI o CDS) solo entra si hay una fuente gratuita y oficial; si no, se documenta su
ausencia en `docs/decisiones.md`.

---

## 4. Mensajes para pegar en cada sesión

Antes de pegar: `/clear`, luego `/model <modelo>` y `/effort <esfuerzo>` según la tabla de la
sección 2, y Shift + Tab si la sesión va en modo plan.

```
A1: Lee docs/estado.md y la sección 0 y A1 de PROMPT_CONTINUACION_FINANZAS.md. Haz A1.
B1: Lee docs/estado.md y las secciones 0, 1 y B1 de PROMPT_CONTINUACION_FINANZAS.md. Propón el plan de B1 antes de escribir código.
B2: Lee docs/estado.md y las secciones 0 y B2 de PROMPT_CONTINUACION_FINANZAS.md. Haz B2.
B3: Lee docs/estado.md y las secciones 0 y B3 de PROMPT_CONTINUACION_FINANZAS.md. Propón el plan de B3 antes de escribir código.
B4: Lee docs/estado.md y las secciones 0 y B4 de PROMPT_CONTINUACION_FINANZAS.md. Haz B4.
C1: Lee docs/estado.md, reports/fase2.md (solo resumen y MCS) y las secciones 0 y C1 de PROMPT_CONTINUACION_FINANZAS.md. Redacta el prerregistro y espera mi confirmación.
C2: Lee docs/prerregistro.md y la sección C2 de PROMPT_CONTINUACION_FINANZAS.md. Haz C2.
D1: Lee docs/estado.md y las secciones 0 y D1 de PROMPT_CONTINUACION_FINANZAS.md. Propón el plan de D1 antes de escribir código.
D2: Lee docs/estado.md y las secciones 0 y D2 de PROMPT_CONTINUACION_FINANZAS.md. Propón el plan de D2 antes de escribir código.
E1: Lee docs/estado.md, la sección 8 de PROMPT_FINANZAS.md y las secciones 0 y E1 de PROMPT_CONTINUACION_FINANZAS.md. Propón el plan de E1 antes de escribir código.
F1: Lee docs/estado.md, la sección 9 de PROMPT_FINANZAS.md y las secciones 0 y F1 de PROMPT_CONTINUACION_FINANZAS.md. Haz F1.
G1: Lee docs/estado.md, la sección 13 de PROMPT_FINANZAS.md y las secciones 0 y G1 de PROMPT_CONTINUACION_FINANZAS.md. Haz G1.
```
