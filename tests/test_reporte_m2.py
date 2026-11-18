"""M2: reporte de la TRM del motor conjunto frente al motor evaluado (reportes/m2_conjunto.py)."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from laboratorio.motor.conjunto import ETIQUETA
from laboratorio.reportes import m2_conjunto as R

RAIZ = Path(__file__).resolve().parents[1]
NUEVAS = re.compile(r"\b(EUR|MXN|JPY|CNY|CHF|BRL)\b")
HASH = re.compile(r"`#([0-9a-f]{10})`")


@pytest.fixture(scope="module")
def md(tmp_path_factory):
    r = tmp_path_factory.mktemp("m2")
    (r / "data/processed").mkdir(parents=True)
    for n in ("divisas.csv", "trm.csv"):
        shutil.copy(RAIZ / "data/processed" / n, r / "data/processed" / n)
    return R.generar(r, trayectorias=300).read_text(encoding="utf-8")


def _cuerpo(texto: str) -> str:
    return texto.split("## Apéndice")[0]


def test_etiqueta_aviso_y_respaldo(md):
    assert ETIQUETA == "motor conjunto, sin evaluación fuera de muestra hasta M3"
    assert f"Etiqueta de todas las cifras del motor conjunto: {ETIQUETA}" in md
    assert "No es asesoría financiera" in md and "no promesas" in md
    assert "**sin evaluación fuera de muestra hasta M3**" in md


def test_cada_cifra_tiene_hash_y_esta_en_el_apendice(md):
    cuerpo, apendice = _cuerpo(md), md.split("## Apéndice")[1]
    hashes = set(HASH.findall(cuerpo))
    assert len(hashes) >= 6 * 8 + 9
    assert all(f"`#{h}`" in apendice for h in hashes)
    filas = [l for l in cuerpo.split("## 2.")[1].split("## 3.")[0].splitlines() if re.match(r"\| \d", l)]
    assert [int(l.split("|")[1]) for l in filas] == list(R.HORIZONTES)
    for l in filas:
        celdas = [x.strip() for x in l.strip("|").split("|")][1:]
        assert all(HASH.search(x) for x in celdas), l


def test_ninguna_cifra_de_divisas_nuevas(md):
    for linea in _cuerpo(md).splitlines():
        if HASH.search(linea):
            assert not NUEVAS.search(linea), linea
    assert not NUEVAS.search(md.split("## Apéndice")[1].replace("USD, EUR, MXN, JPY, CNY, CHF, BRL", ""))


def test_el_reporte_versionado_es_el_del_generador():
    texto = (RAIZ / "reports/m2_conjunto.md").read_text(encoding="utf-8")
    assert "--trayectorias 10000 --semilla 20240501" in texto
    for linea in _cuerpo(texto).splitlines():
        if HASH.search(linea):
            assert not NUEVAS.search(linea), linea
