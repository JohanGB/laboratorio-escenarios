"""Limpieza: data/raw/ (inmutable) -> data/processed/ (CSV listos para modelar).

Decisiones (declaradas; ver docs/estado.md):
- TRM maestra = Superfinanciera (una fila por TRM, fecha = inicio de vigencia). La serie
  de Banco de la República solo se usa para contrastar: coincide salvo 31 fechas (09-feb a 02-abr-1993;
  su exporte duplica el 06-feb-1993 y desplaza los datos un día) y sus 5 primeros días
  (27-nov a 01-dic-1991) quedan fuera por un salto de -7,4 % que Superfinanciera no confirma.
- La UVR baja en meses de IPC mensual negativo (2009, 2020...): es legítimo, no error.
- Valores posteriores a la fecha de descarga se descartan (publicados por adelantado).
- Rendimientos logarítmicos solo para la TRM; el resto se deja en niveles/tasas.
- Sin relleno: no se interpolan huecos ni se arrastran valores; las series se unen por fecha.
- Regímenes y eventos de estrés: constantes editables abajo (supuestos del autor).
"""
from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from .lectores import fecha_descarga, leer_archivo
from .manifiesto import listar_raw

# --- regímenes (supuestos declarados) -----------------------------------------
FIN_BANDA = pd.Timestamp("1999-09-25")  # flotación libre desde el 25-sep-1999
ESTRES = {  # etiqueta: (inicio, fin) inclusive
    "crisis_2008": ("2008-09-15", "2009-03-31"),
    "petroleo_2014_2015": ("2014-06-01", "2015-12-31"),
    "covid_2020": ("2020-02-20", "2020-06-30"),
    "estres_2022": ("2022-06-01", "2022-12-31"),
}


def _ascii(x: str) -> str:
    return unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode().lower()


def _buscar(series: dict[str, pd.Series], *fragmentos: str) -> pd.Series:
    """Serie cuyo nombre (sin tildes, minúsculas) contiene todos los fragmentos."""
    frag = [_ascii(f) for f in fragmentos]
    hallados = [k for k in series if all(f in _ascii(k) for f in frag)]
    if len(hallados) != 1:
        raise KeyError(f"{fragmentos}: {len(hallados)} coincidencias {hallados[:3]}")
    return series[hallados[0]]


def _sin_dup(s: pd.Series, log: dict, nombre: str) -> pd.Series:
    n = int(s.index.duplicated().sum())
    if n:
        log.setdefault("duplicadas_eliminadas", {})[nombre] = n
    return s[~s.index.duplicated(keep="last")].sort_index()


def _hasta(s: pd.Series, corte: pd.Timestamp, log: dict, nombre: str) -> pd.Series:
    n = int((s.index > corte).sum())
    if n:
        log.setdefault("futuras_descartadas", {})[nombre] = n
    return s[s.index <= corte]


def etiquetar_regimen(fechas: pd.DatetimeIndex) -> pd.Series:
    return pd.Series(np.where(fechas < FIN_BANDA, "banda", "flotacion"), index=fechas)


def etiquetar_estres(fechas: pd.DatetimeIndex) -> pd.Series:
    et = pd.Series("", index=fechas, dtype=object)
    for nombre, (ini, fin) in ESTRES.items():
        et[(fechas >= ini) & (fechas <= fin)] = nombre
    return et


def construir_trm(sf: pd.Series, banrep: pd.Series, log: dict) -> pd.DataFrame:
    sf = _sin_dup(sf, log, "trm")
    assert (sf > 0).all(), "TRM no positiva"
    df = pd.DataFrame({"trm": sf})
    df["dias"] = df.index.to_series().diff().dt.days
    df["ret_log"] = np.log(df["trm"]).diff()
    df["regimen"] = etiquetar_regimen(df.index)
    df["estres"] = etiquetar_estres(df.index)
    df.index.name = "fecha"

    b = banrep[~banrep.index.duplicated(keep="last")]
    # Valor vigente por día calendario según Superfinanciera (ver vigencias en raw).
    comunes = df["trm"].index.intersection(b.index)
    dif = (df.loc[comunes, "trm"] - b.loc[comunes]).abs()
    log["contraste_trm_banrep"] = {
        "fechas_comunes": int(len(comunes)),
        "difieren_mas_de_0.01": int((dif > 0.01).sum()),
        "primera_diferencia": str(dif[dif > 0.01].index.min().date())
        if (dif > 0.01).any() else None,
        "ultima_diferencia": str(dif[dif > 0.01].index.max().date())
        if (dif > 0.01).any() else None,
        "banrep_previas_a_superfinanciera": int((b.index < df.index.min()).sum()),
    }
    return df


def construir_ipc(banrep: dict, dane: pd.Series, log: dict) -> pd.DataFrame:
    ipc = _sin_dup(_buscar(banrep, "precios al consumidor", "dato fin de mes"), log, "ipc")
    df = pd.DataFrame({"ipc": ipc})
    df["var_mensual_pct"] = _buscar(banrep, "precios al consumidor", "variacion", "mensual")
    df["var_anual_pct"] = _buscar(banrep, "precios al consumidor", "variacion", "anual").reindex(df.index)
    df["ipc_dane"] = dane.reindex(df.index)
    comunes = df["ipc_dane"].dropna()
    log["contraste_ipc_dane"] = {
        "meses_comunes": int(len(comunes)),
        "max_dif_abs": float((df.loc[comunes.index, "ipc"] - comunes).abs().max()),
    }
    df.index.name = "fecha"
    return df


