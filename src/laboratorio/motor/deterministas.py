"""Escenarios deterministas (base, optimista, estrés) para la TRM.

La TRM sigue una trayectoria exponencial desde la TRM de hoy:
    TRM(m) = TRM0 * exp(g * m / 12),  g = deriva anual logarítmica (supuesto versionado).
Para quien compra dólares, "optimista" = TRM más baja (g menor) y "estrés" = TRM más alta.
"""
from __future__ import annotations

import math
from typing import Sequence

from .plan import PlanCompra, ResultadoPlan, evaluar
from .supuestos import ConjuntoSupuestos

ESCENARIOS = ("optimista", "base", "estres")
PREFIJO = "trm.deriva_anual_log."


def id_deriva(nombre: str) -> str:
    if nombre not in ESCENARIOS:
        raise ValueError(f"escenario desconocido: {nombre!r} (use {ESCENARIOS})")
    return PREFIJO + nombre


def trayectoria(trm0: float, deriva_anual_log: float, meses: Sequence[int]) -> list[float]:
    if not trm0 > 0:
        raise ValueError("TRM0 debe ser positiva")
    return [trm0 * math.exp(deriva_anual_log * m / 12.0) for m in meses]


def validar_orden(conjunto: ConjuntoSupuestos) -> None:
    """Exige deriva optimista <= base <= estrés (si no, los nombres no tendrían sentido)."""
    g = [float(conjunto.valor(id_deriva(n))) for n in ESCENARIOS]
    if not (g[0] <= g[1] <= g[2]):
        raise ValueError(f"deriva fuera de orden (optimista, base, estrés) = {g}")


def correr(plan: PlanCompra, trm0: float, conjunto: ConjuntoSupuestos,
           nombre: str) -> ResultadoPlan:
    validar_orden(conjunto)
    g = float(conjunto.valor(id_deriva(nombre)))
    return evaluar(plan, trayectoria(trm0, g, plan.meses))


def correr_todos(plan: PlanCompra, trm0: float,
                 conjunto: ConjuntoSupuestos) -> dict[str, ResultadoPlan]:
    return {n: correr(plan, trm0, conjunto, n) for n in ESCENARIOS}
