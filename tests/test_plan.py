import numpy as np
import pytest

from laboratorio.motor.plan import PlanCompra, evaluar

rng = np.random.default_rng(1)


def test_construccion_y_validaciones():
    p = PlanCompra.escalonado(12000, 12)
    assert p.meses == tuple(range(12)) and p.meta_usd == pytest.approx(12000)
    assert p.horizonte_meses == 11 and all(u == pytest.approx(1000) for u in p.usd)
    assert PlanCompra.escalonado(900, 3, 2).meses == (0, 2, 4)
    assert PlanCompra.todo_hoy(500).meses == (0,)
    for malo in (lambda: PlanCompra((), ()), lambda: PlanCompra((0, 0), (1, 1)),
                 lambda: PlanCompra((1, 0), (1, 1)), lambda: PlanCompra((0,), (0,)),
                 lambda: PlanCompra((-1,), (1,)), lambda: PlanCompra((0, 1), (1,)),
                 lambda: PlanCompra.escalonado(-1, 3), lambda: PlanCompra.escalonado(10, 0)):
        with pytest.raises(ValueError):
            malo()


def test_costo_es_suma_de_usd_por_trm():
    p = PlanCompra((0, 1, 2), (100.0, 200.0, 300.0))
    r = evaluar(p, [4000.0, 4100.0, 3900.0])
    assert r.costo_cop == pytest.approx(100 * 4000 + 200 * 4100 + 300 * 3900)
    assert r.usd_total == 600 and r.costo_medio == pytest.approx(r.costo_cop / 600)


def test_costo_medio_entre_min_y_max_pagados():
    for _ in range(50):
        n = int(rng.integers(1, 15))
        p = PlanCompra.escalonado(float(rng.uniform(100, 1e5)), n)
        t = rng.uniform(2000, 6000, size=n)
        r = evaluar(p, t)
        assert t.min() - 1e-9 <= r.costo_medio <= t.max() + 1e-9


def test_trm_constante_equivale_a_comprar_hoy():
    t0 = 3316.7
    hoy = evaluar(PlanCompra.todo_hoy(10000), [t0])
    esc = evaluar(PlanCompra.escalonado(10000, 12), [t0] * 12)
    assert hoy.costo_cop == pytest.approx(10000 * t0)
    assert esc.costo_cop == pytest.approx(hoy.costo_cop) and esc.costo_medio == pytest.approx(t0)


def test_escalar_plan_escala_costo_y_no_el_costo_medio():
    p = PlanCompra.escalonado(1000, 4)
    t = [4000.0, 4200.0, 3900.0, 4100.0]
    a, b = evaluar(p, t), evaluar(p.escalar(3.5), t)
    assert b.costo_cop == pytest.approx(3.5 * a.costo_cop)
    assert b.usd_total == pytest.approx(3.5 * a.usd_total)
    assert b.costo_medio == pytest.approx(a.costo_medio)


def test_monotonia_trm_mayor_en_cada_punto_cuesta_mas():
    p = PlanCompra.escalonado(1000, 6)
    t = rng.uniform(3000, 5000, size=6)
    assert evaluar(p, t + 1).costo_cop > evaluar(p, t).costo_cop
    mas = t.copy()
    mas[3] += 100
    assert evaluar(p, mas).costo_cop > evaluar(p, t).costo_cop


def test_presupuesto_y_arrepentimiento():
    p = PlanCompra.escalonado(1000, 2)
    r = evaluar(p, [4000.0, 4400.0])      # costo = 500*4000 + 500*4400 = 4.2e6
    assert r.se_pasa(4.1e6) and not r.se_pasa(4.2e6)
    assert r.arrepentimiento(1000 * 4000) == pytest.approx(2e5)


def test_evaluar_rechaza_entradas_inconsistentes():
    p = PlanCompra.escalonado(1000, 2)
    with pytest.raises(ValueError):
        evaluar(p, [4000.0])
    with pytest.raises(ValueError):
        evaluar(p, [4000.0, 0.0])
