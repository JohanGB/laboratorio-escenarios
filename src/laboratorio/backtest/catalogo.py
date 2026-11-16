"""Catálogo de modelos del backtest de desarrollo (fijado antes de correr).

`LINEAS_BASE` son las referencias: un candidato que no supere a la mejor de ellas en un horizonte
queda descartado en ese horizonte (ver reportes/fase2.py para el criterio exacto).
LightGBM se reajusta cada 63 orígenes (costo de 44 modelos por reajuste); el resto cada 21.

`FABRICAS` = corrida corta (HORIZONTES, embargo 63, runs/backtest_desarrollo/). Todos sus modelos
usan exactamente HORIZONTES: un horizonte mayor cambiaría el embargo y los orígenes (R1).
`FABRICAS_LARGOS` = corrida larga aparte (HORIZONTES_LARGOS, embargo 252, runs/backtest_largo/).
Entran los modelos que producen la distribución a h pasos sin entrenar con objetivos traslapados
a 252 días: líneas base, GARCH, FHS, Markov y bootstrap (todos por trayectorias). Quedan fuera regresión
por cuantiles y LightGBM (entrenarían con ≈ n/252 objetivos independientes).
Los bootstrap nacen de mirar el desarrollo: cuentan como búsqueda (docs/decisiones.md).
O1 agrega GJR/EGARCH con t asimétrica y FHS (EWMA y GJR); O2 agrega Markov de 2 y 3 estados.
También cuentan como búsqueda. Markov de 3 estados tarda > 2 s por estimación: reajuste cada 63.
"""
from __future__ import annotations

from ..modelos.bootstrap import BootstrapEstacionario
from ..modelos.cuantiles import LightGBMCuantiles, RegresionCuantiles
from ..modelos.fhs import FHS
from ..modelos.garch import GarchT
from ..modelos.lineas_base import EWMA, CaminataAleatoria, SimulacionHistorica
from ..modelos.markov import MarkovVarianza
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
    "gjr_skewt": (lambda: GarchT("GJR", dist="skewt"), 21),
    "egarch_skewt": (lambda: GarchT("EGARCH", dist="skewt"), 21),
    "fhs_ewma": (lambda: FHS("ewma"), 21),
    "fhs_gjr": (lambda: FHS("gjr"), 21),
    "markov_2": (lambda: MarkovVarianza(2), 21),
    "markov_3": (lambda: MarkovVarianza(3), 63),
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
    "gjr_skewt": (lambda: GarchT("GJR", dist="skewt", horizontes=_L), 21),
    "egarch_skewt": (lambda: GarchT("EGARCH", dist="skewt", horizontes=_L), 21),
    "fhs_ewma": (lambda: FHS("ewma", horizontes=_L), 21),
    "fhs_gjr": (lambda: FHS("gjr", horizontes=_L), 21),
    "markov_2": (lambda: MarkovVarianza(2, horizontes=_L), 21),
    "markov_3": (lambda: MarkovVarianza(3, horizontes=_L), 63),
}
