"""Acierto direccional: prueba binomial contra 50 % y prueba de Pesaran-Timmermann (1992).

Diagnóstico, no criterio de selección. Se descartan los pares con pronóstico o realización
exactamente cero (sin dirección). Suponen observaciones sin traslape (h = 1).

Pesaran-Timmermann: con P = proporción de aciertos, P_y = P(y > 0), P_x = P(pronóstico > 0),
  P* = P_y·P_x + (1 − P_y)(1 − P_x)                       (aciertos esperados si son independientes)
  var(P)  = P*(1 − P*)/n
  var(P*) = [(2P_y − 1)²·P_x(1 − P_x) + (2P_x − 1)²·P_y(1 − P_y) + 4·P_y·P_x(1 − P_y)(1 − P_x)/n]/n
  S = (P − P*)/√(var(P) − var(P*)) ~ N(0, 1);  p unilateral (H1: más aciertos que por azar).
A diferencia de la binomial, descuenta el acierto que se logra solo por predecir siempre el signo
más frecuente.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

from .pruebas import Resultado


def _pares(pronostico, y):
    x, y = np.asarray(pronostico, float), np.asarray(y, float)
    if x.shape != y.shape or x.ndim != 1:
        raise ValueError("pronóstico y realización con forma distinta")
    ok = (x != 0) & (y != 0) & np.isfinite(x) & np.isfinite(y)
    return x[ok] > 0, y[ok] > 0


def acierto_binomial(pronostico, y) -> Resultado:
    """H0: P(acierto) = 0,5; p-valor exacto bilateral."""
    x, s = _pares(pronostico, y)
    n = len(x)
    if n == 0:
        return Resultado(float("nan"), float("nan"), {"n": 0, "aplica": False})
    k = int((x == s).sum())
    return Resultado(k / n, float(stats.binomtest(k, n, 0.5).pvalue),
                     {"n": n, "aciertos": k, "aplica": True})


def pesaran_timmermann(pronostico, y) -> Resultado:
    x, s = _pares(pronostico, y)
    n = len(x)
    if n == 0:
        return Resultado(float("nan"), float("nan"), {"n": 0, "aplica": False})
    P, Py, Px = float((x == s).mean()), float(s.mean()), float(x.mean())
    Pe = Py * Px + (1 - Py) * (1 - Px)
    vP = Pe * (1 - Pe) / n
    vPe = ((2 * Py - 1) ** 2 * Px * (1 - Px) + (2 * Px - 1) ** 2 * Py * (1 - Py)
           + 4 * Py * Px * (1 - Py) * (1 - Px) / n) / n
    det = {"n": n, "P": P, "P_esperado": Pe, "P_y": Py, "P_x": Px}
    if vP - vPe <= 0:                       # pronóstico de un solo signo: no hay nada que probar
        return Resultado(float("nan"), float("nan"), {**det, "aplica": False})
    S = (P - Pe) / np.sqrt(vP - vPe)
    return Resultado(float(S), float(stats.norm.sf(S)), {**det, "aplica": True})
