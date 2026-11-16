"""PIT (transformada integral de probabilidad) a partir de cuantiles y prueba de uniformidad.

Con k cuantiles solo se conoce la distribución pronosticada en k puntos. Dos herramientas:

- `casillas` + `uniformidad`: ji-cuadrado de Pearson sobre las k+1 casillas que definen los
  niveles: (−∞, q_1], (q_1, q_2], …, (q_k, ∞), con probabilidades τ_1, τ_2−τ_1, …, 1−τ_k. No
  interpola nada: si el pronóstico está calibrado, los conteos son multinomiales con esas
  probabilidades. Con observaciones independientes (h = 1) el estadístico es χ²(casillas − 1).
  Con traslape (h > 1) se pasa `n_efectivo` (≈ n/h): el estadístico se multiplica por n_ef/n y
  las casillas extremas se fusionan hasta tener ≥ 5 esperadas; el resultado es APROXIMADO.
- `pit`: valor u_t = F_t(y_t) por interpolación lineal entre cuantiles (para figuras). Fuera del
  rango [q_1, q_k] no hay información: se asigna el punto medio de la casilla extrema.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

from .perdidas import _como_arrays
from .pruebas import Resultado

MIN_ESPERADO = 5.0


def casillas(y, q, niveles) -> tuple[np.ndarray, np.ndarray]:
    """(conteos observados, probabilidades nominales) de las k+1 casillas."""
    y, q, t = _como_arrays(y, q, niveles)
    pos = (y[:, None] > q).sum(axis=1)                  # casilla j ⇔ q_j < y ≤ q_{j+1}
    obs = np.bincount(pos, minlength=len(t) + 1).astype(float)
    return obs, np.diff(np.concatenate([[0.0], t, [1.0]]))


def _fusionar(obs: np.ndarray, esp: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    obs, esp = list(obs), list(esp)
    for lado in (0, -1):                                # extremos hacia adentro
        while len(esp) > 2 and esp[lado] < MIN_ESPERADO:
            vecino = 1 if lado == 0 else -2
            obs[vecino] += obs[lado]; esp[vecino] += esp[lado]
            del obs[lado], esp[lado]
    return np.array(obs), np.array(esp)


def uniformidad(y, q, niveles, n_efectivo: float | None = None) -> Resultado:
    obs, prob = casillas(y, q, niveles)
    n = obs.sum()
    if n == 0:
        raise ValueError("sin observaciones")
    ne = float(n) if n_efectivo is None else float(n_efectivo)
    o, e = _fusionar(obs * ne / n, prob * ne)
    est = float(np.sum((o - e) ** 2 / e))
    gl = len(e) - 1
    return Resultado(est, float(stats.chi2.sf(est, gl)),
                     {"gl": gl, "n": int(n), "n_efectivo": ne, "casillas": len(e),
                      "aproximada": n_efectivo is not None,
                      "frecuencias": (obs / n).tolist(), "nominales": prob.tolist()})


def pit(y, q, niveles) -> np.ndarray:
    y, q, t = _como_arrays(y, q, niveles)
    u = np.empty(len(y))
    for i in range(len(y)):
        if y[i] <= q[i, 0]:
            u[i] = t[0] / 2
        elif y[i] > q[i, -1]:
            u[i] = (1 + t[-1]) / 2
        else:
            u[i] = np.interp(y[i], q[i], t)
    return u
