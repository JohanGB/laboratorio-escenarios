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


# ---- F5b: análisis posterior, remuestreo solo desde una fecha -----------------------------------------
def vista_dos_tramos(n=1500, corte=700, seed=8):
    """Antes del corte todos los rendimientos son positivos; desde el corte, todos negativos."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2000-01-03", periods=n)
    r = np.where(np.arange(n) < corte, 1.0, -1.0) * rng.uniform(0.001, 0.004, n)
    trm = pd.DataFrame({"trm": 3000 * np.exp(np.cumsum(r)), "regimen": "flotacion", "estres": ""}, index=idx)
    return mc.vista_trm(trm), idx[corte]


@pytest.mark.parametrize("motor", [MOTOR_CASO, MOTOR_SENSIBILIDAD])
def test_desde_remuestrea_solo_ese_tramo_y_no_cambia_nada_mas(motor):
    v, corte = vista_dos_tramos()
    todo = mc.simular(v, motor, sims=200, semilla=3, largo=80)
    solo = mc.simular(v, motor, sims=200, semilla=3, largo=80, desde=corte)
    pasos = lambda s: np.diff(np.vstack([np.zeros((1, s.sims)), s.acum]), axis=0)   # noqa: E731
    assert (pasos(solo) < 0).all()                         # ni un solo rendimiento del tramo anterior
    assert (pasos(todo) > 0).any() and (pasos(todo) < 0).any()
    assert solo.n_muestra == v.n - 700 and todo.n_muestra == v.n - 1
    assert solo.muestra_desde == str(corte.date()) and todo.muestra_desde is None
    # lo único que cambia es la muestra: bloque, volatilidades y persistencia son los del motor
    assert (solo.bloque, solo.rho, solo.sigma_origen, solo.sigma_largo) == (
        todo.bloque, todo.rho, todo.sigma_origen, todo.sigma_largo)
    otra = mc.simular(v, motor, sims=200, semilla=3, largo=80, desde=corte)
    assert hash_resultado(otra.acum) == hash_resultado(solo.acum)                  # misma semilla
    assert hash_resultado(solo.acum) != hash_resultado(todo.acum)
    # una fecha anterior a toda la serie deja la muestra completa: resultado idéntico al del motor
    assert np.array_equal(mc.simular(v, motor, sims=200, semilla=3, largo=80, desde="1990-01-01").acum,
                          todo.acum)
    with pytest.raises(ValueError, match="al menos 250"):
        mc.simular(v, motor, sims=50, largo=30, desde=v.fechas[-100])


def test_resumen_regimenes_coincide_con_el_calculo_a_mano():
    from laboratorio.modelos.bootstrap import residuos_estandarizados
    v, corte = vista_dos_tramos()
    sigma = 0.007
    res = mc.resumen_regimenes(v, corte, sigma)
    r, z = v.r[1:], residuos_estandarizados(v.r)
    antes = np.asarray(v.fechas[1:] < corte)
    for nombre, m in (("antes", antes), ("desde", ~antes)):
        t = res[nombre]
        f = v.fechas[1:][m]
        inicio = v.fechas[v.fechas < f[0]][-1]             # la observación anterior al primer rendimiento
        anios = (f[-1] - inicio).days / 365.25
        assert t["n"] == m.sum() and t["peso"] == pytest.approx(100 * m.mean())
        assert t["media_r"] == pytest.approx(100 * r[m].mean())
        assert t["vol_diaria"] == pytest.approx(100 * r[m].std(ddof=1))
        assert t["deriva_anual"] == pytest.approx(100 * r[m].sum() / anios)
        assert t["media_z"] == pytest.approx(z[m].mean())
        assert t["equiv_diario"] == pytest.approx(100 * z[m].mean() * sigma)
    assert res["antes"]["peso"] + res["desde"]["peso"] == pytest.approx(100)
    assert res["antes"]["aporte_z"] + res["desde"]["aporte_z"] == pytest.approx(z.mean())
    assert res["antes"]["deriva_anual"] > 0 > res["desde"]["deriva_anual"]
    assert set(mc.resumen_regimenes(v, "1990-01-01", sigma)) == {"desde"}          # un solo tramo


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


# ---- F6: análisis posterior, de qué lado de la banda quedó el valor real -----------------------------
def _resultados(h: int, n: int, bajo_mediana: int, bajo_inferior: int, sobre_superior: int) -> pd.DataFrame:
    """n orígenes con banda [−1, 0, 1]: los primeros quedan bajo el límite, luego bajo la mediana…"""
    y = np.full(n, 0.5)                                    # entre la mediana y el límite superior
    y[:bajo_mediana] = -0.5
    y[:bajo_inferior] = -2.0
    y[n - sobre_superior:] = 2.0
    return pd.DataFrame({"h": h, "y": y, "q_0.025": -1.0, "q_0.5": 0.0, "q_0.975": 1.0})


def test_asimetria_cuenta_a_cada_lado_de_la_banda_con_n_efectivo_e_intervalo_exacto():
    from scipy import stats
    from laboratorio.evaluacion.cobertura import cobertura_n_efectivo
    res = {"m": pd.concat([_resultados(1, 200, 120, 10, 4), _resultados(5, 200, 130, 0, 30)])}
    largo = {"m": _resultados(126, 630, 441, 63, 0)}
    a = respaldo.asimetria_motor(res, largo, "m", (1, 5, 21), (126, 252))
    assert set(a) == {"1", "5", "126"}                     # sin filas de un horizonte: no se inventa
    assert a["1"]["n"] == 200 and a["1"]["n_efectivo"] == 200 and a["5"]["n_efectivo"] == 40
    assert a["126"]["n_efectivo"] == 5
    assert [a["1"][k]["proporcion"] for k in respaldo.MEDIDAS_ASIMETRIA] == [0.6, 0.05, 0.02]
    assert [a["1"][k]["esperado"] for k in respaldo.MEDIDAS_ASIMETRIA] == [0.5, 0.025, 0.025]
    ic = stats.binomtest(120, 200).proportion_ci(0.95, method="exact")             # Clopper-Pearson
    assert (a["1"]["bajo_mediana"]["ic_inf"], a["1"]["bajo_mediana"]["ic_sup"]) == pytest.approx(
        (ic.low, ic.high))
    assert not a["1"]["bajo_mediana"]["compatible"]        # 0,5 queda fuera de [0,53; 0,67]
    # las dos colas suman lo que le falta a la cobertura del 95 % publicada
    d = res["m"][res["m"]["h"] == 5]
    cob = cobertura_n_efectivo(d["y"], d["q_0.025"], d["q_0.975"], 0.95, 5)["cobertura"]
    assert 1 - a["5"]["bajo_inferior"]["proporcion"] - a["5"]["sobre_superior"]["proporcion"] == pytest.approx(cob)
    # mismo 0,70 bajo la mediana: con 5 ventanas independientes es compatible con 0,5 (indicio, no prueba)
    assert a["126"]["bajo_mediana"]["proporcion"] == pytest.approx(0.7)
    assert a["126"]["bajo_mediana"]["compatible"] and a["126"]["bajo_mediana"]["ic_inf"] < 0.5
    assert respaldo.asimetria_motor(res, largo, "otro", (1,), (126,)) == {}


def test_respaldo_entrega_la_asimetria_como_cifras_y_none_si_el_archivo_no_la_trae(tmp_path):
    a = respaldo.asimetria_motor({MOTOR_CASO: _resultados(1, 200, 120, 10, 4)}, {}, MOTOR_CASO, (1,), ())
    ruta = tmp_path / "prueba_final.json"
    ruta.write_text(json.dumps(RESPALDO), encoding="utf-8")
    assert respaldo.cargar(ruta).asimetria(MOTOR_CASO, 1) is None                  # archivo anterior a F6
    ruta.write_text(json.dumps({**RESPALDO, "posterior": {
        "titulo": respaldo.TITULO_POSTERIOR, "asimetria": {MOTOR_CASO: a}}}), encoding="utf-8")
    r = respaldo.cargar(ruta)
    c = r.asimetria(MOTOR_CASO, 1)
    assert set(c) == set(respaldo.MEDIDAS_ASIMETRIA)
    assert c["bajo_mediana"]["proporcion"].valor == 0.6 and c["bajo_mediana"]["compatible"].valor == "no"
    assert c["sobre_superior"]["proporcion"].valor == 0.02 and c["sobre_superior"]["esperado"].valor == 0.025
    cifras = [x for campos in c.values() for x in campos.values()]
    assert all(x.origen == "dato" and "posterior;asimetria" in x.referencia for x in cifras)
    assert len({x.hash for x in cifras}) == len(cifras)
    assert r.asimetria(MOTOR_CASO, 5) is None and r.asimetria("otro", 1) is None
