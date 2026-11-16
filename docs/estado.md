# Estado
Fases 0-2, F1, O1 y O2 completas (15-nov-2026). Sigue F2 (PROMPT_FABLE §3). Decisiones en docs/decisiones.md.
- Git: rama main, sin conversión de fin de línea (protege los hashes). data/raw versionado; data/processed, runs/**/*.csv.gz y .playwright-mcp ignorados. A1 pasos 2-9 pendientes.
- Datos: data/raw (inmutable) -> data/processed. EDA en reports/fase0.md. Motor (src/laboratorio/motor/): caso compra_dolares (supuestos ILUSTRATIVOS).
- Backtest: origen móvil desde 2005-01-03, ventana expansiva, reajuste 21, embargo = h_max. PRUEBA FINAL desde 2020-01-01: intocable hasta C2.
- Corrida corta: FABRICAS, HORIZONTES (1,5,21,63), runs/backtest_desarrollo/. Corrida larga: FABRICAS_LARGOS (126,252), `correr --largo`, runs/backtest_largo/ (AÚN NO CORRIDA: O3).
- NIVELES (11) intactos; NIVELES_COLA para ES/Acerbi-Székely (F2).
- Modelos: bases (caminata, sim. hist., EWMA), GARCH/GJR/EGARCH-t, regresión por cuantiles, LightGBM, bootstrap estacionario (simple y filtrado; F5 importa `trayectorias` de modelos/bootstrap.py).
- O1: GARCH con arranque en caliente y tolerancia de persistencia 1e-4 (la causa de los fallos era la holgura de SLSQP en la frontera IGARCH): fallos 38→0 (GARCH), 28→1 (GJR). GARCH/GJR son IGARCH en la práctica. Nuevos: gjr_skewt, egarch_skewt, fhs_ewma, fhs_gjr. reports/o1_convergencia.md.
- O2: markov_2 (reajuste 21) y markov_3 (reajuste 63), filtro de Hamilton propio. Estado alto domina en 2008 y 2014-15; con 2 estados separa sobre todo banda/flotación. reports/o2_markov.md + figs/markov_estado_alto.png.
- Todos los modelos nuevos están en FABRICAS, FABRICAS_LARGOS y el canario anti-fuga. Cuentan como búsqueda: el MCS (F2) compara todo el catálogo.
- O3 DEBE usar `correr --forzar`: los CSV de garch_t/gjr_t/egarch_t en caché son de antes de O1. Faltan CSV de bootstrap, FHS, skewt y Markov.
- Fase 2: candidatos solo superan a las bases a h=1; cola superior subcubierta a h=1 (por revisar con los nuevos en O3).
- Pendiente: F2 (MCS, VaR, ES, PIT, n efectivo), O3 correr todo (corto y largo).
