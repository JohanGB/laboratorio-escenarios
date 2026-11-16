"""Diagnóstico N4 (F3): ¿por qué LightGBM empeora a 21 y 63 días? Solo desarrollo.

Dos explicaciones posibles y cómo se separan:
- La ESTANDARIZACIÓN z = y/(σ_t·√h). Se aísla con el mismo modelo sin variables
  (`RegresionCuantiles(columnas=[])`: cuantiles incondicionales de z reescalados por σ_t·√h). Si
  este ya pierde contra las líneas base, el problema es la escala, no el aprendizaje.
- El SOBREAJUSTE. Se mide con la pérdida de cuantil de LightGBM relativa a la de ese modelo sin
  variables, dentro de la muestra de entrenamiento y fuera de ella. Dentro < 1 y fuera > 1
  significa que las variables aprenden ruido.

  PYTHONPATH=src python -m laboratorio.reportes.lightgbm_n4
Escribe reports/f3_lightgbm.md y reports/figs/f3_lightgbm_pit.png.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ..backtest.catalogo import LINEAS_BASE  # noqa: E402
from ..backtest.corredor import correr, primer_origen  # noqa: E402
from ..backtest.datos import cargar_desarrollo  # noqa: E402
from ..backtest.particion import HORIZONTES, NIVELES  # noqa: E402
from ..evaluacion.origen_movil import bloques, ultimo_origen  # noqa: E402
from ..evaluacion.perdidas import crps_cuantiles, pinball  # noqa: E402
from ..evaluacion.pit import uniformidad  # noqa: E402
from ..modelos import caracteristicas as car  # noqa: E402
from ..modelos.cuantiles import LightGBMCuantiles, RegresionCuantiles  # noqa: E402

COLS = [f"q_{t:g}" for t in NIVELES]
CADA = 8                     # un reajuste de cada 8 (de 56) para la pérdida dentro de muestra
LECTURA = (
    "Escrita para los datos con hash 641393c5df0c869b. Son las dos cosas, en horizontes distintos:\n"
    "\n"
    "- **A 21 días es sobreajuste.** La estandarización sola no cuesta nada (1,001 frente a la base), pero LightGBM pierde 5,1 % contra su propia versión sin variables. Dentro de la muestra parece ganar 30 % (0,696): esa ganancia no existe fuera.\n"
    "- **A 63 días se suman las dos.** La estandarización sola ya pierde 8,8 % (1,088; la regresión lineal por cuantiles, 1,083): la volatilidad de hoy escalada por √63 no describe el trimestre que sigue. LightGBM agrega 4,5 % de sobreajuste (dentro de la muestra, 0,566).\n"
    "- La brecha entre «dentro» y «fuera» crece cuando bajan los objetivos independientes (de 5977 a 93): con ≈ 93 trimestres sin traslape y 14 variables, los árboles memorizan.\n"
    "- El PIT lo confirma: LightGBM deja entre 2,7 % y 3,6 % de las observaciones por fuera de cada cuantil extremo (nominal 1 %) y solo 40-43 % en el centro (nominal 50 %). El modelo sin variables queda cerca del nominal. La ji-cuadrado no rechaza a LightGBM (p = 0,10 y 0,24) porque con n/h observaciones efectivas tiene poca potencia: no es evidencia de buena calibración.\n"
    "- A 1 día pasa lo contrario: las variables sí aportan fuera de la muestra (0,980), aunque menos que dentro (0,881).\n"
    "\n"
    "Consecuencia: LightGBM no se usa por encima de 1 día. No se retoca (ni hiperparámetros ni variables): hacerlo ahora sería buscar con los datos de desarrollo."
)


def _crps(df: pd.DataFrame, h: int) -> float:
    s = df[df["h"] == h]
    return float(crps_cuantiles(s["y"].to_numpy(), s[COLS].to_numpy(), NIVELES).mean())


def dentro_de_muestra(vista, cada: int = CADA, paso: int = 63) -> pd.DataFrame:
    """Pérdida de cuantil media (en unidades de z) dentro de la muestra de entrenamiento, en un
    subconjunto de las fechas de reajuste: LightGBM y cuantiles incondicionales de z."""
    bl = bloques(primer_origen(vista), ultimo_origen(vista.n, max(HORIZONTES)), paso)[::cada]
    filas = []
    for b in bl:
        v = vista.hasta(b.reajuste)
        m = LightGBMCuantiles()
        m.ajustar(v)
        feats, sg = car.construir(v), car.sigma(v)
        ok_x = m._filas_validas(feats)
        for h in HORIZONTES:
            z = v.objetivo(h) / (sg * np.sqrt(h))
            ok = ok_x & np.isfinite(z)
            X, zz = feats.loc[ok, m.columnas], z[ok]
            q_l = np.sort(np.column_stack([m._predecir_nivel(m.modelos[(h, float(t))], X)
                                           for t in NIVELES]), axis=1)
            q_c = np.tile(np.quantile(zz, NIVELES), (len(zz), 1))
            filas.append({"reajuste": b.reajuste, "h": h, "n": int(ok.sum()),
                          "lgbm": float(pinball(zz, q_l, NIVELES).mean()),
                          "const": float(pinball(zz, q_c, NIVELES).mean())})
    return pd.DataFrame(filas)


def generar(raiz: str | Path = ".") -> Path:
    raiz = Path(raiz)
    d = raiz / "runs" / "backtest_desarrollo"
    leer = lambda m: pd.read_csv(d / f"{m}.csv.gz")
    vista = cargar_desarrollo(raiz)
    const = correr(RegresionCuantiles(columnas=[]), vista)
    lgbm, qr = leer("lightgbm_cuantiles"), leer("reg_cuantiles")
    bases = {b: leer(b) for b in LINEAS_BASE}
    if not np.array_equal(const["origen"].to_numpy(), lgbm["origen"].to_numpy()):
        raise RuntimeError("los orígenes del diagnóstico no coinciden con la corrida")
    dm = dentro_de_muestra(vista)
    hash_trm = hashlib.sha256((raiz / "data/processed/trm.csv").read_bytes()).hexdigest()[:16]

    filas, pits = [], {}
    for h in HORIZONTES:
        base = min(bases, key=lambda b: _crps(bases[b], h))
        cb, cc, cl, cq = _crps(bases[base], h), _crps(const, h), _crps(lgbm, h), _crps(qr, h)
        g = dm[dm.h == h]
        filas.append([h, base, f"{cc / cb:.3f}", f"{cq / cb:.3f}", f"{cl / cb:.3f}", f"{cl / cc:.3f}",
                      f"{(g.lgbm / g.const).mean():.3f}", int(g.n.iloc[-1] / h)])
        for nombre, df in (("lightgbm_cuantiles", lgbm), ("sin variables", const)):
            s = df[df["h"] == h]
            pits[(nombre, h)] = uniformidad(s["y"].to_numpy(), s[COLS].to_numpy(), NIVELES,
                                            n_efectivo=None if h == 1 else len(s) / h)

    figs = raiz / "reports" / "figs"
    figs.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.2))
    for a, h in zip(ax, (21, 63)):
        for k, nombre in enumerate(("lightgbm_cuantiles", "sin variables")):
            r = pits[(nombre, h)].detalle
            razon = np.array(r["frecuencias"]) / np.array(r["nominales"])
            a.bar(np.arange(len(razon)) + 0.4 * k - 0.2, razon, width=0.4, label=nombre)
        a.axhline(1.0, color="k", lw=0.8)
        a.set_title(f"h = {h}")
        a.set_xlabel("casilla (cola inferior → superior)")
    ax[0].set_ylabel("frecuencia observada / nominal")
    ax[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(figs / "f3_lightgbm_pit.png", dpi=120)
    plt.close(fig)

    cab = ["h", "mejor línea base", "sin variables / base", "reg. cuantiles / base", "LightGBM / base",
           "LightGBM / sin variables (fuera)", "LightGBM / sin variables (dentro)",
           "objetivos independientes (≈ n/h)"]
    t1 = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)] + \
         ["| " + " | ".join(map(str, f)) + " |" for f in filas]
    cab2 = ["modelo", "h", "p ji-cuadrado", "casilla < 1 %", "casilla > 99 %", "centro (25-75 %)"]
    t2 = ["| " + " | ".join(cab2) + " |", "|" + "---|" * len(cab2)]
    for (nombre, h), r in pits.items():
        f = np.array(r.detalle["frecuencias"])
        p = "<0,001" if r.p_valor < 0.001 else f"{r.p_valor:.3f}"
        t2.append(f"| {nombre} | {h} | {p}{'' if h == 1 else ' (aprox.)'} | {100 * f[0]:.1f} % | "
                  f"{100 * f[-1]:.1f} % | {100 * (f[5] + f[6]):.1f} % |")
    L = ["# F3 · Diagnóstico N4: LightGBM a 21 y 63 días", "",
         f"Solo desarrollo (orígenes {lgbm['fecha'].min()[:10]} a {lgbm['fecha'].max()[:10]}, "
         f"{lgbm['origen'].nunique()} por horizonte). Hash de trm.csv: {hash_trm}. "
         "No se cambia ningún modelo: es diagnóstico.", "",
         "«Sin variables» = el mismo esquema z = y/(σ·√h) con cuantiles incondicionales de z (sin "
         "aprender nada de las variables): aísla el efecto de la estandarización. Las columnas "
         "«/ base» son CRPS relativo a la mejor línea base del horizonte (< 1 = mejor). «Dentro» = "
         "pérdida de cuantil de LightGBM sobre la del modelo sin variables en la propia muestra de "
         f"entrenamiento (promedio de {dm.reajuste.nunique()} fechas de reajuste); «fuera» = lo mismo "
         "en el backtest.", "", *t1, "",
         "## PIT por casillas", "",
         "Frecuencia observada en las casillas extremas (nominal 1 % cada una) y en el centro "
         "(nominal 50 %).", "", *t2, "",
         "![PIT de LightGBM y del modelo sin variables](figs/f3_lightgbm_pit.png)", "",
         "## Lectura", "", LECTURA, ""]
    salida = raiz / "reports" / "f3_lightgbm.md"
    salida.write_bytes("\n".join(L).encode("utf-8"))
    return salida


if __name__ == "__main__":
    print(generar())
