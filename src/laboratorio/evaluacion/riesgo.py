"""VaR en ambas colas, semáforo de Basilea, Expected Shortfall y prueba Z2 de Acerbi-Székely.

Independiente del dominio. Convención de colas sobre una variable y con cuantiles pronosticados:
- cola "inf": violación si y < q_p            (aquí: caída del dólar);
- cola "sup": violación si y > q_{1−p}        (aquí: alza del dólar).
Las pruebas de violaciones suponen observaciones sin traslape (h = 1).

ES por rejilla: ES_α = (1/α)·∫_0^α q(u) du, aproximado con la regla del punto medio sobre m
cuantiles u_i = (i + ½)·α/m. Con simulaciones equivale a promediar la cola simulada.

Z2 (Acerbi y Székely, 2014), escrito con rendimientos y sin cambiar signos:
    Z2 = 1 − (1/(T·α)) · Σ_t I_t · y_t / ES_t,      I_t = 1{violación del VaR_α},
donde ES_t = E[y | y más allá del VaR] lleva el signo de la cola (negativo en "inf", positivo en
"sup"). Bajo H0 (VaR y ES correctos) E[Z2] = 0; Z2 < 0 indica riesgo de cola subestimado. Umbrales
de referencia del artículo, estables entre distribuciones: −0,70 (5 %) y −1,8 (0,01 %).
"""
from __future__ import annotations

import numpy as np

from .pruebas import christoffersen, kupiec

Z2_CRITICO_5 = -0.70
Z2_CRITICO_001 = -1.8
ZONAS_BASILEA = {"verde": (0, 4), "amarillo": (5, 9), "rojo": (10, None)}   # ventana 250, VaR 99 %


def violaciones(y, q, cola: str) -> np.ndarray:
    y, q = np.asarray(y, float), np.asarray(q, float)
    if y.shape != q.shape:
        raise ValueError("y y q con forma distinta")
    if cola == "inf":
        return y < q
    if cola == "sup":
        return y > q
    raise ValueError("cola debe ser 'inf' o 'sup'")


def prueba_var(y, q, p: float, cola: str) -> dict:
    """Kupiec y Christoffersen para el VaR de probabilidad p en la cola indicada."""
    v = violaciones(y, q, cola)
    k, c = kupiec(v, p), christoffersen(v, p)
    return {"n": len(v), "violaciones": int(v.sum()), "tasa": float(v.mean()), "p": p,
            "p_uc": k.p_valor, "p_ind": c["independencia"].p_valor,
            "p_cc": c["condicional"].p_valor}


def semaforo_basilea(viol, ventana: int = 250) -> dict:
    """Excepciones en cada ventana móvil de `ventana` obs. y % de ventanas por zona.

    Zonas del Comité de Basilea para VaR al 99 % y 250 días: verde 0-4, amarillo 5-9, rojo ≥ 10.
    """
    v = np.asarray(viol, dtype=int)
    if len(v) < ventana:
        raise ValueError("menos observaciones que la ventana")
    c = np.concatenate([[0], np.cumsum(v)])
    x = c[ventana:] - c[:-ventana]                       # excepciones por ventana
    out = {"ventanas": len(x), "max": int(x.max()), "media": float(x.mean())}
    for zona, (a, b) in ZONAS_BASILEA.items():
        out[zona] = float(np.mean((x >= a) & (x <= (b if b is not None else np.inf))))
    return out


def rejilla_cola(alfa: float, puntos: int, cola: str) -> np.ndarray:
    """Niveles u_i de la regla del punto medio para la cola (crecientes)."""
    if not 0 < alfa < 0.5 or puntos < 1:
        raise ValueError("se requiere 0 < alfa < 0,5 y puntos ≥ 1")
    u = (np.arange(puntos) + 0.5) * alfa / puntos
    if cola == "inf":
        return u
    if cola == "sup":
        return (1.0 - u)[::-1]
    raise ValueError("cola debe ser 'inf' o 'sup'")


def es_de_rejilla(q_rejilla) -> np.ndarray:
    """ES por fila: promedio de los cuantiles de `rejilla_cola` (forma (n, m) → (n,))."""
    q = np.asarray(q_rejilla, float)
    if q.ndim != 2:
        raise ValueError("q_rejilla debe ser (n, m)")
    return q.mean(axis=1)


def acerbi_szekely_z2(y, var, es, alfa: float, cola: str) -> dict:
    y, var, es = (np.asarray(a, float) for a in (y, var, es))
    if not (y.shape == var.shape == es.shape) or y.ndim != 1 or len(y) == 0:
        raise ValueError("y, var y es deben ser vectores del mismo largo")
    signo = -1.0 if cola == "inf" else 1.0
    if np.any(signo * es <= 0):
        raise ValueError("el ES debe tener el signo de la cola (negativo en 'inf', positivo en 'sup')")
    v = violaciones(y, var, cola)
    T = len(y)
    z2 = 1.0 - float(np.sum(y[v] / es[v])) / (T * alfa)
    return {"z2": z2, "n": T, "violaciones": int(v.sum()), "esperadas": T * alfa,
            "exceso_medio": float(np.mean(y[v] / es[v])) if v.any() else float("nan"),
            "rechaza_5": bool(z2 < Z2_CRITICO_5), "rechaza_001": bool(z2 < Z2_CRITICO_001)}
