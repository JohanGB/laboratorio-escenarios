"""Pérdidas y puntajes para pronósticos probabilísticos.

Convención: `y` tiene forma (n,); `q` son cuantiles pronosticados con forma (n, k) para los
niveles `niveles` (k,), estrictamente crecientes en (0, 1). Menor pérdida = mejor.
Este módulo no conoce ningún dominio (ni finanzas ni fútbol).
"""
from __future__ import annotations

import numpy as np


def _como_arrays(y, q, niveles):
    y = np.asarray(y, dtype=float)
    q = np.asarray(q, dtype=float)
    t = np.asarray(niveles, dtype=float)
    if y.ndim != 1 or q.ndim != 2 or t.ndim != 1:
        raise ValueError("y debe ser (n,), q (n, k) y niveles (k,)")
    if q.shape != (len(y), len(t)):
        raise ValueError(f"q tiene forma {q.shape}; se esperaba {(len(y), len(t))}")
    if len(t) < 1 or np.any(t <= 0) or np.any(t >= 1) or np.any(np.diff(t) <= 0):
        raise ValueError("niveles deben ser estrictamente crecientes en (0, 1)")
    return y, q, t


def verificar_cuantiles(q, niveles, tolerancia: float = 1e-9) -> None:
    """Lanza ValueError si hay NaN/inf o cuantiles que se cruzan (no monótonos)."""
    q = np.asarray(q, dtype=float)
    if q.ndim != 2 or q.shape[1] != len(niveles):
        raise ValueError("q debe ser (n, k) con k = len(niveles)")
    if not np.all(np.isfinite(q)):
        raise ValueError("cuantiles con NaN o infinitos")
    if np.any(np.diff(q, axis=1) < -tolerancia):
        raise ValueError("cuantiles cruzados: no son no decrecientes en el nivel")


def reordenar(q) -> np.ndarray:
    """Reordenamiento monótono (Chernozhukov et al.): ordena cada fila; no cambia filas válidas."""
    return np.sort(np.asarray(q, dtype=float), axis=1)


def pinball(y, q, niveles) -> np.ndarray:
    """Pérdida de cuantil por observación y nivel, forma (n, k).

    L_τ(y, q) = τ·(y − q) si y ≥ q;  (1 − τ)·(q − y) si y < q.
    """
    y, q, t = _como_arrays(y, q, niveles)
    d = y[:, None] - q
    return np.maximum(t[None, :] * d, (t[None, :] - 1.0) * d)


def pinball_medio(y, q, niveles) -> np.ndarray:
    """Pérdida de cuantil media por nivel, forma (k,)."""
    return pinball(y, q, niveles).mean(axis=0)


def crps_cuantiles(y, q, niveles) -> np.ndarray:
    """CRPS aproximado por observación, forma (n,), a partir de cuantiles.

    CRPS(F, y) = 2 ∫₀¹ L_τ(y, F⁻¹(τ)) dτ. Se integra con la regla del trapecio sobre
    [niveles[0], niveles[-1]]; NO incluye las colas fuera de ese rango, así que subestima
    el CRPS verdadero. El sesgo es común a todos los modelos evaluados con los mismos niveles,
    por lo que sirve para compararlos, no como valor absoluto del CRPS.
    """
    y, q, t = _como_arrays(y, q, niveles)
    if len(t) < 2:
        raise ValueError("se necesitan al menos 2 niveles")
    return 2.0 * np.trapezoid(pinball(y, q, t), t, axis=1)


def crps_muestras(y, muestras) -> np.ndarray:
    """CRPS exacto con muestras de la predictiva, forma (n,).

    `muestras` es (n, m) (m trayectorias por observación) o (m,) para una sola predictiva.
    CRPS = E|X − y| − ½ E|X − X'|, con E|X − X'| = (2/m²) Σᵢ (2i − m − 1)·x₍ᵢ₎ (muestra ordenada).
    """
    y = np.atleast_1d(np.asarray(y, dtype=float))
    x = np.asarray(muestras, dtype=float)
    if x.ndim == 1:
        x = np.broadcast_to(x, (len(y), len(x)))
    if x.ndim != 2 or x.shape[0] != len(y):
        raise ValueError("muestras debe ser (n, m) o (m,)")
    m = x.shape[1]
    xs = np.sort(x, axis=1)
    e_xy = np.abs(xs - y[:, None]).mean(axis=1)
    pesos = 2.0 * np.arange(1, m + 1) - m - 1
    e_xx = 2.0 * (xs * pesos[None, :]).sum(axis=1) / m**2
    return e_xy - 0.5 * e_xx


def puntaje_intervalo(y, inferior, superior, alfa: float) -> np.ndarray:
    """Puntaje de intervalo (Gneiting–Raftery) del intervalo central de nivel 1 − alfa, (n,).

    IS = (u − l) + (2/α)(l − y)·1{y < l} + (2/α)(y − u)·1{y > u}.
    """
    if not 0 < alfa < 1:
        raise ValueError("alfa debe estar en (0, 1)")
    y = np.asarray(y, dtype=float)
    lo = np.asarray(inferior, dtype=float)
    hi = np.asarray(superior, dtype=float)
    if np.any(hi < lo):
        raise ValueError("el límite superior es menor que el inferior")
    return (hi - lo) + (2.0 / alfa) * np.maximum(lo - y, 0.0) + (2.0 / alfa) * np.maximum(y - hi, 0.0)
