import math

import pytest

from laboratorio.motor.deterministas import (ESCENARIOS, correr, correr_todos, id_deriva,
                                             trayectoria, validar_orden)
from laboratorio.motor.plan import PlanCompra
from laboratorio.motor.supuestos import Registro

META = dict(unidad="1/año", fuente="prueba", justificacion="j", autor="analista", fecha="2026-01-01")


def conjunto(tmp_path, g=(-0.10, 0.02, 0.25)):
    r = Registro(tmp_path / "r.jsonl")
    for n, v in zip(ESCENARIOS, g):
        r.agregar(id_deriva(n), v, **META)
    return r.conjunto({id_deriva(n): 1 for n in ESCENARIOS})


def test_trayectoria_empieza_en_trm0_y_crece_geometricamente():
    t = trayectoria(4000.0, 0.12, [0, 1, 2, 12])
    assert t[0] == 4000.0 and t[3] == pytest.approx(4000 * math.exp(0.12))
    assert t[2] / t[1] == pytest.approx(t[1] / t[0])
    with pytest.raises(ValueError):
        trayectoria(0.0, 0.1, [0])


def test_deriva_cero_costo_igual_a_comprar_hoy(tmp_path):
    c = conjunto(tmp_path, g=(0.0, 0.0, 0.0))
    plan = PlanCompra.escalonado(10000, 12)
    for n in ESCENARIOS:
        r = correr(plan, 3316.7, c, n)
        assert r.costo_cop == pytest.approx(10000 * 3316.7)


def test_orden_de_escenarios_en_costo(tmp_path):
    c = conjunto(tmp_path)
    r = correr_todos(PlanCompra.escalonado(10000, 12), 3316.7, c)
    assert r["optimista"].costo_cop < r["base"].costo_cop < r["estres"].costo_cop


def test_comprar_hoy_no_depende_del_escenario(tmp_path):
    c = conjunto(tmp_path)
    r = correr_todos(PlanCompra.todo_hoy(10000), 3316.7, c)
    assert all(x.costo_cop == pytest.approx(10000 * 3316.7) for x in r.values())


def test_con_deriva_positiva_escalonar_cuesta_mas_y_con_negativa_menos(tmp_path):
    c = conjunto(tmp_path)
    hoy = 10000 * 3316.7
    esc = correr_todos(PlanCompra.escalonado(10000, 12), 3316.7, c)
    assert esc["estres"].costo_cop > hoy > esc["optimista"].costo_cop


def test_validar_orden_rechaza_derivas_desordenadas(tmp_path):
    c = conjunto(tmp_path, g=(0.1, 0.0, 0.2))
    with pytest.raises(ValueError, match="fuera de orden"):
        validar_orden(c)
    with pytest.raises(ValueError):
        correr(PlanCompra.todo_hoy(1), 4000.0, c, "base")


def test_escenario_desconocido():
    with pytest.raises(ValueError):
        id_deriva("pesimista")
