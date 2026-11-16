"""Escalón 3: cambio de régimen de Markov en la varianza (Hamilton, 1989).

r_t·100 = σ_{S_t}·ε_t,  ε_t ~ N(0, 1),  S_t ∈ {0..k−1} cadena de Markov,  media cero.

- Estimación (`ajustar`): `MarkovRegression(trend="n", switching_variance=True)` de statsmodels,
  ventana expansiva. Arranque en caliente con los parámetros del reajuste anterior y, si falla,
  en frío. Los estados se reordenan por varianza creciente (estado k−1 = «alto»), así la
  etiqueta no salta entre reajustes. Si no converge se conservan los parámetros previos (`fallos`).
- Filtro (`filtrar`): recursión de Hamilton propia con parámetros fijos, arranque en las
  probabilidades ergódicas (igual que statsmodels). Causal: ξ_{t|t} solo usa r[1..t].
- Pronóstico en el origen o: probabilidades del día siguiente π_{o+1} = P·ξ_{o|o}.
  h = 1: cuantiles exactos de la mezcla de normales Σ π_s N(0, σ²_s) (bisección).
  h > 1: trayectorias de estado (S_{o+1} ~ π_{o+1}, luego la matriz de transición) y
  rendimientos normales con la varianza de cada estado; semilla por origen.
Convención: P[i, j] = P(S_t = i | S_{t−1} = j) (columnas suman 1), como statsmodels.
"""
from __future__ import annotations

import warnings

import numpy as np
from scipy import stats

from .base import Pronosticador

MIN_OBS = 250


def ergodicas(P: np.ndarray) -> np.ndarray:
    k = P.shape[0]
    A = np.vstack([np.eye(k) - P, np.ones(k)])
    b = np.zeros(k + 1); b[-1] = 1.0
    pi = np.linalg.lstsq(A, b, rcond=None)[0]
    pi = np.clip(pi, 0, None)
    return pi / pi.sum()


def filtrar(eps: np.ndarray, P: np.ndarray, s2: np.ndarray) -> np.ndarray:
    """ξ (m, k): ξ[t] = P(S_t | eps[0..t]). NaN en eps = sin información (solo predice)."""
    m, k = len(eps), len(s2)
    xi = np.empty((m, k))
    pred = ergodicas(P)
    sd = np.sqrt(s2)
    dens = stats.norm.pdf(eps[:, None] / sd[None, :]) / sd[None, :]
    for t in range(m):
        if np.isfinite(eps[t]):
            j = pred * dens[t]
            tot = j.sum()
            xi[t] = j / tot if tot > 0 and np.isfinite(tot) else pred
        else:
            xi[t] = pred
        pred = P @ xi[t]
    return xi


def cuantiles_mezcla(pesos: np.ndarray, sd: np.ndarray, niveles: np.ndarray,
                     iters: int = 200) -> np.ndarray:
    """Cuantiles de Σ w_s N(0, sd_s²) por bisección (monótonos en el nivel)."""
    niveles = np.asarray(niveles, float)
    lo = np.full(len(niveles), -60.0 * sd.max())
    hi = np.full(len(niveles), 60.0 * sd.max())
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        F = (pesos[None, :] * stats.norm.cdf(mid[:, None] / sd[None, :])).sum(1)
        abajo = F < niveles
        lo = np.where(abajo, mid, lo)
        hi = np.where(abajo, hi, mid)
        if np.all(hi - lo < 1e-13 * sd.max()):
            break
    return 0.5 * (lo + hi)


