"""M1: datos multidivisa (FRED H.10 cruzado con la TRM)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from laboratorio.datos import divisas as D
from laboratorio.datos.lectores import fecha_descarga, leer_archivo
from laboratorio.motor.supuestos import Registro

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"
PROC = RAIZ / "data" / "processed"
DIVISAS_NUEVAS = ("EUR", "MXN", "JPY", "CNY", "CHF", "BRL")


def _archivo(divisa: str) -> Path:
    (f,) = RAW.glob(f"{divisa.lower()}_fred_{D.SERIES[divisa].lower()}_*.csv")
    return f


def _fred(divisa: str) -> pd.Series:
    (s,) = leer_archivo(_archivo(divisa))[0].values()
    return s


@pytest.fixture(scope="module")
def divisas_csv() -> pd.DataFrame:
    return pd.read_csv(PROC / "divisas.csv", parse_dates=["fecha"])


@pytest.fixture(scope="module")
def trm() -> pd.Series:
    return pd.read_csv(PROC / "trm.csv", parse_dates=["fecha"], index_col="fecha")["trm"]


# --- lectura -------------------------------------------------------------------------------------
@pytest.mark.parametrize("divisa", DIVISAS_NUEVAS)
def test_lectura_de_cada_csv_de_fred(divisa):
    f = _archivo(divisa)
    series, filas = leer_archivo(f)
    (s,) = series.values()
    with open(RAW / "MANIFEST.csv", encoding="utf-8", newline="") as fh:
        manifiesto = {r["archivo"]: r for r in csv.DictReader(fh)}
    fila = manifiesto[f.name]
    assert int(fila["filas"]) == filas and len(s) > 6000
    assert fila["url"].endswith(f"id={D.SERIES[divisa]}")
    assert (s > 0).all() and s.index.is_unique and s.index.is_monotonic_increasing
    assert s.index.max() <= fecha_descarga(f)


# --- unidades y cruce ----------------------------------------------------------------------------
def test_eur_ya_viene_en_usd_por_euro_y_las_demas_se_invierten():
    assert D.SERIES["EUR"] == "DEXUSEU"
    eur = D.usd_por_unidad(pd.Series([1.10]), "DEXUSEU")
    mxn = D.usd_por_unidad(pd.Series([20.0]), "DEXMXUS")
    assert eur.iloc[0] == 1.10          # USD por EUR: no se invierte
    assert mxn.iloc[0] == 1 / 20.0      # MXN por USD -> USD por MXN
    for d in DIVISAS_NUEVAS[1:]:
        assert D.SERIES[d] not in D.YA_EN_USD_POR_UNIDAD


def test_desfase_menos_uno_es_el_dia_habil_anterior():
    t = pd.DatetimeIndex(["2024-01-06", "2024-01-09", "2024-01-10"])   # sáb, mar, mié
    assert list(D.fechas_fred(t, -1)) == list(pd.DatetimeIndex(["2024-01-05", "2024-01-08", "2024-01-09"]))
    assert list(D.fechas_fred(t, 0)) == list(t)
    assert list(D.fechas_fred(t, 1)) == list(pd.DatetimeIndex(["2024-01-08", "2024-01-10", "2024-01-11"]))


def test_cruce_sintetico_sin_relleno():
    trm = pd.Series([4000.0, 4010.0, 4020.0],
                    index=pd.DatetimeIndex(["2024-01-06", "2024-01-09", "2024-01-10"]))
    usd_eur = pd.Series([1.10, 1.11], index=pd.DatetimeIndex(["2024-01-05", "2024-01-09"]))  # falta el 8
    a = D.alinear(trm, usd_eur, -1)
    assert list(a.index) == [pd.Timestamp("2024-01-06"), pd.Timestamp("2024-01-10")]
    assert list(a["fecha_fred"]) == [pd.Timestamp("2024-01-05"), pd.Timestamp("2024-01-09")]
    assert a["cop_por_unidad"].tolist() == [4000.0 * 1.10, 4020.0 * 1.11]


def test_cruce_real_contra_valores_calculados_a_mano(divisas_csv):
    # TRM vigente el sáb. 2019-12-14 = 3374,29; H.10 del vie. 2019-12-13: 1,1128 USD/EUR,
    # 19,0660 MXN/USD y 109,28 JPY/USD (archivos de data/raw).
    t = divisas_csv[divisas_csv["fecha"] == "2019-12-14"].set_index("divisa")["cop_por_unidad"]
    assert t["USD"] == pytest.approx(3374.29, rel=1e-12)
    assert t["EUR"] == pytest.approx(3754.909912, rel=1e-9)
    assert t["MXN"] == pytest.approx(176.97943984055388, rel=1e-9)
    assert t["JPY"] == pytest.approx(30.877470717423133, rel=1e-9)


# --- alineación: decisión por calendario, comprobada con datos < 2020 --------------------------
def test_correlaciones_no_miran_datos_desde_2020(trm):
    eur = D.usd_por_unidad(_fred("EUR"), "DEXUSEU")
    base = D.correlaciones_desfase(trm, eur)
    eur_mal = eur.copy()
    eur_mal[eur_mal.index >= "2020-01-01"] *= np.random.default_rng(0).uniform(0.5, 1.5, (eur_mal.index >= "2020-01-01").sum())
    trm_mal = trm.copy()
    trm_mal[trm_mal.index >= "2020-01-01"] = 1.0
    assert D.correlaciones_desfase(trm_mal, eur_mal) == base


def test_desfase_elegido_es_el_de_mayor_correlacion_en_todas_las_divisas(trm):
    medias = {k: 0.0 for k in D.DESFASES}
    for d in DIVISAS_NUEVAS:
        u = D.usd_por_unidad(_fred(d), D.SERIES[d])
        c = D.correlaciones_desfase(trm, u, desde=D.DESDE_CORRELACION.get(d))
        assert max(c, key=lambda k: abs(c[k][0])) == D.DESFASE_FRED, d
        for k in D.DESFASES:
            medias[k] += abs(c[k][0]) / len(DIVISAS_NUEVAS)
    assert max(medias, key=medias.get) == D.DESFASE_FRED == -1


def test_desfase_registrado_como_supuesto():
    s = Registro(RAIZ / "data/supuestos/registro.jsonl").vigente("divisas.desfase_fred")
    assert s.valor == D.DESFASE_FRED
    assert "2020-01-01" in s.fuente


# --- regímenes -----------------------------------------------------------------------------------
@pytest.mark.parametrize("divisa,fecha,esperado", [
    ("CNY", "2005-07-21", "fijo"), ("CNY", "2005-07-22", "flotacion_administrada"),
    ("CHF", "2011-09-05", "flotacion"), ("CHF", "2011-09-06", "piso"),
    ("CHF", "2015-01-14", "piso"), ("CHF", "2015-01-15", "flotacion"),
    ("BRL", "1999-01-15", "banda"), ("BRL", "1999-01-18", "flotacion"),
    ("MXN", "1994-12-21", "banda"), ("MXN", "1994-12-22", "flotacion"),
    ("EUR", "1999-01-04", "flotacion"), ("JPY", "1995-01-03", "flotacion"),
])
def test_regimen_de_la_divisa_por_fecha_de_observacion(divisa, fecha, esperado):
    f = pd.DatetimeIndex([fecha])
    assert D.regimen(divisa, f, pd.DatetimeIndex(["2005-01-04"]))[0] == esperado


def test_la_banda_colombiana_manda_sobre_el_regimen_de_la_divisa():
    r = D.regimen("EUR", pd.DatetimeIndex(["1999-03-01", "1999-10-01"]),
                  pd.DatetimeIndex(["1999-03-02", "1999-10-02"]))
    assert list(r) == ["banda_cop", "flotacion"]


# --- salida data/processed/divisas.csv ----------------------------------------------------------
def test_divisas_csv_formato_largo(divisas_csv):
    assert list(divisas_csv.columns) == ["fecha", "divisa", "cop_por_unidad", "ret_log", "regimen"]
    assert set(divisas_csv["divisa"]) == {"USD", *DIVISAS_NUEVAS}
    assert (divisas_csv["cop_por_unidad"] > 0).all()
    assert not divisas_csv.duplicated(["fecha", "divisa"]).any()
    assert divisas_csv["cop_por_unidad"].notna().all()


def test_ningun_valor_posterior_a_la_fecha_de_descarga(divisas_csv):
    trm_desc = fecha_descarga(next(RAW.glob("trm_superfinanciera_*.csv")))
    assert divisas_csv["fecha"].max() <= trm_desc
    for d in DIVISAS_NUEVAS:
        sub = divisas_csv[divisas_csv["divisa"] == d]
        assert D.fechas_fred(pd.DatetimeIndex(sub["fecha"]), D.DESFASE_FRED).max() <= fecha_descarga(_archivo(d))


def test_triangulacion_y_rendimientos(divisas_csv, trm):
    usd = divisas_csv[divisas_csv["divisa"] == "USD"].set_index("fecha")["cop_por_unidad"]
    assert usd.index.equals(trm.index)
    np.testing.assert_allclose(usd.to_numpy(), trm.to_numpy(), rtol=1e-12)
    for d in DIVISAS_NUEVAS:
        sub = divisas_csv[divisas_csv["divisa"] == d].set_index("fecha")
        u = D.usd_por_unidad(_fred(d), D.SERIES[d])
        ff = D.fechas_fred(sub.index, D.DESFASE_FRED)
        np.testing.assert_allclose(sub["cop_por_unidad"] / usd.loc[sub.index], u.loc[ff].to_numpy(), rtol=1e-9)
        r = np.log(sub["cop_por_unidad"]).diff()
        # el CSV guarda 10 cifras significativas: recalcular desde él difiere a lo sumo ~1e-9
        np.testing.assert_allclose(sub["ret_log"].iloc[1:], r.iloc[1:], rtol=0, atol=1e-8)
        assert np.isnan(sub["ret_log"].iloc[0])


def test_sin_relleno_cada_fila_tiene_su_dato_fred(divisas_csv):
    for d in DIVISAS_NUEVAS:
        sub = divisas_csv[divisas_csv["divisa"] == d]
        ff = D.fechas_fred(pd.DatetimeIndex(sub["fecha"]), D.DESFASE_FRED)
        assert ff.isin(_fred(d).index).all()


def test_dias_perdidos_por_divisa_en_el_log():
    log = json.loads((PROC / "limpieza.json").read_text(encoding="utf-8"))["divisas"]
    for d in DIVISAS_NUEVAS:
        r = log["dias"][d]
        assert r["fechas_trm"] == r["pareadas"] + r["perdidas"] and r["perdidas"] > 0
    assert log["desfase_fred"] == -1


# --- validaciones --------------------------------------------------------------------------------
def test_validacion_lista_los_saltos_y_no_borra_nada():
    df = pd.DataFrame({"fecha": pd.to_datetime(["2014-01-02", "2014-01-03", "2014-01-04"]),
                       "divisa": "BRL", "cop_por_unidad": [100.0, 110.0, 109.0],
                       "ret_log": [np.nan, np.log(1.1), np.log(109 / 110)], "regimen": "flotacion"})
    v = D.validar_divisas(df)
    assert v["positivos"] and v["duplicados"] == 0 and v["filas"] == 3
    assert [s["fecha"] for s in v["saltos_8pct"]] == ["2014-01-03"]
    assert len(df) == 3


def test_validacion_en_data_validacion_json():
    v = json.loads((RAIZ / "data" / "validacion.json").read_text(encoding="utf-8"))
    d = v["processed/divisas.csv"]
    assert d["positivos"] and d["duplicados"] == 0
    assert all(abs(s["cambio_pct"]) > 8 for s in d["saltos_8pct"])


# --- desde 2020: de las divisas nuevas solo conteos (revisión de M1, 17-nov-2026) ----------------
_FECHA = __import__("re").compile(r"(\d{4})-\d{2}-\d{2}")


def _elementos_con_fecha_desde_corte(obj):
    """Elementos de listas (texto o dict) que mencionan una fecha ≥ 2020-01-01."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _elementos_con_fecha_desde_corte(v)
    elif isinstance(obj, list):
        for x in obj:
            texto = json.dumps(x, ensure_ascii=False)
            if any(int(a) >= D.CORTE_VISTO.year for a in _FECHA.findall(texto)):
                yield x
            yield from _elementos_con_fecha_desde_corte(x)


