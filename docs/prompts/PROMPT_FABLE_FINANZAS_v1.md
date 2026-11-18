# PROMPT FABLE — Laboratorio de Escenarios (desde el 15-nov-2026)

Este archivo reordena el trabajo pendiente para que **Fable haga primero lo que exige más
rigor**: la ruta hasta la prueba final y los números del caso «compra de dólares». Todo lo que
estaba asignado a otros modelos y no está en esa ruta queda para después (sección 5).

Relación con los demás archivos:
- `PROMPT_FINANZAS.md`: especificación completa (no cambia).
- `PROMPT_CONTINUACION_FINANZAS.md`: detalle de cada tarea (A1, B1…G1). Aquí se citan sus
  secciones en vez de repetirlas. **Si algo de aquí contradice a ese archivo, manda este.**
- `docs/estado.md`: estado vivo.

---

## 0. Reglas de estas sesiones

1. Aplican todas las reglas de la sección 0 de `PROMPT_CONTINUACION_FINANZAS.md`
   (prueba final intocable, canario anti-fuga, `pytest -q -x`, `docs/estado.md` ≤ 15 líneas,
   `docs/decisiones.md`, nada de leer `data/raw/` ni `runs/**/*.csv.gz` completos).
2. **Fable piensa, decide y escribe el código delicado; los cálculos largos se lanzan como
   comandos** y de su salida se lee solo un resumen de máximo 40 líneas. Las corridas de más
   de 2 minutos van en segundo plano con registro en `runs/`.
3. No leas `reports/fase2.md` completo: usa solo las secciones que pida la tarea.
4. **Lo visual se deja básico**: nada de página web en estas sesiones. Reportes en Markdown;
   figuras solo con matplotlib por defecto, sin estilo, máximo una por tema.
5. Si el contexto pasa de la mitad, `/compact`. Entre sesiones, `/clear`.
6. Autorización del autor para esta ruta: se puede **agregar** la constante
   `HORIZONTES_LARGOS` en `backtest/particion.py` (sección 1, N1). Las constantes existentes
   no se tocan.

---

## 1. Hallazgos de la revisión del 15-nov que se suman al diagnóstico

(El diagnóstico H1–H5 está en la sección 1 de `PROMPT_CONTINUACION_FINANZAS.md`.)

- **N1. Desfase de horizontes.** El caso «compra de dólares» reparte las compras en 11 meses
  (≈ 230 observaciones), pero el backtest solo llega a 63. Hoy ningún número del caso está
  respaldado por una evaluación fuera de muestra. Solución: evaluar también h = 126 y h = 252
  con los modelos que simulan trayectorias (caminata, simulación histórica, bootstrap por
  bloques y, si existen, FHS y Markov). En desarrollo hay pocas ventanas independientes
  (≈ 14 a h=252), así que en horizontes largos el criterio es de **cobertura** (con n efectivo
  = n/h), no de Diebold-Mariano. Se reporta su baja potencia.
- **N2. Comparaciones múltiples.** Se probaron 6 candidatos × 4 horizontes con p < 0,05 sin
  corrección. Los aciertos a h=1 son robustos (p < 0,001), pero los casi-aciertos (EWMA,
  p = 0,053 y 0,056) **no se rescatan**. El prerregistro fija la corrección (MCS como criterio
  principal; Holm por modelo entre horizontes como verificación).
- **N3. Ganancia pequeña.** A h=1 el mejor modelo baja el CRPS entre 2 % y 4 %. Es real, pero
  sirve para riesgo diario (VaR), no para el caso de compras mensuales. El reporte lo dice así.
- **N4. LightGBM empeora a 21 y 63 días** (CRPS/base 1,05 y 1,14). Antes de decidir, diagnostica
  con PIT si es sobreajuste o la estandarización z = y/(σ·√h). Se diagnostica en desarrollo;
  nunca se ajusta mirando la prueba final.
- **N5. H5 casi resuelto.** En `modelos/caracteristicas.py`, `dolar30` y `pol90` quedan en NaN
  antes de existir el dato (no hay relleno con futuro). Falta confirmar qué hace
  `reg_cuantiles` con esos NaN (descarta filas, imputa o falla) y cuántos orígenes de 2005
  se afectan.
- **N6. Violaciones agrupadas.** Christoffersen rechaza independencia en las líneas base y en
  EWMA: las excepciones llegan en racimos. Eso respalda usar bootstrap por bloques en el motor.

---

## 2. Sesiones con Fable (en este orden)

