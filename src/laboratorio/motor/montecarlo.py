"""Monte Carlo del caso (F5): trayectorias de la TRM con el motor evaluado en la prueba final.

No reescribe el bootstrap. `simular` instancia `BootstrapEstacionario` (modelos/bootstrap.py),
usa su `ajustar` (longitud media de bloque de Politis-White; en la variante filtrada, σ̄² y ρ) y
su función `trayectorias`, con el mismo generador por origen `default_rng([semilla, origen])`.
Con los mismos `sims`, `semilla` y largo, los cuantiles de estas trayectorias son idénticos a los
de `pronosticar` (hay prueba): lo que se simula aquí es lo que se evaluó.

Motores (fijados en el prerregistro, backtest/final.py):
- `bootstrap_est_filtrado`: motor del caso en todos los horizontes.
- `bootstrap_est`: análisis de sensibilidad.
Los dos remuestrean TODA la historia de la serie (banda incluida), como en la evaluación.

El origen es la última observación de la vista. La fila k de `acum` es el rendimiento
logarítmico acumulado a k+1 pasos (un paso = una observación de la serie, un día con TRM).

Análisis posterior (no confirmatorio), F5b: `simular(..., desde=fecha)` remuestrea solo las
observaciones con fecha ≥ `desde` (el régimen de flotación). Es lo ÚNICO que cambia: longitud de
bloque, σ̄, ρ, σ del origen, semilla y generador son los del motor ajustado con toda la historia.
Así la diferencia frente al motor se debe a una sola causa, la muestra. Esa variante no se evaluó
nunca: las coberturas de la prueba final no le aplican. `resumen_regimenes` da las cifras que
explican la diferencia (peso, deriva y choque estandarizado medio de cada tramo).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from ..backtest.datos import Vista, construir_vista
from ..backtest.final import MOTOR_CASO, MOTOR_SENSIBILIDAD
from ..modelos.bootstrap import (MIN_OBS, BootstrapEstacionario, _sigma2_ewma,
                                 residuos_estandarizados, trayectorias)
from .plan import PlanCompra

SEMILLA = 20240501
TRAYECTORIAS = 10_000
LARGO_MIN = 252                                   # el abanico llega al último horizonte evaluado
NIVELES_ABANICO = (0.025, 0.25, 0.5, 0.75, 0.975)  # 0,025-0,975 = el intervalo del 95 % evaluado
FILTRADO = {MOTOR_CASO: True, MOTOR_SENSIBILIDAD: False}


@dataclass(frozen=True)
class Simulacion:
    motor: str
    acum: np.ndarray               # (largo, sims) rendimiento logarítmico acumulado
    bloque: float                  # longitud media de bloque usada
    rho: float | None              # persistencia diaria de la varianza (solo filtrado)
    sigma_origen: float | None     # desvío diario previsto en el origen (solo filtrado)
    sigma_largo: float | None      # desvío diario de largo plazo (solo filtrado)
    origen: int
    semilla: int
    muestra_desde: str | None = None   # None = toda la historia (el motor evaluado)
    n_muestra: int = 0                 # observaciones que entran al remuestreo

    @property
    def sims(self) -> int:
        return self.acum.shape[1]


def vista_trm(df: pd.DataFrame) -> Vista:
    """Vista del backtest a partir de trm.csv (columnas trm, regimen, estres); sin series externas."""
    return construir_vista(df, pd.DataFrame(index=df.index[:0]))


def _serie_con_fecha(vista: Vista, filtrado: bool) -> tuple[np.ndarray, np.ndarray]:
    """La serie que remuestrea el motor (z = r/σ si es filtrado; r si no) y la fecha de cada dato."""
    x = residuos_estandarizados(vista.r) if filtrado else vista.r[1:]
    ok = np.isfinite(x)
    return x[ok], np.asarray(vista.fechas[1:])[ok]


def simular(vista: Vista, motor: str = MOTOR_CASO, sims: int = TRAYECTORIAS, semilla: int = SEMILLA,
            largo: int = LARGO_MIN, bloque: float | None = None, desde=None) -> Simulacion:
    """`sims` trayectorias de `largo` pasos desde la última observación de `vista`.

    `bloque` fija la longitud media de bloque (None = Politis-White); con bloque = 1 se obtiene
    el bootstrap simple (sorteos independientes).
    `desde` (análisis posterior, no confirmatorio): remuestrea solo las observaciones con fecha
    ≥ `desde`; todo lo demás (bloque, σ̄, ρ, σ del origen, generador) es lo del motor ajustado
    con toda la historia. Con `desde=None` el resultado es exactamente el del motor evaluado.
    """
    if motor not in FILTRADO:
        raise ValueError(f"motor desconocido: {motor!r} (use {tuple(FILTRADO)})")
    if sims < 1 or largo < 1:
        raise ValueError("sims y largo deben ser >= 1")
    filtrado = FILTRADO[motor]
    m = BootstrapEstacionario(filtrado=filtrado, sims=sims, semilla=semilla, bloque=bloque,
                              horizontes=(largo,))
    m.ajustar(vista)
    o = vista.n - 1
    x = m._serie(vista.r[: o + 1])                           # igual que en `pronosticar`
    if desde is not None:
        todo, fechas = _serie_con_fecha(vista, filtrado)
        x = todo[fechas >= np.datetime64(pd.Timestamp(desde))]
        if len(x) < MIN_OBS:
            raise ValueError(f"solo {len(x)} observaciones desde {pd.Timestamp(desde).date()}: "
                             f"se requieren al menos {MIN_OBS} para remuestrear")
    rng = np.random.default_rng([semilla, o])
    s2o = float(_sigma2_ewma(vista.r)[o]) if filtrado else None
    esc = m.escala(s2o, largo) if filtrado else None
    acum = trayectorias(x, largo, sims, m.bloque, rng, esc)
    return Simulacion(motor, acum, float(m.bloque), m.rho,
                      float(np.sqrt(s2o)) if filtrado else None,
                      float(np.sqrt(m.sigma2_largo)) if filtrado else None, o, semilla,
                      None if desde is None else str(pd.Timestamp(desde).date()), len(x))


def resumen_regimenes(vista: Vista, desde, sigma_largo: float) -> dict[str, dict]:
    """Por qué cambia el resultado al remuestrear solo desde `desde` (análisis posterior).

    Parte la serie en «antes» (fecha < desde) y «desde» (fecha ≥ desde) y da, de cada tramo:
    n; peso (% de las observaciones); deriva_anual (100 × Σ r / años de calendario del tramo);
    vol_diaria (100 × desvío de r); media_r (100 × media de r, % diario); media_z (media del
    choque estandarizado z = r/σ, lo que remuestrea el motor filtrado); aporte_z (peso × media_z:
    cuánto de la media de z del conjunto pone el tramo) y equiv_diario (100 × media_z ×
    `sigma_largo`: el rendimiento diario medio con que ese tramo entra al motor, % diario).
    Un tramo con menos de 2 observaciones no aparece.
    """
    corte = np.datetime64(pd.Timestamp(desde))
    r, fr = _serie_con_fecha(vista, False)
    z, fz = _serie_con_fecha(vista, True)
    fechas = np.asarray(vista.fechas)
    out = {}
    for nombre, mr, mz in (("antes", fr < corte, fz < corte), ("desde", fr >= corte, fz >= corte)):
        if mr.sum() < 2 or mz.sum() < 2:
            continue
        rr, zz = r[mr], z[mz]
        previa = fechas[fechas < fr[mr][0]]                  # la observación anterior al primer rendimiento
        inicio = previa[-1] if len(previa) else fr[mr][0]
        anios = float((fr[mr][-1] - inicio) / np.timedelta64(1, "D")) / 365.25
        out[nombre] = {"n": int(mr.sum()), "peso": 100.0 * float(mr.mean()),
                       "deriva_anual": 100.0 * float(rr.sum()) / anios,
                       "vol_diaria": 100.0 * float(rr.std(ddof=1)),
                       "media_r": 100.0 * float(rr.mean()), "media_z": float(zz.mean()),
                       "aporte_z": float(zz.sum()) / len(z),
                       "equiv_diario": 100.0 * float(zz.mean()) * float(sigma_largo)}
    return out


def costos(plan: PlanCompra, trm0: float, acum: np.ndarray, pasos: Sequence[int]) -> np.ndarray:
    """Costo en COP del plan en cada trayectoria; la compra i se paga `pasos[i]` pasos después de hoy.

    Paso 0 = hoy (TRM cierta). TRM(k) = trm0·exp(acum[k−1]).
    """
    if not trm0 > 0:
        raise ValueError("trm0 debe ser positiva")
    if len(pasos) != len(plan.meses):
        raise ValueError("se requiere un paso por cada compra")
    if any(k < 0 or k > acum.shape[0] for k in pasos):
        raise ValueError("pasos fuera del largo simulado")
    total = np.zeros(acum.shape[1])
    for usd, k in zip(plan.usd, pasos):
        total += usd * trm0 * (np.exp(acum[k - 1]) if k > 0 else 1.0)
    return total


def bandas(acum: np.ndarray, trm0: float, niveles: Sequence[float] = NIVELES_ABANICO) -> np.ndarray:
    """Cuantiles de la TRM por paso: matriz (largo + 1, niveles); la fila 0 es hoy (trm0)."""
    q = np.quantile(acum, np.asarray(niveles, float), axis=1).T
    return trm0 * np.exp(np.vstack([np.zeros((1, q.shape[1])), q]))


def figura_abanico(trm: np.ndarray, niveles: Sequence[float], pasos: Sequence[int],
                   ruta: str | Path, titulo: str) -> Path:
    """Abanico de la TRM (matplotlib por defecto): mediana, banda central y banda del 95 %."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    trm = np.asarray(trm, float)
    niv = [float(n) for n in niveles]
    i = {n: niv.index(n) for n in NIVELES_ABANICO}
    k = np.arange(len(trm))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.fill_between(k, trm[:, i[0.025]], trm[:, i[0.975]], alpha=0.25, label="Percentiles 2,5 a 97,5")
    ax.fill_between(k, trm[:, i[0.25]], trm[:, i[0.75]], alpha=0.45, label="Percentiles 25 a 75")
    ax.plot(k, trm[:, i[0.5]], label="Mediana")
    for j, p in enumerate(p for p in pasos if p > 0):
        ax.axvline(p, linestyle=":", linewidth=0.8, label="Compras del plan" if j == 0 else None)
    ax.set_xlabel("Días con TRM desde hoy")
    ax.set_ylabel("TRM (COP/USD)")
    ax.set_title(titulo)
    ax.legend(loc="upper left")
    fig.tight_layout()
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=120)
    plt.close(fig)
    return ruta
