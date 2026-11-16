"""Reporte de la fase 2: comparación de modelos en el backtest de desarrollo (reports/fase2.md).

Criterio de descarte (fijado antes de ver resultados):
- Por horizonte h, la referencia es la MEJOR línea base (menor CRPS medio en h, muestra completa).
- Un candidato SUPERA su línea base en h si su CRPS medio es menor y la prueba de Diebold-Mariano
  unilateral (pérdida = CRPS por origen, HAC Bartlett con h−1+⌊4(n/100)^(2/9)⌋ rezagos y corrección
  HLN) da p < 0,05. Si no, queda DESCARTADO en ese horizonte.
- Estado global: DESCARTADO si no supera la línea base en ningún horizonte.
Kupiec y Christoffersen se aplican solo a h=1 (sin traslape), en las colas de 1 % y 5 %.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..backtest.catalogo import LINEAS_BASE
from ..backtest.corredor import resumen
from ..backtest.particion import (HORIZONTES, INICIO_DESARROLLO, INICIO_PRUEBA_FINAL,
                                  NIVELES)
from ..evaluacion.perdidas import crps_cuantiles
from ..evaluacion.pruebas import christoffersen, diebold_mariano, kupiec

ALFA = 0.05
COLS = [f"q_{t:g}" for t in NIVELES]
COLAS = {"inf 1 %": ("q_0.01", 0.01, "inf"), "inf 5 %": ("q_0.05", 0.05, "inf"),
         "sup 5 %": ("q_0.95", 0.05, "sup"), "sup 1 %": ("q_0.99", 0.01, "sup")}


def tabla(df: pd.DataFrame) -> str:
    cab = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    filas = ["| " + " | ".join(str(v) for v in fila) + " |" for fila in df.itertuples(index=False)]
    return "\n".join([cab, sep, *filas])


def cargar(directorio: Path) -> tuple[dict[str, pd.DataFrame], dict[str, dict]]:
    res, meta = {}, {}
    for f in sorted(directorio.glob("*.csv.gz")):
        nombre = f.name[: -len(".csv.gz")]
        df = pd.read_csv(f, parse_dates=["fecha"])
        df["estres"] = df["estres"].fillna("")
        res[nombre] = df
        j = f.with_name(nombre + ".json")
        meta[nombre] = json.loads(j.read_text(encoding="utf-8")) if j.exists() else {}
    return res, meta


def crps_por_origen(df: pd.DataFrame, h: int) -> pd.Series:
    s = df[df["h"] == h]
    return pd.Series(crps_cuantiles(s["y"].to_numpy(), s[COLS].to_numpy(), NIVELES),
                     index=s["origen"].to_numpy())


def comparar(res: dict[str, pd.DataFrame], bases=LINEAS_BASE) -> pd.DataFrame:
    """Una fila por (candidato, h): CRPS relativo a la mejor línea base, DM y estado."""
    bases = [b for b in bases if b in res]
    if not bases:
        raise ValueError("no hay resultados de líneas base")
    filas = []
    for h in sorted(set().union(*[set(d["h"]) for d in res.values()])):
        crps = {m: crps_por_origen(d, h) for m, d in res.items()}
        ref = min(bases, key=lambda b: crps[b].mean())
        for m in res:
            if m in bases:
                continue
            comun = crps[m].index.intersection(crps[ref].index)
            a, b = crps[m].loc[comun].to_numpy(), crps[ref].loc[comun].to_numpy()
            dm = diebold_mariano(a, b, h=h)
            supera = bool(a.mean() < b.mean() and dm.p_valor < ALFA)
            filas.append({"modelo": m, "h": h, "linea_base": ref, "crps": a.mean(), "crps_base": b.mean(),
                          "relativo": a.mean() / b.mean(), "dm_t": dm.estadistico, "dm_p": dm.p_valor,
                          "rezagos": dm.detalle["rezagos"], "n": len(comun),
                          "estado": "supera" if supera else "descartado"})
    return pd.DataFrame(filas)


def pruebas_var(df: pd.DataFrame) -> dict[str, tuple]:
    s = df[df["h"] == 1].sort_values("origen")
    out = {}
    for etiqueta, (col, p, lado) in COLAS.items():
        v = (s["y"] < s[col]) if lado == "inf" else (s["y"] > s[col])
        k = kupiec(v.to_numpy(), p)
        c = christoffersen(v.to_numpy(), p)
        out[etiqueta] = (k.detalle["tasa"], k.p_valor, c["independencia"].p_valor, c["condicional"].p_valor)
    return out


def _otros_pasos(meta: dict[str, dict]) -> str:
    """« (markov_3 y lightgbm_cuantiles cada 63)» según el paso de reajuste guardado en cada corrida."""
    otros: dict[int, list[str]] = {}
    for m, md in sorted(meta.items()):
        paso = md.get("paso_reajuste")
        if paso and paso != 21:
            otros.setdefault(int(paso), []).append(m)
    return "".join(f" ({' y '.join(ms)} cada {p})" for p, ms in sorted(otros.items()))


def _f(x, d=3):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


def _p(x):
    return "<0,001" if x < 0.001 else f"{x:.3f}"


def generar(raiz: str | Path = ".", directorio: str | Path | None = None,
            salida: str | Path | None = None, directorio_largo: str | Path | None = None,
            reps_mcs: int | None = None) -> Path:
    from ..evaluacion.mcs import REPS_MCS
    from .pruebas_f2 import secciones
    raiz = Path(raiz)
    directorio = Path(directorio) if directorio else raiz / "runs" / "backtest_desarrollo"
    salida = Path(salida) if salida else raiz / "reports" / "fase2.md"
    directorio_largo = Path(directorio_largo) if directorio_largo else directorio.parent / "backtest_largo"
    res_largo = cargar(directorio_largo)[0] if directorio_largo.exists() else {}
    res, meta = cargar(directorio)
    if not res:
        raise FileNotFoundError(f"sin resultados en {directorio}")
    cmp_ = comparar(res)
    res_sum = {m: resumen(d, episodios=True) for m, d in res.items()}
    estado_h = {(r.modelo, r.h): r for r in cmp_.itertuples()}
    globales = {m: ("línea base" if m in LINEAS_BASE else
                    "SUPERA" if (cmp_[(cmp_.modelo == m)].estado == "supera").any() else "DESCARTADO")
                for m in res}
    ej = next(iter(res.values()))
    L = [f"# Fase 2 — Comparación de modelos (backtest de desarrollo)", "",
         "Distribuciones de pronóstico del rendimiento logarítmico de la TRM a h observaciones (días de "
         "mercado). Los rangos describen incertidumbre estadística; no son recomendaciones financieras.", "",
         "## Protocolo", "",
         f"- Orígenes: {str(ej['fecha'].min())[:10]} a {str(ej['fecha'].max())[:10]} "
         f"({ej['origen'].nunique()} por horizonte); inicio de desarrollo {INICIO_DESARROLLO}. "
         f"La prueba final (desde {INICIO_PRUEBA_FINAL}) NO se cargó.",
         "- Ventana expansiva, reajuste cada 21 orígenes" + _otros_pasos(meta) + ", purga s+h ≤ t, embargo de 63 obs.",
         "- CRPS aproximado por 11 cuantiles (0,01–0,99), en puntos porcentuales de rendimiento log; "
         "menor es mejor. IS95 = puntaje de intervalo del 95 %. cob = cobertura observada.",
         "- **Criterio de descarte** (fijado antes de correr): en cada horizonte la referencia es la mejor "
         "línea base (caminata aleatoria, simulación histórica 756 obs., simulación histórica ponderada "
         "λ=0,994). Un candidato *supera* si su CRPS medio es menor y Diebold-Mariano unilateral (HAC, "
         "corrección HLN) da p < 0,05; si no, queda **descartado** en ese horizonte. Global: descartado "
         "si no supera en ningún horizonte.",
         "- Los orígenes se traslapan para h>1: las coberturas a h=21 y 63 tienen pocas observaciones "
         "independientes (≈ n/h) y su error estándar es grande.", "",
         "## Resumen por modelo", ""]
    filas = []
    for m in res:
        md = meta.get(m, {})
        sup = [str(h) for h in HORIZONTES if (m, h) in estado_h and estado_h[(m, h)].estado == "supera"]
        filas.append([m, "línea base" if m in LINEAS_BASE else "candidato",
                      ", ".join(sup) if sup else ("—" if m in LINEAS_BASE else "ninguno"),
                      f"**{globales[m]}**" if globales[m] != "línea base" else globales[m],
                      md.get("segundos", "—"), md.get("fallos_estimacion", "—")])
    L += [tabla(pd.DataFrame(filas, columns=["modelo", "tipo", "supera en h", "estado", "segundos",
                                             "fallos de estimación"])), ""]

    for h in HORIZONTES:
        L += [f"## Horizonte h = {h}", "", "### Muestra completa", ""]
        filas = []
        for m in res:
            r = res_sum[m].query(f"h=={h} and grupo=='todo'").iloc[0]
            c = estado_h.get((m, h))
            filas.append([m + (" *(línea base)*" if m in LINEAS_BASE else ""), _f(100 * r.crps, 4),
                          _f(100 * r.pinball, 4), _f(100 * r.is95, 3), _f(r.cob90, 3), _f(r.cob95, 3),
                          _f(r.cob98, 3), _f(c.relativo, 3) if c else "—", _p(c.dm_p) if c else "—",
                          (f"**{c.estado}**" if c.estado == "descartado" else c.estado) if c else "—"])
        filas.sort(key=lambda f: float(f[1]))
        L += [tabla(pd.DataFrame(filas, columns=["modelo", "CRPS", "pinball", "IS95", "cob90", "cob95",
                                                 "cob98", "CRPS/base", "DM p", "estado"]))]
        ref = cmp_[cmp_.h == h].linea_base.iloc[0] if (cmp_.h == h).any() else "—"
        L += ["", f"Línea base de referencia en h={h}: `{ref}`.", "", "### Por régimen", ""]
        grupos = [g for g in res_sum[next(iter(res))].query(f"h=={h}").grupo if g not in ("todo",)]
        filas = []
        for m in res:
            s = res_sum[m].query(f"h=={h}").set_index("grupo")
            fila = [m]
            for g in grupos:
                fila += [_f(100 * s.loc[g, "crps"], 4), _f(s.loc[g, "cob95"], 3)] if g in s.index else ["—", "—"]
            filas.append(fila)
        cols = ["modelo"] + [f"{x} {g}" for g in grupos for x in ("CRPS", "cob95")]
        n_g = res_sum[next(iter(res))].query(f"h=={h}").set_index("grupo")["n"]
        L += [tabla(pd.DataFrame(filas, columns=cols)), "",
              "n por grupo: " + ", ".join(f"{g} = {int(n_g[g])}" for g in grupos), ""]

    L += ["## Pruebas de VaR al 95 % y 99 % en ambas colas, h = 1 (Kupiec y Christoffersen)", "",
          "Cola inf = caída del dólar; sup = alza.", "",
          "Tasa = proporción de violaciones (esperada 0,01 o 0,05). p_uc = Kupiec; p_ind = independencia "
          "de Christoffersen; p_cc = cobertura condicional. p < 0,05 rechaza la calibración de esa cola.", ""]
    filas = []
    for m in res:
        pv = pruebas_var(res[m])
        for cola, (tasa, puc, pind, pcc) in pv.items():
            filas.append([m, cola, _f(tasa, 4), _p(puc), _p(pind), _p(pcc)])
    L += [tabla(pd.DataFrame(filas, columns=["modelo", "cola", "tasa", "p_uc", "p_ind", "p_cc"])), ""]

    L += secciones(res, meta, directorio / "cola", res_largo, salida.parent / "figs",
                   reps_mcs=reps_mcs or REPS_MCS)

    L += ["## Detalle Diebold-Mariano (candidato vs. mejor línea base)", "",
          tabla(pd.DataFrame([[r.modelo, r.h, r.linea_base, _f(r.relativo, 3), _f(r.dm_t, 2), _p(r.dm_p),
                               r.rezagos, r.n, r.estado] for r in cmp_.itertuples()],
                             columns=["modelo", "h", "línea base", "CRPS/base", "t (HLN)", "p", "rezagos",
                                      "n", "estado"])), "",
          "## Reproducir", "", "```", "PYTHONPATH=src python -m laboratorio.backtest correr",
          "PYTHONPATH=src python -m laboratorio.backtest correr --largo",
          "PYTHONPATH=src python -m laboratorio.backtest reporte", "```", ""]
    hashes = {md.get("hash_trm_csv") for md in meta.values() if md}
    if hashes:
        L += [f"Hash (SHA-256, 16 hex) de data/processed/trm.csv usado: {', '.join(sorted(map(str, hashes)))}.", ""]
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text("\n".join(L), encoding="utf-8")
    return salida
