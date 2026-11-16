"""Model Confidence Set (Hansen, Lunde y Nason, 2011) sobre una matriz de pérdidas.

Envoltura de `arch.bootstrap.MCS` (única dependencia fuera de numpy/pandas/scipy del paquete
`evaluacion`; se importa al llamar). El MCS es el conjunto de modelos que, con confianza 1 − α,
contiene al mejor: responde a la objeción de comparaciones múltiples (N2), porque compara todos
los candidatos a la vez en lugar de premiar al ganador de muchas pruebas por pares.

- Pérdidas: DataFrame (filas = orígenes comunes, columnas = modelos). Menor = mejor.
- Bootstrap estacionario por bloques; longitud media por defecto máx(2h, 10): las pérdidas a h
  pasos comparten h − 1 observaciones del objetivo.
- Estadístico de rango («R»), α = 0,10, semilla fija → resultado reproducible.
"""
from __future__ import annotations

import pandas as pd

ALFA_MCS = 0.10
REPS_MCS = 5000
SEMILLA_MCS = 20240501


def bloque_por_defecto(h: int) -> int:
    return max(2 * int(h), 10)


def conjunto_confianza(perdidas: pd.DataFrame, h: int = 1, alfa: float = ALFA_MCS,
                       reps: int = REPS_MCS, bloque: int | None = None,
                       semilla: int = SEMILLA_MCS) -> pd.DataFrame:
    """Una fila por modelo: pérdida media, p-valor MCS y si queda en el conjunto superior.

    Ordenado por pérdida media. Filas con NaN se rechazan (use orígenes comunes).
    """
    from arch.bootstrap import MCS
    if perdidas.shape[1] < 2:
        raise ValueError("el MCS necesita al menos dos modelos")
    if perdidas.isna().any().any():
        raise ValueError("pérdidas con NaN: use solo los orígenes comunes a todos los modelos")
    b = bloque_por_defecto(h) if bloque is None else int(bloque)
    # Columnas idénticas (diferencia de pérdidas con varianza cero) rompen el estadístico: se
    # calcula con una representante y las copias heredan su resultado.
    rep = {}
    for c in perdidas.columns:
        rep[c] = next((u for u in rep.values() if perdidas[c].equals(perdidas[u])), c)
    unicas = list(dict.fromkeys(rep.values()))
    if len(unicas) == 1:
        pv, dentro = {unicas[0]: 1.0}, set(unicas)
    else:
        m = MCS(perdidas[unicas], size=alfa, reps=reps, block_size=b, method="R",
                bootstrap="stationary", seed=semilla)
        m.compute()
        pv, dentro = m.pvalues["Pvalue"].to_dict(), set(m.included)
    out = pd.DataFrame({"modelo": perdidas.columns, "perdida": perdidas.mean().to_numpy()})
    out["p_mcs"] = [float(pv[rep[c]]) for c in perdidas.columns]
    out["en_mcs"] = [rep[c] in dentro for c in perdidas.columns]
    out.attrs.update({"alfa": alfa, "reps": reps, "bloque": b, "n": len(perdidas)})
    return out.sort_values("perdida", ignore_index=True)
