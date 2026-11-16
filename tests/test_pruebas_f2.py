"""F2: cada prueba nueva contra un cálculo a mano o un caso con respuesta conocida."""
import numpy as np
import pandas as pd
import pytest
from scipy import stats

from laboratorio.evaluacion.cobertura import cobertura_n_efectivo
from laboratorio.evaluacion.direccion import acierto_binomial, pesaran_timmermann
from laboratorio.evaluacion.mcs import bloque_por_defecto, conjunto_confianza
from laboratorio.evaluacion.pit import casillas, pit, uniformidad
from laboratorio.evaluacion.riesgo import (acerbi_szekely_z2, es_de_rejilla, prueba_var,
                                           rejilla_cola, semaforo_basilea, violaciones)


# ---- VaR en ambas colas -----------------------------------------------------------------------
def test_var_cola_inferior_reproduce_kupiec_clasico_y_la_superior_es_su_espejo():
    # Mismo caso de Jorion que test_pruebas_estadisticas: n=250, x=5, p=0,01 → LR=1,9568, p=0,16186
    y = np.zeros(250); y[[10, 60, 110, 160, 210]] = -3.0
    q = np.full(250, -2.0)
    inf = prueba_var(y, q, 0.01, "inf")
    assert inf["violaciones"] == 5 and inf["tasa"] == 0.02
    assert inf["p_uc"] == pytest.approx(0.16186, abs=1e-4)
    sup = prueba_var(-y, -q, 0.01, "sup")
    assert sup == inf
    assert not violaciones(np.array([-2.0]), np.array([-2.0]), "inf")[0]     # igualdad no viola
    with pytest.raises(ValueError):
        violaciones(y, q, "centro")


# ---- Semáforo de Basilea ----------------------------------------------------------------------
def test_semaforo_basilea_conteo_a_mano():
    # 500 obs., 10 excepciones en las posiciones 0..9. Ventanas de 250: 500 − 250 + 1 = 251.
    # La ventana que empieza en s contiene máx(0, 10 − s) excepciones:
    #   s=0 → 10 (rojo: 1 ventana); s=1..5 → 9..5 (amarillo: 5); s=6..250 → 4..0 (verde: 245).
    v = np.zeros(500, bool); v[:10] = True
    r = semaforo_basilea(v)
    assert r["ventanas"] == 251 and r["max"] == 10
    assert r["rojo"] == pytest.approx(1 / 251) and r["amarillo"] == pytest.approx(5 / 251)
    assert r["verde"] == pytest.approx(245 / 251)
    assert r["verde"] + r["amarillo"] + r["rojo"] == pytest.approx(1.0)
    with pytest.raises(ValueError):
        semaforo_basilea(np.zeros(100, bool))


def test_semaforo_limites_de_zona():
    for x, zona in ((4, "verde"), (5, "amarillo"), (9, "amarillo"), (10, "rojo")):
        v = np.zeros(250, bool); v[:x] = True
        assert semaforo_basilea(v)[zona] == 1.0


# ---- Expected Shortfall -----------------------------------------------------------------------
def test_es_de_rejilla_contra_la_formula_cerrada_de_la_normal():
    # Normal estándar, α = 0,025: ES = −φ(z_α)/α = −0,0584451/0,025 = −2,33780
    exacto = -stats.norm.pdf(stats.norm.ppf(0.025)) / 0.025
    assert exacto == pytest.approx(-2.33780, abs=1e-4)
    u = rejilla_cola(0.025, 25, "inf")
    assert u[0] == pytest.approx(0.0005) and u[-1] == pytest.approx(0.0245) and len(u) == 25
    es = es_de_rejilla(stats.norm.ppf(u)[None, :])[0]
    assert es == pytest.approx(exacto, rel=0.005)            # punto medio: error < 0,5 %
    s = rejilla_cola(0.025, 25, "sup")
    assert np.allclose(s, 1 - u[::-1]) and (np.diff(s) > 0).all()
    assert es_de_rejilla(stats.norm.ppf(s)[None, :])[0] == pytest.approx(-exacto, rel=0.005)


def test_es_de_rejilla_con_simulaciones_es_el_promedio_de_la_cola():
    x = np.random.default_rng(0).standard_t(5, 200_000)
    cola = np.sort(x)[: int(0.025 * len(x))].mean()
    es = es_de_rejilla(np.quantile(x, rejilla_cola(0.025, 25, "inf"))[None, :])[0]
    assert es == pytest.approx(cola, rel=0.01)


