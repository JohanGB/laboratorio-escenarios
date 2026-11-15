"""Bootstrap estacionario por bloques (Politis y Romano, 1994) para trayectorias de la TRM.

Es línea base de los horizontes largos (126 y 252) y el motor de Monte Carlo que usa el caso
«compra de dólares» (F5): el motor importa `trayectorias` desde aquí, no lo reescribe.

Dos variantes (decisión registrada en docs/decisiones.md, 15-nov-2026):
- `BootstrapEstacionario(filtrado=False)`: remuestrea rendimientos diarios observados de TODA la
  historia hasta el origen (banda incluida; conserva 1997-1999, 2008, 2015). Incondicional.
- `BootstrapEstacionario(filtrado=True)`: remuestrea residuos estandarizados z_t = r_t / σ_{t−1}
  (σ = EWMA 0,94, causal) y los reescala con una trayectoria de volatilidad que parte de la
  volatilidad conocida en el origen y vuelve a la de largo plazo:
      σ²_{o+k} = σ̄² + (σ²_o − σ̄²)·ρ^(k−1),   k = 1..h.
  σ̄² (media de r²) y ρ (persistencia de la varianza EWMA, estimada a 21 pasos) salen de `ajustar`.
  Así responde a la volatilidad actual a 1-21 días sin suponer que dura un año, y las colas
  siguen siendo empíricas (los z de las crisis entran al remuestreo).

Longitud media de bloque: Politis y White (2004) con la corrección de Patton, Politis y White
(2009), estimada en `ajustar` (datos hasta el reajuste ≤ origen). Se toma el máximo entre la
estimada sobre la serie y sobre su valor absoluto: los rendimientos casi no tienen
autocorrelación lineal, pero su volatilidad sí; ignorarlo subestima las colas a horizontes largos.

Fronteras: el remuestreo es circular (Politis-Romano), así que h puede exceder la historia; bloque
acotado a [1, min(3√n, n/3)]; ρ acotado a [0,5; 0,9999]; σ con piso 1e-12; NaN se descartan.
Reproducibilidad: generador por origen, `default_rng([semilla, origen])`; el resultado en un origen
no depende de cómo se agrupan los orígenes en bloques de reajuste.
"""
from __future__ import annotations

import numpy as np

from .base import Pronosticador
from .lineas_base import varianza_ewma

MIN_OBS = 250
LAM = 0.94
PASO_RHO = 21
RHO_MIN, RHO_MAX = 0.5, 0.9999


