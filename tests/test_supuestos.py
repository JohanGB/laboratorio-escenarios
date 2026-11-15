import pytest

from laboratorio.motor.supuestos import GENESIS, Registro, RegistroError

BASE = dict(unidad="%", fuente="prueba", justificacion="porque sí", autor="analista",
            fecha="2026-01-01")


@pytest.fixture
def reg(tmp_path):
    return Registro(tmp_path / "registro.jsonl")


def test_agregar_crea_version_1_y_encadena(reg):
    s1 = reg.agregar("a", 1.0, **BASE)
    s2 = reg.agregar("b", 2.0, **BASE)
    assert s1.version == 1 and s1.hash_prev == GENESIS and s2.hash_prev == s1.hash
    reg.verificar()


def test_solo_agregar_lineas_existentes_no_cambian(reg):
    reg.agregar("a", 1.0, **BASE)
    antes = reg.ruta.read_bytes()
    reg.agregar("a", 2.0, **{**BASE, "fecha": "2026-02-01"})
    despues = reg.ruta.read_bytes()
    assert despues.startswith(antes) and len(despues) > len(antes)


def test_editar_crea_version_nueva_y_conserva_anteriores(reg):
    reg.agregar("a", 1.0, **BASE)
    reg.agregar("a", 2.0, **{**BASE, "fecha": "2026-02-01"})
    assert [s.version for s in reg.historial("a")] == [1, 2]
    assert reg.vigente("a").valor == 2.0
    assert reg.version("a", 1).valor == 1.0


def test_vigente_en_una_fecha(reg):
    reg.agregar("a", 1.0, **BASE)
    reg.agregar("a", 2.0, **{**BASE, "fecha": "2026-03-01"})
    assert reg.vigente("a", en="2026-02-15").valor == 1.0
    assert reg.vigente("a", en="2026-03-01").valor == 2.0
    with pytest.raises(KeyError):
        reg.vigente("a", en="2025-12-31")


def test_verificar_detecta_alteracion(reg):
    reg.agregar("a", 1.0, **BASE)
    reg.agregar("b", 2.0, **BASE)
    texto = reg.ruta.read_text(encoding="utf-8")
    reg.ruta.write_text(texto.replace('"valor":1.0', '"valor":9.0'), encoding="utf-8")
    with pytest.raises(RegistroError, match="alterado"):
        reg.verificar()
    with pytest.raises(RegistroError):
        reg.agregar("c", 3.0, **BASE)  # no se agrega sobre un registro corrupto


def test_verificar_detecta_linea_eliminada(reg):
    for i, v in enumerate((1.0, 2.0, 3.0)):
        reg.agregar(f"s{i}", v, **BASE)
    lineas = reg.ruta.read_text(encoding="utf-8").splitlines()
    reg.ruta.write_text("\n".join([lineas[0], lineas[2]]) + "\n", encoding="utf-8")
    with pytest.raises(RegistroError, match="cadena"):
        reg.verificar()


@pytest.mark.parametrize("campo", ["unidad", "fuente", "justificacion", "autor"])
def test_campos_obligatorios(reg, campo):
    with pytest.raises(RegistroError, match=campo):
        reg.agregar("a", 1.0, **{**BASE, campo: "  "})


def test_rechaza_id_invalido_valor_invalido_y_sin_cambios(reg):
    with pytest.raises(RegistroError):
        reg.agregar("A b", 1.0, **BASE)
    with pytest.raises(RegistroError):
        reg.agregar("a", float("nan"), **BASE)
    with pytest.raises(RegistroError):
        reg.agregar("a", True, **BASE)
    reg.agregar("a", 1.0, **BASE)
    with pytest.raises(RegistroError, match="sin cambios"):
        reg.agregar("a", 1.0, **BASE)
    assert len(reg.historial("a")) == 1


def test_hash_del_conjunto_independiente_del_orden_y_sensible_a_versiones(reg):
    reg.agregar("a", 1.0, **BASE)
    reg.agregar("b", 2.0, **BASE)
    c1 = reg.conjunto({"a": 1, "b": 1})
    c2 = reg.conjunto({"b": 1, "a": 1})
    assert c1.hash == c2.hash and c1.valor("b") == 2.0
    reg.agregar("a", 5.0, **{**BASE, "fecha": "2026-02-01"})
    assert reg.conjunto({"a": 2, "b": 1}).hash != c1.hash
    assert reg.conjunto({"a": 1, "b": 1}).hash == c1.hash  # versiones fijadas no cambian


def test_mismo_contenido_mismo_hash_en_registros_distintos(tmp_path):
    r1, r2 = Registro(tmp_path / "1.jsonl"), Registro(tmp_path / "2.jsonl")
    assert r1.agregar("a", 1.0, **BASE).hash == r2.agregar("a", 1.0, **BASE).hash


def test_registro_inexistente_esta_vacio(tmp_path):
    r = Registro(tmp_path / "no_existe.jsonl")
    assert r.ids() == [] and r.verificar() is None
