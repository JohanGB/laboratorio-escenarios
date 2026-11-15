from pathlib import Path

import pandas as pd
import pytest

from laboratorio.motor.datos import DatosTRM
from laboratorio.motor.ficha import hash_archivo

RAIZ = Path(__file__).resolve().parents[1]


def csv(tmp_path, filas, nombre="trm.csv"):
    p = tmp_path / "processed"
    p.mkdir(exist_ok=True)
    texto = "fecha,trm,dias,ret_log,regimen,estres\n" + "\n".join(filas) + "\n"
    (p / nombre).write_text(texto, encoding="utf-8")
    return p


def test_asof_exacto_intermedio_y_anterior(tmp_path):
    p = csv(tmp_path, ["2024-01-02,4000,,,flotacion,", "2024-01-05,4100,3,0.02,flotacion,"])
    d = DatosTRM(p, tmp_path / "raw")
    assert d.asof("2024-01-05")[1] == 4100.0
    assert d.asof("2024-01-04") == (pd.Timestamp("2024-01-02"), 4000.0)
    assert d.asof("2030-01-01")[1] == 4100.0
    with pytest.raises(KeyError):
        d.asof("2023-12-31")


def test_cifra_lleva_hash_del_archivo_y_cambia_si_cambia_el_archivo(tmp_path):
    p = csv(tmp_path, ["2024-01-02,4000,,,flotacion,", "2024-01-05,4100,3,0.02,flotacion,"])
    d = DatosTRM(p, tmp_path / "raw")
    c = d.cifra("2024-01-05")
    assert c.valor == 4100.0 and c.origen == "dato" and "fecha=2024-01-05" in c.referencia
    assert d.hash_trm == hash_archivo(p / "trm.csv")
    with pytest.raises(KeyError):
        d.cifra("2024-01-04")
    p2 = csv(tmp_path, ["2024-01-02,4000,,,flotacion,", "2024-01-05,4100,3,0.02,flotacion,",
                        "2024-01-06,4101,1,0.0002,flotacion,"])
    assert DatosTRM(p2, tmp_path / "raw").cifra("2024-01-05").hash != c.hash


def test_valida_fechas_y_valores(tmp_path):
    with pytest.raises(ValueError, match="no únicas"):
        DatosTRM(csv(tmp_path, ["2024-01-02,4000,,,f,", "2024-01-02,4001,,,f,"]), tmp_path)
    with pytest.raises(ValueError, match="no positiva"):
        DatosTRM(csv(tmp_path, ["2024-01-02,-1,,,f,"]), tmp_path)


@pytest.mark.skipif(not (RAIZ / "data/processed/trm.csv").exists(), reason="sin datos")
def test_datos_reales_incluyen_linaje_crudo():
    d = DatosTRM(RAIZ / "data/processed", RAIZ / "data/raw")
    a = d.archivos()
    assert "processed/trm.csv" in a and any(k.startswith("raw/trm_superfinanciera") for k in a)
    f, v = d.ultima()
    assert f == pd.Timestamp("2026-11-14") and v == pytest.approx(3316.70)
