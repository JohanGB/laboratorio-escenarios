import re
from pathlib import Path

from laboratorio.reportes.fase0 import generar

PROC = Path(__file__).resolve().parents[1] / "data" / "processed"


def test_reporte_fase0_se_genera_con_max_3_graficas(tmp_path):
    md = generar(PROC, tmp_path)
    texto = md.read_text(encoding="utf-8")
    figs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", texto)
    assert 1 <= len(figs) <= 3
    assert all((tmp_path / f).exists() for f in figs)
    assert "nan" not in texto.lower().replace("financ", "")  # sin valores NaN en tablas
    for palabra in ("Banda", "Crisis 2008", "Petróleo 2014", "Covid 2020", "Estrés 2022"):
        assert palabra in texto
