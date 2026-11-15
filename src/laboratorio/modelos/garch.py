"""Familia GARCH con errores t de Student: GARCH(1,1), GJR-GARCH(1,1,1) y EGARCH(1,1,1).

- Estimación (`ajustar`): máxima verosimilitud con `arch` sobre los rendimientos (en %) hasta el
  índice de reajuste, media cero, ventana expansiva. Si la estimación no converge o da parámetros
  inválidos se conservan los del reajuste anterior y se cuenta en `fallos` (nunca se inventan).
- Pronóstico (`pronosticar`): la recursión de varianza con parámetros fijos y la simulación de
  trayectorias son propias (numpy), semillas por (origen) → resultado determinista y
  verificablemente sin fuga: el estado en el origen o solo usa r[1..o].
- Salida: cuantiles del rendimiento log acumulado a h pasos, en unidades naturales (no en %).
"""
from __future__ import annotations

import warnings

import numpy as np
from scipy import stats

from .base import Pronosticador

TIPOS = ("GARCH", "GJR", "EGARCH")
NU_MIN = 2.1
NU_MAX = 200.0
LOGV_MAX = 25.0


def retrocalculo(eps: np.ndarray) -> float:
    """Misma varianza inicial que `arch`: media ponderada (0,94^i) de los primeros ≤75 ε²."""
    tau = min(75, len(eps))
    w = 0.94 ** np.arange(tau)
    return float(np.sum(w / w.sum() * eps[:tau] ** 2))


def varianzas(eps: np.ndarray, tipo: str, p: dict) -> np.ndarray:
    """σ²[k] = varianza condicional de eps[k]; σ²[m] = pronóstico a un paso tras la última obs.

    Causal: σ²[k] depende solo de eps[:k].
    """
    m = len(eps)
    v = np.empty(m + 1)
    v[0] = retrocalculo(eps)
    if tipo in ("GARCH", "GJR"):
        w, a, b = p["omega"], p["alpha"], p["beta"]
        g = p.get("gamma", 0.0)
        e2 = eps ** 2
        for k in range(m):
            v[k + 1] = w + (a + (g if eps[k] < 0 else 0.0)) * e2[k] + b * v[k]
        return v
    w, a, g, b = p["omega"], p["alpha"], p["gamma"], p["beta"]
    c = np.sqrt(2 / np.pi)                      # convención de arch (esperanza normal de |z|)
    lv = np.log(v[0])
    v[0] = np.exp(lv)
    for k in range(m):
        z = eps[k] / np.exp(0.5 * lv)
        lv = w + a * (abs(z) - c) + g * z + b * lv
        lv = min(max(lv, -LOGV_MAX), LOGV_MAX)
        v[k + 1] = np.exp(lv)
    return v


def t_estandarizada(rng: np.random.Generator, nu: float, size) -> np.ndarray:
    """Variable t de Student con media 0 y varianza 1."""
    return rng.standard_t(nu, size) * np.sqrt((nu - 2) / nu)


def simular_acumulados(v1: float, tipo: str, p: dict, hmax: int, z: np.ndarray) -> np.ndarray:
    """Acumulados por trayectoria: devuelve (hmax, S) con Σ ε_{1..h} (en %).

    v1 = varianza del primer paso (ya incluye la información hasta el origen); z (hmax, S).
    """
    S = z.shape[1]
    acum = np.zeros((hmax, S))
    if tipo in ("GARCH", "GJR"):
        w, a, b = p["omega"], p["alpha"], p["beta"]
        g = p.get("gamma", 0.0)
        var = np.full(S, v1)
        tot = np.zeros(S)
        for h in range(hmax):
            e = np.sqrt(var) * z[h]
            tot = tot + e
            acum[h] = tot
            var = w + (a + g * (e < 0)) * e ** 2 + b * var
        return acum
    w, a, g, b = p["omega"], p["alpha"], p["gamma"], p["beta"]
    c = np.sqrt(2 / np.pi)
    lv = np.full(S, np.log(v1))
    tot = np.zeros(S)
    for h in range(hmax):
        e = np.exp(0.5 * lv) * z[h]
        tot = tot + e
        acum[h] = tot
        lv = np.clip(w + a * (np.abs(z[h]) - c) + g * z[h] + b * lv, -LOGV_MAX, LOGV_MAX)
    return acum