def construir_uvr(banrep: dict, corte, log: dict) -> pd.DataFrame:
    uvr = _hasta(_sin_dup(_buscar(banrep, "valor real", "dato diario"), log, "uvr"),
                 corte, log, "uvr")
    log["uvr_bajadas"] = int((uvr.diff() < 0).sum())
    return uvr.rename("uvr").rename_axis("fecha").to_frame()


def construir_tasas(banrep: dict, corte, log: dict) -> pd.DataFrame:
    cols = {"politica": _buscar(banrep, "politica monetaria", "dato diario")}
    for plazo, k in (("on", "overnight"), ("1m", "1 mes"), ("3m", "3 meses"),
                     ("6m", "6 meses"), ("12m", "12 meses")):
        for tipo in ("nominal", "efectiva"):
            cols[f"ibr_{plazo}_{tipo}"] = _buscar(banrep, "referencia", k, tipo, "dato diario")
    df = pd.concat({k: _hasta(_sin_dup(v, log, k), corte, log, k) for k, v in cols.items()},
                   axis=1, sort=True)
    df.index.name = "fecha"
    return df


def construir_dtf(banrep: dict, corte, log: dict) -> pd.DataFrame:
    sem = _buscar(banrep, "dtf", "semanal", "dato semanal")
    men = _buscar(banrep, "dtf", "mensual", "dato fin de mes")
    df = pd.concat({"dtf_semanal": _hasta(_sin_dup(sem, log, "dtf_semanal"), corte, log, "dtf_semanal"),
                    "dtf_mensual": _hasta(_sin_dup(men, log, "dtf_mensual"), corte, log, "dtf_mensual")},
                   axis=1, sort=True)
    df.index.name = "fecha"
    return df


def construir_externas(lecturas: dict, log: dict) -> pd.DataFrame:
    def una(prefijo):
        k = next(k for k in lecturas if k.startswith(prefijo))
        return list(lecturas[k][0].values())[0]
    df = pd.concat({"brent_usd": _sin_dup(una("brent_fred"), log, "brent"),
                    "dolar_amplio": _sin_dup(una("dolar_amplio_fred"), log, "dolar_amplio"),
                    "fed_funds": _sin_dup(una("fed_funds_fred"), log, "fed_funds")},
                   axis=1, sort=True)
    df.index.name = "fecha"
    return df


def _resumen(df: pd.DataFrame) -> dict:
    return {"filas": int(len(df)), "columnas": list(df.columns),
            "fecha_min": str(df.index.min().date()), "fecha_max": str(df.index.max().date()),
            "nulos": {c: int(df[c].isna().sum()) for c in df.columns if df[c].isna().any()}}


def limpiar(raw: Path, salida: Path) -> dict:
    lecturas = {p.name: leer_archivo(p) for p in listar_raw(raw)}

    def uno(prefijo):
        return next(n for n in lecturas if n.startswith(prefijo))

    nombre_banrep = uno("banrep_suameca")
    banrep = lecturas[nombre_banrep][0]
    corte = fecha_descarga(raw / nombre_banrep)
    trm_br = [v for k, v in lecturas[uno("trm_banrep")][0].items()
              if "dato diario" in _ascii(k)][0]
    sf = list(lecturas[uno("trm_superfinanciera")][0].values())[0]
    dane = list(lecturas[uno("ipc_dane")][0].values())[0]

    log: dict = {"fecha_corte": str(corte.date()), "salidas": {}}
    salidas = {
        "trm": construir_trm(sf, trm_br, log.setdefault("trm", {})),
        "ipc_mensual": construir_ipc(banrep, dane, log.setdefault("ipc", {})),
        "uvr_diaria": construir_uvr(banrep, corte, log.setdefault("uvr", {})),
        "tasas_diarias": construir_tasas(banrep, corte, log.setdefault("tasas", {})),
        "dtf": construir_dtf(banrep, corte, log.setdefault("dtf", {})),
        "externas_diario": construir_externas(lecturas, log.setdefault("externas", {})),
    }
    salida.mkdir(parents=True, exist_ok=True)
    for nombre, df in salidas.items():
        df.to_csv(salida / f"{nombre}.csv", date_format="%Y-%m-%d", float_format="%.10g")
        log["salidas"][nombre] = _resumen(df)
    (salida / "limpieza.json").write_text(json.dumps(log, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    return log


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", default="data/raw", type=Path)
    p.add_argument("--salida", default="data/processed", type=Path)
    a = p.parse_args(argv)
    log = limpiar(a.raw, a.salida)
    for n, r in log["salidas"].items():
        print(f"{n:16} filas={r['filas']:6} {r['fecha_min']}..{r['fecha_max']} nulos={r['nulos']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
