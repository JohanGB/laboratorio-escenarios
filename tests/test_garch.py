import numpy as np
import pandas as pd
import pytest
from arch import arch_model
from scipy import stats

from laboratorio.backtest.corredor import correr, resumen
from laboratorio.backtest.datos import construir_vista
from laboratorio.backtest.particion import NIVELES
from laboratorio.modelos.garch import (GarchT, simular_acumulados,
                                       t_estandarizada, varianzas)


def simular_garch(n, w=0.02, a=0.08, b=0.90, g=0.0, nu=6, seed=0):
    rng = np.random.default_rng(seed)
    z = t_estandarizada(rng, nu, n)
    v = w / (1 - a - g / 2 - b); out = np.empty(n)
    for k in range(n):
        out[k] = np.sqrt(v) * z[k]
        v = w + (a + g * (out[k] < 0)) * out[k] ** 2 + b * v
    return out / 100.0                      # en unidades naturales; el modelo reescala ×100


def vista_de(r, inicio="2004-01-02"):
    idx = pd.bdate_range(inicio, periods=len(r))
    trm = pd.DataFrame({"trm": 3000 * np.exp(np.cumsum(r)), "regimen": "flotacion", "estres": ""}, index=idx)
    ext = pd.DataFrame({"brent_usd": 1.0, "dolar_amplio": 1.0, "fed_funds": 1.0, "politica": 1.0}, index=idx)
    return construir_vista(trm, ext)


@pytest.fixture(scope="module")
def datos():
    r = simular_garch(3000, a=0.05, g=0.06, seed=1)      # persistencia 0,98
    return vista_de(r)


def test_t_estandarizada_tiene_varianza_uno():
    z = t_estandarizada(np.random.default_rng(0), 6, 400_000)
    assert z.var() == pytest.approx(1.0, rel=0.03) and abs(z.mean()) < 0.01


@pytest.mark.parametrize("tipo", ["GARCH", "GJR", "EGARCH"])
def test_recursion_propia_coincide_con_arch(datos, tipo):
    m = GarchT(tipo)
    m.ajustar(datos.hasta(2000))
    eps = datos.r[1:2001] * 100
    kw = {"GARCH": dict(vol="GARCH", p=1, q=1), "GJR": dict(vol="GARCH", p=1, o=1, q=1),
          "EGARCH": dict(vol="EGARCH", p=1, o=1, q=1)}[tipo]
    am = arch_model(eps, mean="Zero", dist="t", rescale=False, **kw)
    nombres = {"omega": "omega", "alpha": "alpha[1]", "beta": "beta[1]", "gamma": "gamma[1]", "nu": "nu"}
    por_nombre = {nombres[k]: v for k, v in m.params.items()}
    orden = am.volatility.parameter_names() + am.distribution.parameter_names()    # orden de arch
    fijo = am.fix(pd.Series({k: por_nombre[k] for k in orden}))
    mio = varianzas(eps, tipo, m.params)
    # arch aplica además los parámetros al retrocálculo en t=0; esa diferencia inicial decae
    # con la persistencia, así que se compara tras 500 observaciones de calentamiento.
    assert np.sqrt(mio[:-1])[500:] == pytest.approx(fijo.conditional_volatility[500:], rel=1e-6)


def test_estimacion_recupera_parametros_verdaderos():
    r = simular_garch(8000, w=0.02, a=0.08, b=0.90, nu=6, seed=5)
    m = GarchT("GARCH"); m.ajustar(vista_de(r))
    p = m.params
    assert abs(p["alpha"] - 0.08) < 0.03 and abs(p["beta"] - 0.90) < 0.04 and 4 < p["nu"] < 9


def test_gjr_detecta_asimetria_y_garch_no_la_tiene():
    r = simular_garch(8000, a=0.03, b=0.90, g=0.12, w=0.02, seed=6)
    m = GarchT("GJR"); m.ajustar(vista_de(r))
    assert m.params["gamma"] > 0.05


def test_ajuste_ve_solo_la_vista_recibida(datos):
    a, b = GarchT("GARCH"), GarchT("GARCH")
    a.ajustar(datos.hasta(1500)); b.ajustar(datos.hasta(1500))
    assert a.params == b.params
    c = GarchT("GARCH"); c.ajustar(datos.hasta(1800))
    assert c.params != a.params


@pytest.mark.parametrize("tipo", ["GARCH", "GJR", "EGARCH"])
def test_sin_fuga_y_determinismo(datos, tipo):
    m = GarchT(tipo, sims=500); m.ajustar(datos.hasta(2000))
    origenes = np.array([2000, 2010, 2030])
    base = m.pronosticar(datos.hasta(2030), origenes, NIVELES)
    for i, o in enumerate(origenes):
        solo = m.pronosticar(datos.hasta(int(o)), np.array([o]), NIVELES)
        for h in m.horizontes:
            assert np.array_equal(solo[h][0], base[h][i])          # exacto: misma semilla por origen
            assert (np.diff(base[h][i]) >= 0).all()