# ---- Acerbi-Székely Z2 ------------------------------------------------------------------------
def test_z2_a_mano():
    # T = 10, α = 0,2, VaR = −1, ES = −2. Violaciones (y < −1): −3 y −1,5.
    # Σ y/ES = 3/2 + 1,5/2 = 2,25 ; Z2 = 1 − 2,25/(10·0,2) = 1 − 1,125 = −0,125
    y = np.array([0, 0, -3.0, 0, 0, 0, -1.5, 0, 0, 0])
    var, es = np.full(10, -1.0), np.full(10, -2.0)
    r = acerbi_szekely_z2(y, var, es, 0.2, "inf")
    assert r["z2"] == pytest.approx(-0.125) and r["violaciones"] == 2 and r["esperadas"] == 2
    assert acerbi_szekely_z2(-y, -var, -es, 0.2, "sup")["z2"] == pytest.approx(-0.125)
    # Dos violaciones iguales al ES: Σ y/ES = 2 → Z2 = 0 (calibrado)
    y0 = np.array([0, 0, -2.0, 0, 0, 0, -2.0, 0, 0, 0])
    assert acerbi_szekely_z2(y0, var, es, 0.2, "inf")["z2"] == pytest.approx(0.0)
    with pytest.raises(ValueError):
        acerbi_szekely_z2(y, var, -es, 0.2, "inf")           # ES con el signo equivocado


def test_z2_cero_con_el_modelo_correcto_y_negativo_si_subestima_la_cola():
    rng = np.random.default_rng(1)
    n, a = 200_000, 0.025
    y = rng.standard_normal(n)
    var = np.full(n, stats.norm.ppf(a)); es = np.full(n, -stats.norm.pdf(stats.norm.ppf(a)) / a)
    assert abs(acerbi_szekely_z2(y, var, es, a, "inf")["z2"]) < 0.03
    r = acerbi_szekely_z2(1.5 * y, var, es, a, "inf")        # volatilidad real 50 % mayor
    assert r["z2"] < -0.70 and r["rechaza_5"] and r["exceso_medio"] > 1


# ---- PIT --------------------------------------------------------------------------------------
NIV3 = np.array([0.25, 0.5, 0.75])


def _caso_pit(rep):
    y = np.repeat([-2, -2, -2, -0.5, 0.5, 0.5, 2, 2], rep).astype(float)
    return y, np.tile([-1.0, 0.0, 1.0], (len(y), 1))


def test_uniformidad_ji_cuadrado_a_mano():
    # 40 obs.: conteos por casilla [15, 5, 10, 10]; esperados 40·0,25 = 10 en cada una.
    # χ² = (25 + 25 + 0 + 0)/10 = 5,0 ; 3 g.l. ; p = P(χ²₃ > 5) = 0,171797
    y, q = _caso_pit(5)
    obs, prob = casillas(y, q, NIV3)
    assert obs.tolist() == [15, 5, 10, 10] and prob.tolist() == [0.25, 0.25, 0.25, 0.25]
    r = uniformidad(y, q, NIV3)
    assert r.estadistico == pytest.approx(5.0) and r.detalle["gl"] == 3
    assert r.p_valor == pytest.approx(0.171797, abs=1e-5) and not r.detalle["aproximada"]


def test_uniformidad_con_n_efectivo_y_fusion_de_casillas():
    y, q = _caso_pit(5)
    # n_ef = 20: observados [7,5; 2,5; 5; 5], esperados 5 → χ² = (6,25 + 6,25)/5 = 2,5; 3 g.l.
    r = uniformidad(y, q, NIV3, n_efectivo=20)
    assert r.estadistico == pytest.approx(2.5) and r.detalle["aproximada"]
    assert r.p_valor == pytest.approx(stats.chi2.sf(2.5, 3))
    # n_ef = 8: esperados 2 por casilla (< 5) → se fusionan desde la izquierda hasta quedar 2
    # casillas: [3+1+2, 2] contra [6, 2] → χ² = 0, 1 g.l.
    r = uniformidad(y, q, NIV3, n_efectivo=8)
    assert r.detalle["casillas"] == 2 and r.detalle["gl"] == 1
    assert r.estadistico == pytest.approx(0.0)


def test_uniformidad_no_rechaza_calibrado_y_rechaza_sesgado():
    rng = np.random.default_rng(2)
    niv = np.array([0.01, 0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.975, 0.99])
    y = rng.standard_normal(5000)
    q = np.tile(stats.norm.ppf(niv), (5000, 1))
    assert uniformidad(y, q, niv).p_valor > 0.01
    assert uniformidad(y, 0.7 * q, niv).p_valor < 1e-6        # intervalos demasiado angostos


def test_pit_interpolado():
    y, q = np.array([0.5, -2.0, 2.0, -1.0]), np.tile([-1.0, 0.0, 1.0], (4, 1))
    # 0,5 está a mitad entre q(0,5)=0 y q(0,75)=1 → 0,625; fuera del rango: punto medio de la
    # casilla extrema (0,125 y 0,875); y = q_1 cae en la primera casilla.
    assert pit(y, q, NIV3).tolist() == [0.625, 0.125, 0.875, 0.125]


