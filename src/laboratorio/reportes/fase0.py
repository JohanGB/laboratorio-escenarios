"""Reporte de la Fase 0: análisis exploratorio de la TRM.

Uso (desde la raíz del proyecto):
    PYTHONPATH=src python -m laboratorio.reportes.fase0
Entrada: data/processed/trm.csv (ver laboratorio.datos.limpieza). Salida: reports/fase0.md
y reports/figs/*.png (3 gráficas).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from laboratorio.datos.limpieza import ESTRES, FIN_BANDA  # noqa: E402

COLORES = {"crisis_2008": "#d62728", "petroleo_2014_2015": "#ff7f0e",
           "covid_2020": "#9467bd", "estres_2022": "#2ca02c"}
ETIQ = {"crisis_2008": "Crisis 2008", "petroleo_2014_2015": "Petróleo 2014–2015",
        "covid_2020": "Covid 2020", "estres_2022": "Estrés 2022"}


def cargar(ruta: Path) -> pd.DataFrame:
    df = pd.read_csv(ruta, parse_dates=["fecha"], index_col="fecha")
    df["estres"] = df["estres"].fillna("")  # vacío en el CSV = sin etiqueta
    return df


def _sombrear(ax) -> None:
    ax.axvspan(pd.Timestamp("1991-11-01"), FIN_BANDA, color="#bbbbbb", alpha=0.35, lw=0)
    for k, (a, b) in ESTRES.items():
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color=COLORES[k], alpha=0.30, lw=0)


def _leyenda(ax) -> None:
    from matplotlib.patches import Patch
    h = [Patch(color="#bbbbbb", alpha=0.6, label="Banda cambiaria (hasta sep-1999)")]
    h += [Patch(color=COLORES[k], alpha=0.5, label=ETIQ[k]) for k in ESTRES]
    ax.legend(handles=h, loc="upper left", fontsize=8, frameon=False)


def fig_nivel(df: pd.DataFrame, ruta: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.plot(df.index, df["trm"], lw=0.9, color="#1f3b73")
    ax.set_yscale("log")
    _sombrear(ax)
    _leyenda(ax)
    ax.set_title("TRM (COP por USD), escala logarítmica")
    ax.set_ylabel("COP/USD")
    fig.tight_layout()
    fig.savefig(ruta, dpi=130)
    plt.close(fig)


def fig_retornos(df: pd.DataFrame, ruta: Path) -> None:
    r = df["ret_log"].dropna()
    vol = r.rolling(60).std() * 100
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True,
                                 gridspec_kw={"height_ratios": [2, 1]})
    a1.plot(r.index, r * 100, lw=0.5, color="#333333")
    a1.set_ylabel("Rendimiento log (%)")
    a1.set_title("Rendimientos logarítmicos por observación y volatilidad móvil (60 obs.)")
    a2.plot(vol.index, vol, lw=1, color="#1f3b73")
    a2.set_ylabel("Desv. est. móvil (%)")
    for a in (a1, a2):
        _sombrear(a)
    _leyenda(a1)
    fig.tight_layout()
    fig.savefig(ruta, dpi=130)
    plt.close(fig)


def fig_distribucion(df: pd.DataFrame, ruta: Path) -> None:
    flot = df[df["regimen"] == "flotacion"]
    normal = flot.loc[flot["estres"] == "", "ret_log"].dropna() * 100
    estres = flot.loc[flot["estres"] != "", "ret_log"].dropna() * 100
    fig, ax = plt.subplots(figsize=(8, 4.2))
    bins = np.linspace(-6, 6, 97)
    ax.hist(normal.clip(-6, 6), bins=bins, density=True, alpha=0.6, color="#1f3b73",
            label=f"Flotación sin estrés (n={len(normal)})")
    ax.hist(estres.clip(-6, 6), bins=bins, density=True, alpha=0.5, color="#d62728",
            label=f"Flotación en estrés (n={len(estres)})")
    x = np.linspace(-6, 6, 400)
    ax.plot(x, stats.norm.pdf(x, normal.mean(), normal.std()), "k--", lw=1,
            label="Normal ajustada (sin estrés)")
    ax.set_yscale("log")
    ax.set_ylim(1e-4, None)
    ax.set_xlabel("Rendimiento log (%), recortado a ±6 %")
    ax.set_ylabel("Densidad (escala log)")
    ax.set_title("Distribución de rendimientos: colas más pesadas que la normal")
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(ruta, dpi=130)
    plt.close(fig)


def _desc(r: pd.Series) -> dict:
    return {"n": len(r), "media_%": r.mean() * 100, "desv_%": r.std() * 100,
            "asimetria": r.skew(), "curtosis_exc": r.kurt(),
            "min_%": r.min() * 100, "max_%": r.max() * 100}


def _tabla(filas: dict[str, pd.Series]) -> str:
    cab = "| Grupo | n | Media % | Desv. % | Asimetría | Curtosis exc. | Mín % | Máx % |\n|---|---:|---:|---:|---:|---:|---:|---:|\n"
    out = []
    for nombre, r in filas.items():
        d = _desc(r)
        out.append(f"| {nombre} | {d['n']} | {d['media_%']:.3f} | {d['desv_%']:.3f} | "
                   f"{d['asimetria']:.2f} | {d['curtosis_exc']:.1f} | {d['min_%']:.2f} | {d['max_%']:.2f} |")
    return cab + "\n".join(out)


def _acf(x: pd.Series, k: int) -> float:
    return float(x.autocorr(lag=k))


def generar(procesado: Path, salida: Path) -> Path:
    df = cargar(procesado / "trm.csv")
    r = df["ret_log"].dropna()
    figs = salida / "figs"
    figs.mkdir(parents=True, exist_ok=True)
    fig_nivel(df, figs / "trm_nivel.png")
    fig_retornos(df, figs / "trm_retornos.png")
    fig_distribucion(df, figs / "trm_distribucion.png")

    banda = df[df["regimen"] == "banda"]["ret_log"].dropna()
    flot = df[df["regimen"] == "flotacion"]
    flot_normal = flot.loc[flot["estres"] == "", "ret_log"].dropna()
    grupos = {"Todo": r, "Banda (hasta 24-sep-1999)": banda, "Flotación (desde 25-sep-1999)": flot["ret_log"].dropna(),
              "Flotación sin estrés": flot_normal}
    for k, (a, b) in ESTRES.items():
        grupos[f"{ETIQ[k]} ({a} a {b})"] = df.loc[df["estres"] == k, "ret_log"].dropna()

    jb_todo = stats.jarque_bera(r)
    jb_norm = stats.jarque_bera(flot_normal)
    ac = {k: (_acf(r, k), _acf(r.abs(), k)) for k in (1, 2, 5, 10)}
    top = r.abs().nlargest(8).index
    top_txt = "\n".join(f"| {d.date()} | {r[d]*100:+.2f} | {df.loc[d, 'trm']:.2f} | "
                        f"{int(df.loc[d, 'dias'])} | {df.loc[d, 'regimen']} | {df.loc[d, 'estres'] or '—'} |"
                        for d in top)
    por_dias = (df.dropna(subset=["ret_log"]).assign(d=lambda x: x["dias"].clip(upper=4).astype(int))
                .groupby("d")["ret_log"].agg(["count", "std"]))
    dias_txt = "\n".join(f"| {'4 o más' if d == 4 else d} | {int(v['count'])} | {v['std']*100:.3f} |"
                         for d, v in por_dias.iterrows())
    fuera = int((df.loc[top, "estres"] == "").sum())
    nivel_ini, nivel_fin = df["trm"].iloc[0], df["trm"].iloc[-1]
    ratio = grupos["Flotación (desde 25-sep-1999)"].std() / banda.std()
    vc = df["dias"].dropna().astype(int).value_counts()
    n1, n3 = int(vc.get(1, 0)), int(vc.get(3, 0))
    nx = int(vc.sum()) - n1 - n3
    corr1, corr_abs1 = ac[1]
    corr_abs10 = ac[10][1]

    md = f"""# Fase 0 — Análisis exploratorio de la TRM

