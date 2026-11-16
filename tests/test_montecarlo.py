"""F5: Monte Carlo del caso. Datos sintéticos y como máximo 500 trayectorias."""
import json

import numpy as np
import pandas as pd
import pytest

from laboratorio.backtest.datos import Vista, construir_vista
from laboratorio.backtest.final import MOTOR_CASO, MOTOR_SENSIBILIDAD
from laboratorio.backtest.particion import NIVELES
from laboratorio.modelos.bootstrap import BootstrapEstacionario
from laboratorio.motor import montecarlo as mc
from laboratorio.motor import respaldo
from laboratorio.motor.deterministas import trayectoria
from laboratorio.motor.ficha import hash_resultado
from laboratorio.motor.historica import pasos_por_compra
from laboratorio.motor.plan import PlanCompra, evaluar

PLAN = PlanCompra.escalonado(10000, 12)
TRM0 = 3300.0


def vista(n=1500, seed=5):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2000-01-03", periods=n)
    r = rng.standard_t(5, n) * 0.006
    trm = pd.DataFrame({"trm": 3000 * np.exp(np.cumsum(r)), "regimen": "flotacion", "estres": ""}, index=idx)
    return mc.vista_trm(trm)


def vista_con_rendimiento(d: float, n=600) -> Vista:
    """Serie sin volatilidad: todos los rendimientos diarios valen exactamente d."""
    idx = pd.bdate_range("2000-01-03", periods=n)
    r = np.concatenate([[np.nan], np.full(n - 1, d)])
    logp = np.log(3000.0) + np.concatenate([[0.0], np.cumsum(r[1:])])
    return Vista(idx, logp, r, np.zeros(n, bool), np.full(n, ""), pd.DataFrame(index=idx[:0]))


# ---- invariante 1: volatilidad cero = determinista ------------------------------------------------
def test_volatilidad_cero_coincide_con_el_escenario_determinista():
    g = 0.12                                             # deriva anual logarítmica
    sim = mc.simular(vista_con_rendimiento(g / 252), MOTOR_SENSIBILIDAD, sims=40, largo=252)
    pasos = tuple(21 * m for m in PLAN.meses)            # 21 pasos por mes: d·21·m = g·m/12
    costos = mc.costos(PLAN, TRM0, sim.acum, pasos)
    esperado = evaluar(PLAN, trayectoria(TRM0, g, PLAN.meses)).costo_cop
    assert costos == pytest.approx(esperado, rel=1e-9)   # las 40 trayectorias, la misma cifra
    assert np.ptp(costos) < 1e-6 * esperado


def test_volatilidad_cero_en_el_motor_filtrado_da_el_costo_de_comprar_hoy():
    sim = mc.simular(vista_con_rendimiento(0.0), MOTOR_CASO, sims=40, largo=252)
    assert np.all(sim.acum == 0)
    costos = mc.costos(PLAN, TRM0, sim.acum, tuple(21 * m for m in PLAN.meses))
    assert costos == pytest.approx(PLAN.meta_usd * TRM0, rel=1e-12)   # determinista con g = 0


# ---- invariante 2: misma semilla = mismo hash -----------------------------------------------------
@pytest.mark.parametrize("motor", [MOTOR_CASO, MOTOR_SENSIBILIDAD])
def test_misma_semilla_mismo_hash_y_otra_semilla_otro_hash(motor):
    v = vista()
    pasos = tuple(20 * m for m in PLAN.meses)
    h = [hash_resultado(mc.costos(PLAN, TRM0, mc.simular(v, motor, sims=300, semilla=s).acum, pasos))
         for s in (11, 11, 12)]
    assert h[0] == h[1] and h[0] != h[2]


# ---- invariante 3: bloque 1 = bootstrap simple ----------------------------------------------------
def test_bloque_1_recupera_el_bootstrap_simple():
    v = vista()
    sim = mc.simular(v, MOTOR_SENSIBILIDAD, sims=200, semilla=7, largo=60, bloque=1.0)
    x = v.r[1:]
    rng = np.random.default_rng([7, v.n - 1])
    a_mano = np.cumsum(x[rng.integers(0, len(x), size=(60, 200))], axis=0)   # sorteos independientes
    assert sim.bloque == 1.0 and np.array_equal(sim.acum, a_mano)
    pasos = (0, 20, 40, 60)
    plan = PlanCompra.escalonado(1000, 4)
    assert np.array_equal(mc.costos(plan, TRM0, sim.acum, pasos), mc.costos(plan, TRM0, a_mano, pasos))
    otro = mc.simular(v, MOTOR_SENSIBILIDAD, sims=200, semilla=7, largo=60)   # Politis-White
    assert otro.bloque > 1.0 and not np.array_equal(otro.acum, sim.acum)


# ---- el motor es el modelo evaluado, no una copia --------------------------------------------------
@pytest.mark.parametrize("motor,filtrado", [(MOTOR_CASO, True), (MOTOR_SENSIBILIDAD, False)])
def test_los_cuantiles_del_monte_carlo_son_los_del_modelo_evaluado(motor, filtrado):
    v = vista()
    o = v.n - 1
    modelo = BootstrapEstacionario(filtrado=filtrado, sims=300, horizontes=(1, 21, 126, 252))
    modelo.ajustar(v)
    q = modelo.pronosticar(v, np.array([o]), NIVELES)
    sim = mc.simular(v, motor, sims=300, semilla=modelo.semilla, largo=252)
    assert sim.bloque == modelo.bloque and sim.origen == o
    for h in (1, 21, 126, 252):
        assert np.array_equal(np.quantile(sim.acum[h - 1], NIVELES), q[h][0])


