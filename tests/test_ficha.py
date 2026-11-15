import numpy as np
import pytest

from laboratorio.motor.ficha import (EntradaCambio, calcular_hash_entrada, cargar,
                                     construir_ficha, guardar, hash_codigo, hash_datos,
                                     hash_resultado, normalizar, reproducir)
from laboratorio.motor.supuestos import Registro

BASE = dict(unidad="%", fuente="prueba", justificacion="j", autor="analista", fecha="2026-01-01")


@pytest.fixture
def entorno(tmp_path):
    (tmp_path / "datos").mkdir()
    (tmp_path / "datos" / "trm.csv").write_text("fecha,trm\n2026-01-01,4000\n", encoding="utf-8")
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.py").write_text("x = 1\n", encoding="utf-8")
    reg = Registro(tmp_path / "reg.jsonl")
    reg.agregar("g", 0.05, **BASE)
    return dict(tmp=tmp_path, datos={"trm.csv": tmp_path / "datos" / "trm.csv"}, src=src, reg=reg,
                sup=reg.conjunto({"g": 1}))


def ejecutar(ficha):
    rng = np.random.default_rng(ficha.semilla)
    return {"x": rng.normal(size=3), "n": ficha.parametros["n"]}


def hacer(e, semilla=7, n=3, datos=None):
    res = ejecutar(type("F", (), {"semilla": semilla, "parametros": {"n": n}}))
    return construir_ficha("caso", datos or e["datos"], e["sup"], semilla, {"n": n}, res, e["src"]), res


def test_misma_entrada_mismos_hashes_aunque_cambie_la_fecha(entorno):
    f1, _ = hacer(entorno)
    f2, _ = hacer(entorno)
    assert f1.hash_entrada == f2.hash_entrada
    assert f1.hash_resultado == f2.hash_resultado and f1.hash_ficha == f2.hash_ficha
    assert f1.run_id == f1.hash_entrada[:12]


def test_cambiar_cualquier_entrada_cambia_hash_entrada(entorno):
    base, _ = hacer(entorno)
    assert hacer(entorno, semilla=8)[0].hash_entrada != base.hash_entrada
    assert hacer(entorno, n=4)[0].hash_entrada != base.hash_entrada
    entorno["datos"]["trm.csv"].write_text("fecha,trm\n2026-01-01,4001\n", encoding="utf-8")
    assert hacer(entorno)[0].hash_entrada != base.hash_entrada
    entorno["datos"]["trm.csv"].write_text("fecha,trm\n2026-01-01,4000\n", encoding="utf-8")
    assert hacer(entorno)[0].hash_entrada == base.hash_entrada
    (entorno["src"] / "a.py").write_text("x = 2\n", encoding="utf-8")
    assert hacer(entorno)[0].hash_entrada != base.hash_entrada
    (entorno["src"] / "a.py").write_text("x = 1\n", encoding="utf-8")
    entorno["reg"].agregar("g", 0.06, **{**BASE, "fecha": "2026-02-01"})
    nuevo = entorno["reg"].conjunto({"g": 2})
    f = construir_ficha("caso", entorno["datos"], nuevo, 7, {"n": 3}, {}, entorno["src"])
    assert f.hash_entrada != base.hash_entrada and f.hash_supuestos != base.hash_supuestos


def test_hash_codigo_ignora_crlf_pycache_y_no_py(entorno):
    h = hash_codigo(entorno["src"])
    (entorno["src"] / "a.py").write_bytes(b"x = 1\r\n")
    (entorno["src"] / "__pycache__").mkdir()
    (entorno["src"] / "__pycache__" / "b.py").write_text("basura")
    (entorno["src"] / "notas.txt").write_text("hola")
    assert hash_codigo(entorno["src"]) == h


def test_resultado_numpy_y_orden_de_claves_no_cambian_el_hash():
    a = {"x": np.array([1.0, 2.0]), "y": np.float64(3.5), "z": 1}
    b = {"z": 1, "y": 3.5, "x": [1.0, 2.0]}
    assert hash_resultado(a) == hash_resultado(b)
    assert hash_resultado({"x": 1.0}) != hash_resultado({"x": 1.0000001})
    assert normalizar(float("nan")) == "NaN"
    with pytest.raises(TypeError):
        normalizar(object())


def test_guardar_y_cargar_ida_y_vuelta(entorno, tmp_path):
    f, res = hacer(entorno)
    ruta = guardar(f, res, tmp_path / "runs")
    assert ruta.parent.name == f.run_id
    g = cargar(ruta)
    assert g == f and (ruta.parent / "resultado.json").exists()


def test_reproducir_coincide_y_detecta_cambios_de_entrada(entorno):
    f, _ = hacer(entorno)
    ok, nuevo = reproducir(f, ejecutar, entorno["datos"], entorno["sup"], entorno["src"])
    assert ok and nuevo == f.hash_resultado
    entorno["datos"]["trm.csv"].write_text("otro", encoding="utf-8")
    with pytest.raises(EntradaCambio, match="datos"):
        reproducir(f, ejecutar, entorno["datos"], entorno["sup"], entorno["src"])


def test_reproducir_detecta_resultado_no_determinista(entorno):
    f, _ = hacer(entorno)
    ok, _ = reproducir(f, lambda ficha: {"x": np.random.default_rng().normal(size=3), "n": 3},
                       entorno["datos"], entorno["sup"], entorno["src"])
    assert ok is False


def test_hash_datos_independiente_del_orden(entorno):
    p = entorno["datos"]["trm.csv"]
    assert hash_datos({"a": p, "b": p})[0] == hash_datos({"b": p, "a": p})[0]


def test_calcular_hash_entrada_es_funcion_pura():
    a = calcular_hash_entrada("c", "d", "s", "k", 1, {"n": 1})
    assert a == calcular_hash_entrada("c", "d", "s", "k", 1, {"n": 1})
    assert a != calcular_hash_entrada("c", "d", "s", "k", None, {"n": 1})
