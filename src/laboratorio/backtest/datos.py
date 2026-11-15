"""Datos del backtesting: una `Vista` temporal que impide mirar al futuro por construcción.

- `cargar_desarrollo` carga SOLO filas con fecha < INICIO_PRUEBA_FINAL: la prueba final no
  existe en memoria durante el desarrollo.
- `Vista.hasta(t)` devuelve una copia recortada al índice t (los modelos reciben siempre una
  vista hasta el origen, nunca el arreglo completo).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .particion import INICIO_PRUEBA_FINAL

COLUMNAS_EXTERNAS = {"brent_usd": "externas_diario", "dolar_amplio": "externas_diario",
                     "fed_funds": "externas_diario", "politica": "tasas_diarias"}


@dataclass(frozen=True)
class Vista:
    fechas: pd.DatetimeIndex
    logp: np.ndarray                 # ln(TRM)
    r: np.ndarray                    # rendimiento logarítmico por observación; r[0] = NaN
    banda: np.ndarray                # bool: régimen de banda (conocido en tiempo real)
    estres: np.ndarray               # etiqueta de estrés: SOLO para estratificar resultados
    externas: pd.DataFrame           # series externas indexadas por su propia fecha

    @property
    def n(self) -> int:
        return len(self.fechas)

    def hasta(self, t: int) -> "Vista":
        if not 0 <= t < self.n:
            raise IndexError(f"t={t} fuera de 0..{self.n - 1}")
        k = t + 1
        return Vista(self.fechas[:k], self.logp[:k], self.r[:k], self.banda[:k], self.estres[:k],
                     self.externas.loc[: self.fechas[t]])

    def objetivo(self, h: int) -> np.ndarray:
        """Rendimiento logarítmico acumulado a h pasos: ln TRM(t+h) − ln TRM(t); NaN si no existe."""
        y = np.full(self.n, np.nan)
        if h < self.n:
            y[: self.n - h] = self.logp[h:] - self.logp[: self.n - h]
        return y


def construir_vista(trm: pd.DataFrame, externas: pd.DataFrame) -> Vista:
    logp = np.log(trm["trm"].to_numpy())
    r = np.concatenate([[np.nan], np.diff(logp)])
    return Vista(trm.index, logp, r, (trm["regimen"].to_numpy() == "banda"),
                 trm["estres"].fillna("").to_numpy(), externas)


def cargar_desarrollo(raiz: str | Path = ".", corte: str = INICIO_PRUEBA_FINAL) -> Vista:
    proc = Path(raiz) / "data" / "processed"
    c = pd.Timestamp(corte)
    trm = pd.read_csv(proc / "trm.csv", parse_dates=["fecha"], index_col="fecha")
    trm = trm[trm.index < c]
    ext = pd.read_csv(proc / "externas_diario.csv", parse_dates=["fecha"], index_col="fecha")
    tas = pd.read_csv(proc / "tasas_diarias.csv", parse_dates=["fecha"], index_col="fecha")
    externas = pd.concat([ext[["brent_usd", "dolar_amplio", "fed_funds"]], tas[["politica"]]],
                         axis=1, sort=True)
    externas = externas[externas.index < c]
    if trm.index.max() >= c or externas.index.max() >= c:
        raise RuntimeError("fuga: datos posteriores al corte de la prueba final")
    return construir_vista(trm, externas)
