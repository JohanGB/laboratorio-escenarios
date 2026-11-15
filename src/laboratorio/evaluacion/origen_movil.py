"""Aritmética de índices del backtesting con origen móvil (sin fuga), independiente del dominio.

Convención: las observaciones se indexan 0..n-1 en orden temporal. Un *origen* t es un instante
en el que se emite un pronóstico usando solo datos con índice <= t. El objetivo a horizonte h
es lo que ocurre en t + h, que NO se conoce en t.
- Reajuste: cada `paso` orígenes se reestiman los parámetros con datos <= t0 (el primer origen
  del bloque); dentro del bloque los parámetros quedan congelados y solo se actualiza el estado.
- Purga: para entrenar un modelo supervisado a horizonte h en el instante t solo valen las
  muestras s con s + h <= t (su objetivo ya era conocido).
- Embargo: el último origen de desarrollo deja h_max observaciones antes del corte, de modo
  que ningún objetivo de desarrollo toca la prueba final.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Bloque:
    reajuste: int            # último índice que puede usarse para estimar (= primer origen)
    origenes: np.ndarray     # orígenes (índices) cubiertos con esos parámetros

    def __post_init__(self) -> None:
        if len(self.origenes) == 0 or self.origenes[0] != self.reajuste:
            raise ValueError("el primer origen del bloque debe ser el índice de reajuste")


def ultimo_origen(indice_corte: int, h_max: int) -> int:
    """Último origen permitido: su objetivo más lejano (origen + h_max) cae antes del corte."""
    if h_max < 1:
        raise ValueError("h_max debe ser >= 1")
    return indice_corte - 1 - h_max


def bloques(primer: int, ultimo: int, paso: int) -> list[Bloque]:
    """Particiona los orígenes primer..ultimo (inclusive) en bloques de `paso` con reajuste."""
    if paso < 1:
        raise ValueError("paso debe ser >= 1")
    if ultimo < primer:
        raise ValueError("no hay orígenes: ultimo < primer")
    return [Bloque(t0, np.arange(t0, min(t0 + paso, ultimo + 1)))
            for t0 in range(primer, ultimo + 1, paso)]


def indices_entrenamiento(t: int, h: int, primero: int = 0) -> np.ndarray:
    """Muestras s utilizables a horizonte h en el instante t (con purga): s + h <= t."""
    if h < 1:
        raise ValueError("h debe ser >= 1")
    return np.arange(primero, t - h + 1)


def verificar_sin_solape(origenes, h: int, indice_corte: int) -> None:
    """Falla si el objetivo (origen + h) de algún origen cae en o después del corte."""
    o = np.asarray(origenes)
    if len(o) and int(o.max()) + h >= indice_corte:
        raise ValueError(f"el origen {int(o.max())} con h={h} alcanza el índice {int(o.max()) + h}, "
                         f"que es >= al corte {indice_corte} (prueba final)")
