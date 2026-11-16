"""O2: diagnóstico del cambio de régimen de Markov (reports/o2_markov.md + figura).

Estima Markov de 2 y 3 estados con TODO el desarrollo (1991-12 a 2019-12; nunca la prueba final)
y calcula la probabilidad filtrada del estado de varianza más alta, P(S_t = alto | r_1..r_t).
Diagnóstico esperado (B2): el estado alto domina en 2008 y en 2014-2015. Es un diagnóstico dentro
de muestra para los parámetros (el filtro sí es causal); la evaluación fuera de muestra es el
backtest (O3). También mide el tiempo por estimación, que fija el paso de reajuste (regla: > 2 s
→ cada 63 orígenes).

  PYTHONPATH=src python -m laboratorio.reportes.markov
"""
from __future__ import annotations

import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ..backtest.datos import cargar_desarrollo  # noqa: E402
from ..datos.limpieza import ESTRES, FIN_BANDA  # noqa: E402
from ..modelos.markov import MarkovVarianza, ergodicas  # noqa: E402
from .fase0 import COLORES, ETIQ  # noqa: E402

FIG = Path("reports") / "figs" / "markov_estado_alto.png"


def _fmt(x, d=3):
    return f"{x:.{d}f}".replace(".", ",")


def grupos(vista) -> dict[str, np.ndarray]:
    f = vista.fechas
    flot = f >= FIN_BANDA
    g = {"Banda (1991-12 a 1999-09)": ~flot,
         "  de ella, 1997-07 a 1999-09": (~flot) & (f >= pd.Timestamp("1997-07-01")),
         "Flotación sin estrés": flot & (vista.estres == "")}
    for k in ESTRES:
        m = vista.estres == k
        if m.any():
            g[ETIQ[k]] = m
    g["Todo el desarrollo"] = np.ones(len(f), bool)
    return g


