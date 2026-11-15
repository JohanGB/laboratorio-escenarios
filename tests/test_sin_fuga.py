"""Canario genérico anti-fuga: el pronóstico en el origen o no puede cambiar si se recorta la vista
en o, ni si se alteran los datos posteriores a o. Cada modelo nuevo se agrega a FABRICAS."""
import numpy as np
import pandas as pd
import pytest

from laboratorio.backtest.datos import Vista, construir_vista
from laboratorio.backtest.particion import NIVELES
from laboratorio.modelos.cuantiles import LightGBMCuantiles, RegresionCuantiles
from laboratorio.modelos.garch import GarchT
from laboratorio.modelos.lineas_base import (EWMA, CaminataAleatoria,
                                             SimulacionHistorica)

FABRICAS = {
    "caminata": lambda: CaminataAleatoria(),
    "sim_hist_ventana": lambda: SimulacionHistorica(ventana=300),
    "sim_hist_todo": lambda: SimulacionHistorica(ventana=None),
    "sim_hist_pond": lambda: SimulacionHistorica(ventana=None, lam=0.995),
    "ewma": lambda: EWMA(0.94),
    "garch": lambda: GarchT("GARCH", sims=300),
    "gjr": lambda: GarchT("GJR", sims=300),
    "egarch": lambda: GarchT("EGARCH", sims=300),
    "reg_cuantiles": lambda: RegresionCuantiles(),
    "lightgbm": lambda: LightGBMCuantiles(),
}


def vista(n=900, seed=3):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2004-01-02", periods=n)
    r = rng.standard_t(5, n) * 0.006
    trm = pd.DataFrame({"trm": 3000 * np.exp(np.cumsum(r)), "regimen": "flotacion", "estres": ""}, index=idx)
    ext = pd.DataFrame({"brent_usd": 50 + rng.normal(size=n).cumsum() * 0.1, "dolar_amplio": 100.0,
                        "fed_funds": 1.0, "politica": 5.0}, index=idx)
    return construir_vista(trm, ext)


def corromper_futuro(v: Vista, t: int) -> Vista:
    """Misma historia hasta t y datos absurdos después."""
    logp = v.logp.copy(); logp[t + 1:] += np.random.default_rng(9).normal(0, 1, v.n - t - 1)
    r = np.concatenate([[np.nan], np.diff(logp)])
    ext = v.externas.copy(); ext.iloc[t + 1:] = 1e6
    return Vista(v.fechas, logp, r, v.banda, v.estres, ext)


@pytest.mark.parametrize("nombre", FABRICAS)
def test_pronostico_no_depende_del_futuro(nombre):
    v = vista()
    origenes = np.array([600, 610, 650, 700])
    m = FABRICAS[nombre]()
    m.ajustar(v.hasta(600))
    base = m.pronosticar(v.hasta(700), origenes, NIVELES)
    for o in origenes:
        solo = m.pronosticar(v.hasta(int(o)), np.array([o]), NIVELES)
        sucio = m.pronosticar(corromper_futuro(v, int(o)).hasta(700), np.array([o]), NIVELES)
        for h in m.horizontes:
            i = list(origenes).index(o)
            assert solo[h][0] == pytest.approx(base[h][i], rel=1e-9, abs=1e-12)
            assert sucio[h][0] == pytest.approx(base[h][i], rel=1e-9, abs=1e-12)


@pytest.mark.parametrize("nombre", FABRICAS)
def test_cuantiles_ordenados_y_deterministas(nombre):
    v = vista()
    o = np.array([600, 601])
    a = FABRICAS[nombre](); a.ajustar(v.hasta(600))
    b = FABRICAS[nombre](); b.ajustar(v.hasta(600))
    qa, qb = a.pronosticar(v.hasta(601), o, NIVELES), b.pronosticar(v.hasta(601), o, NIVELES)
    for h in a.horizontes:
        assert qa[h].shape == (2, len(NIVELES)) and np.isfinite(qa[h]).all()
        assert (np.diff(qa[h], axis=1) >= -1e-12).all()
        assert np.array_equal(qa[h], qb[h])
