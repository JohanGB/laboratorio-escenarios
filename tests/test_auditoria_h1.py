"""Auditoría independiente, hallazgo H1: tres errores realistas que la suite no detectaba.

1. M02: rezagos de publicación de las externas en 0 (fuga de datos del mismo día del origen).
2. M07: rezagos HAC por defecto sin el término h − 1 (traslape del objetivo).
3. M11: otra línea base confirmatoria a h = 63 distinta de la del prerregistro.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from laboratorio.backtest import final
from laboratorio.backtest.datos import Vista, construir_vista
from laboratorio.evaluacion.pruebas import diebold_mariano, rezagos_por_defecto, varianza_largo_plazo
from laboratorio.modelos import caracteristicas

RAIZ = Path(__file__).resolve().parents[1]

# Rezagos de publicación en días calendario: el contrato (verificado con datos reales en la auditoría).
REZAGOS_PUBLICACION = {"brent_usd": 3, "dolar_amplio": 8, "fed_funds": 2, "politica": 1}
# Columna externa -> características que la consumen.
CARACT_POR_EXTERNA = {"brent_usd": ["brent30"], "dolar_amplio": ["dolar30"],
                      "fed_funds": ["fed", "fed90"], "politica": ["pol", "pol90"]}


# ---------------------------------------------------------------- 1. rezagos de publicación

def _vista_externas_diarias(n=400, seed=5):
    """TRM en días hábiles; externas en días CALENDARIO (así hay dato en cada fecha de la ventana
    de rezago) con valores positivos y distintos día a día."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2004-01-02", periods=n)
    r = rng.standard_t(5, n) * 0.006
    trm = pd.DataFrame({"trm": 3000 * np.exp(np.cumsum(r)), "regimen": "flotacion", "estres": ""}, index=idx)
    cal = pd.date_range(idx[0] - pd.Timedelta(days=200), idx[-1] + pd.Timedelta(days=10), freq="D")
    ext = pd.DataFrame({c: 50 + rng.normal(size=len(cal)).cumsum() * 0.1 + 100 for c in REZAGOS_PUBLICACION},
                       index=cal)
    return construir_vista(trm, ext)


def _con_externa_alterada(v: Vista, col: str, desde, valor=1e6) -> Vista:
    ext = v.externas.copy()
    ext.loc[ext.index >= desde, col] = valor
    return Vista(v.fechas, v.logp, v.r, v.banda, v.estres, ext)


def test_rezagos_de_publicacion_fijados():
    """El contrato de rezagos (días) está fijado; un cero en cualquiera abre la fuga."""
    assert caracteristicas.REZAGO_DIAS == REZAGOS_PUBLICACION


@pytest.mark.parametrize("col", list(REZAGOS_PUBLICACION))
def test_ninguna_covariable_usa_datos_posteriores_a_origen_menos_rezago(col):
    v = _vista_externas_diarias()
    t = 300
    origen = v.fechas[t]
    rez = REZAGOS_PUBLICACION[col]
    base = caracteristicas.construir(v).iloc[t]
    # Datos con fecha en (origen − rezago, ∞): aún no publicados en el origen. Alterarlos NO puede
    # mover ninguna característica de la fila del origen.
    primera_no_publicada = origen - pd.Timedelta(days=rez) + pd.Timedelta(days=1)
    sucio = caracteristicas.construir(_con_externa_alterada(v, col, primera_no_publicada)).iloc[t]
    for c in CARACT_POR_EXTERNA[col]:
        assert sucio[c] == base[c], f"{c} usa un dato de {col} posterior a origen − {rez} días"
    # Control (la prueba no es vacía): el dato fechado exactamente en origen − rezago SÍ se usa.
    ultimo_publicado = origen - pd.Timedelta(days=rez)
    usado = caracteristicas.construir(_con_externa_alterada(v, col, ultimo_publicado)).iloc[t]
    assert any(usado[c] != base[c] for c in CARACT_POR_EXTERNA[col])


# ---------------------------------------------------------------- 2. HAC con h − 1

def test_varianza_bartlett_calculada_a_mano():
    """d = [1,2,3,2,1]: d̄ = 1,8; γ0 = 0,56, γ1 = 0,032, γ2 = −0,376, γ3 = −0,064, γ4 = 0,128.
    L = 2: 0,56 + 2·(2/3)·0,032 + 2·(1/3)·(−0,376) = 0,352.
    L = 4: 0,56 + 2·[(4/5)·0,032 + (3/5)·(−0,376) + (2/5)·(−0,064) + (1/5)·0,128] = 0,16."""
    d = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
    assert varianza_largo_plazo(d, 2) == pytest.approx(0.352, abs=1e-12)
    assert varianza_largo_plazo(d, 4) == pytest.approx(0.16, abs=1e-12)


def test_rezagos_por_defecto_incluyen_h_menos_1():
    # h − 1 + ⌊4(n/100)^(2/9)⌋: el segundo término es 4 con n = 100 y 7 con n = 1700
    # (la corrida publicada usa 7, 11, 27 y 69 a h = 1, 5, 21 y 63).
    assert rezagos_por_defecto(100, 1) == 4
    assert rezagos_por_defecto(100, 5) == 8
    assert rezagos_por_defecto(100, 21) == 24
    assert rezagos_por_defecto(100, 63) == 66
    assert rezagos_por_defecto(1700, 63) == 62 + 7


def test_dm_por_defecto_usa_los_rezagos_con_traslape():
    """Sin `rezagos` explícito (como en la prueba final) y h = 3, n = 5: L = (3 − 1) + 2 = 4, y la
    varianza de largo plazo es la de Bartlett con L = 4 (0,16), no la de L = 2 (0,352)."""
    d = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
    res = diebold_mariano(d, np.zeros(5), h=3)
    assert res.detalle["rezagos"] == 4
    assert res.detalle["var_lp"] == pytest.approx(0.16, abs=1e-12)


# ---------------------------------------------------------------- 3. línea base confirmatoria

def _tabla_prerregistro_seccion5():
    texto = (RAIZ / "docs" / "prerregistro.md").read_text(encoding="utf-8")
    sec = texto.split("## 5. Hipótesis confirmatorias", 1)[1].split("\n## ", 1)[0]
    filas = re.findall(r"^\|\s*(\d+)\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|", sec, flags=re.M)
    return tuple((int(h), campeon, base) for h, campeon, base in filas)


def test_confirmatorias_coinciden_con_el_prerregistro():
    previstas = _tabla_prerregistro_seccion5()
    assert len(previstas) == 4, "no se pudo leer la tabla de la sección 5 del prerregistro"
    assert tuple(final.CONFIRMATORIAS) == previstas
