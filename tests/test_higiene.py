"""M0: higiene del repositorio (instalación, número de pruebas, entorno, datos de prueba)."""
from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from conftest import PROCESADOS, SinDatos, asegurar_procesados

RAIZ = Path(__file__).resolve().parents[1]


def test_pyproject_instala_extra_dev_y_numpy():
    p = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    assert p["build-system"]["requires"] == ["setuptools>=61"]
    assert {"numpy", "scikit-learn"} <= set(p["project"]["dependencies"])
    assert {"pytest", "hypothesis"} <= set(p["project"]["optional-dependencies"]["dev"])


def test_requirements_prueba_final_coincide_con_prerregistro():
    texto = (RAIZ / "docs/prerregistro.md").read_text(encoding="utf-8")
    linea = re.search(r"^Entorno: (.+)\.$", texto, re.M).group(1)
    esperado = dict(par.split(" ") for par in linea.split(", "))
    assert esperado.pop("python") == "3.11.9"
    req = (RAIZ / "requirements-prueba-final.txt").read_text(encoding="utf-8")
    fijadas = dict(l.split("==") for l in req.splitlines() if l and not l.startswith("#"))
    assert {k: fijadas.get(k) for k in esperado} == esperado
    assert set(fijadas) - set(esperado) == {"scikit-learn"}   # exigida por lightgbm.sklearn
    assert "3.11.9" in req
    assert "requirements-prueba-final.txt" in (RAIZ / "README.md").read_text(encoding="utf-8")


def test_readme_cita_el_numero_real_de_pruebas():
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    citado = int(re.search(r"(\d+) pruebas automáticas", readme).group(1))
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                        "-p", "no:cacheprovider"], cwd=RAIZ, capture_output=True, text=True)
    real = int(re.search(r"(\d+) tests? collected", r.stdout).group(1))
    assert citado == real, f"el README dice {citado} pruebas; hay {real}"


def test_claude_md_apunta_a_archivos_que_existen():
    texto = (RAIZ / "CLAUDE.md").read_text(encoding="utf-8")
    rutas = re.findall(r"(docs/prompts/PROMPT_\w+\.md)", texto)
    assert rutas and all((RAIZ / r).exists() for r in rutas)
    assert not list(RAIZ.glob("PROMPT_*.md"))


def test_sin_raw_falla_con_mensaje_claro(tmp_path):
    with pytest.raises(SinDatos, match="data/raw no se puede regenerar"):
        asegurar_procesados(tmp_path / "raw", tmp_path / "processed")


def test_con_procesados_completos_no_reconstruye(tmp_path):
    raw, proc = tmp_path / "raw", tmp_path / "processed"
    raw.mkdir()
    (raw / "x.csv").write_text("a\n1\n")
    proc.mkdir()
    for n in PROCESADOS:
        (proc / n).write_text("")
    assert asegurar_procesados(raw, proc) == []


def test_ninguna_prueba_se_salta_por_falta_de_datos():
    patron = re.compile(r"skip.*(data/processed|data/raw|sin datos|trm\.csv|RAW\.exists)", re.S)
    for f in sorted((RAIZ / "tests").glob("test_*.py")):
        if f.name == "test_higiene.py":
            continue
        for linea in f.read_text(encoding="utf-8").splitlines():
            assert not patron.search(linea), f"{f.name}: {linea.strip()}"
