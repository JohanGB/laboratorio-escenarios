# PROMPT FABLE — Laboratorio de Escenarios · v2 (15-nov-2026)

Reemplaza a la v1 (guardada como `PROMPT_FABLE_FINANZAS_v1.md`). Ordena el trabajo pendiente
para que **Fable haga primero lo que exige más rigor**: la ruta hasta la prueba final y los
números del caso «compra de dólares». Lo que no está en esa ruta espera (sección 7).

Relación con los demás archivos:
- `PROMPT_FINANZAS.md`: especificación completa (no cambia).
- `PROMPT_CONTINUACION_FINANZAS.md`: detalle de cada tarea (A1, B1…G1). Aquí se citan sus
  secciones en vez de repetirlas. **Si algo de aquí lo contradice, manda este archivo.**
- `docs/estado.md`: estado vivo.

---

## 0. Dónde va el proyecto (revisión del 15-nov)

| Fase | Estado |
|---|---|
| 0. Datos y EDA | Completa: manifiesto SHA-256, limpieza, validación, regímenes, `reports/fase0.md` |
| 1. Motor | Parcial: supuestos encadenados, ficha reproducible, cifras con hash, caso 1 con escenarios deterministas e históricos. Faltan Monte Carlo, Shapley y comparador |
| 2. Modelos y evaluación | Parcial: protocolo aprobado, 9 modelos corridos (2005–2019), CRPS, pinball, cobertura, Kupiec, Christoffersen, DM-HLN. Faltan Markov, MCS, ES, Basilea, PIT, horizontes largos, prerregistro y prueba final |
| 3. Caso hipoteca y web | Sin empezar |
| Repositorio | Sin git, sin README, sin `docs/decisiones.md` |

Resultado principal hasta hoy: **los modelos solo superan a la línea base a 1 día**. A 5, 21 y
63 días ninguno lo logra, y el caso «compra de dólares» trabaja a ≈ 230 días, donde todavía no
hay ninguna evaluación fuera de muestra.

---

## 1. Reglas de estas sesiones

1. Aplican las reglas de la sección 0 de `PROMPT_CONTINUACION_FINANZAS.md` (prueba final
   intocable, canario anti-fuga, `pytest -q -x`, `docs/estado.md` ≤ 15 líneas,
   `docs/decisiones.md`, nada de leer `data/raw/` ni `runs/**/*.csv.gz` completos).
2. **Fable piensa, decide y escribe el código delicado; los cálculos largos se lanzan como
   comandos** y de su salida se lee un resumen de máximo 40 líneas. Las corridas de más de
   2 minutos van en segundo plano con registro en `runs/`.
3. No leas `reports/fase2.md` completo: solo las secciones que pida la tarea.
4. **Lo visual se deja básico**: sin página web. Reportes en Markdown; figuras con matplotlib
   por defecto, sin estilo, máximo una por tema.
5. Si el contexto pasa de la mitad, `/compact`. Entre sesiones, `/clear`.
6. Autorización del autor: se pueden **agregar** constantes en `backtest/particion.py`
   (`HORIZONTES_LARGOS`, `NIVELES_COLA`). Las existentes no se tocan.

---

## 2. Hallazgos que condicionan lo que sigue

Los de la v1 se mantienen (N1 desfase de horizontes, N2 comparaciones múltiples, N3 ganancia
pequeña a 1 día, N4 LightGBM empeora a 21 y 63, N5 NaN de `dolar30`/`pol90`, N6 violaciones
en racimos). En resumen, N1: el caso necesita h = 126 y 252, evaluados por cobertura con
n efectivo = n/h, no por Diebold-Mariano.

Esta revisión agrega cinco:

- **R1. El embargo depende del horizonte máximo del modelo.** En `backtest/corredor.py`,
  `ultimo = ultimo_origen(vista.n, max(modelo.horizontes))`. Si un modelo agrega h = 252,
  pierde ≈ 190 orígenes también a h = 1, y sus cifras dejan de ser comparables con las ya
  corridas. Solución: los horizontes largos son **una corrida aparte**
  (`runs/backtest_largo/`) y la corrida corta conserva exactamente sus 3493 orígenes.
  Prueba: los orígenes de la corrida corta no cambian al agregar modelos largos.
- **R2. La prueba final ya fue vista.** `reports/fase0.md` y el caso «compra de dólares»
  usan datos de 2020 a 2026 (covid, 2022, derivas). Ningún modelo se eligió con ellos, pero
  no son datos ciegos. El prerregistro lo declara así («datos no usados para selección, pero
  vistos en el análisis exploratorio») y no lo presenta como una muestra nunca vista.
