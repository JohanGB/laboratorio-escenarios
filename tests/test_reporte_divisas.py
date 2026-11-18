"""M1: el reporte exploratorio multidivisa no muestra ni resume nada con fecha >= 2020-01-01."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from laboratorio.reportes import fase0_divisas as R

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "data" / "processed"
RAW = RAIZ / "data" / "raw"
AÑO_PROHIBIDO = re.compile(r"(?<![0-9A-Za-z])20[2-9][0-9](?![0-9A-Za-z])")


@pytest.fixture(scope="module")
def reporte(tmp_path_factory):
    sal = tmp_path_factory.mktemp("rep")
    return R.generar(PROC, RAW, sal), sal


def test_maximo_tres_figuras_y_aviso(reporte):
    md, sal = reporte
    texto = md.read_text(encoding="utf-8")
    figuras = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", texto)
    assert 1 <= len(figuras) <= 3
    assert all((sal / f).exists() for f in figuras)
    assert len(list((sal / "figs").glob("*.png"))) == len(figuras)
    assert "No es asesoría financiera" in texto
    assert "sin respaldo fuera de muestra" in texto


def test_el_reporte_no_contiene_fechas_desde_2020(reporte):
    texto = reporte[0].read_text(encoding="utf-8")
    assert not AÑO_PROHIBIDO.findall(texto), AÑO_PROHIBIDO.findall(texto)[:5]


def test_las_cifras_llevan_hash(reporte):
    texto = reporte[0].read_text(encoding="utf-8")
    assert texto.count("`#") >= 10 and "## Apéndice" in texto


def test_los_datos_del_reporte_terminan_antes_de_2020():
    d = R.cargar(PROC, RAW)
    assert d.divisas["fecha"].max() < pd.Timestamp("2020-01-01")
    assert d.trm.index.max() < pd.Timestamp("2020-01-01")
    assert all(s.index.max() < pd.Timestamp("2020-01-01") for s in d.fred.values())


def test_cambiar_datos_desde_2020_no_cambia_el_reporte(tmp_path, reporte):
    proc, raw = tmp_path / "processed", tmp_path / "raw"
    proc.mkdir(), raw.mkdir()
    for n in ("divisas.csv", "trm.csv"):
        df = pd.read_csv(PROC / n)
        num = df.select_dtypes("number").columns
        df.loc[df["fecha"] >= "2020-01-01", num] = 1.2345
        df.to_csv(proc / n, index=False)
    for f in RAW.glob("*_fred_dex*.csv"):
        lineas = f.read_text(encoding="utf-8").splitlines()
        nuevas = [l if l[:4] < "2020" or not l[:1].isdigit() else l.split(",")[0] + ",9.99" for l in lineas]
        (raw / f.name).write_text("\n".join(nuevas) + "\n", encoding="utf-8")
    otro = R.generar(proc, raw, tmp_path / "rep")
    assert otro.read_text(encoding="utf-8") == reporte[0].read_text(encoding="utf-8")
