"""Simulación histórica filtrada (FHS; Barone-Adesi, Giannopoulos y Vosper, 1999).

Idea: dividir cada rendimiento por la volatilidad prevista para ese día (residuo estandarizado
z_t = r_t / σ_{t|t−1}), remuestrear esos residuos empíricos y reescalarlos con la volatilidad de
hoy. Las colas son las observadas (no una t supuesta) y la escala responde a la volatilidad actual.

Dos filtros (decisión O1, docs/decisiones.md):
- `filtro="ewma"`: σ² por EWMA λ = 0,94 (RiskMetrics, sin estimar), unidades naturales.
- `filtro="gjr"`: σ² por GJR-GARCH(1,1,1) estimado con errores t (`GarchT("GJR")`, arranque en
  caliente) sobre r·100. La t solo sirve para estimar; los residuos que se remuestrean son empíricos.

Pronóstico en el origen o (solo usa r[1..o] y los parámetros del último reajuste ≤ o):
- h = 1: exacto, σ_{o+1} · cuantil empírico de {z_1..z_o} (sin simulación).
- h > 1: trayectorias. En cada paso se sortea un z de la historia (uniforme, con reposición),
  e = σ·z, y la varianza se actualiza con la misma recursión del filtro (no se escala por √h).
  Semilla por origen: `default_rng([semilla, o])`.
Los residuos no se renormalizan a varianza 1: es la FHS clásica (la varianza empírica de z ya
recoge el sesgo del filtro).
Con volatilidad constante (λ = 1) se reduce a la simulación histórica de toda la historia: h = 1
coincide exactamente con `SimulacionHistorica(ventana=None)` (hay prueba).
"""
from __future__ import annotations

import numpy as np

from .base import Pronosticador
from .garch import GarchT, simular_acumulados, varianzas
from .lineas_base import cuantil_ponderado, varianza_ewma

FILTROS = ("ewma", "gjr")
MIN_OBS = 250


class FHS(Pronosticador):
    def __init__(self, filtro: str = "ewma", lam: float = 0.94, sims: int = 4000,
                 semilla: int = 20240501, horizontes=None):
        if filtro not in FILTROS:
            raise ValueError(f"filtro debe ser uno de {FILTROS}")
        super().__init__(*(() if horizontes is None else (horizontes,)))
        self.filtro, self.lam, self.sims, self.semilla = filtro, lam, sims, semilla
        self.nombre = f"fhs_{filtro}"
        self._gjr = GarchT("GJR", sims=1, semilla=semilla) if filtro == "gjr" else None
        self.listo = False

    # contadores de estimación (solo el filtro GJR estima)
    @property
    def fallos(self):
        return self._gjr.fallos if self._gjr else 0

    @property
    def reajustes(self):
        return self._gjr.reajustes if self._gjr else None

    def parametros(self):
        d = {"filtro": self.filtro, "sims": self.sims, "semilla": self.semilla,
             "residuos": "empíricos, toda la historia, sin renormalizar", "ventana": "expansiva"}
        if self.filtro == "ewma":
            d["lam"] = self.lam
        else:
            d["estimacion"] = "GJR-GARCH(1,1,1) t, arranque en caliente"
        return d

    def ajustar(self, vista) -> None:
        if vista.n - 1 < MIN_OBS:
            raise ValueError("historia insuficiente para FHS")
        if self._gjr is not None:
            self._gjr.ajustar(vista)
        self.listo = True

    def _filtrar(self, r: np.ndarray):
        """(varianzas v, escala, tipo, params): v[k] = varianza prevista del paso k+1 (r[k+1]).

        Causal: v[k] depende solo de r[1..k]. Unidades: r·escala.
        """
        if self.filtro == "ewma":
            s2 = varianza_ewma(r, self.lam)              # s2[t] = varianza de r[t+1]
            return s2, 1.0, "GARCH", {"omega": 0.0, "alpha": 1 - self.lam, "beta": self.lam}
        p = self._gjr.params
        eps = np.nan_to_num(r[1:]) * 100.0
        return varianzas(eps, "GJR", p), 100.0, "GJR", p

    def pronosticar(self, vista, origenes, niveles):
        if not self.listo:
            raise RuntimeError("modelo sin ajustar")
        r = vista.r
        v, esc, tipo, p = self._filtrar(r)
        x = np.nan_to_num(r[1:]) * esc                       # x[k] = r[k+1]·escala
        zt = x / np.sqrt(np.maximum(v[: len(x)], 1e-300))    # zt[k] = residuo de r[k+1]
        hmax = max(self.horizontes)
        out = {h: np.empty((len(origenes), len(niveles))) for h in self.horizontes}
        for i, o in enumerate(np.asarray(origenes)):
            o = int(o)
            z = zt[:o]
            z = z[np.isfinite(r[1: o + 1])]                  # los NaN de r no son residuos
            if len(z) < MIN_OBS:
                raise ValueError("historia insuficiente para FHS")
            v1 = float(v[o])
            if 1 in self.horizontes:
                out[1][i] = np.sqrt(v1) * cuantil_ponderado(z, np.ones(len(z)), niveles) / esc
            if hmax > 1:
                rng = np.random.default_rng([self.semilla, o])
                zz = z[rng.integers(0, len(z), size=(hmax, self.sims))]
                acum = simular_acumulados(v1, tipo, p, hmax, zz)
                for h in self.horizontes:
                    if h > 1:
                        out[h][i] = np.quantile(acum[h - 1], niveles) / esc
        return out
