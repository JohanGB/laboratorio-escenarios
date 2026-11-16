"""Regresión por cuantiles lineal y LightGBM por cuantiles sobre el rendimiento estandarizado.

z_h = y_h / (σ_t·√h)  →  cuantil previsto del rendimiento = σ_t·√h · ẑ_τ(x_t).
Un modelo por (horizonte, nivel). Los cuantiles se reordenan (sort) para evitar cruces.
Entrenamiento en `ajustar(vista)` con la vista recortada al reajuste: `vista.objetivo(h)` ya es NaN
donde s+h > t0, lo que implementa la purga del protocolo (s+h ≤ t0).

Hiperparámetros fijados de antemano (no se tunean con los datos de desarrollo).
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from ..backtest.particion import NIVELES
from . import caracteristicas as car
from .base import Pronosticador

MIN_FILAS = 150
PARAMS_LGBM = dict(n_estimators=150, learning_rate=0.03, num_leaves=7, min_child_samples=100,
                   subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=5.0,
                   n_jobs=1, deterministic=True, force_row_wise=True, verbose=-1)


class _Estandarizado(Pronosticador):
    columnas: list[str]
    exige_completas = True          # QR: filas con todas las columnas finitas
    cola_defendible = False
    motivo_sin_cola = ("entrena un modelo por nivel solo para los 11 niveles del protocolo; un "
                       "cuantil del 0,25 % se apoyaría en muy pocas observaciones por nivel")

    def __init__(self, columnas: list[str] | None = None, semilla: int = 20240501, horizontes=None):
        super().__init__(*(() if horizontes is None else (horizontes,)))
        self.semilla = semilla
        self.columnas = list(columnas) if columnas is not None else self.columnas_por_defecto()
        self.modelos: dict = {}
        self.fallos = 0
        self.reajustes = 0
        self.n_entrenamiento: dict[int, int] = {}

    def columnas_por_defecto(self) -> list[str]:
        return car.INTERNAS + car.EXTERNAS_COMPLETAS

    def parametros(self):
        return {"columnas": self.columnas, "semilla": self.semilla}

    # subclases
    def _ajustar_nivel(self, X: pd.DataFrame, z: np.ndarray, tau: float):
        raise NotImplementedError

    def _predecir_nivel(self, modelo, X: pd.DataFrame) -> np.ndarray:
        raise NotImplementedError

    def _filas_validas(self, X: pd.DataFrame) -> np.ndarray:
        return np.isfinite(X[self.columnas].to_numpy()).all(axis=1) if self.exige_completas \
            else np.isfinite(X[car.INTERNAS].to_numpy()).all(axis=1)

    def ajustar(self, vista) -> None:
        self.reajustes += 1
        feats = car.construir(vista)
        sg = car.sigma(vista)
        ok_x = self._filas_validas(feats)
        nuevos = {}
        for h in self.horizontes:
            y = vista.objetivo(h)
            z = y / (sg * np.sqrt(h))
            ok = ok_x & np.isfinite(z)
            if ok.sum() < MIN_FILAS:
                raise ValueError(f"filas de entrenamiento insuficientes ({int(ok.sum())}) para h={h}")
            self.n_entrenamiento[h] = int(ok.sum())
            X, zz = feats.loc[ok, self.columnas], z[ok]
            for tau in NIVELES:
                try:
                    nuevos[(h, float(tau))] = self._ajustar_nivel(X, zz, float(tau))
                except Exception:
                    self.fallos += 1
                    if (h, float(tau)) not in self.modelos:
                        raise
                    nuevos[(h, float(tau))] = self.modelos[(h, float(tau))]
        self.modelos = nuevos

    def pronosticar(self, vista, origenes, niveles):
        if not self.modelos:
            raise RuntimeError("modelo sin ajustar")
        if not np.array_equal(np.asarray(niveles, float), NIVELES):
            raise ValueError("el modelo se entrenó con los niveles del protocolo")
        o = np.asarray(origenes)
        feats = car.construir(vista).iloc[o][self.columnas]
        if self.exige_completas and not np.isfinite(feats.to_numpy()).all():
            raise ValueError("características faltantes en el origen")
        sg = car.sigma(vista)[o]
        out = {}
        for h in self.horizontes:
            zq = np.column_stack([self._predecir_nivel(self.modelos[(h, float(t))], feats)
                                  for t in NIVELES])
            out[h] = np.sort(zq, axis=1) * (sg * np.sqrt(h))[:, None]
        return out


class RegresionCuantiles(_Estandarizado):
    """Regresión por cuantiles lineal (statsmodels QuantReg) con intercepto.

    Con `columnas=[]` es la simulación histórica filtrada (cuantiles incondicionales de z).
    """
    nombre = "reg_cuantiles"

    def _ajustar_nivel(self, X, z, tau):
        if not self.columnas:
            return ("const", float(np.quantile(z, tau)))
        import statsmodels.api as sm
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = sm.QuantReg(z, sm.add_constant(X.to_numpy(float), has_constant="add")).fit(
                q=tau, max_iter=2000)
        b = np.asarray(res.params, float)
        if not np.all(np.isfinite(b)):
            raise RuntimeError("coeficientes no finitos")
        return ("lin", b)

    def _predecir_nivel(self, modelo, X):
        tipo, b = modelo
        if tipo == "const":
            return np.full(len(X), b)
        return b[0] + X.to_numpy(float) @ b[1:]


class LightGBMCuantiles(_Estandarizado):
    """LightGBM con objetivo de cuantil; acepta NaN (series externas con inicio tardío)."""
    nombre = "lightgbm_cuantiles"
    exige_completas = False

    def columnas_por_defecto(self):
        return (car.INTERNAS + car.EXTERNAS_COMPLETAS + car.EXTERNAS_PARCIALES
                + car.EXTERNAS_NIVEL)

    def parametros(self):
        return {**super().parametros(), "lgbm": PARAMS_LGBM}

    def _ajustar_nivel(self, X, z, tau):
        import lightgbm as lgb
        m = lgb.LGBMRegressor(objective="quantile", alpha=tau, random_state=self.semilla, **PARAMS_LGBM)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m.fit(X, z)
        return m

    def _predecir_nivel(self, modelo, X):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return modelo.predict(X)