def test_validacion_no_lista_saltos_desde_2020_solo_los_cuenta():
    df = pd.DataFrame({"fecha": pd.to_datetime(["2019-12-30", "2019-12-31", "2021-03-01",
                                                "2021-03-02"]),
                       "divisa": "JPY", "cop_por_unidad": [100.0, 110.0, 111.0, 125.0],
                       "ret_log": [np.nan, np.log(1.1), np.log(111 / 110), np.log(125 / 111)],
                       "regimen": "flotacion"})
    v = D.validar_divisas(df)
    assert [s["fecha"] for s in v["saltos_8pct"]] == ["2019-12-31"]
    assert v["saltos_8pct_desde_corte"] == {"corte": "2020-01-01", "conteo_por_divisa": {"JPY": 1}}
    assert "2021" not in json.dumps(v)


def test_validar_serie_con_censura_no_muestra_saltos_desde_el_corte():
    from laboratorio.datos.validacion import validar_serie
    s = pd.Series([1.0, 1.2, 1.21, 1.5, 1.51],
                  index=pd.to_datetime(["2019-12-26", "2019-12-27", "2019-12-30", "2020-01-02",
                                        "2020-01-03"]))
    r = validar_serie(s, "nivel", censura=D.CORTE_VISTO)
    assert r["saltos"] == 2 and r["saltos_desde_censura"] == 1
    assert len(r["saltos_muestra"]) == 1 and r["saltos_muestra"][0].startswith("2019-12-27")
    assert validar_serie(s, "nivel")["saltos_muestra"][1].startswith("2020-01-02")   # sin censura


def test_data_validacion_json_no_da_valores_de_divisas_nuevas_desde_2020():
    v = json.loads((RAIZ / "data" / "validacion.json").read_text(encoding="utf-8"))
    d = v["processed/divisas.csv"]
    assert all(s["fecha"] < "2020-01-01" for s in d["saltos_8pct"])
    assert d["saltos_8pct_desde_corte"]["corte"] == "2020-01-01"
    assert all(isinstance(n, int) for n in d["saltos_8pct_desde_corte"]["conteo_por_divisa"].values())
    nuevas = {k: s for k, s in v.items() if D.es_divisa_nueva(k)}
    assert len(nuevas) == len(DIVISAS_NUEVAS)
    for nombre, series in nuevas.items():
        for r in series.values():
            assert r["censura"] == "2020-01-01" and isinstance(r["saltos_desde_censura"], int)
    malos = list(_elementos_con_fecha_desde_corte({"d": d, **nuevas}))
    assert not malos, f"{len(malos)} elementos con fecha ≥ 2020 en validacion.json"
