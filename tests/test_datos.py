import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from laboratorio.datos.__main__ import main
from laboratorio.datos.lectores import leer_archivo
from laboratorio.datos.manifiesto import construir_manifiesto, sha256
from laboratorio.datos.validacion import tipo_serie, validar_serie

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"


def serie(valores, inicio="2024-01-01", freq="D"):
    return pd.Series(valores, index=pd.date_range(inicio, periods=len(valores), freq=freq))


# --- validaciones (datos sintéticos) ---------------------------------------

def test_detecta_fechas_duplicadas():
    s = serie([1.0, 2.0, 3.0, 4.0])
    s.index = pd.DatetimeIndex(["2024-01-01", "2024-01-02", "2024-01-02", "2024-01-03"])
    r = validar_serie(s)
    assert r["duplicadas"] == 1
    assert r["duplicadas_muestra"] == ["2024-01-02"]


def test_detecta_huecos_pero_tolera_fin_de_semana():
    fechas = pd.DatetimeIndex(["2024-01-05", "2024-01-08", "2024-01-09",   # viernes -> lunes
                               "2024-01-10", "2024-01-25", "2024-01-26"])  # hueco de 15 d
    s = pd.Series([100.0] * 6, index=fechas)
    r = validar_serie(s)
    assert r["huecos"] == 1
    assert "2024-01-25" in r["huecos_muestra"][0]


def test_salto_mayor_a_5_por_ciento_en_nivel():
    r = validar_serie(serie([100.0, 101.0, 107.0, 107.5]), tipo="nivel")  # +5,9 %
    assert r["saltos"] == 1
    assert validar_serie(serie([100.0, 101.0, 105.0, 105.5]), "nivel")["saltos"] == 0  # +3,96 %


def test_tasa_usa_puntos_porcentuales():
    assert validar_serie(serie([4.75, 5.0, 5.25]), tipo="tasa")["saltos"] == 0
    assert validar_serie(serie([4.75, 11.0, 11.2]), tipo="tasa")["saltos"] == 1


def test_fechas_futuras_se_separan():
    s = serie([1.0, 1.0, 1.0, 1.0, 50.0])
    r = validar_serie(s, corte=pd.Timestamp("2024-01-04"))
    assert r["fechas_futuras"] == 1
    assert r["saltos"] == 0 and r["fecha_max"] == "2024-01-04"


def test_series_de_baja_frecuencia_no_se_prueban_en_saltos():
    r = validar_serie(serie([1.0, 9.0, 1.0, 9.0], freq="YE"), tipo="nivel")
    assert r["saltos_probados"] is False and r["saltos"] == 0


def test_clasificacion_nivel_o_tasa():
    assert tipo_serie("TRM (Superfinanciera)") == "nivel"
    assert tipo_serie("Unidad de Valor Real (UVR)(Dato diario)") == "nivel"
    assert tipo_serie("Índice de Precios al Consumidor (IPC)(Dato fin de mes)") == "nivel"
    assert tipo_serie("Tasa de política monetaria(Dato diario)") == "tasa"
    assert tipo_serie("Indicador Bancario de Referencia (IBR) a 1 mes, nominal(Dato diario)") == "tasa"
    assert tipo_serie("Unidad de Valor Real (UVR)(Variación porcentual anual)") == "tasa"


# --- manifiesto (archivo sintético) ----------------------------------------