def longitud_bloque_pw(x: np.ndarray) -> float:
    """Longitud media óptima del bloque para el bootstrap estacionario (Politis-White / PPW 2009)."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 20:
        raise ValueError("serie demasiado corta para estimar la longitud de bloque")
    e = x - x.mean()
    b_max = np.ceil(min(3 * np.sqrt(n), n / 3))
    kn = max(5, int(np.ceil(np.log10(n))))
    m_max = int(np.ceil(np.sqrt(n))) + kn
    acv = np.array([e[k:] @ e[: n - k] / n for k in range(m_max + kn + 1)])
    if acv[0] <= 0:
        return 1.0
    rho = np.abs(acv / acv[0])
    cv = 2.0 * np.sqrt(np.log10(n) / n)
    m_hat = None
    for m in range(0, m_max + 1):                      # primer m con ρ_{m+1..m+kn} insignificantes
        if np.all(rho[m + 1: m + kn + 1] < cv):
            m_hat = m
            break
    M = m_max if m_hat is None else min(2 * max(m_hat, 1), m_max)
    k = np.arange(1, M + 1)
    lam = np.where(k / M <= 0.5, 1.0, 2.0 * (1.0 - k / M))   # núcleo trapezoidal plano
    g = 2.0 * np.sum(lam * k * acv[1: M + 1])
    s = acv[0] + 2.0 * np.sum(lam * acv[1: M + 1])
    if s <= 0 or g == 0:
        return 1.0
    b = (2.0 * g ** 2 / (2.0 * s ** 2)) ** (1 / 3) * n ** (1 / 3)
    return float(np.clip(b, 1.0, b_max))


def indices_estacionarios(rng: np.random.Generator, n: int, largo: int, sims: int,
                          bloque: float) -> np.ndarray:
    """Índices (largo, sims) del bootstrap estacionario circular sobre 0..n−1.

    En cada paso, con probabilidad p = 1/bloque se salta a un índice uniforme; si no, se avanza
    uno (circular). Con bloque = 1 (p = 1) los índices son exactamente los sorteos uniformes:
    bootstrap simple.
    """
    p = 1.0 / max(float(bloque), 1.0)
    saltos = rng.integers(0, n, size=(largo, sims))
    nuevo = rng.random((largo, sims)) < p
    nuevo[0] = True
    idx = np.empty((largo, sims), dtype=np.int64)
    idx[0] = saltos[0]
    for k in range(1, largo):
        idx[k] = np.where(nuevo[k], saltos[k], (idx[k - 1] + 1) % n)
    return idx


def trayectorias(x: np.ndarray, largo: int, sims: int, bloque: float, rng: np.random.Generator,
                 escala: np.ndarray | None = None) -> np.ndarray:
    """Rendimientos logarítmicos ACUMULADOS (largo, sims): fila k = suma de los k+1 primeros pasos.

    x: serie a remuestrear (rendimientos o residuos estandarizados, sin NaN).
    escala: desvío por paso (largo,) que multiplica cada paso remuestreado (variante filtrada).
    """
    x = np.asarray(x, float)
    pasos = x[indices_estacionarios(rng, len(x), largo, sims, bloque)]
    if escala is not None:
        pasos = pasos * np.asarray(escala, float)[:, None]
    return np.cumsum(pasos, axis=0)


def _sigma2_ewma(r: np.ndarray) -> np.ndarray:
    return np.maximum(varianza_ewma(r, LAM)[: len(r)], 1e-24)


def residuos_estandarizados(r: np.ndarray) -> np.ndarray:
    """z[t] = r[t] / σ_{t−1} para t = 1..n−1 (σ_{t−1} = desvío previsto para t con info hasta t−1)."""
    s2 = _sigma2_ewma(r)
    return r[1:] / np.sqrt(s2[:-1])


class BootstrapEstacionario(Pronosticador):
    def __init__(self, filtrado: bool = False, sims: int = 4000, semilla: int = 20240501,
                 bloque: float | None = None, horizontes=None):
        super().__init__(*(() if horizontes is None else (horizontes,)))
        self.filtrado, self.sims, self.semilla, self.bloque_fijo = filtrado, sims, semilla, bloque
        self.nombre = "bootstrap_est_filtrado" if filtrado else "bootstrap_est"
        self.bloque: float | None = None
        self.sigma2_largo: float | None = None
        self.rho: float | None = None
        self.reajustes = 0
        self.historial: list[dict] = []

    def parametros(self):
        return {"filtrado": self.filtrado, "sims": self.sims, "semilla": self.semilla,
                "bloque": self.bloque_fijo or "politis_white(max serie, |serie|)",
                "lam_ewma": LAM, "ventana": "expansiva (toda la historia)"}

    def _serie(self, r: np.ndarray) -> np.ndarray:
        x = residuos_estandarizados(r) if self.filtrado else r[1:]
        return x[np.isfinite(x)]

    def ajustar(self, vista) -> None:
        r = vista.r
        x = self._serie(r)
        if len(x) < MIN_OBS:
            raise ValueError("historia insuficiente para el bootstrap")
        self.reajustes += 1
        self.bloque = (float(self.bloque_fijo) if self.bloque_fijo else
                       max(longitud_bloque_pw(x), longitud_bloque_pw(np.abs(x))))
        if self.filtrado:
            rr = r[1:][np.isfinite(r[1:])]
            self.sigma2_largo = float(np.mean(rr ** 2))
            s2 = _sigma2_ewma(r)[1:]
            a, b = s2[:-PASO_RHO] - self.sigma2_largo, s2[PASO_RHO:] - self.sigma2_largo
            beta = float(a @ b / (a @ a)) if a @ a > 0 else RHO_MAX ** PASO_RHO
            beta = min(max(beta, RHO_MIN ** PASO_RHO), RHO_MAX ** PASO_RHO)
            self.rho = beta ** (1 / PASO_RHO)
        self.historial.append({"t": vista.n - 1, "bloque": self.bloque, "rho": self.rho})

    def escala(self, sigma2_origen: float, largo: int) -> np.ndarray:
        k = np.arange(largo)
        s2 = self.sigma2_largo + (sigma2_origen - self.sigma2_largo) * self.rho ** k
        return np.sqrt(np.maximum(s2, 1e-24))

    def pronosticar(self, vista, origenes, niveles):
        if self.bloque is None:
            raise RuntimeError("modelo sin ajustar")
        hmax = max(self.horizontes)
        s2 = _sigma2_ewma(vista.r) if self.filtrado else None
        out = {h: np.empty((len(origenes), len(niveles))) for h in self.horizontes}
        for i, o in enumerate(np.asarray(origenes)):
            o = int(o)
            x = self._serie(vista.r[: o + 1])
            rng = np.random.default_rng([self.semilla, o])
            esc = self.escala(float(s2[o]), hmax) if self.filtrado else None
            acum = trayectorias(x, hmax, self.sims, self.bloque, rng, esc)
            for h in self.horizontes:
                out[h][i] = np.quantile(acum[h - 1], niveles)
        return out
