"""Divisas contra el peso (M1): cruces X/COP = TRM × (USD por X), sin relleno.

Fuente de las divisas: FRED, tasas H.10 de la Reserva Federal (mediodía en Nueva York), un CSV
por serie en data/raw (`<divisa>_fred_<id>_<AAAAMMDD>.csv`). La TRM es la de Superfinanciera
(data/processed/trm.csv).

Alineación (supuesto `divisas.desfase_fred` del registro, docs/supuestos.md). La fecha de la TRM
es la de su vigencia (martes a sábado): la TRM vigente el día t se calcula con las operaciones del
día hábil anterior. Por eso la TRM de t se cruza con el precio H.10 del día hábil (lunes a viernes)
anterior a t: `DESFASE_FRED = -1`. Se comprobó con datos anteriores a 2020-01-01: de los desfases
−1, 0 y +1, el −1 tiene la mayor correlación contemporánea de rendimientos en las seis divisas
(`correlaciones_desfase`; hay prueba). El desfase se cuenta en días de lunes a viernes; si el
precio H.10 de ese día no existe (festivo en EE. UU.), la fila no existe: unión interna, sin
relleno ni arrastre.

Cada fila de `divisas.csv` lleva la fecha de la TRM. Su régimen es el de la divisa en la fecha
de su precio H.10, salvo durante la banda cambiaria colombiana, que manda (`banda_cop`).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .limpieza import FIN_BANDA

CORTE_ALINEACION = pd.Timestamp("2020-01-01")  # la alineación se decide sin mirar 2020 en adelante

# Divisa -> serie FRED. Todas vienen en «X por USD» salvo DEXUSEU, que ya es USD por EUR.
SERIES = {"EUR": "DEXUSEU", "MXN": "DEXMXUS", "JPY": "DEXJPUS",
          "CNY": "DEXCHUS", "CHF": "DEXSZUS", "BRL": "DEXBZUS"}
YA_EN_USD_POR_UNIDAD = {"DEXUSEU"}
ORDEN = ("USD", *SERIES)

DESFASES = (-1, 0, 1)
DESFASE_FRED = -1
# La correlación con el yuan fijo no informa nada (su rendimiento es cero): se mide desde que flota.
DESDE_CORRELACION = {"CNY": pd.Timestamp("2005-07-22")}

SALTO_REVISION = 0.08   # cambios diarios mayores al 8 % se listan para revisión manual; nunca se borran

# Regímenes por divisa (editables): lista de (desde, etiqueta), en orden; la primera etiqueta
# rige antes de la primera fecha.
REGIMENES: dict[str, list[tuple[str | None, str]]] = {
    # PBoC, anuncio de reforma del régimen cambiario del RMB, 21-jul-2005: deja el tipo fijo
    # (8,2765 por USD) por una flotación administrada frente a una canasta.
    "CNY": [(None, "fijo"), ("2005-07-22", "flotacion_administrada")],
    # BNS: piso de 1,20 CHF por EUR desde el 6-sep-2011; lo abandona el 15-ene-2015 (episodio).
    "CHF": [(None, "flotacion"), ("2011-09-06", "piso"), ("2015-01-15", "flotacion")],
    # BCB, Comunicado 6.565: libre flotación del real desde el 18-ene-1999 (antes, bandas).
    "BRL": [(None, "banda"), ("1999-01-18", "flotacion")],
    # Banxico/SHCP: libre flotación del peso mexicano desde el 22-dic-1994 (antes, banda).
    "MXN": [(None, "banda"), ("1994-12-22", "flotacion")],
    # El euro cotiza desde el 4-ene-1999 (primer dato de DEXUSEU).
    "EUR": [(None, "flotacion")],
    "JPY": [(None, "flotacion")],
    "USD": [(None, "flotacion")],
}
EPISODIOS = {"chf_fin_del_piso": "2015-01-15", "cny_fin_del_tipo_fijo": "2005-07-21"}


def usd_por_unidad(valores: pd.Series, serie: str) -> pd.Series:
    """Precio en USD de una unidad de la divisa, a partir de la cotización de FRED."""
    return valores.astype(float) if serie in YA_EN_USD_POR_UNIDAD else 1.0 / valores.astype(float)


def fechas_fred(fechas_trm: pd.DatetimeIndex, desfase: int) -> pd.DatetimeIndex:
    """Fecha del precio H.10 que se cruza con la TRM de cada fecha (días de lunes a viernes).

    −1: día hábil anterior a t (sábado -> viernes, martes -> lunes); 0: el mismo día; +1: el
    siguiente día hábil después de t.
    """
    d = pd.DatetimeIndex(fechas_trm).values.astype("datetime64[D]")
    if desfase == 0:
        return pd.DatetimeIndex(d)
    roll = "forward" if desfase < 0 else "backward"
    return pd.DatetimeIndex(np.busday_offset(d, desfase, roll=roll))


def alinear(trm: pd.Series, usd_x: pd.Series, desfase: int = DESFASE_FRED) -> pd.DataFrame:
    """Une la TRM con el precio H.10 que le corresponde. Unión interna: sin relleno."""
    ff = fechas_fred(trm.index, desfase)
    usd_x = usd_x.dropna()
    df = pd.DataFrame({"trm": trm.to_numpy(dtype=float), "fecha_fred": ff}, index=trm.index)
    df = df[df["fecha_fred"].isin(usd_x.index)].copy()
    df["usd_por_unidad"] = usd_x.loc[df["fecha_fred"]].to_numpy()
    df["cop_por_unidad"] = df["trm"] * df["usd_por_unidad"]
    df.index.name = "fecha"
    return df


def correlaciones_desfase(trm: pd.Series, usd_x: pd.Series, desfases=DESFASES,
                          hasta: pd.Timestamp = CORTE_ALINEACION,
                          desde: pd.Timestamp | None = None) -> dict[int, tuple[float, int]]:
    """Correlación de Pearson entre los rendimientos de la TRM y de USD por X, por desfase.

    Solo usa datos con fecha < `hasta` en las dos series (ningún dato posterior entra). Los
    rendimientos se calculan entre filas consecutivas de la unión, así los dos cubren el mismo
    intervalo. Devuelve {desfase: (correlación, n)}.
    """
    trm = trm[trm.index < hasta]
    usd_x = usd_x[usd_x.index < hasta]
    if desde is not None:
        trm = trm[trm.index >= desde]
        usd_x = usd_x[usd_x.index >= desde]
    out = {}
    for k in desfases:
        a = alinear(trm, usd_x, k)
        r = np.log(a[["trm", "usd_por_unidad"]]).diff().dropna()
        out[k] = (round(float(r["trm"].corr(r["usd_por_unidad"])), 12), int(len(r)))
    return out


def regimen(divisa: str, fechas_fred_: pd.DatetimeIndex, fechas_trm: pd.DatetimeIndex) -> np.ndarray:
    """Régimen de cada fila: el de la divisa en la fecha de su precio; la banda del COP manda."""
    tramos = REGIMENES[divisa]
    f = pd.DatetimeIndex(fechas_fred_)
    out = np.full(len(f), tramos[0][1], dtype=object)
    for desde, etiqueta in tramos[1:]:
        out[f >= pd.Timestamp(desde)] = etiqueta
    out[pd.DatetimeIndex(fechas_trm) < FIN_BANDA] = "banda_cop"
    return out


def series_fred(lecturas: dict) -> dict[str, pd.Series]:
    """{divisa: cotización FRED} desde las lecturas de data/raw (por prefijo de nombre)."""
    out = {}
    for divisa, serie in SERIES.items():
        prefijo = f"{divisa.lower()}_fred_{serie.lower()}_"
        (nombre,) = [n for n in lecturas if n.lower().startswith(prefijo)]
        (s,) = lecturas[nombre][0].values()
        out[divisa] = s
    return out


def construir_divisas(trm: pd.Series, fred: dict[str, pd.Series], log: dict | None = None) -> pd.DataFrame:
    """Formato largo: fecha, divisa, cop_por_unidad, ret_log, regimen (USD incluido)."""
    log = {} if log is None else log
    log["desfase_fred"] = DESFASE_FRED
    log["dias"] = {}
    partes = []
    usd = pd.DataFrame({"cop_por_unidad": trm.to_numpy(dtype=float),
                        "regimen": regimen("USD", trm.index, trm.index)}, index=trm.index)
    partes.append(("USD", usd))
    for divisa in SERIES:
        s = fred[divisa]
        assert not s.index.duplicated().any(), f"{divisa}: fechas duplicadas en FRED"
        assert (s.dropna() > 0).all(), f"{divisa}: cotización no positiva"
        a = alinear(trm, usd_por_unidad(s, SERIES[divisa]), DESFASE_FRED)
        a["regimen"] = regimen(divisa, pd.DatetimeIndex(a["fecha_fred"]), a.index)
        # TRM con fecha en el tramo cubierto por FRED: las que quedan sin pareja se pierden.
        en_rango = trm[(fechas_fred(trm.index, DESFASE_FRED) >= s.dropna().index.min())
                       & (fechas_fred(trm.index, DESFASE_FRED) <= s.dropna().index.max())]
        log["dias"][divisa] = {"fechas_trm": int(len(en_rango)), "pareadas": int(len(a)),
                               "perdidas": int(len(en_rango) - len(a)),
                               "desde": str(a.index.min().date()), "hasta": str(a.index.max().date())}
        partes.append((divisa, a[["cop_por_unidad", "regimen"]]))
    filas = []
    for divisa, df in partes:
        df = df.sort_index()
        filas.append(pd.DataFrame({"fecha": df.index, "divisa": divisa,
                                   "cop_por_unidad": df["cop_por_unidad"].to_numpy(),
                                   "ret_log": np.log(df["cop_por_unidad"]).diff().to_numpy(),
                                   "regimen": df["regimen"].to_numpy()}))
    return pd.concat(filas, ignore_index=True)


def validar_divisas(df: pd.DataFrame) -> dict:
    """Positivos, duplicados y saltos diarios > 8 % (listados para revisión, nunca borrados)."""
    cambio = np.expm1(df["ret_log"])
    saltos = df[cambio.abs() > SALTO_REVISION]
    return {
        "filas": int(len(df)),
        "positivos": bool((df["cop_por_unidad"] > 0).all()),
        "duplicados": int(df.duplicated(["fecha", "divisa"]).sum()),
        "saltos_8pct": [{"fecha": str(pd.Timestamp(r.fecha).date()), "divisa": r.divisa,
                         "cambio_pct": round(100 * float(np.expm1(r.ret_log)), 4),
                         "regimen": r.regimen} for r in saltos.itertuples()],
    }


def desde_lecturas(lecturas: dict) -> pd.DataFrame:
    """Lo mismo que escribe la limpieza, calculado en memoria desde las lecturas de data/raw."""
    from .limpieza import construir_trm
    (nombre,) = [n for n in lecturas if n.startswith("trm_superfinanciera")]
    (sf,) = lecturas[nombre][0].values()
    sin_contraste = pd.Series(dtype=float, index=pd.DatetimeIndex([]))  # el contraste con BanRep no cambia la TRM
    trm = construir_trm(sf, sin_contraste, {})["trm"]
    return construir_divisas(trm, series_fred(lecturas))
