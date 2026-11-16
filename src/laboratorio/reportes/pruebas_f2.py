"""Secciones de F2 para el reporte de la fase 2 (las llama `reportes.fase2.generar`).

MCS por horizonte, semáforo de Basilea, ES 97,5 % con Z2 de Acerbi-Székely, uniformidad del PIT,
acierto direccional y, si existe la corrida larga, cobertura con n efectivo a 126 y 252.
Entradas: los CSV del backtest ya cargados (`res`), sus metadatos, el directorio de tablas de
cola (runs/.../cola/) y el de la corrida larga. Nunca lee la prueba final.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ..backtest.particion import ALFA_ES, HORIZONTES, NIVELES  # noqa: E402
from ..evaluacion.cobertura import cobertura_n_efectivo  # noqa: E402
from ..evaluacion.direccion import acierto_binomial, pesaran_timmermann  # noqa: E402
from ..evaluacion.mcs import ALFA_MCS, REPS_MCS, conjunto_confianza  # noqa: E402
from ..evaluacion.perdidas import crps_cuantiles  # noqa: E402
from ..evaluacion.pit import uniformidad  # noqa: E402
from ..evaluacion.riesgo import (Z2_CRITICO_5, acerbi_szekely_z2, semaforo_basilea,  # noqa: E402
                                 violaciones)

COLS = [f"q_{t:g}" for t in NIVELES]
VENTANA_BASILEA = 250
INTERVALOS_LARGOS = (("q_0.05", "q_0.95", 0.90), ("q_0.025", "q_0.975", 0.95))


def _tabla(filas, columnas) -> str:
    cab = "| " + " | ".join(columnas) + " |"
    sep = "|" + "|".join("---" for _ in columnas) + "|"
    return "\n".join([cab, sep, *["| " + " | ".join(str(v) for v in f) + " |" for f in filas]])


def _f(x, d=3):
    return "—" if x is None or not np.isfinite(x) else f"{x:.{d}f}"


def _p(x):
    return "—" if x is None or not np.isfinite(x) else "<0,001" if x < 0.001 else f"{x:.3f}"


def _pct(x):
    return f"{100 * x:.1f} %"


def perdidas_crps(res: dict[str, pd.DataFrame], h: int) -> pd.DataFrame:
    """CRPS por origen (filas) y modelo (columnas), solo orígenes comunes a todos."""
    series = {}
    for m, d in res.items():
        s = d[d["h"] == h]
        if len(s):
            series[m] = pd.Series(crps_cuantiles(s["y"].to_numpy(), s[COLS].to_numpy(), NIVELES),
                                  index=s["origen"].to_numpy())
    return pd.DataFrame(series).dropna().sort_index()


def seccion_mcs(res, reps: int) -> tuple[list[str], dict[int, str]]:
    L = [f"## Model Confidence Set (α = {ALFA_MCS:.2f})".replace(".", ","), "",
         "Conjunto de modelos que, con 90 % de confianza, contiene al de menor CRPS esperado "
         "(Hansen, Lunde y Nason). Compara TODOS los modelos a la vez, líneas base incluidas, así "
         "que no premia al ganador de muchas pruebas por pares. Bootstrap estacionario, "
         f"{reps} réplicas, bloque máx(2h, 10), estadístico de rango, semilla fija. "
         "p_mcs ≥ 0,10 ⇒ el modelo queda en el conjunto.", ""]
    mejor = {}
    for h in HORIZONTES:
        P = perdidas_crps(res, h)
        if P.shape[1] < 2 or len(P) == 0:
            continue
        r = conjunto_confianza(P, h=h, reps=reps)
        mejor[h] = r.modelo.iloc[0]
        dentro = [m for m, e in zip(r.modelo, r.en_mcs) if e]
        L += [f"### h = {h}", "",
              _tabla([[m, _f(100 * c, 4), _p(p), "**sí**" if e else "no"]
                      for m, c, p, e in zip(r.modelo, r.perdida, r.p_mcs, r.en_mcs)],
                     ["modelo", "CRPS", "p_mcs", "en el MCS"]), "",
              f"Conjunto superior en h={h} ({len(dentro)} de {len(r)}, n = {len(P)}, bloque "
              f"{r.attrs['bloque']}): " + ", ".join(f"`{m}`" for m in dentro) + ".", ""]
    return L, mejor


def seccion_basilea(res) -> list[str]:
    L = ["## Semáforo de Basilea (VaR al 99 %, h = 1)", "",
         f"Excepciones en ventanas móviles de {VENTANA_BASILEA} observaciones: verde 0-4, amarillo "
         "5-9, rojo 10 o más (esperadas 2,5). Porcentaje de ventanas en cada zona. Cola inferior = "
         "caída del dólar; superior = alza.", ""]
    filas = []
    for m, d in res.items():
        s = d[d["h"] == 1].sort_values("origen")
        if len(s) < VENTANA_BASILEA:
            continue
        for cola, col in (("inferior", "q_0.01"), ("superior", "q_0.99")):
            v = violaciones(s["y"].to_numpy(), s[col].to_numpy(), "inf" if cola == "inferior" else "sup")
            b = semaforo_basilea(v, VENTANA_BASILEA)
            filas.append([m, cola, _pct(b["verde"]), _pct(b["amarillo"]), _pct(b["rojo"]),
                          b["max"], _f(b["media"], 2)])
    if not filas:
        return L + ["Sin suficientes observaciones a h = 1.", ""]
    return L + [_tabla(filas, ["modelo", "cola", "verde", "amarillo", "rojo", "máx. excepciones",
                               "media por ventana"]), ""]


def seccion_es(res, meta, dir_cola: Path) -> list[str]:
    L = [f"## Expected Shortfall al {100 * (1 - ALFA_ES):g} % y prueba Z2 de Acerbi-Székely (h = 1)".replace(".", ","), "",
         "ES = promedio de la cola de probabilidad 2,5 % de cada pronóstico (rejilla de 25 cuantiles "
         "pedida en la misma corrida). Z2 = 1 − Σ y·I/(T·α·ES): vale 0 si VaR y ES son correctos y "
         "es negativo si el riesgo de cola está subestimado. «exceso» = promedio de y/ES en los días "
         "de violación (1 = el ES acierta la magnitud). Umbral de referencia del artículo: "
         f"Z2 < {Z2_CRITICO_5:.2f} rechaza al 5 %. No hay p-valor exacto (no se guardan las "
         "simulaciones completas).".replace("-0.70", "−0,70"), ""]
    filas, sin = [], []
    for m in res:
        f = dir_cola / f"{m}.csv.gz"
        if not f.exists():
            sin.append(f"- `{m}`: {meta.get(m, {}).get('es', 'no aplica: sin tabla de cola en esta corrida')}.")
            continue
        c = pd.read_csv(f)
        c = c[c["h"] == 1].sort_values("origen")
        for cola, var, es in (("inferior", "c_0.025", "es_inf"), ("superior", "c_0.975", "es_sup")):
            z = acerbi_szekely_z2(c["y"].to_numpy(), c[var].to_numpy(), c[es].to_numpy(), ALFA_ES,
                                  "inf" if cola == "inferior" else "sup")
            filas.append([m, cola, z["violaciones"], _f(z["esperadas"], 1), _f(z["exceso_medio"], 3),
                          _f(z["z2"], 3), "**rechaza**" if z["rechaza_5"] else "no rechaza"])
    if filas:
        L += [_tabla(filas, ["modelo", "cola", "violaciones", "esperadas", "exceso", "Z2",
                             "al 5 %"]), ""]
    if sin:
        L += ["ES «no aplica»:", *sin, ""]
    return L


def seccion_pit(res, mejor: dict[int, str], dir_figs: Path, rel_figs: str) -> list[str]:
    L = ["## Uniformidad del PIT", "",
         "Ji-cuadrado sobre las 12 casillas que definen los 11 cuantiles (si el pronóstico está "
         "calibrado, cada casilla recibe su probabilidad nominal). A h = 1 es exacta; a h > 1 las "
         "observaciones se traslapan: se usa n efectivo = n/h, se fusionan casillas extremas con "
         "menos de 5 esperadas y el p-valor es **aproximado**. p < 0,05 rechaza la calibración.", ""]
    filas, hs = [], [h for h in HORIZONTES if any((d["h"] == h).any() for d in res.values())]
    detalle = {}
    for m, d in res.items():
        fila = [m]
        for h in hs:
            s = d[d["h"] == h]
            if len(s) == 0:
                fila.append("—"); continue
            r = uniformidad(s["y"].to_numpy(), s[COLS].to_numpy(), NIVELES,
                            n_efectivo=None if h == 1 else len(s) / h)
            detalle[(m, h)] = r
            fila.append(_p(r.p_valor))
        filas.append(fila)
    L += [_tabla(filas, ["modelo"] + [f"p (h={h})" + ("" if h == 1 else ", aprox.") for h in hs]), ""]
    if mejor:
        dir_figs.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(1, len(mejor), figsize=(3.6 * len(mejor), 3.2), squeeze=False)
        for a, (h, m) in zip(ax[0], mejor.items()):
            r = detalle[(m, h)]
            razon = np.array(r.detalle["frecuencias"]) / np.array(r.detalle["nominales"])
            a.bar(range(len(razon)), razon)
            a.axhline(1.0, color="k", lw=0.8)
            a.set_title(f"h = {h}: {m}", fontsize=9)
            a.set_xlabel("casilla (cola inferior → superior)")
        ax[0][0].set_ylabel("frecuencia observada / nominal")
        fig.tight_layout()
        fig.savefig(dir_figs / "fase2_pit.png", dpi=120)
        plt.close(fig)
        L += [f"![PIT por casillas]({rel_figs}/fase2_pit.png)", "",
              "Figura: frecuencia observada sobre nominal por casilla, para el modelo de menor CRPS "
              "en cada horizonte. 1 = calibrado; barras extremas > 1 = colas subcubiertas.", ""]
    return L


def seccion_direccion(res) -> list[str]:
    L = ["## Acierto direccional (h = 1, diagnóstico)", "",
         "Signo de la mediana pronosticada contra el signo del rendimiento observado (se descartan "
         "los ceros). Binomial: H0 acierto = 50 %. Pesaran-Timmermann (PT): descuenta el acierto "
         "que se logra por predecir siempre el signo más frecuente. Se reporta, no se optimiza. En "
         "los modelos de media cero que simulan, la mediana es ruido de simulación: su acierto "
         "ronda el 50 % por construcción. «no aplica» = mediana siempre cero o de un solo signo.", ""]
    filas = []
    for m, d in res.items():
        s = d[d["h"] == 1]
        if len(s) == 0:
            continue
        b = acierto_binomial(s["q_0.5"].to_numpy(), s["y"].to_numpy())
        pt = pesaran_timmermann(s["q_0.5"].to_numpy(), s["y"].to_numpy())
        if not b.detalle["aplica"]:
            filas.append([m, "no aplica", 0, "—", "—", "—"]); continue
        filas.append([m, _pct(b.estadistico), b.detalle["n"], _p(b.p_valor),
                      _f(pt.estadistico, 2) if pt.detalle["aplica"] else "no aplica",
                      _p(pt.p_valor) if pt.detalle["aplica"] else "—"])
    return L + [_tabla(filas, ["modelo", "acierto", "n", "p binomial", "PT S", "p PT"]), ""]


def seccion_largos(res_largo: dict[str, pd.DataFrame]) -> list[str]:
    L = ["## Horizontes largos (h = 126 y 252): cobertura con n efectivo", "",
         "Corrida aparte (runs/backtest_largo/). Los orígenes diarios se traslapan casi por "
         "completo: la evidencia equivale a n/h ventanas independientes. Se reporta la cobertura "
         "observada y el intervalo binomial exacto del 95 % con n efectivo. Es **descriptivo**: "
         "«compatible» solo dice que el nominal cae en un intervalo muy ancho. Sin MCS ni "
         "Diebold-Mariano a estos horizontes (N1).", ""]
    filas = []
    for m, d in res_largo.items():
        for h in sorted(set(d["h"])):
            s = d[d["h"] == h]
            crps = float(crps_cuantiles(s["y"].to_numpy(), s[COLS].to_numpy(), NIVELES).mean())
            for lo, hi, nominal in INTERVALOS_LARGOS:
                c = cobertura_n_efectivo(s["y"].to_numpy(), s[lo].to_numpy(), s[hi].to_numpy(), nominal, h)
                filas.append([m, h, f"{100 * nominal:.0f} %", _f(c["cobertura"], 3), c["n"],
                              c["n_efectivo"], f"{_f(c['ic_inf'], 2)} – {_f(c['ic_sup'], 2)}",
                              "sí" if c["compatible"] else "**no**", _f(100 * crps, 3)])
    return L + [_tabla(filas, ["modelo", "h", "intervalo", "cobertura", "n", "n efectivo",
                               "IC 95 % (n ef.)", "compatible", "CRPS (descr.)"]), ""]


def secciones(res, meta, dir_cola: Path, res_largo: dict | None, dir_figs: Path,
              rel_figs: str = "figs", reps_mcs: int = REPS_MCS) -> list[str]:
    mcs, mejor = seccion_mcs(res, reps_mcs)
    L = mcs + seccion_basilea(res) + seccion_es(res, meta, dir_cola)
    L += seccion_pit(res, mejor, dir_figs, rel_figs) + seccion_direccion(res)
    if res_largo:
        L += seccion_largos(res_largo)
    return L
