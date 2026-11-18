"""M2: motor conjunto multidivisa (motor/conjunto.py) y refactorización de modelos/bootstrap.

Las pruebas con datos reales usan un origen anterior a 2020 (`ORIGEN`): ninguna salida de M2,
ni siquiera un mensaje de error, muestra cifras de las divisas nuevas desde 2020.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from laboratorio.datos.limpieza import FIN_BANDA
from laboratorio.modelos.bootstrap import (BootstrapEstacionario, _sigma2_ewma, aplicar_indices,
                                           indices_bloques, indices_estacionarios, trayectorias)
from laboratorio.motor import conjunto as C

RAIZ = Path(__file__).resolve().parents[1]
ORIGEN = "2019-12-31"
SIETE = ("USD", "EUR", "MXN", "JPY", "CNY", "CHF", "BRL")


@pytest.fixture(scope="module")
def vistas():
    df = pd.read_csv(RAIZ / "data/processed/divisas.csv", parse_dates=["fecha"])
    df = df[df["fecha"] <= ORIGEN]                       # nada de 2020 en adelante entra a la prueba
    return C.vistas_divisas(df)


def _sha(a: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


# --- refactorización de trayectorias sin cambiar ningún número ----------------------------------
# Huellas de la salida de `trayectorias` ANTES de la refactorización (commit 06dd050), con
# entradas exactas (enteros / 1e5, linspace) para que no dependan de la plataforma.
HUELLAS = {
    (None, 5.3): "d7493a349b40692e78649b6ad6b005cc041a709390a6ea3db303c871b66e10e8",
    ("esc", 5.3): "d25120fcea41941218267a956cc8a7de62375bbe4535c5ce19e9b537b2bfada4",
    (None, 1.0): "09a8aef862b0a7534f16174bee9039fafb469fc3c59bb838ba5d7dc40582ed3b",
}


def _entrada():
    x = np.random.default_rng(7).integers(-2000, 2001, 800) / 1e5
    return x, np.linspace(0.8, 1.3, 40)


@pytest.mark.parametrize("clave", list(HUELLAS))
def test_trayectorias_conserva_su_salida_bit_a_bit(clave):
    x, esc = _entrada()
    e, b = clave
    a = trayectorias(x, 40, 300, b, np.random.default_rng([2024, 17]), esc if e else None)
    assert _sha(a) == HUELLAS[clave]


@pytest.mark.parametrize("con_escala", [False, True])
def test_aplicar_indices_con_una_serie_reproduce_trayectorias_bit_a_bit(con_escala):
    x, esc = _entrada()
    esperado = trayectorias(x, 40, 300, 5.3, np.random.default_rng([2024, 17]),
                            esc if con_escala else None)
    idx = indices_bloques(np.random.default_rng([2024, 17]), len(x), 40, 300, 5.3)
    conjunta = aplicar_indices(x[:, None], idx, esc[:, None] if con_escala else None)
    assert conjunta.shape == (40, 300, 1)
    assert np.array_equal(conjunta[..., 0], esperado) and _sha(conjunta[..., 0]) == _sha(esperado)
    assert indices_estacionarios is indices_bloques                  # el nombre anterior sigue


def test_indices_compartidos_entre_series():
    x2 = np.column_stack([np.arange(100.0), 1000 + np.arange(100.0)])
    idx = indices_bloques(np.random.default_rng(1), 100, 10, 50, 4.0)
    a = aplicar_indices(x2, idx)
    pasos = np.diff(np.concatenate([np.zeros((1, 50, 2)), a]), axis=0)
    assert np.array_equal(pasos[..., 1] - pasos[..., 0], np.full((10, 50), 1000.0))  # mismo índice


# --- motor conjunto: una sola serie reproduce el bootstrap de la TRM bit a bit -------------------
class _V:
    def __init__(self, r):
        self.r, self.n = r, len(r)


@pytest.mark.parametrize("motor", ["bootstrap_est_filtrado", "bootstrap_est"])
def test_conjunto_con_solo_la_trm_reproduce_el_bootstrap_bit_a_bit(vistas, motor):
    s = C.simular_conjunto(vistas, ("USD",), motor, sims=200, semilla=11, largo=30)
    trm = vistas["USD"]["cop_por_unidad"]
    trm = trm[trm.index >= pd.Timestamp(s.muestra_desde)]
    r = np.r_[np.nan, np.diff(np.log(trm.to_numpy()))]
    m = BootstrapEstacionario(filtrado=(motor == "bootstrap_est_filtrado"), sims=200, semilla=11)
    m.ajustar(_V(r))
    esc = m.escala(float(_sigma2_ewma(r)[-1]), 30) if m.filtrado else None
    esperado = trayectorias(m._serie(r), 30, 200, m.bloque, np.random.default_rng([11, len(r) - 1]), esc)
    assert np.array_equal(s.acum[..., 0], esperado)
    assert s.bloque == m.bloque and s.regla_bloque == "trm"


# --- diseño obligatorio ---------------------------------------------------------------------------
def test_triangulacion_exacta_en_cada_trayectoria(vistas):
    s = C.simular_conjunto(vistas, ("USD", "EUR", "CNY", "BRL"), sims=500, semilla=3, largo=63)
    niv = s.niveles()                                    # (largo + 1, sims, divisas)
    f = s.niveles_factores()
    for d in ("EUR", "CNY", "BRL"):
        cruce = niv[..., s.divisas.index(d)] / niv[..., s.divisas.index("USD")]
        np.testing.assert_allclose(cruce, f[..., s.factores.index(f"USD por {d}")],
                                   rtol=1e-12, atol=0)
    assert s.acum.shape == (63, 500, 4) and s.etiqueta == C.ETIQUETA


def _corr_pasos(acum: np.ndarray) -> np.ndarray:
    pasos = np.diff(np.concatenate([np.zeros((1, *acum.shape[1:])), acum]), axis=0)
    return np.corrcoef(pasos.reshape(-1, acum.shape[2]), rowvar=False)


def test_correlacion_simulada_dentro_de_005_de_la_historica(vistas):
    """bootstrap_est: la correlación de Pearson de los rendimientos diarios simulados de las siete
    X/COP está a ±0,05 de la histórica de la muestra (10.000 trayectorias)."""
    s = C.simular_conjunto(vistas, SIETE, "bootstrap_est", sims=10_000, semilla=20240501, largo=21)
    hist = C.rendimientos_muestra(vistas, SIETE, s.muestra_desde).corr().to_numpy()
    dif = np.abs(_corr_pasos(s.acum) - hist)
    assert dif.max() <= 0.05, f"máxima diferencia {dif.max():.3f}"


def test_correlacion_filtrada_conserva_la_de_los_choques_estandarizados(vistas):
    """bootstrap_est_filtrado remuestrea z = r/σ con índices compartidos: la correlación simulada
    de los factores está a ±0,05 de la histórica de los z (10.000 trayectorias). La de los X/COP
    NO se exige: cada factor se reescala con su propia σ del origen y la correlación de los
    cruces queda condicionada a esas σ (docs/decisiones.md, M2)."""
    from laboratorio.modelos.bootstrap import residuos_estandarizados
    s = C.simular_conjunto(vistas, SIETE, "bootstrap_est_filtrado", sims=10_000, semilla=20240501,
                           largo=21)
    R = np.diff(np.log(C.niveles_factores(vistas, SIETE, s.muestra_desde).to_numpy()), axis=0)
    Z = np.column_stack([residuos_estandarizados(np.r_[np.nan, R[:, j]]) for j in range(R.shape[1])])
    hist_z = np.corrcoef(Z[np.isfinite(Z).all(axis=1)], rowvar=False)
    dif = np.abs(_corr_pasos(s.acum_factores) - hist_z)
    assert dif.max() <= 0.05, f"máxima diferencia {dif.max():.3f}"


def test_semilla_fija_resultado_identico(vistas):
    a = C.simular_conjunto(vistas, ("USD", "EUR", "JPY"), sims=300, semilla=5, largo=21)
    b = C.simular_conjunto(vistas, ("USD", "EUR", "JPY"), sims=300, semilla=5, largo=21)
    c = C.simular_conjunto(vistas, ("USD", "EUR", "JPY"), sims=300, semilla=6, largo=21)
    assert np.array_equal(a.acum, b.acum) and not np.array_equal(a.acum, c.acum)


def test_muestra_comun_empieza_cuando_todas_flotan(vistas):
    con_cny = C.muestra_comun(vistas, SIETE)
    assert con_cny == pd.Timestamp("2005-07-23")         # TRM del sábado 23 = H.10 del 22-jul-2005
    sin_cny = C.muestra_comun(vistas, ("USD", "EUR", "BRL"))
    assert sin_cny >= FIN_BANDA                          # nunca incluye la banda colombiana
    s = C.simular_conjunto(vistas, SIETE, sims=50, largo=5)
    assert s.muestra_desde == "2005-07-23" and s.muestra_hasta <= ORIGEN
    with pytest.raises(ValueError, match="flotación"):
        C.simular_conjunto(vistas, SIETE, sims=50, largo=5, desde="2000-01-01")
    tarde = C.simular_conjunto(vistas, SIETE, sims=50, largo=5, desde="2010-01-04")
    assert tarde.muestra_desde >= "2010-01-04"


def test_bloque_comun_trm_y_alternativa_mediana(vistas):
    s = C.simular_conjunto(vistas, SIETE, sims=50, largo=5)
    assert s.regla_bloque == "trm" and s.bloque == s.bloques_factor["TRM"]
    m = C.simular_conjunto(vistas, SIETE, sims=50, largo=5, bloque="mediana")
    assert m.bloque == float(np.median(list(m.bloques_factor.values()))) and len(m.bloques_factor) == 7
    with pytest.raises(ValueError):
        C.simular_conjunto(vistas, SIETE, sims=50, largo=5, bloque="otra")


def test_variante_filtrada_cada_serie_con_su_sigma(vistas):
    s = C.simular_conjunto(vistas, ("USD", "EUR", "BRL"), "bootstrap_est_filtrado", sims=50, largo=5)
    assert set(s.sigma_origen) == set(s.factores) == {"TRM", "USD por EUR", "USD por BRL"}
    assert len(set(s.sigma_origen.values())) == 3 and all(v > 0 for v in s.sigma_largo.values())
    n = C.simular_conjunto(vistas, ("USD", "EUR"), "bootstrap_est", sims=50, largo=5)
    assert n.sigma_origen is None and n.rho is None


def test_entradas_invalidas(vistas):
    with pytest.raises(ValueError, match="motor"):
        C.simular_conjunto(vistas, ("USD",), "otro", sims=10, largo=5)
    with pytest.raises(ValueError, match="divisa"):
        C.simular_conjunto(vistas, ("USD", "XYZ"), sims=10, largo=5)
    with pytest.raises(ValueError):
        C.simular_conjunto(vistas, ("USD",), sims=0, largo=5)


# --- fuga: nada posterior al origen entra al remuestreo -----------------------------------------
def _sinteticas(n=900, seed=4):
    rng = np.random.default_rng(seed)
    fechas = pd.bdate_range("2006-01-02", periods=n)
    out = {}
    for j, d in enumerate(SIETE):
        nivel = (100 + j) * np.exp(np.cumsum(rng.standard_t(5, n) * 0.006))
        out[d] = pd.DataFrame({"cop_por_unidad": nivel, "regimen": "flotacion"}, index=fechas)
    return out


@pytest.mark.parametrize("motor", ["bootstrap_est_filtrado", "bootstrap_est"])
def test_sin_fuga_datos_posteriores_al_origen_no_cambian_nada(motor):
    v = _sinteticas()
    o = v["USD"].index[700]
    base = C.simular_conjunto(v, SIETE, motor, sims=200, semilla=9, largo=21, origen=o)
    recortada = {d: x[x.index <= o] for d, x in v.items()}
    alterada = {d: x.assign(cop_por_unidad=np.where(x.index > o, x["cop_por_unidad"] * 3.0,
                                                    x["cop_por_unidad"])) for d, x in v.items()}
    for otra in (C.simular_conjunto(recortada, SIETE, motor, sims=200, semilla=9, largo=21),
                 C.simular_conjunto(alterada, SIETE, motor, sims=200, semilla=9, largo=21, origen=o)):
        assert np.array_equal(base.acum, otra.acum)
    assert base.muestra_hasta == str(o.date())
    sin_origen = C.simular_conjunto(alterada, SIETE, motor, sims=200, semilla=9, largo=21)
    assert not np.array_equal(base.acum, sin_origen.acum)        # el canario sí detecta datos nuevos