Reporte generado automáticamente por `laboratorio.reportes.fase0` a partir de
`data/processed/trm.csv` (TRM de la Superfinanciera, {df.index.min().date()} a {df.index.max().date()},
{len(df)} observaciones). Describe incertidumbre histórica; no es asesoría financiera ni un pronóstico.

## 1. Datos y convenciones

- Rendimiento logarítmico por observación: `r_t = ln(TRM_t) − ln(TRM_(t−1))`. Cada fila es una
  vigencia de la TRM (fecha = inicio de vigencia), así que el intervalo entre observaciones es
  de 1 día ({n1:,} casos), 3 días ({n3:,}, fines de semana) u otros ({nx:,}, festivos). **No se
  anualiza ni se reescala por días**; la sección 4 muestra el efecto.
- Régimen **banda cambiaria** hasta el 24-sep-1999; **flotación** desde el 25-sep-1999 (supuesto
  del autor, editable en `laboratorio/datos/limpieza.py`).
- Periodos de estrés (supuestos del autor): {"; ".join(f"{ETIQ[k]} {a} a {b}" for k, (a, b) in ESTRES.items())}.
- Nivel: de {nivel_ini:,.2f} a {nivel_fin:,.2f} COP/USD ({nivel_fin/nivel_ini:.1f} veces).

