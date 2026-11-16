"""Reproducción histórica (sección 5.3): aplicar a un plan los movimientos reales de la TRM.

Dos modos para una ventana que empieza en `inicio`:
- "calendario":   cada compra se paga a la TRM real de la fecha inicio + m meses
                  (qué habría costado el plan en esa época).
- "movimientos":  se toma la razón TRM(inicio + m meses) / TRM(inicio) y se aplica a la TRM
                  de hoy (qué costaría el plan hoy si el mercado se repitiera).
Fechas sin dato (fin de semana, festivo) usan la última TRM anterior; nunca se usan datos
posteriores a la fecha de la compra. Una ventana que no cabe en los datos lanza error.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .plan import PlanCompra, ResultadoPlan, evaluar

MODOS = ("calendario", "movimientos")


def desplazar_meses(fecha, k: int) -> pd.Timestamp:
    return pd.Timestamp(fecha) + pd.DateOffset(months=int(k))


def _asof_pos(trm: pd.Series, fechas) -> np.ndarray:
    return trm.index.searchsorted(pd.DatetimeIndex(fechas), side="right") - 1


def trms_ventana(trm: pd.Series, inicio, meses) -> np.ndarray:
    """TRM real en inicio + m meses (última observación <= esa fecha)."""
    ini = pd.Timestamp(inicio)
    if ini < trm.index[0]:
        raise ValueError(f"inicio {ini.date()} es anterior a los datos ({trm.index[0].date()})")
    fin = desplazar_meses(ini, max(meses))
    if fin > trm.index[-1]:
        raise ValueError(f"la ventana termina {fin.date()}, después del último dato "
                         f"({trm.index[-1].date()})")
    objetivos = [desplazar_meses(ini, m) for m in meses]
    return trm.to_numpy()[_asof_pos(trm, objetivos)]


def ratios_ventana(trm: pd.Series, inicio, meses) -> np.ndarray:
    """TRM(inicio + m) / TRM(inicio); el de m = 0 es exactamente 1."""
    niveles = trms_ventana(trm, inicio, meses)
    base = trms_ventana(trm, inicio, [0])[0]
    return niveles / base


def reproducir(plan: PlanCompra, trm: pd.Series, inicio, modo: str = "movimientos",
               trm0: float | None = None) -> ResultadoPlan:
    if modo not in MODOS:
        raise ValueError(f"modo desconocido: {modo!r}")
    if modo == "calendario":
        return evaluar(plan, trms_ventana(trm, inicio, plan.meses))
    if trm0 is None or not trm0 > 0:
        raise ValueError("el modo 'movimientos' requiere trm0 > 0 (TRM de hoy)")
    return evaluar(plan, trm0 * ratios_ventana(trm, inicio, plan.meses))


# --- todas las ventanas -----------------------------------------------------------------
@dataclass(frozen=True)
class DistribucionHistorica:
    inicios: pd.DatetimeIndex
    costos: np.ndarray             # COP, uno por ventana (modo movimientos)
    costo_hoy: float               # COP de comprar todo hoy (referencia, no aleatorio)

    def __len__(self) -> int:
        return len(self.costos)

    def percentil(self, q: float) -> float:
        return float(np.percentile(self.costos, q))

    def prob_superar(self, presupuesto_cop: float) -> float:
        return float(np.mean(self.costos > presupuesto_cop))

    def prob_mas_barato_que_hoy(self) -> float:
        return float(np.mean(self.costos < self.costo_hoy))

    def resumen(self, presupuesto_cop: float) -> dict:
        c = self.costos
        return {"ventanas": len(c), "media": float(c.mean()), "desv": float(c.std(ddof=1)),
                "p5": self.percentil(5), "p50": self.percentil(50), "p95": self.percentil(95),
                "min": float(c.min()), "max": float(c.max()),
                "inicio_min": self.inicios[int(c.argmin())], "inicio_max": self.inicios[int(c.argmax())],
                "prob_superar_presupuesto": self.prob_superar(presupuesto_cop),
                "prob_mas_barato_que_hoy": self.prob_mas_barato_que_hoy()}


def ratios_todas(trm: pd.Series, plan: PlanCompra, desde) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Matriz (ventanas x compras) de razones, para toda fecha de inicio >= desde que quepa."""
    limite = desplazar_meses(trm.index[-1], -plan.horizonte_meses)
    inicios = trm.index[(trm.index >= pd.Timestamp(desde)) & (trm.index <= limite)]
    if len(inicios) == 0:
        raise ValueError("ninguna ventana cabe en los datos con ese plan y fecha 'desde'")
    niveles = np.column_stack([
        trm.to_numpy()[_asof_pos(trm, inicios + pd.DateOffset(months=m))] for m in plan.meses])
    return inicios, niveles / trm.loc[inicios].to_numpy()[:, None]


def pasos_por_compra(trm: pd.Series, plan: PlanCompra, desde) -> tuple[int, ...]:
    """Observaciones de la serie (días con TRM) entre hoy y cada compra del plan.

    Mediana, sobre las mismas ventanas de `ratios_todas`, del número de observaciones entre el
    inicio y inicio + m meses. Así el Monte Carlo (que avanza por observaciones) y la
    distribución histórica (que avanza por meses de calendario) usan la misma escala de tiempo.
    La compra de hoy (m = 0) queda en el paso 0.
    """
    limite = desplazar_meses(trm.index[-1], -plan.horizonte_meses)
    inicios = trm.index[(trm.index >= pd.Timestamp(desde)) & (trm.index <= limite)]
    if len(inicios) == 0:
        raise ValueError("ninguna ventana cabe en los datos con ese plan y fecha 'desde'")
    base = _asof_pos(trm, inicios)
    return tuple(int(np.floor(np.median(_asof_pos(trm, inicios + pd.DateOffset(months=m)) - base)
                              + 0.5)) for m in plan.meses)


def distribucion(plan: PlanCompra, trm: pd.Series, trm0: float, desde) -> DistribucionHistorica:
    """Costo en COP del plan, hoy, bajo cada ventana histórica real (empírica, sin supuestos).

    Las ventanas se traslapan: sus resultados no son independientes, así que los percentiles
    extremos descansan en pocos episodios distintos (ver n efectivo en el reporte).
    """
    if not trm0 > 0:
        raise ValueError("trm0 debe ser positiva")
    inicios, r = ratios_todas(trm, plan, desde)
    costos = (r * np.asarray(plan.usd)[None, :]).sum(axis=1) * trm0
    return DistribucionHistorica(inicios, costos, plan.meta_usd * trm0)