def test_motor_filtrado_parte_de_la_volatilidad_actual():
    sim = mc.simular(vista(), MOTOR_CASO, sims=50, largo=30)
    assert sim.sigma_origen > 0 and sim.sigma_largo > 0 and 0.5 <= sim.rho <= 0.9999
    assert mc.simular(vista(), MOTOR_SENSIBILIDAD, sims=50, largo=30).sigma_origen is None
    with pytest.raises(ValueError, match="motor desconocido"):
        mc.simular(vista(), "ewma_0.94", sims=50)


# ---- costos, bandas y pasos -------------------------------------------------------------------------
def test_costos_a_mano_y_fronteras():
    acum = np.log(np.array([[1.10, 0.90], [1.20, 0.80], [1.50, 0.50]]))     # 3 pasos, 2 trayectorias
    plan = PlanCompra((0, 1, 2), (100.0, 100.0, 100.0))
    c = mc.costos(plan, 1000.0, acum, (0, 1, 3))
    assert c == pytest.approx([100e3 * (1 + 1.10 + 1.50), 100e3 * (1 + 0.90 + 0.50)])
    for pasos in ((0, 1), (0, 1, 4), (-1, 1, 2)):
        with pytest.raises(ValueError):
            mc.costos(plan, 1000.0, acum, pasos)
    with pytest.raises(ValueError):
        mc.costos(plan, 0.0, acum, (0, 1, 2))


def test_bandas_empiezan_en_la_trm_de_hoy_y_estan_ordenadas():
    sim = mc.simular(vista(), MOTOR_CASO, sims=400, largo=120)
    b = mc.bandas(sim.acum, TRM0)
    assert b.shape == (121, len(mc.NIVELES_ABANICO)) and np.all(b[0] == TRM0)
    assert (np.diff(b, axis=1) >= 0).all()
    ancho = b[:, -1] - b[:, 0]
    assert ancho[120] > ancho[20] > ancho[1] > 0          # el abanico se abre con el horizonte


def test_pasos_por_compra_sigue_el_calendario_de_la_serie():
    idx = pd.bdate_range("2010-01-04", periods=2600)       # ≈ 21,7 días hábiles por mes
    trm = pd.Series(3000.0, index=idx)
    pasos = pasos_por_compra(trm, PLAN, "2010-01-04")
    assert pasos[0] == 0 and all(b > a for a, b in zip(pasos, pasos[1:]))
    assert 21 <= pasos[1] <= 23 and 11 * 21 <= pasos[-1] <= 11 * 22 + 2
    assert pasos_por_compra(trm, PlanCompra.todo_hoy(100), "2010-01-04") == (0,)
    with pytest.raises(ValueError):
        pasos_por_compra(trm, PLAN, "2030-01-01")


def test_figura_abanico_se_escribe(tmp_path):
    sim = mc.simular(vista(), MOTOR_CASO, sims=100, largo=60)
    ruta = mc.figura_abanico(mc.bandas(sim.acum, TRM0), mc.NIVELES_ABANICO, (0, 20, 40, 60),
                             tmp_path / "figs" / "abanico.png", "prueba")
    assert ruta.exists() and ruta.stat().st_size > 1000


# ---- respaldo ---------------------------------------------------------------------------------------
RESPALDO = {
    "nominal": 0.95, "sha256_hecho": "0" * 64,
    "cobertura": {MOTOR_CASO: {
        "1": {"cobertura": 0.91, "n": 1000, "n_efectivo": 1000, "ic_inf": 0.89, "ic_sup": 0.93, "compatible": False},
        "63": {"cobertura": 0.96, "n": 1000, "n_efectivo": 16, "ic_inf": 0.7, "ic_sup": 1.0, "compatible": True}}},
    "confirmatorias": {
        "1": {"campeon": "lightgbm_cuantiles", "base": "sim_hist_pond", "relativo": 0.97, "p_holm": 0.001,
              "n": 1000, "exito": True},
        "5": {"campeon": "ewma_0.94", "base": "sim_hist_pond", "relativo": 0.99, "p_holm": 0.4,
              "n": 1000, "exito": False}},
    "var_h1": {"lightgbm_cuantiles": {"sup 5 %": {"tasa": 0.07, "p_kupiec": 0.002}}},
}


def test_respaldo_entrega_cifras_con_fuente_y_hash(tmp_path):
    assert respaldo.cargar(None) is None and respaldo.cargar(tmp_path / "no_existe.json") is None
    ruta = tmp_path / "prueba_final.json"
    ruta.write_text(json.dumps(RESPALDO), encoding="utf-8")
    r = respaldo.cargar(ruta)
    cob = r.cobertura(MOTOR_CASO, 63)
    assert cob["cobertura"].valor == 0.96 and cob["n_efectivo"].valor == 16
    assert all(c.origen == "dato" and c.referencia.startswith(respaldo.ARCHIVO) for c in cob.values())
    assert len({c.hash for c in cob.values()}) == len(cob)             # una cifra por campo
    assert r.cobertura(MOTOR_CASO, 21) is None and r.cobertura("otro", 1) is None
    assert r.exito(1)["campeon"].valor == "lightgbm_cuantiles"
    assert r.exito(5) is None and r.exito(21) is None                  # solo se cita lo que tuvo éxito
    assert r.var_h1("lightgbm_cuantiles", "sup 5 %")["tasa"].valor == 0.07
    assert r.var_h1("lightgbm_cuantiles", "sup 1 %") is None
    ruta.write_text(json.dumps({**RESPALDO, "nominal": 0.9}), encoding="utf-8")
    assert respaldo.cargar(ruta).cobertura(MOTOR_CASO, 63)["cobertura"].hash != cob["cobertura"].hash


def test_generar_respaldo_exige_la_prueba_final_terminada(tmp_path):
    with pytest.raises(FileNotFoundError, match="no ha terminado"):
        respaldo.generar(tmp_path)
