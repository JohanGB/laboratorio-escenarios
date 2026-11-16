"""Corredor de backtesting con origen móvil y métricas de resumen."""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from ..evaluacion.cobertura import cobertura_intervalo
from ..evaluacion.origen_movil import bloques, ultimo_origen, verificar_sin_solape
from ..evaluacion.perdidas import (crps_cuantiles, pinball, puntaje_intervalo,
                                   verificar_cuantiles)
from ..modelos.base import Pronosticador
from .datos import Vista
from ..evaluacion.riesgo import es_de_rejilla, rejilla_cola
from .particion import (ALFA_ES, INICIO_DESARROLLO, NIVELES, NIVELES_COLA, PASO_REAJUSTE,
                        PUNTOS_REJILLA_ES)


def primer_origen(vista: Vista, inicio: str = INICIO_DESARROLLO) -> int:
    i = int(vista.fechas.searchsorted(pd.Timestamp(inicio)))
    if i >= vista.n:
        raise ValueError("el inicio del desarrollo es posterior a los datos")
    return i


def _niveles_extendidos(niveles: np.ndarray):
    """Unión ordenada de niveles + NIVELES_COLA + rejillas del ES y dónde cae cada grupo."""
    inf = rejilla_cola(ALFA_ES, PUNTOS_REJILLA_ES, "inf")
    sup = rejilla_cola(ALFA_ES, PUNTOS_REJILLA_ES, "sup")
    red = lambda x: np.round(np.asarray(x, float), 10)
    ext = np.unique(np.concatenate([red(niveles), red(NIVELES_COLA), red(inf), red(sup)]))
    pos = lambda x: np.searchsorted(ext, red(x))
    return ext, pos(niveles), pos(NIVELES_COLA), pos(inf), pos(sup)


def correr(modelo: Pronosticador, vista: Vista, primero: int | None = None,
           ultimo: int | None = None, paso: int = PASO_REAJUSTE,
           niveles: np.ndarray = NIVELES) -> pd.DataFrame:
    """Backtest de origen móvil sobre la vista de desarrollo.

    Devuelve un DataFrame largo con columnas: origen, fecha, h, y, estres, q_<nivel>...
    `ultimo` por defecto = último origen permitido por el embargo (n − 1 − h_max).
    """
    return correr_con_cola(modelo, vista, primero, ultimo, paso, niveles, con_cola=False)[0]


def correr_con_cola(modelo: Pronosticador, vista: Vista, primero: int | None = None,
                    ultimo: int | None = None, paso: int = PASO_REAJUSTE,
                    niveles: np.ndarray = NIVELES, con_cola: bool = True
                    ) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Como `correr`, y además la tabla de cola (o None si el modelo no la puede dar).

    Tabla de cola: origen, fecha, estres, h, y, c_<nivel> (NIVELES_COLA), es_inf, es_sup
    (ES de probabilidad ALFA_ES en cada cola, con su signo). Se pide todo en UNA llamada a
    `pronosticar` (mismas simulaciones), así que la tabla principal es la misma que sin cola.
    """
    con_cola = con_cola and modelo.cola_defendible
    if con_cola:
        pedir, i_niv, i_cola, i_inf, i_sup = _niveles_extendidos(niveles)
    else:
        pedir = niveles
    cols_cola = [f"c_{t:g}" for t in NIVELES_COLA]
    piezas_cola = []
    hmax = max(modelo.horizontes)
    primero = primer_origen(vista) if primero is None else primero
    tope = ultimo_origen(vista.n, hmax)
    ultimo = tope if ultimo is None else min(ultimo, tope)
    objetivos = {h: vista.objetivo(h) for h in modelo.horizontes}
    cols = [f"q_{t:g}" for t in niveles]
    piezas = []
    for b in bloques(primero, ultimo, paso):
        modelo.ajustar(vista.hasta(b.reajuste))
        qx = modelo.pronosticar(vista.hasta(int(b.origenes[-1])), b.origenes, pedir)
        for h in modelo.horizontes:
            verificar_sin_solape(b.origenes, h, vista.n)
            verificar_cuantiles(qx[h], pedir)
            q = {h: qx[h][:, i_niv]} if con_cola else qx
            if con_cola:
                dc = pd.DataFrame(qx[h][:, i_cola], columns=cols_cola)
                dc["es_inf"] = es_de_rejilla(qx[h][:, i_inf])
                dc["es_sup"] = es_de_rejilla(qx[h][:, i_sup])
                piezas_cola.append((h, b.origenes, dc))
            df = pd.DataFrame(q[h], columns=cols)
            df.insert(0, "y", objetivos[h][b.origenes])
            df.insert(0, "h", h)
            df.insert(0, "estres", vista.estres[b.origenes])
            df.insert(0, "fecha", vista.fechas[b.origenes])
            df.insert(0, "origen", b.origenes)
            piezas.append(df)
    out = pd.concat(piezas, ignore_index=True).sort_values(["h", "origen"], ignore_index=True)
    if out["y"].isna().any():
        raise RuntimeError("objetivo faltante en desarrollo (fallo del embargo)")
    if not con_cola:
        return out, None
    colas = []
    for h, origenes, dc in piezas_cola:
        dc.insert(0, "y", objetivos[h][origenes])
        dc.insert(0, "h", h)
        dc.insert(0, "estres", vista.estres[origenes])
        dc.insert(0, "fecha", vista.fechas[origenes])
        dc.insert(0, "origen", origenes)
        colas.append(dc)
    cola = pd.concat(colas, ignore_index=True).sort_values(["h", "origen"], ignore_index=True)
    return out, cola


def resumen(df: pd.DataFrame, niveles: np.ndarray = NIVELES, episodios: bool = False) -> pd.DataFrame:
    """Métricas por horizonte y grupo (todo / estrés / normal; con `episodios`, uno por etiqueta).

    pinball = pérdida de cuantil media sobre todos los niveles; crps = CRPS aproximado por
    cuantiles (truncado en [τ_min, τ_max]); is95 = puntaje de intervalo del 95 %;
    cob90/cob95/cob98 = cobertura real de los intervalos centrales.
    """
    cols = [f"q_{t:g}" for t in niveles]
    pos = {round(float(t), 6): i for i, t in enumerate(niveles)}
    filas = []
    for h, g in df.groupby("h"):
        grupos = [("todo", g), ("estres", g[g["estres"] != ""]), ("normal", g[g["estres"] == ""])]
        if episodios:
            grupos += [(str(e), g[g["estres"] == e]) for e in sorted(set(g["estres"]) - {""})]
        for nombre, sub in grupos:
            if len(sub) == 0:
                continue
            y, q = sub["y"].to_numpy(), sub[cols].to_numpy()
            fila = {"h": h, "grupo": nombre, "n": len(sub),
                    "pinball": float(pinball(y, q, niveles).mean()),
                    "crps": float(crps_cuantiles(y, q, niveles).mean())}
            for etiqueta, (a, b) in {"95": (0.025, 0.975), "90": (0.05, 0.95), "98": (0.01, 0.99)}.items():
                if a in pos and b in pos:
                    lo, hi = q[:, pos[a]], q[:, pos[b]]
                    fila["cob" + etiqueta] = cobertura_intervalo(y, lo, hi)
                    if etiqueta == "95":
                        fila["is95"] = float(puntaje_intervalo(y, lo, hi, 0.05).mean())
            filas.append(fila)
    return pd.DataFrame(filas)


def correr_y_medir(modelo: Pronosticador, vista: Vista, **kw) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    t0 = time.time()
    df = correr(modelo, vista, **kw)
    return df, resumen(df), time.time() - t0
