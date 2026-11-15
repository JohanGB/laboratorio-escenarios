"""Cobertura y calibración de cuantiles e intervalos (independiente del dominio)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from .perdidas import _como_arrays


def _wilson(k: float, n: float, z: float = 1.959964) -> tuple[float, float]:
    if n <= 0:
        return (np.nan, np.nan)
    p = k / n
    den = 1 + z**2 / n
    centro = (p + z**2 / (2 * n)) / den
    mitad = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return (centro - mitad, centro + mitad)


def cobertura_intervalo(y, inferior, superior) -> float:
    """Fracción de observaciones dentro de [inferior, superior] (extremos incluidos)."""
    y = np.asarray(y, dtype=float)
    lo, hi = np.asarray(inferior, dtype=float), np.asarray(superior, dtype=float)
    if len(y) == 0:
        raise ValueError("sin observaciones")
    return float(np.mean((y >= lo) & (y <= hi)))


def calibracion(y, q, niveles, n_efectivo: float | None = None) -> pd.DataFrame:
    """Frecuencia observada de y ≤ q_τ contra el nivel nominal τ.

    Columnas: nivel, observado, error (obs − nominal), n, ic_inf, ic_sup (Wilson 95 %) y
    p_binomial (prueba exacta bilateral de H0: P(y ≤ q) = τ). Si las observaciones se
    traslapan (horizonte > 1), pase `n_efectivo` (≈ n / h) para no subestimar la incertidumbre;
    el intervalo y el p-valor usan ese tamaño efectivo.
    """
    y, q, t = _como_arrays(y, q, niveles)
    n = len(y)
    if n == 0:
        raise ValueError("sin observaciones")
    ne = float(n_efectivo) if n_efectivo is not None else float(n)
    filas = []
    for j, tau in enumerate(t):
        p = float(np.mean(y <= q[:, j]))
        lo, hi = _wilson(p * ne, ne)
        pv = float(stats.binomtest(int(round(p * ne)), int(round(ne)), tau).pvalue)
        filas.append((tau, p, p - tau, n, lo, hi, pv))
    return pd.DataFrame(filas, columns=["nivel", "observado", "error", "n", "ic_inf", "ic_sup",
                                        "p_binomial"])


def cobertura_intervalos(y, q, niveles, pares=((0.25, 0.75), (0.10, 0.90), (0.05, 0.95),
                                                (0.025, 0.975), (0.01, 0.99))) -> pd.DataFrame:
    """Cobertura real de intervalos centrales formados por pares de niveles presentes en `niveles`."""
    y, q, t = _como_arrays(y, q, niveles)
    filas = []
    for a, b in pares:
        ia, ib = np.flatnonzero(np.isclose(t, a)), np.flatnonzero(np.isclose(t, b))
        if len(ia) == 0 or len(ib) == 0:
            continue
        filas.append((a, b, b - a, cobertura_intervalo(y, q[:, ia[0]], q[:, ib[0]]),
                      float(np.mean(q[:, ib[0]] - q[:, ia[0]]))))
    return pd.DataFrame(filas, columns=["nivel_inf", "nivel_sup", "nominal", "observado",
                                        "ancho_medio"])
