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


def _sin_cifras_de_divisas_nuevas_desde_2020(texto: str) -> None:
    """Fuera de la sección 4 ninguna línea con cifra nombra una divisa nueva; la sección 4 y cada
    fila del apéndice que nombra una solo usan datos hasta CORTE_CORR (2019-12-31)."""
    cuerpo = _cuerpo(texto)
    sec4 = cuerpo.split("## 4.")[1].split("## 5.")[0]
    assert f"datos hasta el {R.CORTE_CORR}" in sec4
    for linea in cuerpo.replace(sec4, "").splitlines():
        if HASH.search(linea):
            assert not NUEVAS.search(linea), linea
    for linea in texto.split("## Apéndice")[1].splitlines():
        if NUEVAS.search(linea.replace("USD, EUR, MXN, JPY, CNY, CHF, BRL", "")):
            assert f"datos hasta {R.CORTE_CORR}" in linea, linea


def test_ninguna_cifra_de_divisas_nuevas_desde_2020(md):
    _sin_cifras_de_divisas_nuevas_desde_2020(md)


def test_correlaciones_ccc_con_hash_y_limitacion(md):
    sec4 = _cuerpo(md).split("## 4.")[1].split("## 5.")[0]
    filas = [l for l in sec4.splitlines() if l.startswith("| TRM y ")]
    assert len(filas) == 6 and all(len(HASH.findall(l)) == 4 for l in filas)
    assert "Bollerslev, 1990" in sec4 and "en episodios de estrés" in sec4
    assert "puede no serlo" in sec4 and "bootstrap_est` como sensibilidad" in sec4


def test_el_reporte_versionado_es_el_del_generador():
    texto = (RAIZ / "reports/m2_conjunto.md").read_text(encoding="utf-8")
    assert "--trayectorias 10000 --semilla 20240501" in texto
    _sin_cifras_de_divisas_nuevas_desde_2020(texto)
