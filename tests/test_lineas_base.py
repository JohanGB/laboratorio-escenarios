import numpy as np
import pandas as pd
import pytest
from scipy import stats

from laboratorio.backtest.corredor import correr, resumen
from laboratorio.backtest.datos import construir_vista
from laboratorio.backtest.particion import NIVELES
from laboratorio.modelos.lineas_base import (EWMA, CaminataAleatoria,
                                             SimulacionHistorica,
                                             cuantil_ponderado, varianza_ewma)


def vista_de(r, inicio="2004-01-02"):
    idx = pd.bdate_range(inicio, periods=len(r))
    trm = pd.DataFrame({"trm": 3000 * np.exp(np.cumsum(r)), "regimen": "flotacion", "estres": ""}, index=idx)
    ext = pd.DataFrame({"brent_usd": 1.0, "dolar_amplio": 1.0, "fed_funds": 1.0, "politica": 1.0}, index=idx)
    return construir_vista(trm, ext)


def test_cuantil_ponderado_pesos_iguales_y_extremos():
    x = np.arange(1.0, 101.0)
    q = cuantil_ponderado(x, np.ones(100), np.array([0.5]))
    assert q[0] == pytest.approx(50.5)
    q = cuantil_ponderado(x, np.ones(100), np.array([0.0001, 0.9999]))
    assert q[0] == 1.0 and q[1] == 100.0          # no extrapola
    # peso exponencial hacia el final: la mediana se desplaza hacia los datos grandes
    w = 0.9 ** np.arange(99, -1, -1)
    assert cuantil_ponderado(x, w, np.array([0.5]))[0] > 90


def test_varianza_ewma_coincide_con_recursion_directa():
    rng = np.random.default_rng(0)
    r = np.concatenate([[np.nan], rng.normal(0, 0.01, 300)])
    s2 = varianza_ewma(r, 0.94)
    s = float(np.var(r[1:26])); esp = [s]
    for x in r[1:]:
        s = 0.94 * s + 0.06 * x**2; esp.append(s)
    assert s2 == pytest.approx(esp)


def test_ewma_reacciona_a_un_choque_y_decae():
    r = np.concatenate([[np.nan], np.full(200, 0.005), [0.05], np.full(100, 0.005)])
    s2 = varianza_ewma(r, 0.94)
    assert s2[201] > 5 * s2[200] and s2[300] < s2[201] and s2[201] == pytest.approx(0.94 * s2[200] + 0.06 * 0.05**2)


def test_ewma_es_normal_con_raiz_de_h():
    r = np.concatenate([[np.nan], np.random.default_rng(1).normal(0, 0.01, 400)])
    v = vista_de(np.nan_to_num(r))
    q = EWMA().pronosticar(v, np.array([300]), NIVELES)
    s = np.sqrt(varianza_ewma(v.r, 0.94)[300])
    assert q[21][0] == pytest.approx(s * np.sqrt(21) * stats.norm.ppf(NIVELES))
    assert q[63][0, 5] == pytest.approx(0.0)       # mediana cero


def test_simulacion_historica_ventana_fija_usa_solo_la_ventana_y_retornos_completos():
    # primeros 300 retornos enormes, luego tranquilo: la ventana de 100 debe ignorarlos
    rng = np.random.default_rng(2)
    r = np.concatenate([rng.normal(0, 0.05, 300), rng.normal(0, 0.002, 400)])
    v = vista_de(r)
    corta = SimulacionHistorica(ventana=100).pronosticar(v, np.array([650]), NIVELES)[1][0]
    larga = SimulacionHistorica(ventana=None).pronosticar(v, np.array([650]), NIVELES)[1][0]
    assert (corta[-1] - corta[0]) < 0.02 < (larga[-1] - larga[0])
    # h=5: usa rendimientos a 5 pasos que ya terminaron en o (s+h ≤ o)
    q5 = SimulacionHistorica(ventana=100).pronosticar(v, np.array([650]), NIVELES)[5][0]
    esp = cuantil_ponderado(v.logp[551:651] - v.logp[546:646], np.ones(100), NIVELES)
    assert q5 == pytest.approx(esp)


def test_ponderada_pesa_mas_lo_reciente():
    rng = np.random.default_rng(3)
    r = np.concatenate([rng.normal(0, 0.03, 400), rng.normal(0, 0.003, 200)])
    v = vista_de(r)
    pond = SimulacionHistorica(ventana=None, lam=0.98).pronosticar(v, np.array([590]), NIVELES)[1][0]
    plano = SimulacionHistorica(ventana=None).pronosticar(v, np.array([590]), NIVELES)[1][0]
    assert (pond[-2] - pond[1]) < (plano[-2] - plano[1])


def test_historia_insuficiente_falla_en_vez_de_inventar():
    v = vista_de(np.random.default_rng(4).normal(0, 0.01, 100))
    for m in (CaminataAleatoria(), SimulacionHistorica(ventana=None)):
        with pytest.raises(ValueError, match="insuficiente"):
            m.pronosticar(v, np.array([10]), NIVELES)


def test_calibracion_en_proceso_iid_normal():
    """DGP simple: ningún modelo de línea base debe estar muy descalibrado a h=1 y h=21."""
    r = np.random.default_rng(5).normal(0, 0.008, 5000)
    v = vista_de(r)
    for m in (CaminataAleatoria(), SimulacionHistorica(ventana=None), EWMA(0.99)):
        res = resumen(correr(m, v, primero=500, paso=63))
        for h in (1, 21):
            f = res[(res.h == h) & (res.grupo == "todo")].iloc[0]
            assert abs(f.cob95 - 0.95) < 0.025, (m.nombre, h, f.cob95)


def test_ewma_supera_a_la_caminata_con_volatilidad_agrupada():
    """DGP con volatilidad que cambia por regímenes: EWMA debe tener menor CRPS a h=1."""
    rng = np.random.default_rng(6)
    sig = np.repeat(rng.choice([0.004, 0.015], 60), 80)
    v = vista_de(rng.normal(0, 1, len(sig)) * sig)
    a = resumen(correr(EWMA(0.94), v, primero=500, paso=21)).query("h==1 and grupo=='todo'").iloc[0]
    b = resumen(correr(CaminataAleatoria(), v, primero=500, paso=21)).query("h==1 and grupo=='todo'").iloc[0]
    assert a.crps < b.crps
