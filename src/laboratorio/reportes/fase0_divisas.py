"""Reporte exploratorio multidivisa (M1): solo datos hasta el 31-dic-2019.

Uso (desde la raíz del proyecto):
    PYTHONPATH=src python -m laboratorio.reportes.fase0_divisas
Entrada: data/processed/divisas.csv y los CSV de FRED de data/raw. Salida:
reports/fase0_divisas.md y reports/figs/divisas_*.png (3 figuras).

Las filas con fecha desde el corte (`CORTE`) se descartan al leer: el reporte no las muestra ni
las resume, así la evaluación de M3 conserva un tramo sin ver para las divisas nuevas. Cada cifra
lleva su `#hash` (motor/cifras.py); los insumos se hashean solo con las filas anteriores al corte,
así que cambiar datos posteriores no cambia el reporte (hay prueba).
"""
from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from laboratorio.datos import divisas as D  # noqa: E402
from laboratorio.datos.lectores import leer_archivo  # noqa: E402
from laboratorio.motor.cifras import Cifra, Reporte  # noqa: E402

CORTE = D.CORTE_ALINEACION
ULTIMO_DIA = CORTE - pd.Timedelta(days=1)
PERIODOS = {"2005-2014": ("2005-01-01", "2014-12-31"), "2015-2019": ("2015-01-01", "2019-12-31")}
VENTANA_VOL = 63
# Okabe-Ito (apta para daltonismo) + estilos de línea: el color nunca es el único código.
COLORES = {"USD": "#000000", "EUR": "#E69F00", "MXN": "#56B4E9", "JPY": "#009E73",
           "CNY": "#CC79A7", "CHF": "#0072B2", "BRL": "#D55E00"}
ESTILOS = {"USD": "-", "EUR": "--", "MXN": "-.", "JPY": ":", "CNY": "-", "CHF": "--", "BRL": "-."}
AVISO = ("**No es asesoría financiera**; los rangos describen incertidumbre estadística, no promesas. "
         "Todas las cifras de este reporte son descriptivas: **sin respaldo fuera de muestra**.")


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _csv(df: pd.DataFrame) -> str:
    return df.to_csv(index=False, float_format="%.10g", date_format="%Y-%m-%d", lineterminator="\n")


@dataclass
class Datos:
    divisas: pd.DataFrame                      # formato largo, fecha < CORTE
    trm: pd.Series                             # filas USD de divisas.csv
    fred: dict[str, pd.Series]                 # cotización FRED original, fecha < CORTE
    insumos: dict[str, Cifra] = field(default_factory=dict)


def cargar(procesado: Path, raw: Path) -> Datos:
    df = pd.read_csv(Path(procesado) / "divisas.csv", parse_dates=["fecha"])
    df = df[df["fecha"] < CORTE].reset_index(drop=True)
    insumos = {"divisas": Cifra.de_dato(len(df), "filas", "processed/divisas.csv",
                                        "filas con fecha <= 2019-12-31", _sha(_csv(df)))}
    fred = {}
    for divisa, serie in D.SERIES.items():
        (f,) = Path(raw).glob(f"{divisa.lower()}_fred_{serie.lower()}_*.csv")
        (s,) = leer_archivo(f)[0].values()
        s = s[s.index < CORTE]
        fred[divisa] = s
        insumos[divisa] = Cifra.de_dato(len(s), "filas", f"raw/{f.name}", "filas con fecha <= 2019-12-31",
                                        _sha(_csv(s.rename("v").rename_axis("fecha").reset_index())))
    trm = df[df["divisa"] == "USD"].set_index("fecha")["cop_por_unidad"]
    return Datos(df, trm, fred, insumos)


def _ancho(df: pd.DataFrame, col: str) -> pd.DataFrame:
    return df.pivot(index="fecha", columns="divisa", values=col)[list(D.ORDEN)]


# --- figuras --------------------------------------------------------------------------------------
def fig_niveles(niveles: pd.DataFrame, base: pd.Timestamp, ruta: Path) -> None:
    n = niveles[niveles.index >= base].dropna(how="all")
    fig, ax = plt.subplots(figsize=(10, 4.4))
    for d in D.ORDEN:
        s = n[d].dropna()
        ax.plot(s.index, 100 * s / s.iloc[0], color=COLORES[d], ls=ESTILOS[d], lw=1.1, label=f"{d}/COP")
    ax.set_xlim(base, ULTIMO_DIA)
    ax.set_ylabel("Base 100 en el primer dato común")
    ax.set_title("Pesos por unidad de cada divisa (base 100), hasta 2019")
    ax.legend(ncol=4, fontsize=8, frameon=False)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(ruta, dpi=130)
    plt.close(fig)


