"""Catálogo de modelos del backtest de desarrollo (fijado antes de correr).

`LINEAS_BASE` son las referencias: un candidato que no supere a la mejor de ellas en un horizonte
queda descartado en ese horizonte (ver reportes/fase2.py para el criterio exacto).
LightGBM se reajusta cada 63 orígenes (costo de 44 modelos por reajuste); el resto cada 21.

`FABRICAS` = corrida corta (HORIZONTES, embargo 63, runs/backtest_desarrollo/). Todos sus modelos
usan exactamente HORIZONTES: un horizonte mayor cambiaría el embargo y los orígenes (R1).
`FABRICAS_LARGOS` = corrida larga aparte (HORIZONTES_LARGOS, embargo 252, runs/backtest_largo/).
Entran los modelos que producen la distribución a h pasos sin entrenar con objetivos traslapados
a 252 días: líneas base, GARCH (trayectorias) y bootstrap (trayectorias). Quedan fuera regresión
por cuantiles y LightGBM (entrenarían con ≈ n/252 objetivos independientes).
Los bootstrap nacen de mirar el desarrollo: cuentan como búsqueda (docs/decisiones.md).
"""
from __future__ import annotations

from ..modelos.bootstrap import BootstrapEstacionario
from ..modelos.cuantiles import LightGBMCuantiles, RegresionCuantiles
from ..modelos.garch import GarchT
from ..modelos.lineas_base import EWMA, CaminataAleatoria, SimulacionHistorica
from .particion import HORIZONTES_LARGOS

LINEAS_BASE = ("caminata_aleatoria", "sim_hist_756", "sim_hist_pond")
LINEAS_BASE_LARGOS = ("caminata_aleatoria", "sim_hist_pond", "bootstrap_est")

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
    "bootstrap_est": (lambda: BootstrapEstacionario(), 21),
    "bootstrap_est_filtrado": (lambda: BootstrapEstacionario(filtrado=True), 21),
}

_L = HORIZONTES_LARGOS
FABRICAS_LARGOS = {
    "caminata_aleatoria": (lambda: CaminataAleatoria(horizontes=_L), 21),
    "sim_hist_756": (lambda: SimulacionHistorica(ventana=756, horizontes=_L), 21),
    "sim_hist_pond": (lambda: SimulacionHistorica(ventana=None, lam=0.994, horizontes=_L), 21),
    "ewma_0.94": (lambda: EWMA(0.94, horizontes=_L), 21),
    "garch_t": (lambda: GarchT("GARCH", horizontes=_L), 21),
    "gjr_t": (lambda: GarchT("GJR", horizontes=_L), 21),
    "egarch_t": (lambda: GarchT("EGARCH", horizontes=_L), 21),
    "bootstrap_est": (lambda: BootstrapEstacionario(horizontes=_L), 21),
    "bootstrap_est_filtrado": (lambda: BootstrapEstacionario(filtrado=True, horizontes=_L), 21),
}
