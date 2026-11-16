"""Monte Carlo del caso (F5): trayectorias de la TRM con el motor evaluado en la prueba final.

No reescribe el bootstrap. `simular` instancia `BootstrapEstacionario` (modelos/bootstrap.py),
usa su `ajustar` (longitud media de bloque de Politis-White; en la variante filtrada, σ̄² y ρ) y
su función `trayectorias`, con el mismo generador por origen `default_rng([semilla, origen])`.
Con los mismos `sims`, `semilla` y largo, los cuantiles de estas trayectorias son idénticos a los
de `pronosticar` (hay prueba): lo que se simula aquí es lo que se evaluó.

Motores (fijados en el prerregistro, backtest/final.py):
- `bootstrap_est_filtrado`: motor del caso en todos los horizontes.
- `bootstrap_est`: análisis de sensibilidad.
Los dos remuestrean TODA la historia de la serie (banda incluida), como en la evaluación.

El origen es la última observación de la vista. La fila k de `acum` es el rendimiento
logarítmico acumulado a k+1 pasos (un paso = una observación de la serie, un día con TRM).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from ..backtest.datos import Vista, construir_vista
from ..backtest.final import MOTOR_CASO, MOTOR_SENSIBILIDAD
from ..modelos.bootstrap import BootstrapEstacionario, _sigma2_ewma, trayectorias
from .plan import PlanCompra

SEMILLA = 20240501
TRAYECTORIAS = 10_000
LARGO_MIN = 252                                   # el abanico llega al último horizonte evaluado
NIVELES_ABANICO = (0.025, 0.25, 0.5, 0.75, 0.975)  # 0,025-0,975 = el intervalo del 95 % evaluado
FILTRADO = {MOTOR_CASO: True, MOTOR_SENSIBILIDAD: False}


@dataclass(frozen=True)
class Simulacion:
    motor: str
    acum: np.ndarray               # (largo, sims) rendimiento logarítmico acumulado
    bloque: float                  # longitud media de bloque usada
    rho: float | None              # persistencia diaria de la varianza (solo filtrado)
    sigma_origen: float | None     # desvío diario previsto en el origen (solo filtrado)
    sigma_largo: float | None      # desvío diario de largo plazo (solo filtrado)
    origen: int
    semilla: int

    @property
    def sims(self) -> int:
        return self.acum.shape[1]


def vista_trm(df: pd.DataFrame) -> Vista:
    """Vista del backtest a partir de trm.csv (columnas trm, regimen, estres); sin series externas."""
    return construir_vista(df, pd.DataFrame(index=df.index[:0]))


def simular(vista: Vista, motor: str = MOTOR_CASO, sims: int = TRAYECTORIAS, semilla: int = SEMILLA,
            largo: int = LARGO_MIN, bloque: float | None = None) -> Simulacion:
    """`sims` trayectorias de `largo` pasos desde la última observación de `vista`.

    `bloque` fija la longitud media de bloque (None = Politis-White); con bloque = 1 se obtiene
    el bootstrap simple (sorteos independientes).
    """
    if motor not in FILTRADO:
        raise ValueError(f"motor desconocido: {motor!r} (use {tuple(FILTRADO)})")
    if sims < 1 or largo < 1:
        raise ValueError("sims y largo deben ser >= 1")
    filtrado = FILTRADO[motor]
    m = BootstrapEstacionario(filtrado=filtrado, sims=sims, semilla=semilla, bloque=bloque,
                              horizontes=(largo,))
    m.ajustar(vista)
    o = vista.n - 1
    x = m._serie(vista.r[: o + 1])                           # igual que en `pronosticar`
    rng = np.random.default_rng([semilla, o])
    s2o = float(_sigma2_ewma(vista.r)[o]) if filtrado else None
    esc = m.escala(s2o, largo) if filtrado else None
    acum = trayectorias(x, largo, sims, m.bloque, rng, esc)
    return Simulacion(motor, acum, float(m.bloque), m.rho,
                      float(np.sqrt(s2o)) if filtrado else None,
                      float(np.sqrt(m.sigma2_largo)) if filtrado else None, o, semilla)


def costos(plan: PlanCompra, trm0: float, acum: np.ndarray, pasos: Sequence[int]) -> np.ndarray:
    """Costo en COP del plan en cada trayectoria; la compra i se paga `pasos[i]` pasos después de hoy.

    Paso 0 = hoy (TRM cierta). TRM(k) = trm0·exp(acum[k−1]).
    """
    if not trm0 > 0:
        raise ValueError("trm0 debe ser positiva")
    if len(pasos) != len(plan.meses):
        raise ValueError("se requiere un paso por cada compra")
    if any(k < 0 or k > acum.shape[0] for k in pasos):
        raise ValueError("pasos fuera del largo simulado")
    total = np.zeros(acum.shape[1])
    for usd, k in zip(plan.usd, pasos):
        total += usd * trm0 * (np.exp(acum[k - 1]) if k > 0 else 1.0)
    return total


def bandas(acum: np.ndarray, trm0: float, niveles: Sequence[float] = NIVELES_ABANICO) -> np.ndarray:
    """Cuantiles de la TRM por paso: matriz (largo + 1, niveles); la fila 0 es hoy (trm0)."""
    q = np.quantile(acum, np.asarray(niveles, float), axis=1).T
    return trm0 * np.exp(np.vstack([np.zeros((1, q.shape[1])), q]))


def figura_abanico(trm: np.ndarray, niveles: Sequence[float], pasos: Sequence[int],
                   ruta: str | Path, titulo: str) -> Path:
    """Abanico de la TRM (matplotlib por defecto): mediana, banda central y banda del 95 %."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    trm = np.asarray(trm, float)
    niv = [float(n) for n in niveles]
    i = {n: niv.index(n) for n in NIVELES_ABANICO}
    k = np.arange(len(trm))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.fill_between(k, trm[:, i[0.025]], trm[:, i[0.975]], alpha=0.25, label="Percentiles 2,5 a 97,5")
    ax.fill_between(k, trm[:, i[0.25]], trm[:, i[0.75]], alpha=0.45, label="Percentiles 25 a 75")
    ax.plot(k, trm[:, i[0.5]], label="Mediana")
    for j, p in enumerate(p for p in pasos if p > 0):
        ax.axvline(p, linestyle=":", linewidth=0.8, label="Compras del plan" if j == 0 else None)
    ax.set_xlabel("Días con TRM desde hoy")
    ax.set_ylabel("TRM (COP/USD)")
    ax.set_title(titulo)
    ax.legend(loc="upper left")
    fig.tight_layout()
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=120)
    plt.close(fig)
    return ruta