class GarchT(Pronosticador):
    def __init__(self, tipo: str = "GARCH", sims: int = 4000, semilla: int = 20240501,
                 horizontes=None):
        if tipo not in TIPOS:
            raise ValueError(f"tipo debe ser uno de {TIPOS}")
        super().__init__(*(() if horizontes is None else (horizontes,)))
        self.tipo, self.sims, self.semilla = tipo, sims, semilla
        self.nombre = {"GARCH": "garch_t", "GJR": "gjr_t", "EGARCH": "egarch_t"}[tipo]
        self.params: dict | None = None
        self.fallos = 0
        self.reajustes = 0

    def parametros(self):
        return {"tipo": self.tipo, "dist": "t", "media": "cero", "sims": self.sims,
                "semilla": self.semilla, "ventana": "expansiva"}

    # ---- estimación -------------------------------------------------------------------------
    def _estimar(self, eps: np.ndarray) -> dict | None:
        from arch import arch_model
        kw = {"GARCH": dict(vol="GARCH", p=1, o=0, q=1),
              "GJR": dict(vol="GARCH", p=1, o=1, q=1),
              "EGARCH": dict(vol="EGARCH", p=1, o=1, q=1)}[self.tipo]
        am = arch_model(eps, mean="Zero", dist="t", rescale=False, **kw)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = am.fit(disp="off", show_warning=False, options={"maxiter": 500})
        except Exception:
            return None
        if res.convergence_flag != 0 or not np.all(np.isfinite(res.params.to_numpy())):
            return None
        d = res.params
        p = {"omega": float(d["omega"]), "alpha": float(d["alpha[1]"]),
             "beta": float(d["beta[1]"]), "nu": float(d["nu"])}
        if self.tipo != "GARCH":
            p["gamma"] = float(d["gamma[1]"])
        if not NU_MIN <= p["nu"] <= NU_MAX:
            return None
        if self.tipo != "EGARCH":
            gam = p.get("gamma", 0.0)
            # La TRM estima persistencia ≈ 1 (IGARCH en la frontera que impone arch). Se acepta hasta
            # 1 + 1e-6: el pronóstico a 63 pasos es finito. Solo se rechaza la explosividad estricta.
            if (p["omega"] <= 0 or p["alpha"] < 0 or p["beta"] < 0
                    or p["alpha"] + gam / 2 + p["beta"] > 1.0 + 1e-6):
                return None
        return p

    def ajustar(self, vista) -> None:
        eps = vista.r[1:] * 100.0
        if len(eps) < 250:
            raise ValueError("historia insuficiente para estimar GARCH")
        self.reajustes += 1
        p = self._estimar(eps)
        if p is None:
            self.fallos += 1
            if self.params is None:
                raise RuntimeError("la primera estimación GARCH no convergió")
            return
        self.params = p

    # ---- pronóstico ------------------------------------------------------------------------
    def pronosticar(self, vista, origenes, niveles):
        if self.params is None:
            raise RuntimeError("modelo sin ajustar")
        p = self.params
        eps = vista.r[1:] * 100.0
        v = varianzas(eps, self.tipo, p)
        hmax = max(self.horizontes)
        out = {h: np.empty((len(origenes), len(niveles))) for h in self.horizontes}
        for i, o in enumerate(origenes):
            # eps[k] ↔ vista índice k+1; el origen o usó eps[:o]; varianza del siguiente = v[o]
            rng = np.random.default_rng([self.semilla, int(o)])
            z = t_estandarizada(rng, p["nu"], (hmax, self.sims))
            acum = simular_acumulados(v[o], self.tipo, p, hmax, z)
            for h in self.horizontes:
                out[h][i] = np.quantile(acum[h - 1], niveles) / 100.0
        return out