- **R3. El código de la prueba final debe existir antes del prerregistro.** Hoy
  `cargar_desarrollo` impide leer datos ≥ 2020, y no hay función para la prueba final. Si se
  escribe en S5, el hash del código no coincidirá con el prerregistro. Solución: en F4 se
  escribe `cargar_prueba_final` y el comando `python -m laboratorio.backtest final`, se
  prueban **con datos sintéticos** (sin abrir 2020+) y entran en el hash que se congela.
- **R4. Los niveles de cola van aparte.** El ES y Acerbi-Székely necesitan niveles
  0,0025–0,025, pero cambiar `NIVELES` altera el CRPS y rompe la comparación. Se agrega
  `NIVELES_COLA` y el CRPS sigue con los 11 niveles actuales.
- **R5. A 252 días la prueba final casi no tiene potencia.** De 2020 a nov-2026 caben unas
  6 ventanas independientes de un año. En la prueba final, h = 126 y 252 se reportan como
  **descriptivos** (cobertura observada e intervalo binomial con n efectivo), no como
  aprobado o rechazado. El caso lo dice en cada cifra que dependa de ellos.

---

## 3. Orden de sesiones

Primero va lo que necesita Fable. Las tareas de otros modelos que siguen aquí son las que
**deben existir antes del prerregistro** (un modelo que no exista en F4 ya no puede entrar
a la prueba final); todo lo demás espera.

| # | Sesión | Qué hace | Modelo · esfuerzo | Modo plan |
|---|---|---|---|---|
| 1 | **F1** | git mínimo, N5, R1, R4, horizontes largos, bootstrap por bloques | **fable · high** | Sí |
| 2 | O1 | B1: valores iniciales GARCH, t asimétrica, FHS | opus · high | Sí |
| 3 | O2 | B2: Markov (2 y 3 estados) | opus · medium | No |
| 4 | **F2** | B3: MCS, VaR, Basilea, ES/Acerbi-Székely, PIT, dirección, n efectivo | **fable · high** | Sí |
| 5 | O3 | B4: correr todo en segundo plano y regenerar el reporte | sonnet · medium | No |
| 6 | **F3** | Conclusiones, N4 (PIT de LightGBM), N2 (MCS y Holm), fichas de modelo | **fable · high** | No |
| 7 | **F4** | Prerregistro + código de la prueba final (R2, R3, R5) | **fable · high** | Sí |
| 8 | O4 | C2: prueba final, una sola vez | sonnet · medium | No |
| 9 | **F5** | D1: Monte Carlo en el caso «compra de dólares» | **fable · high** | Sí |
| 10 | **F6** | G1: revisión externa de S1–F5 y fases 0–2 | **fable · high** | Sí |

Si `/model` no ofrece Fable, usa `opus` con esfuerzo `high` en las sesiones F, sin cambiar
nada más.

Si quieres ir aún más rápido, O2 (Markov) es la única que se puede saltar: entonces Markov
no entra a la prueba final y cualquier resultado suyo posterior se etiqueta «no
confirmatorio». Decídelo antes de F4.

---

## F1. Cimientos (Fable)

1. **Git mínimo** (paso 1 de A1): `git init`, rama `main`, `.gitignore` de A1 (incluye
   `.playwright-mcp/`), primer commit. El resto de A1 espera.
2. **N5** con cifras. Lo que se sabe (15-nov): `dolar_amplio` empieza el 2006-01-02, así que
   `dolar30` es NaN en los orígenes de 2005; `politica` empieza en 1998-02, así que `pol90`
   debería existir desde mediados de 1998 y sus NaN estar solo en filas de entrenamiento
   1992–1998. Solo LightGBM usa ambas (NaN nativo); la regresión por cuantiles no las usa.
   Confírmalo con conteos (orígenes y filas de entrenamiento con NaN, por variable y año) y
   di qué hace cada modelo con ellos. Si alguno usa información futura, corrígelo y agrega el
   caso al canario.
3. **R1**: corrida larga separada. Agrega `HORIZONTES_LARGOS = (126, 252)`; el corredor
   evalúa en ellos solo los modelos que simulan trayectorias. Prueba de que los orígenes de
   la corrida corta no cambian y de que ningún objetivo de desarrollo cae en 2020 o después.
