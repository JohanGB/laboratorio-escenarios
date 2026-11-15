"""Pruebas estadísticas de pronósticos: Kupiec, Christoffersen y Diebold-Mariano.

Independiente del dominio: recibe secuencias de aciertos/violaciones o de pérdidas.
- Kupiec (1995), proporción de fallas (POF): H0 tasa de violación = p.  LR ~ χ²(1).
- Christoffersen (1998): independencia de primer orden (Markov) LR_ind ~ χ²(1) y cobertura
  condicional LR_cc = LR_uc + LR_ind ~ χ²(2).
- Diebold-Mariano (1995) con varianza de largo plazo Newey-West (Bartlett) y la corrección de
  muestra pequeña de Harvey, Leybourne y Newbold (1997), distribución t con n−1 g.l.
Las pruebas de violaciones suponen observaciones no traslapadas (usar h = 1).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats
from scipy.special import xlogy


@dataclass(frozen=True)
class Resultado:
    estadistico: float
    p_valor: float
    detalle: dict


def _loglik_bernoulli(x: int, n: int, p: float) -> float:
    """ln[(1−p)^(n−x) · p^x] con la convención 0·ln 0 = 0."""
    return float(xlogy(n - x, 1 - p) + xlogy(x, p))


def kupiec(violaciones, p: float) -> Resultado:
    v = np.asarray(violaciones, dtype=bool)
    n, x = len(v), int(v.sum())
    if n == 0 or not 0 < p < 1:
        raise ValueError("se requiere n > 0 y 0 < p < 1")
    lr = -2 * (_loglik_bernoulli(x, n, p) - _loglik_bernoulli(x, n, x / n))
    lr = max(lr, 0.0)
    return Resultado(lr, float(stats.chi2.sf(lr, 1)), {"n": n, "x": x, "tasa": x / n, "p": p})


def transiciones(violaciones) -> dict[str, int]:
    v = np.asarray(violaciones, dtype=int)
    a, b = v[:-1], v[1:]
    return {"n00": int(((a == 0) & (b == 0)).sum()), "n01": int(((a == 0) & (b == 1)).sum()),
            "n10": int(((a == 1) & (b == 0)).sum()), "n11": int(((a == 1) & (b == 1)).sum())}


def christoffersen(violaciones, p: float) -> dict[str, Resultado]:
    """Devuelve {'independencia': ..., 'condicional': ...}."""
    t = transiciones(violaciones)
    n00, n01, n10, n11 = t["n00"], t["n01"], t["n10"], t["n11"]
    pi01 = n01 / (n00 + n01) if n00 + n01 else 0.0
    pi11 = n11 / (n10 + n11) if n10 + n11 else 0.0
    pi = (n01 + n11) / (n00 + n01 + n10 + n11)
    l_ind = float(xlogy(n00 + n10, 1 - pi) + xlogy(n01 + n11, pi))
    l_mk = float(xlogy(n00, 1 - pi01) + xlogy(n01, pi01) + xlogy(n10, 1 - pi11) + xlogy(n11, pi11))
    lr_ind = max(-2 * (l_ind - l_mk), 0.0)
    uc = kupiec(violaciones, p)
    lr_cc = uc.estadistico + lr_ind
    det = {**t, "pi01": pi01, "pi11": pi11, "pi": pi}
    return {"independencia": Resultado(lr_ind, float(stats.chi2.sf(lr_ind, 1)), det),
            "condicional": Resultado(lr_cc, float(stats.chi2.sf(lr_cc, 2)), {**det, "lr_uc": uc.estadistico})}


def rezagos_por_defecto(n: int, h: int) -> int:
    """h−1 (traslape del objetivo) + regla de Newey-West ⌊4(n/100)^(2/9)⌋ (autocorrelación de pérdidas)."""
    return int(h - 1 + np.floor(4 * (n / 100) ** (2 / 9)))


def varianza_largo_plazo(d: np.ndarray, rezagos: int) -> float:
    """γ0 + 2 Σ_{k=1..L} (1 − k/(L+1)) γk, con γk = (1/n) Σ (d_t − d̄)(d_{t−k} − d̄)."""
    n = len(d)
    e = d - d.mean()
    s = float(e @ e) / n
    for k in range(1, rezagos + 1):
        s += 2 * (1 - k / (rezagos + 1)) * float(e[k:] @ e[:-k]) / n
    return s


def diebold_mariano(perdida_a, perdida_b, h: int = 1, rezagos: int | None = None,
                    alternativa: str = "menor") -> Resultado:
    """d_t = pérdida_a − pérdida_b.  alternativa='menor': H1 E[d] < 0 (A mejor que B);
    'dos_colas' para H1 E[d] ≠ 0."""
    a, b = np.asarray(perdida_a, float), np.asarray(perdida_b, float)
    if a.shape != b.shape or a.ndim != 1:
        raise ValueError("pérdidas con forma distinta")
    d = a - b
    n = len(d)
    L = rezagos_por_defecto(n, h) if rezagos is None else rezagos
    var = varianza_largo_plazo(d, L)
    if var <= 0:
        raise ValueError("varianza de largo plazo no positiva")
    dm = d.mean() / np.sqrt(var / n)
    hln = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    t = dm * hln
    if alternativa == "menor":
        p = float(stats.t.cdf(t, n - 1))
    elif alternativa == "dos_colas":
        p = float(2 * stats.t.sf(abs(t), n - 1))
    else:
        raise ValueError("alternativa debe ser 'menor' o 'dos_colas'")
    return Resultado(float(t), p, {"dm_sin_corregir": float(dm), "media_d": float(d.mean()),
                                   "rezagos": L, "n": n, "var_lp": var})