# ---- Acierto direccional ----------------------------------------------------------------------
def test_pesaran_timmermann_y_binomial_a_mano():
    # n = 10. pronóstico: + + + + + + − − − −   realización: + + + + + − − − − +
    # aciertos = 8 → P = 0,8 ; P_y = 0,6 ; P_x = 0,6 ; P* = 0,36 + 0,16 = 0,52
    # var(P) = 0,52·0,48/10 = 0,02496
    # var(P*) = [0,2²·0,24 + 0,2²·0,24 + 4·0,6·0,6·0,4·0,4/10]/10 = [0,0096+0,0096+0,02304]/10 = 0,004224
    # S = 0,28/√0,020736 = 0,28/0,144 = 1,94444 ; p = 1 − Φ(1,94444) = 0,02592
    x = np.array([1, 1, 1, 1, 1, 1, -1, -1, -1, -1.0])
    y = np.array([2, 2, 2, 2, 2, -2, -2, -2, -2, 2.0])
    r = pesaran_timmermann(x, y)
    assert r.estadistico == pytest.approx(1.944444, abs=1e-5)
    assert r.p_valor == pytest.approx(0.02592, abs=1e-4)
    assert r.detalle["P_esperado"] == pytest.approx(0.52)
    # Binomial bilateral: 8 de 10 → 2·(C(10,8)+C(10,9)+C(10,10))/2¹⁰ = 2·56/1024 = 0,109375
    b = acierto_binomial(x, y)
    assert b.estadistico == 0.8 and b.p_valor == pytest.approx(0.109375)


def test_direccion_descarta_ceros_y_no_aplica_con_un_solo_signo():
    x = np.array([1, 0, 1, -1.0]); y = np.array([1, 1, 0, -1.0])
    assert acierto_binomial(x, y).detalle == {"n": 2, "aciertos": 2, "aplica": True}
    siempre = pesaran_timmermann(np.ones(50), np.random.default_rng(0).standard_normal(50))
    assert not siempre.detalle["aplica"] and np.isnan(siempre.p_valor)
    assert not acierto_binomial(np.zeros(5), np.ones(5)).detalle["aplica"]


# ---- Cobertura con n efectivo -----------------------------------------------------------------
def test_cobertura_n_efectivo_clopper_pearson_a_mano():
    # n = 504 orígenes a h = 126 → n_ef = 4. Cobertura observada 0,75 → k_ef = 3.
    # Clopper-Pearson 95 % para 3 de 4: inf = Beta⁻¹(0,025; 3, 2) = 0,19412 ;
    # sup = Beta⁻¹(0,975; 4, 1) = 0,975^(1/4) = 0,99369
    y = np.zeros(504); y[:126] = 5.0
    r = cobertura_n_efectivo(y, np.full(504, -1.0), np.full(504, 1.0), 0.95, 126)
    assert r["cobertura"] == 0.75 and r["n_efectivo"] == 4 and r["k_efectivo"] == 3
    assert r["ic_inf"] == pytest.approx(0.19412, abs=1e-5)
    assert r["ic_sup"] == pytest.approx(0.975 ** 0.25, abs=1e-9) and r["compatible"]
    todo = cobertura_n_efectivo(np.zeros(252), np.full(252, -1.0), np.full(252, 1.0), 0.5, 126)
    # 2 de 2: inf = 0,025^(1/2) = 0,15811 ; sup = 1
    assert todo["ic_inf"] == pytest.approx(0.025 ** 0.5) and todo["ic_sup"] == 1.0


# ---- Model Confidence Set ---------------------------------------------------------------------
def test_mcs_excluye_al_claramente_peor_y_conserva_a_los_equivalentes():
    rng = np.random.default_rng(3)
    n = 800
    base = rng.gamma(2.0, 1.0, n)
    L = pd.DataFrame({"a": base + rng.normal(0, 0.3, n), "b": base + rng.normal(0, 0.3, n),
                      "peor": base + 0.5 + rng.normal(0, 0.3, n)})
    r = conjunto_confianza(L, h=1, reps=1000)
    en = dict(zip(r.modelo, r.en_mcs))
    assert en == {"a": True, "b": True, "peor": False}
    assert r.set_index("modelo").loc["peor", "p_mcs"] < 0.10
    assert r.perdida.is_monotonic_increasing and r.attrs["bloque"] == 10
    r2 = conjunto_confianza(L, h=1, reps=1000)
    assert r.equals(r2)                                      # semilla fija → reproducible


def test_mcs_modelos_identicos_quedan_todos_y_valida_entradas():
    x = np.random.default_rng(4).gamma(2.0, 1.0, 300)
    r = conjunto_confianza(pd.DataFrame({"a": x, "b": x, "c": x}), reps=200)
    assert r.en_mcs.all()
    assert bloque_por_defecto(1) == 10 and bloque_por_defecto(63) == 126
    with pytest.raises(ValueError):
        conjunto_confianza(pd.DataFrame({"a": x}))
    with pytest.raises(ValueError):
        conjunto_confianza(pd.DataFrame({"a": x, "b": np.where(x > 5, np.nan, x)}))