def test_cuantiles_aumentan_con_h_y_con_la_volatilidad_actual(datos):
    m = GarchT("GARCH", sims=3000); m.ajustar(datos.hasta(2000))
    q = m.pronosticar(datos.hasta(2000), np.array([2000]), NIVELES)
    anchos = [q[h][0, -2] - q[h][0, 1] for h in m.horizontes]
    assert anchos == sorted(anchos)
    # tras un choque grande la dispersión a h=1 sube
    r = datos.r.copy()[: 2001]; r[-1] = 0.08
    v2 = vista_de(np.nan_to_num(r))
    q2 = m.pronosticar(v2, np.array([2000]), NIVELES)
    assert (q2[1][0, -2] - q2[1][0, 1]) > 1.5 * anchos[0]


def test_la_simulacion_reproduce_la_varianza_teorica_de_garch():
    p = {"omega": 0.02, "alpha": 0.08, "beta": 0.90}
    z = t_estandarizada(np.random.default_rng(1), 8, (21, 200_000))
    acum = simular_acumulados(1.0, "GARCH", p, 21, z)
    # varianza esperada acumulada: Σ E[σ²_k]; E[σ²_{k+1}] = ω + (α+β)E[σ²_k]
    s, ev = 0.0, 1.0
    for _ in range(21):
        s += ev; ev = p["omega"] + (p["alpha"] + p["beta"]) * ev
    assert acum[-1].var() == pytest.approx(s, rel=0.03)


def test_fallo_de_convergencia_conserva_parametros_previos(datos, monkeypatch):
    m = GarchT("GARCH"); m.ajustar(datos.hasta(1500)); antes = dict(m.params)
    monkeypatch.setattr(GarchT, "_estimar", lambda self, eps: None)
    m.ajustar(datos.hasta(1800))
    assert m.params == antes and m.fallos == 1 and m.reajustes == 2
    with pytest.raises(RuntimeError):
        g = GarchT("GARCH"); g.ajustar(datos.hasta(1500))


@pytest.mark.parametrize("tipo", ["GARCH", "GJR"])
def test_calibracion_con_su_propio_proceso_generador(tipo):
    g = 0.0 if tipo == "GARCH" else 0.08
    r = simular_garch(3200, w=0.02, a=0.07 if tipo == "GARCH" else 0.04, b=0.90, g=g, nu=6, seed=11)
    v = vista_de(r)
    m = GarchT(tipo, sims=1500)
    res = resumen(correr(m, v, primero=1200, paso=63, ultimo=2900))
    for h in (1, 5, 21):
        f = res[(res.h == h) & (res.grupo == "todo")].iloc[0]
        assert abs(f.cob95 - 0.95) < 0.03 and abs(f.cob90 - 0.90) < 0.04, (tipo, h, f.cob95, f.cob90)
    assert m.fallos == 0


# ---- O1: t asimétrica y arranque en caliente --------------------------------------------------
from laboratorio.modelos.garch import innovaciones, persistencia, skewt_estandarizada  # noqa: E402


def simular_gjr_skewt(n, w=0.02, a=0.04, b=0.90, g=0.08, nu=6, lam=-0.3, seed=0):
    z = skewt_estandarizada(np.random.default_rng(seed), nu, lam, n)
    v = w / (1 - a - g / 2 - b); out = np.empty(n)
    for k in range(n):
        out[k] = np.sqrt(v) * z[k]
        v = w + (a + g * (out[k] < 0)) * out[k] ** 2 + b * v
    return out / 100.0


@pytest.mark.parametrize("nu,lam", [(6.0, -0.3), (4.5, 0.4), (30.0, 0.0)])
def test_skewt_muestreo_exacto_coincide_con_la_ppf_de_arch(nu, lam):
    """El muestreo de dos lados tiene la misma distribución que invertir la CDF de `arch`."""
    from arch.univariate import SkewStudent
    z = skewt_estandarizada(np.random.default_rng(7), nu, lam, 400_000)
    u = np.array([0.001, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 0.999])
    teor = SkewStudent().ppf(u, np.array([nu, lam]))
    assert np.quantile(z, u) == pytest.approx(teor, abs=0.03, rel=0.02)
    cdf = SkewStudent().cdf(np.sort(z[:20000]), np.array([nu, lam]))
    assert stats.kstest(cdf, "uniform").pvalue > 0.001