4. **R4**: agrega `NIVELES_COLA` sin tocar `NIVELES`.
5. **Bootstrap estacionario por bloques** (Politis-Romano; longitud media de bloque de
   Politis-White estimada solo con datos hasta el origen) como modelo del catálogo, en
   `modelos/`. Es línea base de horizontes largos y el motor que usará F5: se escribe una
   sola vez y el motor lo importa.
6. Registra en `docs/decisiones.md` que estos modelos nacen de mirar el desarrollo (cuenta
   como búsqueda; el MCS los compara a todos).

**Termina cuando:** pruebas del bootstrap (cuantiles no cruzados, semilla reproducible,
bloque 1 = bootstrap simple), canario ampliado, prueba de R1 y commit. No corras el
backtest completo.

## O1. GARCH y cola superior (Opus)

B1 con una corrección: la escala ×100 **ya existe** (`modelos/garch.py` estima sobre `r·100`,
no la reimplementes). Lo nuevo es usar los parámetros del reajuste anterior como valores
iniciales (posible causa de los 38 fallos de GARCH y 28 de GJR), GJR y EGARCH con
`skewt`, FHS con EWMA y con GJR-t, trayectorias simuladas para h > 1. Reporta fallos de
convergencia antes y después. Pruebas: FHS con volatilidad constante = simulación histórica
escalada. Commit.

## O2. Markov (Opus)

B2 tal cual. Pruebas, canario y una figura de diagnóstico básica. Commit.

## F2. Pruebas que faltan (Fable)

B3 completo, más:
- ES con `NIVELES_COLA` (R4) o desde las simulaciones; si un modelo no puede dar un ES
  defendible, «no aplica» con el motivo.
- Cobertura con n efectivo para horizontes largos: intervalo binomial con n/h observaciones.
- Cada función verificada contra un cálculo a mano o un caso con respuesta conocida
  (como ya se hizo con Kupiec y DM).

**Termina cuando:** pruebas en verde y commit.

## O3. Backtest completo (Sonnet)

B4 pasos 1 y 2: corre corta y larga en segundo plano; vigila tiempo y RAM (8 GB). Si un
modelo pasa de 15 minutos, sube su paso de reajuste y anótalo. Regenera `reports/fase2.md`
con un comando. **No escribe conclusiones ni fichas**: eso es F3. Commit.

## F3. Conclusiones (Fable)

1. N4: PIT de LightGBM a 21 y 63 días; di si es sobreajuste o la estandarización
   z = y/(σ·√h). Solo diagnóstico en desarrollo.
2. N2: MCS por horizonte como criterio principal y Holm por modelo entre horizontes como
   verificación. Los casi-aciertos no se rescatan.
3. Conclusiones honestas, máximo 15 líneas: qué horizonte tiene un modelo útil, cuál no y
   qué motor debe usar el caso en cada horizonte (por defecto, bootstrap por bloques).
4. Fichas de máximo una página en `models/model_cards/`, solo para modelos que sobreviven.

**Termina cuando:** cada cifra trae el hash de datos y hay commit.

## F4. Prerregistro y código de la prueba final (Fable)

Todo lo de C1, más:
- **R3**: `cargar_prueba_final` y `python -m laboratorio.backtest final`, probados con datos
  sintéticos, sin abrir 2020+. Quedan dentro del hash del código.
- **R2**: la declaración de que los datos 2020+ fueron vistos en el EDA.
- **R5**: h = 126 y 252 como descriptivos en la prueba final.
- Corrección por comparaciones múltiples (N2) y criterio de éxito por horizonte.
- Qué motor usa el caso por horizonte según el resultado (si un modelo falla, bootstrap).
- El hash de `trm.csv` queda fijo: no se actualizan datos entre F4 y O4.
- Al final, de 5 a 8 preguntas de sí o no, en lenguaje sencillo y con un ejemplo en pesos,
  para que el autor confirme. Espera la confirmación antes del commit
  `prerregistro prueba final`.

## O4. Prueba final (Sonnet)

C2 tal cual. Antes de correr, verifica el hash del código y de los datos contra
`docs/prerregistro.md`; si no coinciden, **detente y no corras nada**. Usa solo el comando
del prerregistro. Resultados en `reports/prueba_final.md`, con covid 2020 y estrés 2022
aparte. No interpreta más allá de lo prerregistrado. Commit.

## F5. Monte Carlo en el caso (Fable)

D1 completo, con estos cambios:
- Usa el bootstrap de F1 (no lo reescribas).
- La variante con modelos solo entra en los horizontes donde el modelo pasó la prueba final.
- Cada cifra principal del reporte lleva una línea con la evaluación que la respalda
  (horizonte y cobertura medida) o «sin respaldo fuera de muestra».