def fig_volatilidad(ret: pd.DataFrame, ruta: Path) -> None:
    r = ret[ret.index >= "1995-01-01"]
    fig, ax = plt.subplots(figsize=(10, 4.4))
    for d in D.ORDEN:
        s = r[d].dropna()
        v = 100 * np.sqrt(252) * s.rolling(VENTANA_VOL).std()
        ax.plot(v.index, v, color=COLORES[d], ls=ESTILOS[d], lw=1.0, label=f"{d}/COP")
    ax.set_xlim(pd.Timestamp("1995-01-01"), ULTIMO_DIA)
    ax.set_ylabel(f"% anual (ventana de {VENTANA_VOL} obs.)")
    ax.set_title("Volatilidad móvil del rendimiento diario contra el peso, hasta 2019")
    ax.legend(ncol=4, fontsize=8, frameon=False)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(ruta, dpi=130)
    plt.close(fig)


def fig_correlaciones(matrices: dict[str, pd.DataFrame], ruta: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    for ax, (nombre, m) in zip(axes, matrices.items()):
        im = ax.imshow(m.to_numpy(), cmap="PuOr", vmin=-1, vmax=1)
        ax.set_xticks(range(len(m)), [f"{d}" for d in m.columns], fontsize=8)
        ax.set_yticks(range(len(m)), [f"{d}" for d in m.index], fontsize=8)
        for i in range(len(m)):
            for j in range(len(m)):
                v = m.iat[i, j]
                ax.text(j, i, f"{v:.2f}".replace(".", ","), ha="center", va="center", fontsize=7,
                        color="white" if abs(v) > 0.6 else "black")
        ax.set_title(f"{nombre}", fontsize=10)
    fig.colorbar(im, ax=axes, shrink=0.8, label="Correlación de rendimientos diarios (X/COP)")
    fig.suptitle("Cómo se mueven juntas las divisas contra el peso")
    fig.savefig(ruta, dpi=130)
    plt.close(fig)


# --- cálculos -------------------------------------------------------------------------------------
def dias_perdidos(d: Datos) -> dict[str, tuple[int, int]]:
    """(fechas de TRM en el tramo de FRED, filas pareadas), solo hasta 2019."""
    out = {}
    for divisa, s in d.fred.items():
        s = s.dropna()
        ff = D.fechas_fred(d.trm.index, D.DESFASE_FRED)
        en_rango = int(((ff >= s.index.min()) & (ff <= s.index.max())).sum())
        out[divisa] = (en_rango, int((d.divisas["divisa"] == divisa).sum()))
    return out


def generar(procesado: Path, raw: Path, salida: Path) -> Path:
    d = cargar(procesado, raw)
    rep = Reporte()
    ins = d.insumos
    figs = Path(salida) / "figs"
    figs.mkdir(parents=True, exist_ok=True)

    niveles = _ancho(d.divisas, "cop_por_unidad")
    ret = _ancho(d.divisas, "ret_log")
    base = niveles.dropna().index.min()
    matrices = {}
    for nombre, (a, b) in PERIODOS.items():
        matrices[nombre] = ret.loc[a:b].corr()
    fig_niveles(niveles, base, figs / "divisas_niveles.png")
    fig_volatilidad(ret, figs / "divisas_volatilidad.png")
    fig_correlaciones(matrices, figs / "divisas_correlaciones.png")

    def calc(valor, unidad, formula, *claves):
        return Cifra.derivada(float(valor), unidad, formula, [ins[k] for k in claves])

    # 1. Fuentes
    filas_fuente = []
    for divisa, serie in D.SERIES.items():
        s = d.fred[divisa].dropna()
        unidad = "USD por EUR" if serie in D.YA_EN_USD_POR_UNIDAD else f"{divisa} por USD"
        n = Cifra.derivada(int(len(s)), "obs.", f"valores no vacíos de {serie} hasta 2019-12-31", [ins[divisa]])
        filas_fuente.append(f"| {divisa} | `{serie}` | {unidad} | {s.index.min().date()} | {rep.r(n, 0)} |")

    # 2. Alineación
    filas_alin = []
    for divisa, serie in D.SERIES.items():
        c = D.correlaciones_desfase(d.trm, D.usd_por_unidad(d.fred[divisa], serie),
                                    desde=D.DESDE_CORRELACION.get(divisa))
        celdas = [rep.r(calc(c[k][0], "", f"corr(r_TRM, r_USD/{divisa}) desfase {k:+d}", "divisas", divisa), 3)
                  for k in D.DESFASES]
        n = rep.r(Cifra.derivada(c[-1][1], "pares", f"pares de rendimientos {divisa} desfase -1",
                                 [ins["divisas"], ins[divisa]]), 0)
        filas_alin.append(f"| {divisa} | " + " | ".join(celdas) + f" | {n} |")

    # 3. Días perdidos por la unión interna
    filas_dias = []
    for divisa, (en_rango, pareadas) in dias_perdidos(d).items():
        c1 = Cifra.derivada(en_rango, "días", f"fechas de TRM en el tramo de {divisa} hasta 2019", [ins["divisas"], ins[divisa]])
        c2 = Cifra.derivada(en_rango - pareadas, "días", f"fechas de TRM sin precio H.10 ({divisa}) hasta 2019",
                            [ins["divisas"], ins[divisa]])
        c3 = calc(100 * (en_rango - pareadas) / en_rango, "%", f"porcentaje perdido {divisa} hasta 2019", "divisas", divisa)
        filas_dias.append(f"| {divisa} | {rep.r(c1, 0)} | {rep.r(c2, 0)} | {rep.r(c3, 2)} |")

    # 4. Regímenes
    filas_reg = []
    for divisa in D.SERIES:
        tramos = "; ".join(f"{e} desde {a}" if a else f"{e}" for a, e in D.REGIMENES[divisa])
        filas_reg.append(f"| {divisa} | {tramos} |")

    # 5. Volatilidad y correlación con USD/COP por periodo
    filas_vol = []
    for divisa in D.ORDEN:
        celdas = []
        for nombre, (a, b) in PERIODOS.items():
            r = ret.loc[a:b, divisa].dropna()
            v = calc(100 * np.sqrt(252) * r.std(), "%", f"desv. est. anualizada de r_{divisa}/COP {nombre}", "divisas")
            celdas.append(rep.r(v, 1, unidad=False))
            if divisa != "USD":
                cc = calc(matrices[nombre].loc[divisa, "USD"], "", f"corr(r_{divisa}/COP, r_USD/COP) {nombre}", "divisas")
                celdas.append(rep.r(cc, 3))
            else:
                celdas.append("—")
        filas_vol.append(f"| {divisa}/COP | " + " | ".join(celdas) + " |")

    # 6. Saltos > 8 %
    v = D.validar_divisas(d.divisas)
    filas_saltos = []
    for s_ in v["saltos_8pct"]:
        c = calc(s_["cambio_pct"], "%", f"cambio diario {s_['divisa']}/COP del {s_['fecha']}", "divisas")
        filas_saltos.append(f"| {s_['fecha']} | {s_['divisa']} | {rep.r(c, 1)} | {s_['regimen']} |")

    n_total = rep.r(ins["divisas"], 0)
    md = f"""# Fase 0 multidivisa: análisis exploratorio (hasta 2019)

{AVISO}

Siete divisas contra el peso colombiano: USD (TRM) y EUR, MXN, JPY, CNY, CHF y BRL, cruzadas como
X/COP = TRM × (USD por X) con las tasas H.10 de la Reserva Federal (FRED). **Este reporte solo usa
datos hasta el 31-dic-2019** ({n_total} de `processed/divisas.csv`): lo posterior queda sin ver para
la evaluación de las divisas nuevas (M3). Generado por `python -m laboratorio.reportes.fase0_divisas`.

## 1. Fuentes

| Divisa | Serie FRED | Unidad original | Primer dato | Observaciones hasta 2019 |
|---|---|---|---|---:|
{chr(10).join(filas_fuente)}

`DEXUSEU` ya viene en USD por EUR; las demás se invierten (USD por X = 1 / valor). La fecha de
descarga, la URL y el SHA-256 de cada archivo están en `data/raw/MANIFEST.csv`.

## 2. Alineación de fechas TRM–FRED

La TRM vigente en la fecha *t* (martes a sábado) se calcula con las operaciones del día hábil
anterior; H.10 es el precio de mediodía en Nueva York del día *d*. Por calendario, la TRM de *t* se
cruza con el precio H.10 del **día hábil anterior** (desfase −1, supuesto `divisas.desfase_fred`
del registro). Se comprobó con la correlación de los rendimientos de la TRM y de USD por X:

| Divisa | desfase −1 | desfase 0 | desfase +1 | pares (−1) |
|---|---:|---:|---:|---:|
{chr(10).join(filas_alin)}

El desfase −1 tiene la mayor correlación en valor absoluto en las seis divisas. El signo
negativo es el esperado: cuando el dólar se fortalece en el mundo, sube la TRM y baja el precio
en dólares de las otras divisas. El yen tiene la correlación más débil. El yuan se mide solo
desde que dejó el tipo fijo (2005-07-22).

## 3. Días que se pierden en la unión (sin relleno)

Una fila existe solo si hay TRM en *t* y precio H.10 el día hábil anterior. Los festivos de
EE. UU. que no lo son en Colombia eliminan la fila; no se interpola ni se arrastra ningún valor.

| Divisa | Fechas de TRM en el tramo | Perdidas | % perdido |
|---|---:|---:|---:|
{chr(10).join(filas_dias)}

## 4. Regímenes por divisa

Constantes editables en `src/laboratorio/datos/divisas.py` (con su fuente). El régimen de cada
fila es el de la divisa en la fecha de su precio H.10; durante la banda cambiaria colombiana
(hasta el 24-sep-1999) la fila se marca `banda_cop`.

| Divisa | Tramos |
|---|---|
{chr(10).join(filas_reg)}

Episodios declarados en la constante `EPISODIOS` (no son una columna de los datos): fin del piso
del franco suizo (15-ene-2015) y fin del tipo fijo del yuan (21-jul-2005).

## 5. Niveles, volatilidad y correlaciones

![Niveles base 100](figs/divisas_niveles.png)

![Volatilidad móvil](figs/divisas_volatilidad.png)

![Correlaciones por periodo](figs/divisas_correlaciones.png)

| Cruce | Vol. anual % 2005-2014 | Corr. con USD/COP 2005-2014 | Vol. anual % 2015-2019 | Corr. con USD/COP 2015-2019 |
|---|---:|---:|---:|---:|
{chr(10).join(filas_vol)}

Todos los cruces se correlacionan positivamente con USD/COP en parte por construcción: cada X/COP
lleva la TRM dentro. Por eso el motor conjunto (M2) simula los factores (TRM y USD por X) y no los
cruces. El yuan casi replica al dólar (muy administrado); el real brasileño es el que menos se
mueve con él.

## 6. Saltos diarios mayores al 8 % (para revisión manual; no se borran)

| Fecha | Divisa | Cambio | Régimen |
|---|---|---:|---|
{chr(10).join(filas_saltos)}

## 7. Implicaciones para el motor conjunto (M2)

1. La muestra común empieza cuando todas las divisas incluidas flotan (con el yuan, desde el
   2005-07-22): el motor conjunto no incluye la banda colombiana y no es el motor evaluado en la
   prueba final.
2. Los saltos de la crisis mexicana (1994-1995), la unificación cambiaria china (1994) y la
   devaluación brasileña (1999) quedan fuera de esa muestra común. Quedan dentro el real en
   2002, el yen en octubre de 2008 y los dos saltos del franco suizo (inicio del piso en 2011 y
   su fin en 2015).
3. Las correlaciones cambian entre periodos: el remuestreo por bloques con índices de fecha
   compartidos las conserva tal como fueron, sin suponer que son constantes.

## Reproducir

```
PYTHONPATH=src python -m laboratorio.datos.limpieza       # data/processed/divisas.csv
PYTHONPATH=src python -m laboratorio.datos                # data/validacion.json
PYTHONPATH=src python -m laboratorio.reportes.fase0_divisas
```

## Apéndice: fuente y hash de cada cifra

{rep.apendice()}
"""
    destino = Path(salida) / "fase0_divisas.md"
    destino.write_text(md, encoding="utf-8")
    return destino


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--procesado", default="data/processed", type=Path)
    p.add_argument("--raw", default="data/raw", type=Path)
    p.add_argument("--salida", default="reports", type=Path)
    a = p.parse_args(argv)
    print(generar(a.procesado, a.raw, a.salida))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
