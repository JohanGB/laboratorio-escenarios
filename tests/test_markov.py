"""O2: cambio de régimen de Markov en la varianza."""
import warnings

import numpy as np
import pytest
from scipy import stats

from laboratorio.backtest.corredor import correr, resumen
from laboratorio.backtest.particion import NIVELES
from laboratorio.modelos.markov import (MarkovVarianza, cuantiles_mezcla, ergodicas,
                                        filtrar)
from test_garch import vista_de

P_VERD = np.array([[0.98, 0.05], [0.02, 0.95]])      # columna j: desde el estado j
S2_VERD = np.array([0.25, 4.0])                      # en %²


def simular_markov(n, P=P_VERD, s2=S2_VERD, seed=0):
    rng = np.random.default_rng(seed)
    s = np.empty(n, int); s[0] = 0
    for t in range(1, n):
        s[t] = rng.random() > P[0, s[t - 1]]         # dos estados
    return np.sqrt(s2[s]) * rng.standard_normal(n) / 100.0, s


@pytest.fixture(scope="module")
def datos():
    r, s = simular_markov(4000, seed=1)
    return vista_de(r), s


def test_ergodicas_son_estacionarias():
    pi = ergodicas(P_VERD)
    assert P_VERD @ pi == pytest.approx(pi) and pi.sum() == pytest.approx(1)


def test_filtro_propio_coincide_con_statsmodels(datos):
    from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression
    v, _ = datos
    eps = v.r[1:] * 100
    mod = MarkovRegression(eps, k_regimes=2, trend="n", switching_variance=True)
    th = np.array([P_VERD[0, 0], P_VERD[0, 1], *S2_VERD])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sm = mod.filter(th).filtered_marginal_probabilities
    assert filtrar(eps, P_VERD, S2_VERD) == pytest.approx(np.asarray(sm), abs=1e-9)


def test_cuantiles_de_la_mezcla():
    q = cuantiles_mezcla(np.array([1.0, 0.0]), np.array([1.0, 3.0]), NIVELES)
    assert q == pytest.approx(stats.norm.ppf(NIVELES), abs=1e-9)
    w, sd = np.array([0.3, 0.7]), np.array([0.5, 2.0])
    q = cuantiles_mezcla(w, sd, NIVELES)
    F = (w * stats.norm.cdf(q[:, None] / sd)).sum(1)
    assert F == pytest.approx(NIVELES, abs=1e-10) and (np.diff(q) > 0).all()


def test_estimacion_recupera_parametros_y_ordena_estados(datos):
    v, s = datos
    m = MarkovVarianza(2); m.ajustar(v)
    assert m.s2[0] < m.s2[1]                                   # estado 1 = alto
    assert m.s2 == pytest.approx(S2_VERD, rel=0.15)
    assert np.diag(m.P) == pytest.approx(np.diag(P_VERD), abs=0.03)
    alto = m.probabilidades(v)[1:, 1]
    assert ((alto > 0.5) == (s[1:] == 1)).mean() > 0.9         # el filtro identifica el estado


def test_varianzas_iguales_dan_normal_con_raiz_de_h(datos):
    v, _ = datos
    m = MarkovVarianza(2, sims=40000); m.ajustar(v.hasta(2000))
    m.s2 = np.array([1.0, 1.0])
    q = m.pronosticar(v.hasta(2000), np.array([2000]), NIVELES)
    z = stats.norm.ppf(NIVELES)
    ee = np.sqrt(NIVELES * (1 - NIVELES) / m.sims) / stats.norm.pdf(z)   # error est. del cuantil
    for h in m.horizontes:
        esperado = z * np.sqrt(h) / 100
        tol = 1e-9 if h == 1 else 4 * ee * np.sqrt(h) / 100
        assert np.all(np.abs(q[h][0] - esperado) <= tol)


def test_calibrado_en_su_proceso_generador():
    r, _ = simular_markov(3200, seed=7)
    m = MarkovVarianza(2, sims=1500)
    res = resumen(correr(m, vista_de(r), primero=1200, paso=63, ultimo=2900))
    for h in (1, 5, 21):
        f = res[(res.h == h) & (res.grupo == "todo")].iloc[0]
        assert abs(f.cob95 - 0.95) < 0.03 and abs(f.cob90 - 0.90) < 0.04, (h, f.cob95, f.cob90)
    assert m.fallos == 0


def test_fallo_conserva_parametros_y_arranca_en_caliente(datos, monkeypatch):
    v, _ = datos
    m = MarkovVarianza(2); m.ajustar(v.hasta(1500))
    P, s2, crudos = m.P.copy(), m.s2.copy(), m._crudos.copy()
    vistos = []
    monkeypatch.setattr(MarkovVarianza, "_intento", lambda self, eps, ini: vistos.append(ini))
    m.ajustar(v.hasta(1800))
    assert np.array_equal(m.P, P) and np.array_equal(m.s2, s2) and m.fallos == 1
    assert np.array_equal(vistos[0], crudos) and vistos[1] is None
    with pytest.raises(RuntimeError):
        MarkovVarianza(2).ajustar(v.hasta(1500))
