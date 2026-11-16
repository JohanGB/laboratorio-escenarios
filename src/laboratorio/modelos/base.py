"""Interfaz común de los pronosticadores probabilísticos.

Contrato anti-fuga:
- `ajustar(vista)` recibe una vista recortada al índice de reajuste t0: puede usar solo eso.
- `pronosticar(vista, origenes, niveles)` recibe una vista hasta el último origen del bloque.
  Para cada origen o, la salida SOLO puede depender de vista.hasta(o) y de los parámetros
  ajustados. Se verifica con `tests/test_sin_fuga.py` (la salida en o no cambia si se
  recorta la vista en o).
La salida es {h: array (n_origenes, n_niveles)} con cuantiles del rendimiento logarítmico
acumulado a h pasos, no decrecientes en el nivel.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from ..backtest.datos import Vista
from ..backtest.particion import HORIZONTES


class Pronosticador(ABC):
    nombre: str = "modelo"
    # ¿Puede dar cuantiles extremos (NIVELES_COLA y la rejilla del ES) defendibles? Los modelos que
    # simulan o tienen forma cerrada, sí. Los que entrenan un modelo por nivel, no: lo declaran.
    cola_defendible: bool = True
    motivo_sin_cola: str = ""

    def __init__(self, horizontes=HORIZONTES) -> None:
        self.horizontes = tuple(horizontes)

    def ajustar(self, vista: Vista) -> None:           # por defecto: sin parámetros
        return None

    @abstractmethod
    def pronosticar(self, vista: Vista, origenes: np.ndarray,
                    niveles: np.ndarray) -> dict[int, np.ndarray]:
        ...

    def parametros(self) -> dict:
        """Hiperparámetros fijados de antemano (para la ficha de la corrida)."""
        return {}
