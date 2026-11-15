"""Características causales para los modelos de cuantiles.

Contrato: la fila t de `construir(vista)` solo depende de datos con fecha ≤ fechas[t] (las series
externas, además, con su rezago de publicación). Se verifica en tests comparando la fila t calculada
con la vista completa contra la calculada con `vista.hasta(t)`.

Objetivo estandarizado: z_h = y_h / (σ_t·√h), con σ_t = raíz de la varianza EWMA(0,94) a un paso
conocida en t. Los modelos predicen cuantiles de z y se desestandariza con σ_t·√h.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .lineas_base import varianza_ewma

LAM_CORTA, LAM_LARGA = 0.94, 0.99
CALENTAMIENTO = 260          # observaciones mínimas antes de que existan todas las características internas
REZAGO_DIAS = {"brent_usd": 3, "dolar_amplio": 8, "fed_funds": 2, "politica": 1}   # publicación

INTERNAS = ["lsig", "lratio", "z1", "z5", "z21", "z63", "dist252", "banda"]
EXTERNAS_COMPLETAS = ["brent30", "fed90"]                 # cambios; existen desde antes de 2005
EXTERNAS_PARCIALES = ["dolar30", "pol90"]                 # cambios; con huecos al inicio (NaN)
# Niveles no estacionarios: solo para árboles (extrapolan plano). Un nivel como regresor lineal de
# cuantiles produjo subcobertura (95 % → 79 % a h=21, 70 % a h=63) en datos simulados GARCH.
EXTERNAS_NIVEL = ["fed", "pol"]


def sigma(vista) -> np.ndarray:
    """σ_t: desvío diario previsto para t+1 con información hasta t (EWMA 0,94)."""
    return np.sqrt(np.maximum(varianza_ewma(vista.r, LAM_CORTA)[: vista.n], 1e-12))


def _valor_en(serie: pd.Series, fechas: pd.DatetimeIndex, rezago: int, atras: int = 0) -> np.ndarray:
    """Último valor publicado en (fecha − rezago − atras) días; NaN si aún no hay."""
    s = serie.dropna()
    if s.empty:
        return np.full(len(fechas), np.nan)
    corte = fechas - pd.Timedelta(days=rezago + atras)
    pos = s.index.searchsorted(corte, side="right") - 1
    out = np.where(pos >= 0, s.to_numpy()[np.maximum(pos, 0)], np.nan)
    return out.astype(float)


def construir(vista) -> pd.DataFrame:
    n, lp, f = vista.n, vista.logp, vista.fechas
    sg = sigma(vista)
    sg_larga = np.sqrt(np.maximum(varianza_ewma(vista.r, LAM_LARGA)[:n], 1e-12))
    d = pd.DataFrame(index=f)
    d["lsig"] = np.log(sg)
    d["lratio"] = np.log(sg / sg_larga)
    prev = np.concatenate([[np.nan], sg[:-1]])
    d["z1"] = vista.r / prev
    for k in (5, 21, 63):
        cam = np.full(n, np.nan); cam[k:] = lp[k:] - lp[:-k]
        d[f"z{k}"] = cam / (sg * np.sqrt(k))
    media = pd.Series(lp).rolling(252, min_periods=252).mean().to_numpy()
    d["dist252"] = (lp - media) / (sg * np.sqrt(252))
    d["banda"] = vista.banda.astype(float)
    ex = vista.externas
    L = REZAGO_DIAS
    d["brent30"] = np.log(_valor_en(ex["brent_usd"], f, L["brent_usd"]) /
                          _valor_en(ex["brent_usd"], f, L["brent_usd"], 30))
    d["fed"] = _valor_en(ex["fed_funds"], f, L["fed_funds"])
    d["fed90"] = d["fed"] - _valor_en(ex["fed_funds"], f, L["fed_funds"], 90)
    d["dolar30"] = np.log(_valor_en(ex["dolar_amplio"], f, L["dolar_amplio"]) /
                          _valor_en(ex["dolar_amplio"], f, L["dolar_amplio"], 30))
    d["pol"] = _valor_en(ex["politica"], f, L["politica"])
    d["pol90"] = d["pol"] - _valor_en(ex["politica"], f, L["politica"], 90)
    return d.replace([np.inf, -np.inf], np.nan)