## 2. Nivel de la TRM

![TRM nivel](figs/trm_nivel.png)

La escala logarítmica permite comparar variaciones relativas entre décadas. La zona gris
corresponde a la banda cambiaria; desde la flotación, los periodos de estrés coinciden con
tramos de movimiento más fuerte del nivel (compárese con la volatilidad de la sección 3).

## 3. Rendimientos y volatilidad

![Rendimientos](figs/trm_retornos.png)

La desviación estándar por observación en flotación es {ratio:.1f} veces la de la banda
({grupos["Flotación (desde 25-sep-1999)"].std()*100:.2f} % frente a {banda.std()*100:.2f} %). La
volatilidad móvil se agrupa en racimos (alta volatilidad sigue a alta volatilidad), con picos
en los periodos de estrés etiquetados.

{_tabla(grupos)}

(Todos los valores en porcentaje; curtosis en exceso sobre la normal = 0.)

## 4. Forma de la distribución

![Distribución](figs/trm_distribucion.png)

- Jarque–Bera, toda la muestra: estadístico {jb_todo.statistic:,.0f} (p = {jb_todo.pvalue:.2g}); se rechaza normalidad.
- Jarque–Bera, flotación sin estrés: estadístico {jb_norm.statistic:,.0f} (p = {jb_norm.pvalue:.2g}); las colas pesadas persisten fuera de los periodos de estrés.
- Los rendimientos en estrés tienen una dispersión visiblemente mayor que la normal ajustada fuera de estrés.

Autocorrelación (Pearson) de los rendimientos y de su valor absoluto:

| Rezago | r_t | \\|r_t\\| |
|---:|---:|---:|
""" + "\n".join(f"| {k} | {a:+.3f} | {b:+.3f} |" for k, (a, b) in ac.items()) + f"""

El valor absoluto de los rendimientos mantiene autocorrelación positiva y lenta
({corr_abs1:+.2f} en el rezago 1 y {corr_abs10:+.2f} en el 10): agrupamiento de volatilidad. Los
propios rendimientos muestran una autocorrelación de {corr1:+.2f} en el rezago 1 y casi nula
después; no se investigó su causa (podría deberse a cómo se construye la TRM o al intervalo
irregular entre observaciones), así que se reporta sin interpretarla. Un modelo probabilístico
debe permitir varianza variable y colas pesadas.

Efecto del intervalo entre observaciones (desviación estándar del rendimiento):

| Días entre observaciones | n | Desv. % |
|---|---:|---:|
{dias_txt}

## 5. Mayores movimientos

| Fecha | Rendimiento % | TRM | Días | Régimen | Estrés |
|---|---:|---:|---:|---|---|
{top_txt}

{fuera} de los 8 mayores movimientos caen fuera de las ventanas de estrés definidas (por ejemplo,
a mediados de 2008 y en la crisis de la banda de 1998): conviene revisar si las ventanas deben ampliarse.

## 6. Implicaciones para el modelado (sección 6 del prompt)

1. Calibrar **solo con el régimen de flotación** (o declarar explícitamente si se usa la banda): la volatilidad y la dinámica son distintas.
2. Usar rendimientos logarítmicos; nunca mezclar niveles y rendimientos sin decirlo.
3. Colas pesadas y agrupamiento de volatilidad: la normal con varianza constante subestima los extremos; los periodos de estrés deben poder activarse como escenario.
4. Decidir el tratamiento del intervalo irregular (1, 3 o más días) antes de anualizar: la desviación por observación crece con los días transcurridos.
5. Las ventanas de estrés son supuestos; conviene probar sensibilidad a sus fechas de inicio y fin.

## Reproducir

```
PYTHONPATH=src python -m laboratorio.datos.limpieza   # si cambian los datos crudos
PYTHONPATH=src python -m laboratorio.reportes.fase0
```
"""
    destino = salida / "fase0.md"
    destino.write_text(md, encoding="utf-8")
    return destino


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--procesado", default="data/processed", type=Path)
    p.add_argument("--salida", default="reports", type=Path)
    a = p.parse_args(argv)
    print(generar(a.procesado, a.salida))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
