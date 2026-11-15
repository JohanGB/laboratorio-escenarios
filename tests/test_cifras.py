import re

import pytest

from laboratorio.motor.cifras import Cifra, CifraError, Reporte, formatear
from laboratorio.motor.supuestos import Registro

H = "ab" * 32


@pytest.fixture
def sup(tmp_path):
    r = Registro(tmp_path / "r.jsonl")
    s = r.agregar("meta_usd", 10000, "USD", "prueba", "j", "analista", "2026-01-01")
    return r, s


def test_cifra_de_dato_requiere_origen_completo():
    c = Cifra.de_dato(3316.7, "COP/USD", "trm.csv", "2026-11-14", H)
    assert c.origen == "dato" and c.referencia == "trm.csv#2026-11-14" and len(c.hash) == 64
    with pytest.raises(CifraError):
        Cifra.de_dato(1.0, "COP", "", "x", H)
    with pytest.raises(CifraError):
        Cifra.de_dato(1.0, "COP", "a", "x", "")


def test_hash_de_dato_cambia_con_valor_ubicacion_o_archivo():
    base = Cifra.de_dato(1.0, "COP", "a.csv", "f1", H)
    assert Cifra.de_dato(1.0, "COP", "a.csv", "f1", H).hash == base.hash
    assert Cifra.de_dato(1.1, "COP", "a.csv", "f1", H).hash != base.hash
    assert Cifra.de_dato(1.0, "COP", "a.csv", "f2", H).hash != base.hash
    assert Cifra.de_dato(1.0, "COP", "a.csv", "f1", "cd" * 32).hash != base.hash


def test_cifra_de_supuesto_usa_el_hash_del_registro(sup):
    _, s = sup
    c = Cifra.de_supuesto(s)
    assert c.hash == s.hash and c.referencia == "meta_usd@v1" and c.valor == 10000


def test_derivada_hereda_hashes_y_cambia_si_cambia_un_insumo(sup):
    _, s = sup
    a = Cifra.de_supuesto(s)
    t1 = Cifra.de_dato(4000.0, "COP/USD", "trm.csv", "f", H)
    t2 = Cifra.de_dato(4000.0, "COP/USD", "trm.csv", "f", "cd" * 32)  # otro archivo, mismo valor
    d1 = Cifra.derivada(4e7, "COP", "meta_usd × TRM_hoy", [a, t1])
    d2 = Cifra.derivada(4e7, "COP", "meta_usd × TRM_hoy", [a, t2])
    assert d1.hash != d2.hash
    assert d1.hash == Cifra.derivada(4e7, "COP", "meta_usd × TRM_hoy", [a, t1]).hash
    assert Cifra.derivada(4e7, "COP", "otra fórmula", [a, t1]).hash != d1.hash
    with pytest.raises(CifraError):
        Cifra.derivada(1.0, "COP", "x", [])
    with pytest.raises(CifraError):
        Cifra.derivada(1.0, "COP", " ", [a])


def test_hojas_recorre_el_linaje_sin_repetir(sup):
    _, s = sup
    a = Cifra.de_supuesto(s)
    t = Cifra.de_dato(4000.0, "COP/USD", "trm.csv", "f", H)
    d1 = Cifra.derivada(1.0, "COP", "f1", [a, t])
    d2 = Cifra.derivada(2.0, "COP", "f2", [d1, a, t])
    assert {h.hash for h in d2.hojas()} == {a.hash, t.hash} and len(d2.hojas()) == 2


def test_formato_es_co():
    assert formatear(3316.7) == "3.316,70"
    assert formatear(1234567.891, 0) == "1.234.568"
    assert formatear(0.0525, 4) == "0,0525"
    assert formatear(10000, 0) == "10.000"


def test_reporte_toda_cifra_mostrada_aparece_en_el_apendice(sup):
    _, s = sup
    rep = Reporte()
    a = Cifra.de_supuesto(s)
    t = Cifra.de_dato(3316.7, "COP/USD", "trm.csv", "2026-11-14", H)
    d = Cifra.derivada(a.valor * t.valor, "COP", "meta_usd × TRM_hoy", [a, t])
    texto = " ".join([rep.r(a, 0), rep.r(t), rep.r(d, 0)])
    usados = set(re.findall(r"`#([0-9a-f]+)`", texto))
    apendice = rep.apendice()
    assert usados == {a.corto, t.corto, d.corto}
    assert all(f"`#{u}`" in apendice for u in usados)
    assert d.hash in apendice and "3.316,70 COP/USD" in texto
    assert len(rep.cifras()) == 3


def test_reporte_misma_cifra_dos_veces_una_sola_fila(sup):
    _, s = sup
    rep = Reporte()
    a = Cifra.de_supuesto(s)
    rep.r(a, 0)
    rep.r(a, 0)
    assert rep.apendice().count(a.hash) == 1