- Una sola gráfica de abanico, matplotlib por defecto.
- Invariantes con prueba: volatilidad cero = determinista; misma semilla = mismo hash;
  bloque 1 = bootstrap simple.

## F6. Revisión externa (Fable)

G1 limitada a lo hecho en F1–F5 y fases 0–2. Corrige solo lo bloqueante; lo demás queda
listado en `docs/estado.md`.

---

## 4. Mensajes para pegar en cada sesión

Antes de cada uno: `/clear`, luego `/model` y `/effort` según la tabla de la sección 3, y
Shift + Tab si la sesión va en modo plan.

```
F1: Lee docs/estado.md y las secciones 1, 2 y F1 de PROMPT_FABLE_FINANZAS.md. De PROMPT_CONTINUACION_FINANZAS.md lee solo la sección 0 y el paso 1 de A1. Propón el plan de F1 antes de escribir código.
O1: Lee docs/estado.md, la sección O1 de PROMPT_FABLE_FINANZAS.md y las secciones 0 y B1 de PROMPT_CONTINUACION_FINANZAS.md. Propón el plan de O1 antes de escribir código.
O2: Lee docs/estado.md, la sección O2 de PROMPT_FABLE_FINANZAS.md y las secciones 0 y B2 de PROMPT_CONTINUACION_FINANZAS.md. Haz O2.
F2: Lee docs/estado.md, las secciones 1, 2 y F2 de PROMPT_FABLE_FINANZAS.md y la sección B3 de PROMPT_CONTINUACION_FINANZAS.md. Propón el plan de F2 antes de escribir código.
O3: Lee docs/estado.md, la sección O3 de PROMPT_FABLE_FINANZAS.md y la sección B4 de PROMPT_CONTINUACION_FINANZAS.md. Haz O3.
F3: Lee docs/estado.md, el resumen y el MCS de reports/fase2.md y las secciones 1, 2 y F3 de PROMPT_FABLE_FINANZAS.md. Haz F3.
F4: Lee docs/estado.md, las conclusiones de reports/fase2.md, las secciones 1, 2 y F4 de PROMPT_FABLE_FINANZAS.md y la sección C1 de PROMPT_CONTINUACION_FINANZAS.md. Propón el plan de F4, haz el código, redacta el prerregistro y espera mi confirmación.
O4: Lee docs/prerregistro.md, la sección O4 de PROMPT_FABLE_FINANZAS.md y la sección C2 de PROMPT_CONTINUACION_FINANZAS.md. Haz O4.
F5: Lee docs/estado.md, el resumen de reports/prueba_final.md, las secciones 1 y F5 de PROMPT_FABLE_FINANZAS.md y la sección D1 de PROMPT_CONTINUACION_FINANZAS.md. Propón el plan de F5 antes de escribir código.
F6: Lee docs/estado.md, la sección 13 de PROMPT_FINANZAS.md, la sección F6 de PROMPT_FABLE_FINANZAS.md y la sección G1 de PROMPT_CONTINUACION_FINANZAS.md. Haz F6.
```

---

## 5. Qué revisa el autor en cada sesión (sin saber programar)

- Al final, pide: «Resúmeme en 5 líneas qué cambió y qué quedó pendiente».
- Confirma que `docs/estado.md` cambió y que hubo commit (`git log --oneline -3`).
- En F4 responde las preguntas de sí o no. Si una no la entiendes, pide un ejemplo en pesos
  antes de aceptar. **No confirmes el prerregistro con prisa**: después de O4 no hay vuelta.

## 6. Señales de alarma (detén la sesión y pregunta)

- Un modelo supera a la base a 63 o 252 días por mucho (CRPS/base < 0,90): casi siempre es
  una fuga de información, no un hallazgo.
- Alguna prueba se cambia para que pase, en vez de corregir el código.
- Se propone tocar `INICIO_PRUEBA_FINAL`, `NIVELES` o el criterio de descarte.

---

## 7. Lo que espera (después de F6)

- Resto de A1: README, `docs/uso_de_ia.md`, `docs/supuestos.md`, manifiesto CSV, borrar
  `.playwright-mcp/` (sonnet · medium).
- D2: Shapley, cascada y comparador (opus · high).
- E1: caso hipoteca UVR vs. pesos (opus · high).
- F1 de la continuación (página web): cuando lo visual vuelva a importar (sonnet · medium).
- Fase 4: deep learning en Kaggle/Colab, combinación de pronósticos, caso pyme.
