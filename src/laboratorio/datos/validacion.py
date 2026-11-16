"""Validaciones de series: fechas duplicadas, huecos y saltos.

Reglas (declaradas, no ocultas):
- Fechas posteriores a la fecha de descarga se separan (`fechas_futuras`): son valores
  publicados por adelantado (UVR, tasa de política) y no entran en las demás pruebas.
- Hueco: diferencia entre fechas consecutivas > max(5 días, 1,5 x mediana + 3).
  Con datos diarios eso tolera fines de semana y puentes festivos (hasta 5 días).
- Salto: en series de *nivel* (TRM, UVR, IPC) cambio relativo > 5 %; en series de
  *tasa* (%, variaciones) cambio absoluto > 5 puntos porcentuales, porque un 5 %
  relativo sobre una tasa (4,75 -> 5,00) no es un salto imposible. Series con
  periodicidad mayor a mensual no se prueban en saltos (el agregado lo hace natural).
"""
from __future__ import annotations

import re

import pandas as pd

UMBRAL_SALTO = 0.05          # 5 % relativo (niveles)
UMBRAL_SALTO_PP = 5.0        # 5 pp (tasas)
MAX_PERIODO_SALTOS = 35      # días: solo se prueban series diarias/semanales/mensuales
MUESTRA = 5

_TASA = re.compile(r"tasa|ibr|dtf|variaci|inflaci|fed funds", re.I)
_NIVEL = re.compile(r"UVR\)\(Dato|TRM|ndice de Precios|IPC \(DANE|Brent|dólar amplio", re.I)


def tipo_serie(nombre: str) -> str:
    """'tasa' (porcentaje) o 'nivel' (TRM, UVR, índice)."""
    if re.search(r"variaci|inflaci", nombre, re.I):
        return "tasa"
    if _NIVEL.search(nombre) and not re.search(r"Variaci", nombre, re.I):
        return "nivel"
    return "tasa" if _TASA.search(nombre) else "nivel"


def hueco_maximo(mediana_dias: float) -> float:
    return max(5.0, 1.5 * mediana_dias + 3)


def _muestra(ix) -> list[str]:
    return [pd.Timestamp(x).date().isoformat() for x in list(ix)[:MUESTRA]]


def validar_serie(s: pd.Series, tipo: str = "nivel",
                  corte: pd.Timestamp | None = None) -> dict:
    s = s.dropna()
    n_total = len(s)
    dup_mask = s.index.duplicated(keep=False)
    n_dup = int(s.index.duplicated().sum())
    dup_fechas = s.index[dup_mask].unique()
    s = s[~s.index.duplicated(keep="last")].sort_index()

    n_fut = int((s.index > corte).sum()) if corte is not None else 0
    if corte is not None:
        s = s[s.index <= corte]

    res = {"tipo": tipo, "observaciones": n_total,
           "fecha_min": s.index.min().date().isoformat() if len(s) else None,
           "fecha_max": s.index.max().date().isoformat() if len(s) else None,
           "duplicadas": n_dup, "duplicadas_muestra": _muestra(dup_fechas),
           "fechas_futuras": n_fut,
           "huecos": 0, "huecos_muestra": [], "saltos": 0, "saltos_muestra": [],
           "saltos_probados": False}
    if len(s) < 3:
        return res

    dias = s.index.to_series().diff().dt.days.dropna()
    mediana = float(dias.median())
    huecos = dias[dias > hueco_maximo(mediana)]
    res["mediana_dias"] = mediana
    res["huecos"] = int(len(huecos))
    res["huecos_muestra"] = [f"{d.date()} (+{int(v)} d)"
                             for d, v in huecos.head(MUESTRA).items()]

    if mediana <= MAX_PERIODO_SALTOS:
        cambio = s.diff() if tipo == "tasa" else s.pct_change()
        umbral = UMBRAL_SALTO_PP if tipo == "tasa" else UMBRAL_SALTO
        saltos = cambio[cambio.abs() > umbral].dropna()
        res["saltos_probados"] = True
        res["saltos"] = int(len(saltos))
        res["saltos_muestra"] = [f"{d.date()} ({v:+.3f})"
                                 for d, v in saltos.head(MUESTRA).items()]
    return res


def validar_archivo(series: dict[str, pd.Series], corte: pd.Timestamp | None) -> dict:
    return {nombre: validar_serie(s, tipo_serie(nombre), corte)
            for nombre, s in series.items()}
