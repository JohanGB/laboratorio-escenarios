import numpy as np
import pandas as pd
import pytest

from laboratorio.motor.historica import (desplazar_meses, distribucion, ratios_todas,
                                         ratios_ventana, reproducir, trms_ventana)
from laboratorio.motor.plan import PlanCompra, evaluar

rng = np.random.default_rng(3)


def serie(n=1500, inicio="2015-01-01", paso=0.01, constante=None):
    idx = pd.bdate_range(inicio, periods=n)
    if constante is not None:
        return pd.Series(constante, index=idx)
    return pd.Series(3000 * np.exp(np.cumsum(rng.normal(0, paso, n))), index=idx)


def test_desplazar_meses_ajusta_fin_de_mes():
    assert desplazar_meses("2024-01-31", 1) == pd.Timestamp("2024-02-29")
    assert desplazar_meses("2024-03-15", 12) == pd.Timestamp("2025-03-15")


def test_ratio_inicial_es_uno_y_fines_de_semana_usan_dato_previo():
    s = serie()
    ini = s.index[10]
    r = ratios_ventana(s, ini, [0, 1, 3])
    assert r[0] == 1.0
    objetivo = desplazar_meses(ini, 1)
    esperado = s[s.index <= objetivo].iloc[-1] / s[ini]
    assert r[1] == pytest.approx(esperado)


def test_ida_y_vuelta_movimientos_con_trm0_igual_al_inicio_reproduce_calendario():
    s = serie()
    plan = PlanCompra.escalonado(12000, 12)
    for ini in rng.choice(s.index[:-400], 10, replace=False):
        cal = reproducir(plan, s, ini, "calendario")
        mov = reproducir(plan, s, ini, "movimientos", trm0=s[ini])
        assert mov.costo_cop == pytest.approx(cal.costo_cop, rel=1e-12)
        assert np.allclose(mov.trms, cal.trms, rtol=1e-12)


def test_movimientos_escala_linealmente_con_trm0():
    s = serie()
    plan = PlanCompra.escalonado(1000, 6)
    a = reproducir(plan, s, s.index[5], "movimientos", trm0=3000.0)
    b = reproducir(plan, s, s.index[5], "movimientos", trm0=6000.0)
    assert b.costo_cop == pytest.approx(2 * a.costo_cop)
    assert b.costo_medio == pytest.approx(2 * a.costo_medio)


def test_serie_constante_razones_uno_y_costo_igual_a_hoy():
    s = serie(constante=3500.0)
    plan = PlanCompra.escalonado(1000, 12)
    d = distribucion(plan, s, 4000.0, s.index[0])
    assert np.allclose(d.costos, 1000 * 4000.0)
    assert d.percentil(95) == pytest.approx(d.costo_hoy) and d.prob_mas_barato_que_hoy() == 0.0


def test_ventanas_fuera_de_los_datos_fallan():
    s = serie()
    plan = PlanCompra.escalonado(1000, 12)
    with pytest.raises(ValueError, match="anterior"):
        trms_ventana(s, "2000-01-01", [0])
    with pytest.raises(ValueError, match="después del último"):
        reproducir(plan, s, s.index[-5], "calendario")
    with pytest.raises(ValueError):
        reproducir(plan, s, s.index[0], "movimientos")        # falta trm0
    with pytest.raises(ValueError):
        reproducir(plan, s, s.index[0], "otro", trm0=1.0)


def test_sin_mirar_el_futuro_cambiar_datos_posteriores_no_altera_la_ventana():
    s = serie()
    plan = PlanCompra.escalonado(1000, 6)
    ini = s.index[100]
    base = reproducir(plan, s, ini, "calendario").costo_cop
    fin = desplazar_meses(ini, plan.horizonte_meses)
    s2 = s.copy()
    s2[s2.index > fin] *= 10
    assert reproducir(plan, s2, ini, "calendario").costo_cop == base


def test_vectorizado_coincide_con_el_calculo_individual():
    s = serie()
    plan = PlanCompra.escalonado(1000, 12)
    inicios, r = ratios_todas(s, plan, s.index[0])
    for i in rng.choice(len(inicios), 25, replace=False):
        assert np.allclose(r[i], ratios_ventana(s, inicios[i], plan.meses), rtol=1e-12)


def test_numero_de_ventanas_y_limites():
    s = serie()
    plan = PlanCompra.escalonado(1000, 12)
    inicios, _ = ratios_todas(s, plan, s.index[200])
    limite = desplazar_meses(s.index[-1], -11)
    assert inicios.min() >= s.index[200] and inicios.max() <= limite
    assert len(inicios) == ((s.index >= s.index[200]) & (s.index <= limite)).sum()
    with pytest.raises(ValueError, match="ninguna ventana"):
        ratios_todas(s, plan, s.index[-3])


def test_plan_todo_hoy_es_degenerado_y_resumen_coherente():
    s = serie()
    d1 = distribucion(PlanCompra.todo_hoy(1000), s, 4000.0, s.index[0])
    assert np.allclose(d1.costos, 1000 * 4000.0)
    d = distribucion(PlanCompra.escalonado(1000, 12), s, 4000.0, s.index[0])
    r = d.resumen(presupuesto_cop=1e18)
    assert r["p5"] <= r["p50"] <= r["p95"] and r["min"] <= r["media"] <= r["max"]
    assert r["prob_superar_presupuesto"] == 0.0
    assert d.resumen(0.0)["prob_superar_presupuesto"] == 1.0
    assert 0.0 <= r["prob_mas_barato_que_hoy"] <= 1.0
    assert r["ventanas"] == len(d)


def test_costo_por_ventana_coincide_con_evaluar_directo():
    s = serie()
    plan = PlanCompra.escalonado(5000, 12)
    d = distribucion(plan, s, 3900.0, s.index[0])
    i = len(d) // 2
    directo = evaluar(plan, 3900.0 * ratios_ventana(s, d.inicios[i], plan.meses)).costo_cop
    assert d.costos[i] == pytest.approx(directo, rel=1e-12)
