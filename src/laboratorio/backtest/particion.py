"""Constantes del protocolo de backtesting (sección 7) y de la partición de datos.

Decisiones del autor (editables, pero cambiarlas invalida los resultados previos):
- Desarrollo con origen móvil desde 2005-01-03; la banda cambiaria NO se excluye del
  entrenamiento (la historia desde 1991 entra; la bandera `banda` es variable explicativa).
- Prueba final: desde 2020-01-01. Se usa una sola vez, con prerregistro. Incluye covid (2020)
  y el estrés de 2022; el desarrollo conserva 2008 y 2014–2015.
- Horizontes en observaciones (una fila de la TRM = un día de mercado).
- Reajuste de parámetros cada 21 orígenes, con ventana expansiva.
"""
from __future__ import annotations

import numpy as np

INICIO_DESARROLLO = "2005-01-03"
INICIO_PRUEBA_FINAL = "2020-01-01"
HORIZONTES = (1, 5, 21, 63)
PASO_REAJUSTE = 21
NIVELES = np.array([0.01, 0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975, 0.99])

# Agregadas el 15-nov-2026 (autorización del autor; las de arriba no cambian).
# Horizontes del caso: corrida APARTE (runs/backtest_largo/) con su propio embargo, para que la
# corrida corta conserve sus orígenes. Se evalúan por cobertura con n efectivo = n/h.
HORIZONTES_LARGOS = (126, 252)
# Niveles de cola para ES y Acerbi-Székely (ambas colas: la superior es el alza del dólar).
# El CRPS y el pinball siguen con NIVELES.
NIVELES_COLA = np.array([0.0025, 0.005, 0.01, 0.025, 0.975, 0.99, 0.995, 0.9975])
# ES al 97,5 % (F2): promedio de PUNTOS_REJILLA_ES cuantiles en los puntos medios de cada cola de
# probabilidad ALFA_ES. Se piden en la misma llamada que NIVELES (mismas simulaciones) y se
# guardan aparte (runs/.../cola/); el CSV principal y el CRPS no cambian.
ALFA_ES = 0.025
PUNTOS_REJILLA_ES = 25