| Sesión | Qué hace | Esfuerzo | Modo plan |
|---|---|---|---|
| S1 | git mínimo, N5, B1, bootstrap por bloques como modelo, horizontes largos (N1) | high | Sí |
| S2 | B2 (Markov) y B3 (pruebas que faltan) | high | Sí |
| S3 | B4: correr todo, reporte, conclusiones y fichas de modelo | high | No |
| S4 | C1: prerregistro de la prueba final | high | Sí |
| S5 | C2: prueba final, una sola vez | medium | No |
| S6 | D1: Monte Carlo en el caso «compra de dólares» | high | Sí |
| S7 | G1: revisión externa de lo hecho | high | Sí |

Si `/model` no ofrece Fable, usa `opus` con esfuerzo `high` en todas, sin cambiar nada más.

---

## S1. Cimientos y candidatos nuevos

1. **Git mínimo** (solo el paso 1 de A1): `git init`, rama `main`, `.gitignore` como dice A1,
   primer commit. El resto de A1 (README, `uso_de_ia.md`, limpieza de `.playwright-mcp/`,
   manifiesto CSV) **espera**; solo se agrega `.playwright-mcp/` al `.gitignore`.
2. **N5**: responde con cifras (orígenes afectados, tratamiento de NaN por modelo). Si algún
   modelo usa información futura, corrígelo y agrega el caso al canario.
3. **B1 completo** (GARCH en escala ×100 con valores iniciales del reajuste anterior; GJR y
   EGARCH con t asimétrica; FHS con EWMA y con GJR-t; trayectorias simuladas para h > 1).
4. **Bootstrap estacionario por bloques** (Politis-Romano, longitud media de bloque de
   Politis-White estimada solo con datos hasta el origen) como **modelo nuevo** del catálogo.
   Es a la vez línea base de horizontes largos y el motor que usará S6, así que se escribe una
   sola vez en `modelos/` y el motor lo importa después.
5. **N1**: agrega `HORIZONTES_LARGOS = (126, 252)` y que el corredor pueda evaluar solo los
   modelos que simulan trayectorias en esos horizontes. Verifica que la purga y el último
   origen de desarrollo respeten h = 252 (ningún objetivo puede caer en 2020 o después).
6. Registra en `docs/decisiones.md` que B1 y el bootstrap nacieron de mirar el desarrollo
   (cuenta como búsqueda; el MCS los compara a todos).

**Termina cuando:** pruebas de cada modelo nuevo (cuantiles no cruzados, semilla reproducible,
FHS con volatilidad constante = simulación histórica escalada, bootstrap con bloque 1 = bootstrap
simple), canario ampliado, prueba de que ningún objetivo de desarrollo pasa del corte, commit.
No corras el backtest completo.

## S2. Markov y pruebas que faltan

- **B2** tal como está en `PROMPT_CONTINUACION_FINANZAS.md`. Va antes del prerregistro porque
  la prueba final se usa una sola vez: un modelo que no exista en S4 ya no puede entrar.
- **B3** completo (MCS, VaR 95/99 en ambas colas, Basilea, ES 97,5 % con Acerbi-Székely Z2,
  PIT, acierto direccional con Pesaran-Timmermann), cada función verificada contra un cálculo
  a mano o un caso con respuesta conocida.
- Agrega la **evaluación de cobertura con n efectivo** para horizontes largos (N1): intervalo
  binomial con n/h observaciones independientes.

**Termina cuando:** pruebas en verde, canario con Markov, commit.

## S3. Backtest completo y conclusiones

1. B4 completo. Corre en segundo plano; vigila tiempo y RAM (8 GB). Si un modelo pasa de 15
   minutos, sube su paso de reajuste y anótalo.
2. Regenera `reports/fase2.md` con todo lo de B4 **más** horizontes 126 y 252, N4 (PIT de
   LightGBM) y N2 (MCS y Holm). El criterio de descarte fijado no cambia.
3. Sección de conclusiones honestas de máximo 15 líneas: qué horizonte tiene un modelo útil,
   cuál no, y qué motor debe usar el caso en cada horizonte.
4. Fichas cortas en `models/model_cards/` (máximo una página cada una) solo para los modelos
   que sobreviven en algún horizonte.

**Termina cuando:** el reporte se regenera con un comando, cada cifra trae el hash de datos y
hay commit.

## S4. Prerregistro

Todo lo de C1, más:
- Horizontes largos y su criterio de cobertura con n efectivo.
- La corrección por comparaciones múltiples (N2).
- Qué motor usará el caso por horizonte según lo que pase en la prueba final (si un modelo
  falla allí, el caso usa el bootstrap por bloques).
