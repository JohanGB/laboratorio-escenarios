# Estado
Brújula FX (fases M0-M7, docs/prompts/PROMPT_BRUJULA_FX.md). M0 hecho (17-nov), en revisión del autor; SIGUE M1 (datos multidivisa) tras su visto bueno. Decisiones en docs/decisiones.md.
- M0: pyproject instalable (`pip install -e ".[dev]"`), requirements-prueba-final.txt, prompts en docs/prompts/, conftest reconstruye data/processed (I7 cerrado), CI en .github/workflows/pruebas.yml (`-m "not lento"`), runs/*.log se quedan. PENDIENTE: licencia (pregunta al autor) y CI verde en GitHub (falta push).
- Suite: 372 pruebas pasan, 0 saltadas (`pytest -q -x`, 7 min 48 s, 17-nov); 2 marcadas `lento`. El README cita el número y hay prueba.
- Git: rama main; `* -text` salvo `*.py` y `docs/prerregistro*.md` (`eol=lf`). data/raw versionado; data/processed, runs/**/*.csv.gz, *.egg-info y .playwright-mcp ignorados. Repo PÚBLICO.
- Datos: data/raw (inmutable) -> data/processed (`python -m laboratorio.datos.limpieza`). trm.csv: 8387 obs., 1991-12-02 a 2026-11-14. EDA en reports/fase0.md.
- Backtest: origen móvil desde 2005-01-03, ventana expansiva, reajuste 21, embargo = h_max; 17 modelos (runs/backtest_desarrollo/, runs/backtest_largo/). En desarrollo solo `lightgbm_cuantiles` a h = 1 sobrevive.
- Prueba final (16-nov, prerregistro cerrado, etiquetas `prerregistro-final`, `prerregistro-adenda-1`): única confirmatoria con ÉXITO = `lightgbm_cuantiles` a h = 1 (CRPS/base 0,977). Cobertura 95 % del motor 0,950/0,961/0,968/0,960/0,992/0,932 a 1/5/21/63/126/252 (n ef. 1564/313/74/25/11/5).
- Caso compra de dólares (F5/F5b/F6): motor `bootstrap_est_filtrado`; respaldo en data/respaldo/prueba_final.json. P(superar presupuesto) 25,5 % histórico, 31,5 % solo flotación, 45,4 % motor (la banda entra amplificada 2,1 veces). Runs 6506dbba3261 y 200b84c2c1a1.
- Auditoría independiente cerrada (docs/auditoria_independiente.md). Portafolio: ficha «Vektor FX», PR #5 en JohanGB.github.io sin fusionar.
- F6 importante SIN corregir: I2 csv.gz de la prueba final sin versionar (24 MB); I5 cifras en prosa sin hash; I6 reports/prueba_final.md y fase2.md sin hash por cifra; I9 dos `hash_codigo` distintos.
- F6 menor SIN corregir: prueba de fase 0 solo cuenta figuras; «volatilidad cero = determinista» solo con deriva nula; revisiones de `dolar_amplio` no modeladas; canario `lam=0.995` vs catálogo 0,994.
