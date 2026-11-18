"""Datos de las pruebas (pendiente I7): ninguna prueba se salta en silencio por falta de datos.

Al iniciar la sesión, si falta algún archivo de `data/processed`, se reconstruye una vez desde
`data/raw` con la misma función que lo generó (`laboratorio.datos.limpieza.limpiar`, byte a byte
idéntico). Si tampoco hay `data/raw`, la sesión se detiene con un mensaje claro.
"""
from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"
PROC = RAIZ / "data" / "processed"
PROCESADOS = ("trm.csv", "ipc_mensual.csv", "uvr_diaria.csv", "tasas_diarias.csv", "dtf.csv",
              "externas_diario.csv", "limpieza.json")


class SinDatos(RuntimeError):
    """Faltan los datos crudos: las pruebas con datos reales no pueden correr."""


def asegurar_procesados(raw: Path = RAW, proc: Path = PROC) -> list[str]:
    """Devuelve los archivos que faltaban y se reconstruyeron ([] si no faltaba ninguno)."""
    if not raw.is_dir() or not any(raw.glob("*.csv")):
        raise SinDatos(
            f"No existe {raw} (o no tiene CSV). Las pruebas usan los datos reales versionados: "
            "clona el repositorio completo; data/raw no se puede regenerar.")
    faltan = [n for n in PROCESADOS if not (proc / n).exists()]
    if faltan:
        from laboratorio.datos.limpieza import limpiar
        limpiar(raw, proc)
    return faltan


def pytest_sessionstart(session):
    try:
        faltan = asegurar_procesados()
    except SinDatos as e:
        pytest.exit(str(e), returncode=4)
    if faltan:
        print(f"\ndata/processed reconstruido desde data/raw (faltaban: {', '.join(faltan)})")
