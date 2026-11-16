"""Familia GARCH con errores t de Student o t asimétrica de Hansen (`skewt`): GARCH(1,1),
GJR-GARCH(1,1,1) y EGARCH(1,1,1).

- Estimación (`ajustar`): máxima verosimilitud con `arch` sobre los rendimientos (en %) hasta el
  índice de reajuste, media cero, ventana expansiva. Arranque en caliente (O1): primero se parte de
  los parámetros del reajuste anterior; si eso falla se reintenta con los valores iniciales de
  `arch` (arranque en frío). Si ambos fallan o dan parámetros inválidos se conservan los del
  reajuste anterior y se cuenta en `fallos` (nunca se inventan); `causas` dice por qué.
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


def skewt_estandarizada(rng: np.random.Generator, nu: float, lam: float, size) -> np.ndarray:
    """t asimétrica de Hansen (1994) con media 0 y varianza 1 (misma que `arch`), por inversión."""
    from arch.univariate import SkewStudent
    u = rng.random(size)
    return SkewStudent().ppf(u.ravel(), np.array([nu, lam])).reshape(np.shape(u))


def innovaciones(rng: np.random.Generator, p: dict, size) -> np.ndarray:
    """Innovaciones estandarizadas según la distribución de los parámetros (con 'lam' = skewt)."""
    if "lam" in p:
        return skewt_estandarizada(rng, p["nu"], p["lam"], size)
    return t_estandarizada(rng, p["nu"], size)


def persistencia(tipo: str, p: dict) -> float:
    """α + γ/2 + β (GARCH/GJR; γ/2 es exacto solo con innovaciones simétricas) o β (EGARCH)."""
    if tipo == "EGARCH":
        return p["beta"]
    return p["alpha"] + p.get("gamma", 0.0) / 2 + p["beta"]


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


DISTS = ("t", "skewt")
ARRANQUES = ("caliente", "frio")
TOL_PERSISTENCIA = 1e-4          # antes de O1: 1e-6
# nombre de arch ↔ nombre propio
_NOMBRES = {"omega": "omega", "alpha[1]": "alpha", "gamma[1]": "gamma", "beta[1]": "beta",
            "nu": "nu", "eta": "nu", "lambda": "lam"}


class GarchT(Pronosticador):
    """`arranque="frio", tol_persistencia=1e-6` reproduce el código previo a O1 (diagnóstico)."""

    def __init__(self, tipo: str = "GARCH", sims: int = 4000, semilla: int = 20240501,
                 horizontes=None, dist: str = "t", arranque: str = "caliente",
                 tol_persistencia: float = TOL_PERSISTENCIA):
        if tipo not in TIPOS:
            raise ValueError(f"tipo debe ser uno de {TIPOS}")
        if dist not in DISTS or arranque not in ARRANQUES:
            raise ValueError(f"dist ∈ {DISTS}, arranque ∈ {ARRANQUES}")
        super().__init__(*(() if horizontes is None else (horizontes,)))
        self.tipo, self.sims, self.semilla, self.dist, self.arranque = tipo, sims, semilla, dist, arranque
        self.tol = tol_persistencia
        self.nombre = {"GARCH": "garch", "GJR": "gjr", "EGARCH": "egarch"}[tipo] + "_" + dist
        self.params: dict | None = None
        self.fallos = 0
        self.reajustes = 0
        self.rescates = 0           # el arranque en caliente falló pero el frío sirvió
        self.causas: dict[str, int] = {}
        self.historial: list[dict] = []

    def parametros(self):
        return {"tipo": self.tipo, "dist": self.dist, "media": "cero", "sims": self.sims,
                "semilla": self.semilla, "ventana": "expansiva", "arranque": self.arranque,
                "tol_persistencia": self.tol}

    # ---- estimación -------------------------------------------------------------------------
    def _modelo(self, eps: np.ndarray):
        from arch import arch_model
        kw = {"GARCH": dict(vol="GARCH", p=1, o=0, q=1),
              "GJR": dict(vol="GARCH", p=1, o=1, q=1),
              "EGARCH": dict(vol="EGARCH", p=1, o=1, q=1)}[self.tipo]
        return arch_model(eps, mean="Zero", dist=self.dist, rescale=False, **kw)

    def _validar(self, d) -> tuple[dict | None, str]:
        if not np.all(np.isfinite(d.to_numpy())):
            return None, "no_finito"
        p = {_NOMBRES[k]: float(v) for k, v in d.items()}
        if not NU_MIN <= p["nu"] <= NU_MAX:
            return None, "nu_fuera"
        if "lam" in p and not -0.99 < p["lam"] < 0.99:
            return None, "lambda_fuera"
        if self.tipo != "EGARCH":
            # La TRM estima persistencia ≈ 1 (IGARCH en la frontera que impone arch). Se acepta hasta
            # 1 + tol. O1: SLSQP de arch termina en la frontera con holgura ≈ 1e-5 (α+β = 1,00001); con
            # tol = 1e-6 eso se contaba como «explosivo» (36 de 38 fallos de GARCH). Con 1e-4 la
            # varianza a 252 pasos crece a lo sumo 2,5 %. Solo se rechaza la explosividad real.
            if p["omega"] <= 0 or p["alpha"] < 0 or p["beta"] < 0:
                return None, "signo"
            if persistencia(self.tipo, p) > 1.0 + self.tol:
                return None, "explosivo"
        return p, ""

    def _intento(self, am, inicio: np.ndarray | None) -> tuple[dict | None, str]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = am.fit(disp="off", show_warning=False, options={"maxiter": 500},
                             starting_values=inicio)
        except Exception:
            return None, "excepcion"
        if res.convergence_flag != 0:
            return None, "no_convergio"
        return self._validar(res.params)

    def _estimar(self, eps: np.ndarray) -> dict | None:
        am = self._modelo(eps)
        causa = ""
        if self.arranque == "caliente" and self.params is not None:
            orden = am.volatility.parameter_names() + am.distribution.parameter_names()
            inicio = np.array([self.params[_NOMBRES[k]] for k in orden])
            p, causa = self._intento(am, inicio)
            if p is not None:
                return p
        p, causa_frio = self._intento(am, None)
        if p is not None:
            if causa:
                self.rescates += 1
            return p
        self._ultima_causa = causa_frio
        return None

    def ajustar(self, vista) -> None:
        eps = vista.r[1:] * 100.0
        if len(eps) < 250:
            raise ValueError("historia insuficiente para estimar GARCH")
        self.reajustes += 1
        self._ultima_causa = "desconocida"
        p = self._estimar(eps)
        if p is None:
            self.fallos += 1
            self.causas[self._ultima_causa] = self.causas.get(self._ultima_causa, 0) + 1
            if self.params is None:
                raise RuntimeError("la primera estimación GARCH no convergió")
            self.historial.append({"t": vista.n - 1, "fallo": True})
            return
        self.params = p
        self.historial.append({"t": vista.n - 1, "fallo": False, **p,
                               "persistencia": persistencia(self.tipo, p)})

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
            z = innovaciones(rng, p, (hmax, self.sims))
            acum = simular_acumulados(v[o], self.tipo, p, hmax, z)
            for h in self.horizontes:
                out[h][i] = np.quantile(acum[h - 1], niveles) / 100.0
        return out
