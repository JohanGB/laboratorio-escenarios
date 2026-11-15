# Estado
Fases 0-2 completas; F1 (cimientos) completa el 15-nov-2026. Sigue O1 (PROMPT_FABLE §3). Decisiones en docs/decisiones.md.
- Git: rama main, sin conversión de fin de línea (protege los hashes). data/raw versionado; data/processed, runs/**/*.csv.gz y .playwright-mcp ignorados. A1 pasos 2-9 pendientes.
- Datos: data/raw (inmutable) -> data/processed. EDA en reports/fase0.md. Motor (src/laboratorio/motor/): supuestos encadenados, ficha con hashes, caso compra_dolares (`python -m laboratorio.motor compra_dolares`; supuestos ILUSTRATIVOS).
- Backtest: origen móvil desde 2005-01-03, ventana expansiva, reajuste 21, embargo = h_max. PRUEBA FINAL desde 2020-01-01: intocable hasta C2.
- Corrida corta: FABRICAS, HORIZONTES (1,5,21,63), 3493 orígenes, runs/backtest_desarrollo/. Corrida larga: FABRICAS_LARGOS, HORIZONTES_LARGOS (126,252), 3304 orígenes, `correr --largo` -> runs/backtest_largo/ (AÚN NO CORRIDA: O3).
- NIVELES (11, CRPS/pinball) intactos; NIVELES_COLA (0,0025-0,025 y espejos) para ES/Acerbi-Székely (F2).
- Modelos: líneas base (caminata, sim. hist., EWMA), GARCH/GJR/EGARCH-t, regresión por cuantiles, LightGBM, y bootstrap estacionario (modelos/bootstrap.py; simple y filtrado; bloque Politis-White máx(r, |r|)). F5 debe importar `trayectorias` de ahí.
- Bootstrap nuevo en FABRICAS (corta y larga) pero sin correr en el backtest: falta su CSV antes del reporte de fase 2 (O3). Costo ≈ 0,1 s/origen.
- N5 resuelto con cifras: dolar30 NaN en 263 orígenes (2005-feb 2006), pol90 en 0 orígenes; NaN causal; canario cubre series que empiezan tarde.
- Canario anti-fuga (tests/test_sin_fuga.py) cubre los catálogos corto y largo (prueba automática).
- Fase 2: candidatos solo superan a las bases a h=1; GARCH con fallos de convergencia y IGARCH; cola superior subcubierta a h=1.
- Pendiente: O1 (GARCH estable, t asimétrica, FHS), O2 Markov, F2 (MCS, VaR, ES, PIT, n efectivo), O3 correr todo.
