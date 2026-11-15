"""Catálogo de modelos del backtest de desarrollo (fijado antes de correr).

`LINEAS_BASE` son las referencias: un candidato que no supere a la mejor de ellas en un horizonte
queda descartado en ese horizonte (ver reportes/fase2.py para el criterio exacto).
LightGBM se reajusta cada 63 orígenes (costo de 44 modelos por reajuste); el resto cada 21.
"""
from __future__ import annotations

from ..modelos.cuantiles import LightGBMCuantiles, RegresionCuantiles
from ..modelos.garch import GarchT
from ..modelos.lineas_base import EWMA, CaminataAleatoria, SimulacionHistorica

LINEAS_BASE = ("caminata_aleatoria", "sim_hist_756", "sim_hist_pond")

FABRICAS = {
    "caminata_aleatoria": (lambda: CaminataAleatoria(), 21),
    "sim_hist_756": (lambda: SimulacionHistorica(ventana=756), 21),
    "sim_hist_pond": (lambda: SimulacionHistorica(ventana=None, lam=0.994), 21),
    "ewma_0.94": (lambda: EWMA(0.94), 21),
    "garch_t": (lambda: GarchT("GARCH"), 21),
    "gjr_t": (lambda: GarchT("GJR"), 21),
    "egarch_t": (lambda: GarchT("EGARCH"), 21),
    "reg_cuantiles": (lambda: RegresionCuantiles(), 21),
    "lightgbm_cuantiles": (lambda: LightGBMCuantiles(), 63),
}
