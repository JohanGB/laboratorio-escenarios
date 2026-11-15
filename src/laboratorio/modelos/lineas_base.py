"""Líneas base: caminata aleatoria, simulación histórica (ventana fija / ponderada) y EWMA.

Todas usan solo `vista.r` / `vista.logp` hasta el origen (sin parámetros ajustados:
`ajustar` no hace nada), así que cumplen el contrato anti-fuga por construcción.
Salida: cuantiles del rendimiento logarítmico acumulado a h pasos.
"""
from __future__ import annotations

import numpy as np
from scipy import stats
from scipy.signal import lfilter

from .base import Pronosticador

MIN_OBS = 30


def cuantil_ponderado(x: np.ndarray, w: np.ndarray, niveles: np.ndarray) -> np.ndarray:
    """Cuantiles ponderados con interpolación (posición = suma acumulada − w/2, normalizada)."""
    o = np.argsort(x, kind="stable")
    x, w = x[o], w[o]
    pos = (np.cumsum(w) - 0.5 * w) / w.sum()
    return np.interp(niveles, pos, x)


def varianza_ewma(r: np.ndarray, lam: float, calentamiento: int = 25) -> np.ndarray:
    """s2[t] = varianza prevista para t+1 con información hasta t (r[0] es NaN y se ignora).

    s2[t] = lam·s2[t−1] + (1−lam)·r[t]²; arranque = varianza de las primeras `calentamiento` obs.
    Recursión causal: s2[t] solo depende de r[1..t].
    """
    x = np.nan_to_num(r[1:], nan=0.0)
    s0 = float(np.var(x[:calentamiento])) if len(x) >= calentamiento else float(np.var(x))
    # lfilter: y[n] = (1-lam)·x²[n] + lam·y[n−1], con condición inicial zi = lam·s0
    y, _ = lfilter([1 - lam], [1, -lam], x**2, zi=[lam * s0])
    return np.concatenate([[s0], y])


class CaminataAleatoria(Pronosticador):
    """Mediana cero y normal con desvío histórico expansivo: σ_h = σ_diario·√h."""
    nombre = "caminata_aleatoria"

    def pronosticar(self, vista, origenes, niveles):
        z = stats.norm.ppf(niveles)
        r = vista.r
        cum = np.cumsum(np.nan_to_num(r)); cum2 = np.cumsum(np.nan_to_num(r) ** 2)
        out = {h: np.empty((len(origenes), len(niveles))) for h in self.horizontes}
        for i, o in enumerate(origenes):
            n = o                                   # observaciones r[1..o]
            if n < MIN_OBS:
                raise ValueError("historia insuficiente")
            var = cum2[o] / n - (cum[o] / n) ** 2
            for h in self.horizontes:
                out[h][i] = np.sqrt(var * h) * z
        return out


class SimulacionHistorica(Pronosticador):
    """Cuantiles empíricos de los rendimientos a h pasos ya observados (s+h ≤ o).

    ventana: número de observaciones más recientes (None = todo el historial).
    lam: si se da, pondera exponencialmente por antigüedad (lam por observación).
    """

    def __init__(self, ventana: int | None = 756, lam: float | None = None, horizontes=None):
        super().__init__(*(() if horizontes is None else (horizontes,)))
        self.ventana, self.lam = ventana, lam
        self.nombre = ("sim_hist_pond" if lam else
                       f"sim_hist_{ventana}" if ventana else "sim_hist_todo")

    def parametros(self):
        return {"ventana": self.ventana, "lam": self.lam}

    def pronosticar(self, vista, origenes, niveles):
        logp = vista.logp
        out = {h: np.empty((len(origenes), len(niveles))) for h in self.horizontes}
        for i, o in enumerate(origenes):
            for h in self.horizontes:
                fin = np.arange(h, o + 1)           # índices de llegada s+h ≤ o
                if self.ventana:
                    fin = fin[-self.ventana:]
                if len(fin) < MIN_OBS:
                    raise ValueError("historia insuficiente")
                x = logp[fin] - logp[fin - h]
                w = (self.lam ** (o - fin)) if self.lam else np.ones(len(fin))
                out[h][i] = cuantil_ponderado(x, w, niveles)
        return out


class EWMA(Pronosticador):
    """RiskMetrics: σ²_{t+1} por EWMA (λ=0,94), normal, σ_h² = h·σ²_{t+1}, mediana cero."""

    def __init__(self, lam: float = 0.94, horizontes=None):
        super().__init__(*(() if horizontes is None else (horizontes,)))
        self.lam = lam
        self.nombre = f"ewma_{lam:g}"

    def parametros(self):
        return {"lam": self.lam}

    def pronosticar(self, vista, origenes, niveles):
        z = stats.norm.ppf(niveles)
        s2 = varianza_ewma(vista.r, self.lam)
        return {h: np.sqrt(h * s2[np.asarray(origenes)])[:, None] * z[None, :]
                for h in self.horizontes}
