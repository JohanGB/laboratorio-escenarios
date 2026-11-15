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
