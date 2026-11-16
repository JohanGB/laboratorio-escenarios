"""Lectores de los archivos de data/raw/ -> series de pandas indexadas por fecha.

Cada lector devuelve (series, filas): `series` es {nombre: pd.Series} y `filas` el
número de filas de datos con fecha válida del archivo (sin encabezados ni notas).
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
         "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11,
         "diciembre": 12}


def _num_es(x: pd.Series) -> pd.Series:
    """'3.316,70' -> 3316.70; '-' o vacío -> NaN."""
    s = x.astype("string").str.strip().replace({"-": pd.NA, "": pd.NA})
    s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def _leer_trm_superfinanciera(ruta: Path):
    df = pd.read_csv(ruta)
    df.columns = [c.lower() for c in df.columns]
    fechas = pd.to_datetime(df["vigenciadesde"], format="%d/%m/%Y", errors="coerce")
    s = pd.Series(pd.to_numeric(df["valor"], errors="coerce").to_numpy(), index=fechas)
    s = s[s.index.notna()].sort_index()
    return {"TRM (Superfinanciera)": s}, len(s)


def _leer_suameca(ruta: Path):
    """Exportes de SUAMECA: hoja 'Datos', fila 2 = unidades, última fila = nota."""
    df = pd.read_excel(ruta, sheet_name="Datos", header=0, skiprows=[1], dtype=str)
    fechas = pd.to_datetime(df.iloc[:, 0], format="%d/%m/%Y", errors="coerce")
    ok = fechas.notna()
    df, fechas = df[ok], fechas[ok]
    series = {}
    for col in df.columns[1:]:
        s = pd.Series(_num_es(df[col]).to_numpy(), index=fechas.to_numpy()).dropna()
        if len(s):
            series[col] = s.sort_index()
    return series, int(ok.sum())


def _leer_ipc_dane(ruta: Path):
    """Matriz mes x año (hoja IndicesIPC) -> serie mensual a fin de mes."""
    df = pd.read_excel(ruta, sheet_name=0, header=None, dtype=object)
    fila_enc = df.index[df.iloc[:, 0].astype(str).str.strip() == "Mes"][0]
    años = {j: int(float(v)) for j, v in df.iloc[fila_enc].items()
            if j > 0 and pd.notna(v)}
    datos = {}
    for i in range(fila_enc + 1, len(df)):
        mes = MESES.get(str(df.iat[i, 0]).strip().lower())
        if mes is None:
            break
        for j, año in años.items():
            v = pd.to_numeric(df.iat[i, j], errors="coerce")
            if pd.notna(v):
                datos[pd.Timestamp(año, mes, 1) + pd.offsets.MonthEnd(0)] = float(v)
    s = pd.Series(datos).sort_index()
    return {"IPC (DANE, índice)": s}, len(s)


NOMBRES_FRED = {"DCOILBRENTEU": "Brent spot, USD/barril (FRED)",
                "DTWEXBGS": "Índice dólar amplio nominal (FRED)",
                "DFF": "Tasa Fed funds efectiva, % (FRED)"}


def _leer_fred(ruta: Path):
    """CSV de FRED: observation_date,<ID>; '.' o vacío = sin dato."""
    df = pd.read_csv(ruta, na_values=[".", ""])
    col = df.columns[1]
    fechas = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    s = pd.Series(pd.to_numeric(df[col], errors="coerce").to_numpy(), index=fechas)
    s = s[s.index.notna()].dropna().sort_index()
    return {NOMBRES_FRED.get(col, col): s}, len(df)


def leer_archivo(ruta: str | Path):
    ruta = Path(ruta)
    n = ruta.name.lower()
    if "_fred_" in n and n.endswith(".csv"):
        return _leer_fred(ruta)
    if n.startswith("trm_superfinanciera") and n.endswith(".csv"):
        return _leer_trm_superfinanciera(ruta)
    if n.startswith("ipc_dane"):
        return _leer_ipc_dane(ruta)
    if n.endswith(".xlsx"):
        return _leer_suameca(ruta)
    raise ValueError(f"Formato no soportado: {ruta.name}")


def fecha_descarga(ruta: str | Path) -> pd.Timestamp | None:
    """Fecha de descarga a partir del sufijo _YYYYMMDD del nombre."""
    m = re.search(r"_(\d{8})\.[a-z]+$", Path(ruta).name.lower())
    return pd.to_datetime(m.group(1), format="%Y%m%d") if m else None
