"""Carga de la TRM procesada con hash y linaje a los datos crudos."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .cifras import Cifra
from .ficha import hash_archivo


class DatosTRM:
    def __init__(self, procesado: str | Path = "data/processed", raw: str | Path = "data/raw"):
        self.procesado = Path(procesado)
        self.raw = Path(raw)
        self._ruta = self.procesado / "trm.csv"
        df = pd.read_csv(self._ruta, parse_dates=["fecha"], index_col="fecha")
        df["estres"] = df["estres"].fillna("")
        if not df.index.is_monotonic_increasing or not df.index.is_unique:
            raise ValueError("trm.csv: fechas no únicas o no ordenadas")
        if not (df["trm"] > 0).all():
            raise ValueError("trm.csv: TRM no positiva")
        self.df = df
        self.hash_trm = hash_archivo(self._ruta)

    @property
    def trm(self) -> pd.Series:
        return self.df["trm"]

    def archivos(self) -> dict[str, Path]:
        """Archivos que entran en el hash de datos: el procesado y su origen crudo."""
        out = {"processed/trm.csv": self._ruta}
        for p in sorted(self.raw.glob("trm_superfinanciera_*.csv")):
            out[f"raw/{p.name}"] = p
        return out

    def ultima(self) -> tuple[pd.Timestamp, float]:
        return self.trm.index[-1], float(self.trm.iloc[-1])

    def asof(self, fecha) -> tuple[pd.Timestamp, float]:
        """Última TRM con fecha <= `fecha` (lanza error si la fecha es anterior a la serie)."""
        f = pd.Timestamp(fecha)
        if f < self.trm.index[0]:
            raise KeyError(f"{f.date()} es anterior al inicio de la serie")
        pos = self.trm.index.searchsorted(f, side="right") - 1
        return self.trm.index[pos], float(self.trm.iloc[pos])

    def cifra(self, fecha, unidad: str = "COP/USD") -> Cifra:
        """TRM en una fecha exacta de la serie, como cifra con fuente y hash."""
        f = pd.Timestamp(fecha)
        if f not in self.trm.index:
            raise KeyError(f"{f.date()} no es una fecha de la serie")
        return Cifra.de_dato(float(self.trm[f]), unidad, "processed/trm.csv",
                             f"fecha={f.date()};columna=trm", self.hash_trm)
