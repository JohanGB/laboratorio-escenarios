"""Bootstrap estacionario por bloques: longitud de bloque, índices, reproducibilidad, colas."""
import numpy as np
import pandas as pd
import pytest

from laboratorio.backtest.datos import construir_vista
from laboratorio.backtest.particion import HORIZONTES_LARGOS, NIVELES
from laboratorio.modelos.bootstrap import (BootstrapEstacionario, indices_estacionarios,
                                           longitud_bloque_pw, trayectorias)


def vista(n=1500, seed=5, df=5):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2000-01-03", periods=n)
    r = rng.standard_t(df, n) * 0.006
    trm = pd.DataFrame({"trm": 3000 * np.exp(np.cumsum(r)), "regimen": "flotacion", "estres": ""}, index=idx)
    ext = pd.DataFrame({"brent_usd": 50.0, "dolar_amplio": 100.0, "fed_funds": 1.0, "politica": 5.0}, index=idx)
    return construir_vista(trm, ext)


def test_bloque_corto_con_ruido_y_largo_con_persistencia():
    rng = np.random.default_rng(1)
    e = rng.normal(size=5000)
    assert longitud_bloque_pw(e) < 3
    ar = np.empty(5000); ar[0] = 0
    for t in range(1, 5000):
        ar[t] = 0.8 * ar[t - 1] + e[t]
    assert longitud_bloque_pw(ar) > 8
    n = 5000
    assert longitud_bloque_pw(np.cumsum(e)) <= np.ceil(min(3 * np.sqrt(n), n / 3))   # tope


def test_bloque_1_es_bootstrap_simple():
    a = indices_estacionarios(np.random.default_rng(7), 400, 30, 50, bloque=1.0)
    b = np.random.default_rng(7).integers(0, 400, size=(30, 50))
    assert np.array_equal(a, b)


def test_bloques_largos_avanzan_y_son_circulares():
    idx = indices_estacionarios(np.random.default_rng(2), 20, 300, 10, bloque=50.0)
    pasos = np.diff(idx, axis=0)
    seguidos = (pasos == 1) | (pasos == -19)            # avance de uno, con vuelta circular
    assert seguidos.mean() > 0.9
    assert idx.min() >= 0 and idx.max() < 20            # largo 300 > historia 20: circular


@pytest.mark.parametrize("filtrado", [False, True])
def test_cuantiles_no_cruzados_y_semilla_reproducible(filtrado):
    v = vista()
    hs = (1, 21, 63) + HORIZONTES_LARGOS
    o = np.array([1300, 1310])
    a = BootstrapEstacionario(filtrado=filtrado, sims=800, horizontes=hs); a.ajustar(v.hasta(1300))
    b = BootstrapEstacionario(filtrado=filtrado, sims=800, horizontes=hs); b.ajustar(v.hasta(1300))
    qa, qb = a.pronosticar(v.hasta(1310), o, NIVELES), b.pronosticar(v.hasta(1310), o, NIVELES)
    for h in hs:
        assert np.isfinite(qa[h]).all() and (np.diff(qa[h], axis=1) >= 0).all()
        assert np.array_equal(qa[h], qb[h])
    c = BootstrapEstacionario(filtrado=filtrado, sims=800, semilla=1, horizontes=hs)
    c.ajustar(v.hasta(1300))
    assert not np.array_equal(c.pronosticar(v.hasta(1310), o, NIVELES)[252], qa[252])


def test_escala_iid_aproxima_raiz_de_h():
    """Rendimientos iid: el ancho 5-95 a 252 días ≈ 2·1,645·σ·√252 (TCL), dentro de 10 %."""
    v = vista(n=3000, df=8)
    m = BootstrapEstacionario(sims=4000, horizontes=(252,)); m.ajustar(v.hasta(2900))
    q = m.pronosticar(v.hasta(2900), np.array([2900]), np.array([0.05, 0.95]))[252][0]
    sd = np.nanstd(v.r[1:2901])
    assert (q[1] - q[0]) == pytest.approx(2 * 1.645 * sd * np.sqrt(252), rel=0.10)


def test_filtrado_parte_de_la_volatilidad_actual_y_vuelve_al_largo_plazo():
    v = vista()
    m = BootstrapEstacionario(filtrado=True, sims=200); m.ajustar(v.hasta(1400))
    assert 0.5 <= m.rho <= 0.9999
    alta = 9 * m.sigma2_largo
    esc = m.escala(alta, 2000)
    assert esc[0] == pytest.approx(np.sqrt(alta))
    assert np.all(np.diff(esc) <= 0) and esc[-1] < 1.05 * np.sqrt(m.sigma2_largo)


def test_filtrado_mas_ancho_tras_un_choque():
    """Tras un choque de volatilidad, la variante filtrada ensancha a 1 día; la simple casi no."""
    v = vista()
    r = v.r.copy(); r[1395:1401] = 0.05 * np.array([1, -1, 1, -1, 1, -1])
    lp = np.concatenate([[v.logp[0]], v.logp[0] + np.cumsum(r[1:])])
    w = type(v)(v.fechas, lp, r, v.banda, v.estres, v.externas)
    anchos = {}
    for f in (False, True):
        m = BootstrapEstacionario(filtrado=f, sims=2000, horizontes=(1,)); m.ajustar(w.hasta(1390))
        q0 = m.pronosticar(w.hasta(1390), np.array([1390]), np.array([0.05, 0.95]))[1][0]
        q1 = m.pronosticar(w.hasta(1400), np.array([1400]), np.array([0.05, 0.95]))[1][0]
        anchos[f] = (q1[1] - q1[0]) / (q0[1] - q0[0])
    assert anchos[True] > 2 and anchos[False] < 1.3


def test_trayectorias_acumula():
    x = np.arange(10.0)
    acum = trayectorias(x, 5, 3, 1.0, np.random.default_rng(0))
    pasos = np.diff(np.vstack([np.zeros((1, 3)), acum]), axis=0)
    assert np.isin(pasos, x).all()


def test_historia_insuficiente():
    with pytest.raises(ValueError):
        BootstrapEstacionario().ajustar(vista().hasta(100))
