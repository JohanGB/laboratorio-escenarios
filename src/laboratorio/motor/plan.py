"""Plan de compra de dólares para una meta (caso 1 de la sección 8).

Un plan es un conjunto de compras en USD en desplazamientos de meses desde hoy (0 = hoy).
El costo en COP de cada compra es usd_i x TRM(mes_i). No se modela rendimiento del dinero
mientras espera (limitación declarada: ignora el costo de oportunidad de comprar antes).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class PlanCompra:
    meses: tuple[int, ...]
    usd: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.meses) != len(self.usd) or not self.meses:
            raise ValueError("meses y usd deben tener el mismo largo (>= 1)")
        if any(m < 0 for m in self.meses) or any(b <= a for a, b in zip(self.meses, self.meses[1:])):
            raise ValueError("meses deben ser >= 0 y estrictamente crecientes")
        if any(not u > 0 for u in self.usd):
            raise ValueError("cada compra debe ser > 0 USD")

    @property
    def meta_usd(self) -> float:
        return float(sum(self.usd))

    @property
    def horizonte_meses(self) -> int:
        return self.meses[-1]

    @staticmethod
    def todo_hoy(meta_usd: float) -> "PlanCompra":
        return PlanCompra((0,), (float(meta_usd),))

    @staticmethod
    def escalonado(meta_usd: float, n: int, intervalo_meses: int = 1) -> "PlanCompra":
        """n compras iguales; la primera hoy y luego cada `intervalo_meses`."""
        if n < 1 or intervalo_meses < 1 or not meta_usd > 0:
            raise ValueError("meta > 0, n >= 1 e intervalo >= 1")
        return PlanCompra(tuple(i * intervalo_meses for i in range(n)),
                          tuple(float(meta_usd) / n for _ in range(n)))

    def escalar(self, k: float) -> "PlanCompra":
        return PlanCompra(self.meses, tuple(u * k for u in self.usd))


@dataclass(frozen=True)
class ResultadoPlan:
    usd_total: float
    costo_cop: float
    costo_medio: float            # COP por USD
    trms: tuple[float, ...]

    def se_pasa(self, presupuesto_cop: float) -> bool:
        return self.costo_cop > presupuesto_cop

    def arrepentimiento(self, costo_referencia_cop: float) -> float:
        """Costo menos el de referencia (p. ej. comprar todo hoy). > 0 = salió más caro."""
        return self.costo_cop - costo_referencia_cop


def evaluar(plan: PlanCompra, trms: Sequence[float]) -> ResultadoPlan:
    """Costo del plan con la TRM de cada fecha de compra (alineada con plan.meses)."""
    if len(trms) != len(plan.meses):
        raise ValueError("se requiere una TRM por cada compra")
    if any(not t > 0 for t in trms):
        raise ValueError("TRM debe ser positiva")
    costo = sum(u * t for u, t in zip(plan.usd, trms))
    total = plan.meta_usd
    return ResultadoPlan(usd_total=total, costo_cop=costo, costo_medio=costo / total,
                         trms=tuple(float(t) for t in trms))
