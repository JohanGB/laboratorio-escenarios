"""R1: la corrida larga va aparte y no altera los orígenes de la corrida corta; ningún objetivo
de desarrollo cae en la prueba final. R4: NIVELES_COLA no toca NIVELES."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from laboratorio.backtest import particion as P
from laboratorio.backtest.catalogo import FABRICAS, FABRICAS_LARGOS
from laboratorio.backtest.corredor import correr, primer_origen
from laboratorio.evaluacion.origen_movil import ultimo_origen
from laboratorio.modelos.bootstrap import BootstrapEstacionario
from laboratorio.modelos.lineas_base import EWMA

RAIZ = Path(__file__).resolve().parents[1]
ORIGENES_CORTA = 3493          # orígenes de runs/backtest_desarrollo (fase 2)


def test_constantes_previas_intactas():
    assert P.HORIZONTES == (1, 5, 21, 63)
    assert np.array_equal(P.NIVELES, [0.01, 0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975, 0.99])
    assert P.HORIZONTES_LARGOS == (126, 252)
    assert (np.diff(P.NIVELES_COLA) > 0).all()
    assert np.allclose(P.NIVELES_COLA + P.NIVELES_COLA[::-1], 1)
    assert P.NIVELES_COLA.min() == 0.0025 and P.NIVELES_COLA[P.NIVELES_COLA < 0.5].max() == 0.025


def test_catalogos_separados():
    for nombre, (f, _) in FABRICAS.items():
        assert f().horizontes == P.HORIZONTES, nombre
    for nombre, (f, _) in FABRICAS_LARGOS.items():
        assert f().horizontes == P.HORIZONTES_LARGOS, nombre


def test_corrida_corta_no_cambia_al_agregar_modelos_largos():
    """Los orígenes dependen solo de h_max del modelo: los cortos conservan los suyos."""
    rng = np.random.default_rng(0)
    n = 1400
    idx = pd.bdate_range("2004-01-02", periods=n)
    r = rng.normal(0, 0.006, n)
    from laboratorio.backtest.datos import construir_vista
    trm = pd.DataFrame({"trm": 3000 * np.exp(np.cumsum(r)), "regimen": "flotacion", "estres": ""}, index=idx)
    ext = pd.DataFrame({"brent_usd": 50.0, "dolar_amplio": 100.0, "fed_funds": 1.0, "politica": 5.0}, index=idx)
    v = construir_vista(trm, ext)
    corta = correr(EWMA(), v, primero=300)
    larga = correr(BootstrapEstacionario(sims=100, horizontes=P.HORIZONTES_LARGOS), v, primero=300)
    corta2 = correr(EWMA(), v, primero=300)
    assert corta["origen"].max() == ultimo_origen(v.n, 63)
    assert larga["origen"].max() == ultimo_origen(v.n, 252)
    pd.testing.assert_frame_equal(corta, corta2)
    assert set(larga["h"]) == {126, 252} and set(corta["h"]) == set(P.HORIZONTES)


def _vista_real():
    if not (RAIZ / "data/processed/trm.csv").exists():
        pytest.skip("sin data/processed")
    from laboratorio.backtest.datos import cargar_desarrollo
    return cargar_desarrollo(RAIZ)


def test_origenes_reales_y_sin_objetivos_en_prueba_final():
    v = _vista_real()
    corte = pd.Timestamp(P.INICIO_PRUEBA_FINAL)
    p0 = primer_origen(v)
    for hmax, esperado in ((max(P.HORIZONTES), ORIGENES_CORTA), (max(P.HORIZONTES_LARGOS), None)):
        u = ultimo_origen(v.n, hmax)
        if esperado is not None:
            assert u - p0 + 1 == esperado
        assert v.fechas[u + hmax] < corte                # objetivo más lejano del último origen
    for j in (RAIZ / "runs/backtest_desarrollo").glob("*.json"):
        assert json.loads(j.read_text(encoding="utf-8"))["n_origenes"] == ORIGENES_CORTA, j.name
