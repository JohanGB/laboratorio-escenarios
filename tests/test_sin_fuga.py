"""Canario genérico anti-fuga: el pronóstico en el origen o no puede cambiar si se recorta la vista
en o, ni si se alteran los datos posteriores a o. Cada modelo nuevo se agrega a FABRICAS."""
import numpy as np
import pandas as pd
import pytest

from laboratorio.backtest.datos import Vista, construir_vista
from laboratorio.backtest.catalogo import FABRICAS as CATALOGO, FABRICAS_LARGOS
from laboratorio.backtest.particion import HORIZONTES_LARGOS as L, NIVELES
from laboratorio.modelos.bootstrap import BootstrapEstacionario
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
    "bootstrap": lambda: BootstrapEstacionario(sims=300),
    "bootstrap_filtrado": lambda: BootstrapEstacionario(filtrado=True, sims=300),
    # corrida larga (h = 126, 252)
    "caminata_largo": lambda: CaminataAleatoria(horizontes=L),
    "sim_hist_largo": lambda: SimulacionHistorica(ventana=300, horizontes=L),
    "ewma_largo": lambda: EWMA(0.94, horizontes=L),
    "garch_largo": lambda: GarchT("GARCH", sims=300, horizontes=L),
    "bootstrap_largo": lambda: BootstrapEstacionario(sims=300, horizontes=L),
    "bootstrap_filtrado_largo": lambda: BootstrapEstacionario(filtrado=True, sims=300, horizontes=L),
}


def test_canario_cubre_el_catalogo():
    """Toda clase de modelo de los catálogos (corto y largo) tiene un caso en el canario."""
    clases = {type(f()) for f, _ in list(CATALOGO.values()) + list(FABRICAS_LARGOS.values())}
    assert clases <= {type(f()) for f in FABRICAS.values()}


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


def test_lightgbm_sin_fuga_con_series_externas_que_empiezan_tarde():
    """N5: `dolar_amplio` empieza tarde (como en 2006) y `politica` tiene hueco inicial (como en
    1998). Los orígenes 600-700 cruzan la aparición de `dolar30` (≈ obs. 677): el pronóstico no
    puede depender del futuro ni de cuándo aparecerá la serie."""
    from laboratorio.modelos import caracteristicas as car
    v = vista()
    ext = v.externas.copy()
    ext.iloc[:650, ext.columns.get_loc("dolar_amplio")] = np.nan
    ext.iloc[:200, ext.columns.get_loc("politica")] = np.nan
    ext["dolar_amplio"] = ext["dolar_amplio"] * np.exp(np.random.default_rng(4).normal(0, 0.01, v.n).cumsum())
    v = Vista(v.fechas, v.logp, v.r, v.banda, v.estres, ext)
    d = car.construir(v)
    assert d["dolar30"].iloc[:600].isna().all() and d["dolar30"].iloc[700:].notna().all()
    origenes = np.array([600, 650, 680, 700])
    m = LightGBMCuantiles(); m.ajustar(v.hasta(600))
    base = m.pronosticar(v.hasta(700), origenes, NIVELES)
    for i, o in enumerate(origenes):
        solo = m.pronosticar(v.hasta(int(o)), np.array([o]), NIVELES)
        sucio = m.pronosticar(corromper_futuro(v, int(o)).hasta(700), np.array([o]), NIVELES)
        for h in m.horizontes:
            assert solo[h][0] == pytest.approx(base[h][i], rel=1e-9, abs=1e-12)
            assert sucio[h][0] == pytest.approx(base[h][i], rel=1e-9, abs=1e-12)
    m2 = LightGBMCuantiles(); m2.ajustar(v.hasta(700))          # entrenamiento con NaN y valores
    assert all(np.isfinite(q).all() for q in m2.pronosticar(v.hasta(700), origenes, NIVELES).values())