class MarkovVarianza(Pronosticador):
    def __init__(self, k: int = 2, sims: int = 4000, semilla: int = 20240501, horizontes=None):
        if k not in (2, 3):
            raise ValueError("k debe ser 2 o 3")
        super().__init__(*(() if horizontes is None else (horizontes,)))
        self.k, self.sims, self.semilla = k, sims, semilla
        self.nombre = f"markov_{k}"
        self.P: np.ndarray | None = None
        self.s2: np.ndarray | None = None
        self._crudos: np.ndarray | None = None
        self.fallos = 0
        self.reajustes = 0
        self.historial: list[dict] = []

    def parametros(self):
        return {"estados": self.k, "media": "cero", "varianza": "por estado", "dist": "normal",
                "sims": self.sims, "semilla": self.semilla, "ventana": "expansiva",
                "arranque": "caliente"}

    def _intento(self, eps, inicio):
        from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression
        mod = MarkovRegression(eps, k_regimes=self.k, trend="n", switching_variance=True)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = mod.fit(disp=False, start_params=inicio, maxiter=500)   # statsmodels: 50
        except Exception:
            return None
        th = np.asarray(res.params, float)
        if not (res.mle_retvals.get("converged", False) and np.all(np.isfinite(th))):
            return None
        P = mod.regime_transition_matrix(th)[:, :, 0]
        s2 = th[-self.k:]
        if np.any(s2 <= 0) or np.any(P < -1e-10) or not np.allclose(P.sum(0), 1, atol=1e-8):
            return None
        return th, np.clip(P, 0, 1), s2

    def ajustar(self, vista) -> None:
        eps = vista.r[1:] * 100.0
        eps = eps[np.isfinite(eps)]
        if len(eps) < MIN_OBS:
            raise ValueError("historia insuficiente para Markov")
        self.reajustes += 1
        res = self._intento(eps, self._crudos) if self._crudos is not None else None
        if res is None:
            res = self._intento(eps, None)
        if res is None:
            self.fallos += 1
            if self.P is None:
                raise RuntimeError("la primera estimación de Markov no convergió")
            self.historial.append({"t": vista.n - 1, "fallo": True})
            return
        th, P, s2 = res
        orden = np.argsort(s2)
        self._crudos = th
        self.P, self.s2 = P[np.ix_(orden, orden)], s2[orden]
        self.historial.append({"t": vista.n - 1, "fallo": False, "s2": self.s2.tolist(),
                               "permanencia": np.diag(self.P).tolist()})

    def probabilidades(self, vista) -> np.ndarray:
        """ξ (n, k) alineado con la vista: fila t = P(S_t | r[1..t]); fila 0 = ergódicas."""
        xi = filtrar(vista.r[1:] * 100.0, self.P, self.s2)
        return np.vstack([ergodicas(self.P), xi])

    def pronosticar(self, vista, origenes, niveles):
        if self.P is None:
            raise RuntimeError("modelo sin ajustar")
        xi = self.probabilidades(vista)
        sd = np.sqrt(self.s2)
        hmax = max(self.horizontes)
        acumP = np.cumsum(self.P, axis=0)                 # columna j: CDF del estado siguiente
        out = {h: np.empty((len(origenes), len(niveles))) for h in self.horizontes}
        for i, o in enumerate(np.asarray(origenes)):
            o = int(o)
            pi1 = self.P @ xi[o]
            if 1 in self.horizontes:
                out[1][i] = cuantiles_mezcla(pi1, sd, niveles) / 100.0
            if hmax > 1:
                rng = np.random.default_rng([self.semilla, o])
                u = rng.random((hmax, self.sims))
                z = rng.standard_normal((hmax, self.sims))
                s = np.minimum(np.searchsorted(np.cumsum(pi1), u[0]), self.k - 1)
                tot = np.zeros(self.sims)
                acum = np.empty((hmax, self.sims))
                for h in range(hmax):
                    if h > 0:
                        s = np.minimum((u[h][:, None] > acumP[:, s].T).sum(1), self.k - 1)
                    tot = tot + sd[s] * z[h]
                    acum[h] = tot
                for h in self.horizontes:
                    if h > 1:
                        out[h][i] = np.quantile(acum[h - 1], niveles) / 100.0
        return out