def test_skewt_estandarizada_media_cero_varianza_uno_y_asimetria():
    z = skewt_estandarizada(np.random.default_rng(0), 6, -0.3, 400_000)
    assert z.var() == pytest.approx(1.0, rel=0.03) and abs(z.mean()) < 0.01
    assert stats.skew(z) < -0.3                     # λ < 0: cola izquierda más larga
    assert innovaciones(np.random.default_rng(1), {"nu": 6.0}, 10).shape == (10,)


@pytest.mark.parametrize("tipo", ["GJR", "EGARCH"])
def test_recursion_propia_coincide_con_arch_en_skewt(tipo):
    v = vista_de(simular_gjr_skewt(3000, seed=2))
    m = GarchT(tipo, dist="skewt"); m.ajustar(v.hasta(2000))
    assert set(m.params) >= {"nu", "lam"}
    eps = v.r[1:2001] * 100
    am = m._modelo(eps)
    inv = {"omega": "omega", "alpha": "alpha[1]", "beta": "beta[1]", "gamma": "gamma[1]",
           "nu": "eta", "lam": "lambda"}
    por_nombre = {inv[k]: x for k, x in m.params.items()}
    orden = am.volatility.parameter_names() + am.distribution.parameter_names()
    fijo = am.fix(pd.Series({k: por_nombre[k] for k in orden}))
    mio = varianzas(eps, tipo, m.params)
    assert np.sqrt(mio[:-1])[500:] == pytest.approx(fijo.conditional_volatility[500:], rel=1e-6)


def test_skewt_recupera_la_asimetria_y_la_traslada_a_los_cuantiles():
    v = vista_de(simular_gjr_skewt(6000, lam=-0.35, seed=4))
    m = GarchT("GJR", dist="skewt", sims=20000); m.ajustar(v)
    assert -0.5 < m.params["lam"] < -0.2 and m.nombre == "gjr_skewt"
    q = m.pronosticar(v, np.array([v.n - 1]), NIVELES)[1][0]
    niv = list(np.round(NIVELES, 6))
    assert -q[niv.index(0.01)] > q[niv.index(0.99)]     # cola izquierda (1 %) más larga


def test_arranque_en_caliente_usa_los_parametros_previos_y_rescata_en_frio(datos, monkeypatch):
    m = GarchT("GJR"); m.ajustar(datos.hasta(1500)); previos = dict(m.params)
    llamadas = []
    original = GarchT._intento

    def espia(self, am, inicio):
        llamadas.append(None if inicio is None else inicio.copy())
        if inicio is not None:
            return None, "no_convergio"          # el caliente falla → debe reintentar en frío
        return original(self, am, inicio)
    monkeypatch.setattr(GarchT, "_intento", espia)
    m.ajustar(datos.hasta(1800))
    orden = ["omega", "alpha", "gamma", "beta", "nu"]
    assert np.allclose(llamadas[0], [previos[k] for k in orden]) and llamadas[1] is None
    assert m.rescates == 1 and m.fallos == 0 and m.params != previos


def test_arranque_en_caliente_y_en_frio_llegan_al_mismo_optimo(datos):
    c, f = GarchT("GJR"), GarchT("GJR", arranque="frio")
    for t in (1500, 1800):
        c.ajustar(datos.hasta(t)); f.ajustar(datos.hasta(t))
    for k in c.params:
        assert c.params[k] == pytest.approx(f.params[k], rel=2e-2, abs=2e-3)
    assert c.historial[-1]["persistencia"] == pytest.approx(persistencia("GJR", c.params))


def test_tolerancia_de_persistencia_acepta_la_holgura_del_optimizador():
    """α+β = 1,00001 (holgura de SLSQP en la frontera IGARCH) se acepta; 1,001 es explosivo."""
    def serie(a, b):
        return pd.Series({"omega": 0.002, "alpha[1]": a, "beta[1]": b, "nu": 6.0})
    nuevo, viejo = GarchT("GARCH"), GarchT("GARCH", tol_persistencia=1e-6)
    assert nuevo._validar(serie(0.22748, 0.77253))[0] is not None
    assert viejo._validar(serie(0.22748, 0.77253)) == (None, "explosivo")
    assert nuevo._validar(serie(0.2, 0.801)) == (None, "explosivo")
    assert nuevo.parametros()["tol_persistencia"] == 1e-4


def test_fallo_registra_la_causa(datos, monkeypatch):
    m = GarchT("GARCH"); m.ajustar(datos.hasta(1500))
    monkeypatch.setattr(GarchT, "_intento", lambda self, am, inicio: (None, "explosivo"))
    m.ajustar(datos.hasta(1800))
    assert m.causas == {"explosivo": 1} and m.historial[-1]["fallo"]