- **No se actualizan los datos** entre S4 y S5: el hash de `trm.csv` queda fijo.
- Al final, una lista de 5 a 8 preguntas de sí o no, en lenguaje sencillo, para que el autor
  confirme (por ejemplo: «¿Estás de acuerdo en que si EWMA no supera a la base a 21 días en la
  prueba final, se publica como fracaso?»). Espera la confirmación antes del commit
  `prerregistro prueba final`.

## S5. Prueba final

C2 tal cual. Además: si el hash del código no coincide con el prerregistro, **detente y no
corras nada**. Resultados en `reports/prueba_final.md`, con covid 2020 y estrés 2022 aparte.

## S6. Monte Carlo en el caso «compra de dólares»

D1 completo, con estos cambios:
- Usa el bootstrap por bloques escrito en S1 (no lo reescribas).
- La variante con modelos solo entra en los horizontes donde el modelo pasó la prueba final.
- El reporte del caso agrega una línea por cifra principal diciendo qué evaluación la respalda
  (horizonte, cobertura medida en la prueba final) o que no tiene respaldo.
- Gráfica de abanico básica (una sola, matplotlib por defecto).
- Invariantes con prueba: volatilidad cero = determinista; misma semilla = mismo hash;
  bloque 1 = bootstrap simple.

## S7. Revisión externa

G1 tal cual, limitada a lo hecho en S1–S6 y a las fases 0–2. Corrige solo lo bloqueante y
deja lo demás listado en `docs/estado.md`.

---

## 3. Mensajes para pegar en cada sesión

Antes de cada uno: `/clear`, luego `/model` (elige Fable), luego `/effort` según la tabla y
Shift + Tab si la sesión va en modo plan.

```
S1: Lee docs/estado.md, la sección 0 y 1 de PROMPT_FABLE_FINANZAS.md y la sección S1. De PROMPT_CONTINUACION_FINANZAS.md lee solo la sección 0, el paso 1 de A1 y B1. Propón el plan de S1 antes de escribir código.
S2: Lee docs/estado.md, la sección 0 y S2 de PROMPT_FABLE_FINANZAS.md, y las secciones B2 y B3 de PROMPT_CONTINUACION_FINANZAS.md. Propón el plan de S2 antes de escribir código.
S3: Lee docs/estado.md, la sección 0, N2, N4 y S3 de PROMPT_FABLE_FINANZAS.md, y la sección B4 de PROMPT_CONTINUACION_FINANZAS.md. Haz S3.
S4: Lee docs/estado.md, las conclusiones y el MCS de reports/fase2.md, la sección 0 y S4 de PROMPT_FABLE_FINANZAS.md y la sección C1 de PROMPT_CONTINUACION_FINANZAS.md. Redacta el prerregistro y espera mi confirmación.
S5: Lee docs/prerregistro.md, la sección S5 de PROMPT_FABLE_FINANZAS.md y la sección C2 de PROMPT_CONTINUACION_FINANZAS.md. Haz S5.
S6: Lee docs/estado.md, el resumen de reports/prueba_final.md, la sección 0 y S6 de PROMPT_FABLE_FINANZAS.md y la sección D1 de PROMPT_CONTINUACION_FINANZAS.md. Propón el plan de S6 antes de escribir código.
S7: Lee docs/estado.md, la sección 13 de PROMPT_FINANZAS.md, la sección S7 de PROMPT_FABLE_FINANZAS.md y la sección G1 de PROMPT_CONTINUACION_FINANZAS.md. Haz S7.
```

---

## 4. Qué debe revisar el autor en cada sesión (sin saber programar)

- Al final de cada sesión, pide: «Resúmeme en 5 líneas qué cambió y qué quedó pendiente».
- Confirma que `docs/estado.md` cambió y que hubo commit (`git log --oneline -3`).
- En S4 responde las preguntas de sí o no. Si una no la entiendes, pide que te la expliquen
  con un ejemplo en pesos antes de aceptar.

---

## 5. Lo que espera (otros modelos, después de S7)

- Resto de A1: README, `docs/uso_de_ia.md`, `docs/supuestos.md`, manifiesto CSV, borrar
  `.playwright-mcp/` (sonnet · medium).
- D2: Shapley, cascada y comparador (opus · high).
- E1: caso hipoteca UVR vs. pesos (opus · high).
- F1: página web (sonnet · medium), cuando lo visual vuelva a importar.
- Fase 4: deep learning en Kaggle/Colab, combinación de pronósticos, caso pyme.