def test_manifiesto_sintetico(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    csv = raw / "trm_superfinanciera_20240110.csv"
    csv.write_text("VALOR,UNIDAD,VIGENCIADESDE,VIGENCIAHASTA\n"
                   "3900.50,COP,03/01/2024,03/01/2024\n"
                   "3910.00,COP,02/01/2024,02/01/2024\n", encoding="utf-8")
    (raw / "MANIFEST.csv").write_text("archivo,url\ntrm_superfinanciera_20240110.csv,http://x\n")
    m = construir_manifiesto(raw)
    (a,) = m["archivos"]
    assert a["archivo"] == csv.name and a["url"] == "http://x"
    assert a["sha256"] == hashlib.sha256(csv.read_bytes()).hexdigest() == sha256(csv)
    assert (a["filas"], a["fecha_min"], a["fecha_max"]) == (2, "2024-01-02", "2024-01-03")
    assert a["fecha_descarga"] == "2024-01-10"


# --- datos reales ------------------------------------------------------------

def test_trm_superfinanciera_real_sin_duplicados():
    series, filas = leer_archivo(next(RAW.glob("trm_superfinanciera_*.csv")))
    (s,) = series.values()
    assert filas == len(s) > 8000
    assert s.index.min() == pd.Timestamp("1991-12-02")
    assert validar_serie(s, "nivel")["duplicadas"] == 0


def test_trm_banrep_inicia_27_nov_1991():
    series, _ = leer_archivo(next(RAW.glob("trm_banrep_*.xlsx")))
    s = next(v for k, v in series.items() if "Dato diario" in k)
    assert s.index.min() == pd.Timestamp("1991-11-27") and abs(s.iloc[0] - 693.32) < 1e-6


def test_ipc_dane_real():
    series, _ = leer_archivo(next(RAW.glob("ipc_dane_*.xlsx")))
    (s,) = series.values()
    assert s.index.min() == pd.Timestamp("2003-01-31") and abs(s.iloc[0] - 50.42) < 1e-9


def test_cli_genera_manifest_y_validacion(tmp_path):
    assert main(["--raw", str(RAW), "--salida", str(tmp_path)]) == 0
    m = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    en_disco = {p.name for p in RAW.iterdir() if p.is_file() and p.name != "MANIFEST.csv"}
    assert {a["archivo"] for a in m["archivos"]} == en_disco
    for a in m["archivos"]:
        assert a["sha256"] == sha256(RAW / a["archivo"])
        assert a["filas"] > 0 and a["fecha_min"] <= a["fecha_max"]
    val = json.loads((tmp_path / "validacion.json").read_text(encoding="utf-8"))
    assert set(val) == en_disco


# --- limpieza -----------------------------------------------------------------

from laboratorio.datos.limpieza import (construir_trm, etiquetar_estres,  # noqa: E402
                                        etiquetar_regimen, limpiar)


def test_regimen_banda_y_flotacion():
    f = pd.DatetimeIndex(["1999-09-24", "1999-09-25", "2000-01-03"])
    assert list(etiquetar_regimen(f)) == ["banda", "flotacion", "flotacion"]


def test_estres_etiqueta_ventanas():
    f = pd.DatetimeIndex(["2008-01-02", "2008-10-10", "2020-03-13", "2021-06-01"])
    assert list(etiquetar_estres(f)) == ["", "crisis_2008", "covid_2020", ""]


def test_construir_trm_retornos_y_duplicados():
    idx = pd.DatetimeIndex(["2020-01-01", "2020-01-02", "2020-01-02", "2020-01-05"])
    sf = pd.Series([100.0, 110.0, 110.0, 99.0], index=idx)
    br = pd.Series([100.0, 110.0], index=pd.DatetimeIndex(["2019-12-31", "2020-01-02"]))
    log: dict = {}
    df = construir_trm(sf, br, log)
    assert len(df) == 3 and log["duplicadas_eliminadas"]["trm"] == 1
    assert df["ret_log"].iloc[1] == pytest.approx(np.log(1.1))
    assert list(df["dias"].iloc[1:]) == [1, 3]
    assert log["contraste_trm_banrep"]["banrep_previas_a_superfinanciera"] == 1


@pytest.fixture(scope="module")
def procesado(tmp_path_factory):
    sal = tmp_path_factory.mktemp("processed")
    log = limpiar(RAW, sal)
    return sal, log


def test_limpieza_trm_real(procesado):
    sal, log = procesado
    df = pd.read_csv(sal / "trm.csv", parse_dates=["fecha"], index_col="fecha")
    assert df.index.is_unique and df.index.is_monotonic_increasing
    assert (df["trm"] > 0).all() and df.index.min() == pd.Timestamp("1991-12-02")
    assert (df.loc[:"1999-09-24", "regimen"] == "banda").all()
    assert (df.loc["1999-09-25":, "regimen"] == "flotacion").all()
    assert np.allclose(df["ret_log"].dropna(), np.log(df["trm"]).diff().dropna())
    assert log["trm"]["contraste_trm_banrep"]["difieren_mas_de_0.01"] < 50


def test_limpieza_sin_fechas_futuras_ni_duplicadas(procesado):
    sal, log = procesado
    corte = pd.Timestamp(log["fecha_corte"])
    for nombre in log["salidas"]:
        df = pd.read_csv(sal / f"{nombre}.csv", parse_dates=["fecha"], index_col="fecha")
        assert df.index.is_unique, nombre
        if nombre != "ipc_mensual":
            assert df.index.max() <= corte, nombre


def test_ipc_banrep_coincide_con_dane(procesado):
    _, log = procesado
    assert log["ipc"]["contraste_ipc_dane"]["max_dif_abs"] == 0.0
    assert log["ipc"]["contraste_ipc_dane"]["meses_comunes"] == 286
