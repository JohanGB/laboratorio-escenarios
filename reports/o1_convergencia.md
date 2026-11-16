# O1 · Convergencia de la familia GARCH (desarrollo)

Reajustes: 167 (paso 21, 2005-01-04 a 2019-09-18), ventana expansiva desde 1991, r·100, media cero.
«Antes» = arranque en frío (valores iniciales de `arch`) y persistencia aceptada hasta 1 + 1e-6, igual al código de la fase 2. «Solo caliente» = parte de los parámetros del reajuste anterior (si falla, reintenta en frío), misma tolerancia. «Después» = caliente y tolerancia 1 + 1e-04 (lo que usa el catálogo desde O1). Un fallo conserva los parámetros previos.

| modelo | reajustes | fallos antes (causas) | solo caliente | fallos después (causas) | rescatados por el frío |
|---|---|---|---|---|---|
| garch_t | 167 | 38 (explosivo 38) | 36 | 0 (—) | 0 |
| gjr_t | 167 | 28 (explosivo 27, no_convergio 1) | 25 | 1 (no_convergio 1) | 0 |
| egarch_t | 167 | 0 (—) | 0 | 0 (—) | 0 |
| gjr_skewt | 167 | 32 (explosivo 30, no_convergio 2) | 29 | 1 (no_convergio 1) | 0 |
| egarch_skewt | 167 | 0 (—) | 0 | 0 (—) | 0 |

Causas: `no_convergio` = el optimizador no cerró; `explosivo` = persistencia > 1 + tolerancia; `nu_fuera` = grados de libertad fuera de [2,1; 200]; `excepcion` = error de `arch`.

## Persistencia (reajustes aceptados, después)

Persistencia = α + γ/2 + β (GARCH, GJR) o β (EGARCH). Último reajuste a la derecha.

| modelo | mediana | rango | % > 0,999 | α | β | γ | ν | λ (skewt) |
|---|---|---|---|---|---|---|---|---|
| garch_t | 1,0000 | 1,0000 – 1,0000 | 100% | 0,184 | 0,816 | — | 7,3 | — |
| gjr_t | 1,0000 | 1,0000 – 1,0000 | 100% | 0,199 | 0,815 | -0,028 | 7,3 | — |
| egarch_t | 0,9737 | 0,9491 – 0,9804 | 0% | 0,385 | 0,980 | 0,012 | 6,3 | — |
| gjr_skewt | 1,0000 | 1,0000 – 1,0000 | 100% | 0,197 | 0,815 | -0,025 | 7,3 | 0,015 |
| egarch_skewt | 0,9738 | 0,9492 – 0,9804 | 0% | 0,385 | 0,980 | 0,011 | 6,3 | 0,008 |

Referencia EWMA 0,94 (RiskMetrics) = IGARCH sin estimar: ω = 0, α = 0,06, β = 0,94, persistencia exactamente 1.

**Lectura.** El arranque en caliente casi no ayuda (38 → 36, 28 → 25): la causa era la tolerancia. Con ella, GARCH y GJR quedan sin fallos por explosividad, pero su persistencia es 1 en todos los reajustes: en la práctica son IGARCH, como EWMA. La diferencia con RiskMetrics está en la reacción: α ≈ 0,18-0,20 frente a 0,06 de EWMA, o sea que el GARCH estimado responde unas tres veces más a cada choque y olvida más rápido (β ≈ 0,82 frente a 0,94). EGARCH no es integrado (β ≈ 0,95-0,98). En GJR, γ sale levemente negativo: las alzas del dólar suben la volatilidad un poco más que las bajas. La t asimétrica estima λ ≈ 0 (casi sin asimetría en las innovaciones), así que no es de esperar que corrija sola la cola superior; la FHS, con residuos empíricos, es la otra apuesta. Lo decide el backtest (O3).