def generar(raiz: Path = Path(".")) -> str:
    vista = cargar_desarrollo(raiz)
    modelos, tiempos, xi = {}, {}, {}
    for k in (2, 3):
        m = MarkovVarianza(k)
        t0 = time.time(); m.ajustar(vista); frio = time.time() - t0
        t0 = time.time(); m.ajustar(vista); caliente = time.time() - t0
        corto = MarkovVarianza(k)
        t0 = time.time(); corto.ajustar(vista.hasta(int(vista.fechas.searchsorted("2005-01-03"))))
        tiempos[k] = (time.time() - t0, frio, caliente)
        modelos[k], xi[k] = m, m.probabilidades(vista)[:, -1]
        print(f"markov_{k}: frío {frio:.1f} s, caliente {caliente:.1f} s", flush=True)

    tab = []
    for nombre, msk in grupos(vista).items():
        tab.append(f"| {nombre} | {msk.sum()} | " + " | ".join(
            f"{_fmt(xi[k][msk].mean(), 2)} | {(xi[k][msk] > 0.5).mean():.0%}" for k in (2, 3)) + " |")
    par = []
    for k, m in modelos.items():
        sd_anual = np.sqrt(m.s2 * 252)                      # % anual
        dur = 1 / (1 - np.diag(m.P))
        pi = ergodicas(m.P)
        for s in range(k):
            par.append(f"| {k} | {s} | {_fmt(m.s2[s], 4)} | {_fmt(sd_anual[s], 1)} % | "
                       f"{_fmt(m.P[s, s], 4)} | {_fmt(dur[s], 0)} | {pi[s]:.0%} |")

    # figura
    f = vista.fechas
    fig, ax = plt.subplots(3, 1, figsize=(10, 7), sharex=True,
                           gridspec_kw={"height_ratios": [1.2, 1, 1]})
    ax[0].plot(f, vista.r * 100, lw=0.4, color="#1f3b73")
    ax[0].set_ylabel("rend. diario (%)")
    ax[0].set_title("TRM: rendimientos y probabilidad filtrada del estado de varianza alta")
    for i, k in enumerate((2, 3), start=1):
        ax[i].fill_between(f, 0, xi[k], color="#7a1f1f", lw=0, alpha=0.75)
        ax[i].set_ylim(0, 1); ax[i].set_ylabel(f"P(alto), {k} estados")
    for a in ax:
        a.axvspan(f[0], FIN_BANDA, color="#bbbbbb", alpha=0.35, lw=0)
        for kk, (ini, fin) in ESTRES.items():
            if pd.Timestamp(ini) <= f[-1]:
                a.axvspan(pd.Timestamp(ini), min(pd.Timestamp(fin), f[-1]), color=COLORES[kk],
                          alpha=0.30, lw=0)
        a.set_xlim(f[0], f[-1])
    from matplotlib.patches import Patch
    h = [Patch(color="#bbbbbb", alpha=0.6, label="Banda cambiaria")]
    h += [Patch(color=COLORES[kk], alpha=0.5, label=ETIQ[kk]) for kk, (ini, _) in ESTRES.items()
          if pd.Timestamp(ini) <= f[-1]]
    ax[0].legend(handles=h, loc="upper right", fontsize=8, frameon=False)
    fig.tight_layout()
    (raiz / FIG).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(raiz / FIG, dpi=130)
    plt.close(fig)

    md = [
        "# O2 · Cambio de régimen de Markov: diagnóstico (desarrollo)", "",
        f"Datos: {str(f[0])[:10]} a {str(f[-1])[:10]} (desarrollo; la prueba final no se usa). "
        "Modelo: r·100 = σ_S·ε, ε normal, media cero, varianza por estado; estados ordenados por "
        "varianza (el último es «alto»). Parámetros estimados con todo el desarrollo (diagnóstico "
        "dentro de muestra); la probabilidad filtrada solo usa datos hasta cada día.", "",
        "## Parámetros", "",
        "| estados | estado | σ² (%²/día) | desvío anual | permanencia P(s→s) | duración media (días) | prob. ergódica |",
        "|---|---|---|---|---|---|---|", *par, "",
        "## Probabilidad filtrada del estado alto por periodo", "",
        "| periodo | días | 2 estados: media | 2 estados: % días > 0,5 | 3 estados: media | 3 estados: % días > 0,5 |",
        "|---|---|---|---|---|---|", *tab, "",
        f"![Probabilidad filtrada del estado alto](figs/{FIG.name})", "",
        "**Lectura.** El estado alto domina en 2008 y 2014-2015, como pide el diagnóstico de B2. "
        "Con 2 estados, sin embargo, «alto» también ocupa cerca de la mitad de los días normales "
        "de la flotación: el modelo separa sobre todo la banda (volatilidad baja) de la flotación, "
        "más que el estrés de la calma. Con 3 estados el estado alto se concentra en los "
        "episodios y cae a una quinta parte de los días normales. La cola de 1997-1999 (banda) "
        "apenas activa el estado alto: sus saltos son pocos y aislados. Esto es diagnóstico, no "
        "una conclusión sobre el pronóstico: eso lo decide el backtest (O3) y el MCS (F2).", "",
        "## Tiempo por estimación", "",
        "| estados | hasta 2005-01 (primer reajuste) | todo el desarrollo, frío | todo el desarrollo, caliente |",
        "|---|---|---|---|",
        *[f"| {k} | {_fmt(a, 1)} s | {_fmt(b, 1)} s | {_fmt(c, 1)} s |" for k, (a, b, c) in tiempos.items()],
        "",
        "Regla de B2: reajuste cada 63 orígenes si la estimación tarda más de 2 s. Con 2 estados "
        "se queda en 21; con 3 estados pasa a 63.", "",
    ]
    texto = "\n".join(md)
    (raiz / "reports" / "o2_markov.md").write_bytes(texto.encode("utf-8"))
    return texto


if __name__ == "__main__":
    print(generar())
