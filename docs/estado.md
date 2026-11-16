# Estado
Fases 0-2, F1, O1, O2 y F2 completas (15-nov-2026). Sigue O3 (PROMPT_FABLE §3). Decisiones en docs/decisiones.md.
- Git: rama main, sin conversión de fin de línea (protege los hashes). data/raw versionado; data/processed, runs/**/*.csv.gz y .playwright-mcp ignorados. A1 pasos 2-9 pendientes.
- Datos: data/raw (inmutable) -> data/processed. EDA en reports/fase0.md. Motor (src/laboratorio/motor/): caso compra_dolares (supuestos ILUSTRATIVOS).
- Backtest: origen móvil desde 2005-01-03, ventana expansiva, reajuste 21, embargo = h_max. PRUEBA FINAL desde 2020-01-01: intocable hasta C2.
- Corrida corta: FABRICAS (17 modelos), HORIZONTES (1,5,21,63), runs/backtest_desarrollo/ + cola/ (NIVELES_COLA y ES). Corrida larga: FABRICAS_LARGOS (126,252), `correr --largo`, runs/backtest_largo/. NINGUNA corrida está al día: O3.
- Modelos: bases, GARCH/GJR/EGARCH (t y skewt), FHS (EWMA, GJR), Markov 2 y 3, regresión por cuantiles, LightGBM, bootstrap estacionario (F5 importa `trayectorias` de modelos/bootstrap.py). Todos en el canario.
- O1: tolerancia de persistencia 1e-4 + arranque en caliente: fallos GARCH 38→0, GJR 28→1; GARCH/GJR son IGARCH en la práctica (reports/o1_convergencia.md). O2: reports/o2_markov.md.
- F2 (evaluacion/): mcs.py (MCS α=0,10), riesgo.py (VaR dos colas, Basilea, ES por rejilla, Z2), pit.py (ji-cuadrado por casillas), direccion.py (binomial, Pesaran-Timmermann), cobertura_n_efectivo. Cada una con prueba a mano (tests/test_pruebas_f2.py).
- El reporte (`python -m laboratorio.backtest reporte`) ya incluye MCS, Basilea, ES/Z2, PIT + figs/fase2_pit.png, dirección y horizontes largos; probado solo con datos sintéticos.
- ES «no aplica» en reg_cuantiles y lightgbm (motivo en el JSON de la corrida).
- O3: `correr --forzar`, `correr --largo --forzar`, luego `reporte`. markov_3 es el más lento (reajuste 63, ≈ 7-15 s por estimación). Registro en runs/.
- Los candidatos de F1/O1/O2 cuentan como búsqueda: la conclusión sale del MCS, no del DM por pares.
- Pendiente: O3 (correr todo), F3 (conclusiones), F4 (prerregistro y código de la prueba final).
