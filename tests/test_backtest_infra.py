from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from laboratorio.backtest.corredor import correr, primer_origen, resumen
from laboratorio.backtest.datos import Vista, cargar_desarrollo, construir_vista
from laboratorio.backtest.particion import INICIO_PRUEBA_FINAL, NIVELES
from laboratorio.modelos.base import Pronosticador

RAIZ = Path(__file__).resolve().parents[1]


def vista_sintetica(n=900, seed=0, inicio="2004-01-02"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(inicio, periods=n)
    trm = pd.DataFrame({"trm": 3000 * np.exp(np.cumsum(rng.normal(0, 0.007, n))),
                        "regimen": "flotacion", "estres": ""}, index=idx)
    ext = pd.DataFrame({"brent_usd": 50 + rng.normal(size=n).cumsum() * 0.1,
                        "dolar_amplio": 100.0, "fed_funds": 1.0, "politica": 5.0}, index=idx)
    return construir_vista(trm, ext)


class Espia(Pronosticador):
    """Registra hasta qué índice mira cada llamada; pronostica normal(0, 0.007·√h)."""
    nombre = "espia"

    def __init__(self):
        super().__init__()
        self.visto_ajuste, self.visto_pronostico, self.origenes = [], [], []

    def ajustar(self, vista):
        self.visto_ajuste.append(vista.n - 1)

    def pronosticar(self, vista, origenes, niveles):
        self.visto_pronostico.append(vista.n - 1)
        self.origenes.append(np.array(origenes))
        z = stats.norm.ppf(niveles)
        return {h: np.tile(0.007 * np.sqrt(h) * z, (len(origenes), 1)) for h in self.horizontes}


def test_vista_hasta_recorta_todo_y_objetivo_es_el_retorno_acumulado():
    v = vista_sintetica(100)
    w = v.hasta(40)
    assert w.n == 41 and len(w.logp) == len(w.r) == len(w.banda) == 41
    assert w.externas.index.max() <= v.fechas[40]
    y = v.objetivo(5)
    assert y[10] == pytest.approx(v.logp[15] - v.logp[10]) and np.isnan(y[-5:]).all()
    assert not np.isnan(y[:-5]).any()
    assert np.isnan(v.objetivo(1000)).all()
    with pytest.raises(IndexError):
        v.hasta(100)


def test_r_es_la_diferencia_de_logaritmos():
    v = vista_sintetica(50)
    assert np.isnan(v.r[0]) and v.r[1:] == pytest.approx(np.diff(v.logp))


def test_corredor_ningun_ajuste_ni_pronostico_ve_el_futuro_y_el_embargo_se_cumple():
    v = vista_sintetica(900)
    m = Espia()
    df = correr(m, v, primero=300, paso=21)
    blocks_first = [int(o[0]) for o in m.origenes]
    assert m.visto_ajuste == blocks_first                         # ajuste ve exactamente hasta t0
    assert m.visto_pronostico == [int(o[-1]) for o in m.origenes]  # pronóstico ve hasta el último origen
    assert df["origen"].max() + max(m.horizontes) == v.n - 1       # embargo: objetivo máximo = n-1
    assert df["origen"].min() == 300 and not df["y"].isna().any()
    assert len(df) == (df["origen"].max() - 300 + 1) * len(m.horizontes)
    for h in m.horizontes:
        sub = df[df.h == h]
        assert np.array_equal(sub["origen"], np.arange(300, df["origen"].max() + 1))
        assert sub["y"].to_numpy() == pytest.approx(v.objetivo(h)[sub["origen"]])


def test_corredor_rechaza_cuantiles_cruzados():
    class Malo(Espia):
        def pronosticar(self, vista, origenes, niveles):
            return {h: np.tile(np.arange(len(niveles))[::-1] * 1.0, (len(origenes), 1))
                    for h in self.horizontes}
    with pytest.raises(ValueError, match="cruzados"):
        correr(Malo(), vista_sintetica(500), primero=300)


def test_resumen_de_un_modelo_correcto_tiene_cobertura_nominal():
    v = vista_sintetica(6000, seed=1)
    df = correr(Espia(), v, primero=100, paso=63)
    r = resumen(df)
    uno = r[(r.h == 1) & (r.grupo == "todo")].iloc[0]
    assert abs(uno.cob95 - 0.95) < 0.015 and abs(uno.cob90 - 0.90) < 0.02 and abs(uno.cob98 - 0.98) < 0.01
    assert {"pinball", "crps", "is95", "n"} <= set(r.columns)
    assert set(r["h"]) == {1, 5, 21, 63} and set(r["grupo"]) == {"todo", "normal"}


def test_resumen_separa_estres_y_normal():
    v = vista_sintetica(700)
    est = v.estres.copy()
    est[400:500] = "crisis"
    v = Vista(v.fechas, v.logp, v.r, v.banda, est, v.externas)
    r = resumen(correr(Espia(), v, primero=300))
    assert set(r["grupo"]) == {"todo", "estres", "normal"}
    t = r[r.h == 1].set_index("grupo")["n"]
    assert t["estres"] + t["normal"] == t["todo"]


@pytest.mark.skipif(not (RAIZ / "data/processed/trm.csv").exists(), reason="sin datos")
def test_la_prueba_final_no_se_carga_en_desarrollo():
    v = cargar_desarrollo(RAIZ)
    corte = pd.Timestamp(INICIO_PRUEBA_FINAL)
    assert v.fechas.max() < corte and v.externas.index.max() < corte
    assert v.n == 6760 and v.fechas[0] == pd.Timestamp("1991-12-02")
    i = primer_origen(v)
    assert v.fechas[i] >= pd.Timestamp("2005-01-03") and v.fechas[i - 1] < pd.Timestamp("2005-01-03")
    assert set(v.externas.columns) == {"brent_usd", "dolar_amplio", "fed_funds", "politica"}
    assert v.banda[:100].all() and not v.banda[-100:].any()


# ---- F2: tabla de cola (NIVELES_COLA y ES) sin alterar la tabla principal ---------------------
def test_tabla_de_cola_no_cambia_la_principal_y_el_es_es_coherente():
    from scipy import stats
    from laboratorio.backtest.corredor import correr, correr_con_cola
    from laboratorio.backtest.particion import ALFA_ES, NIVELES_COLA
    from laboratorio.modelos.bootstrap import BootstrapEstacionario
    from laboratorio.modelos.cuantiles import RegresionCuantiles
    from laboratorio.modelos.lineas_base import EWMA
    from test_sin_fuga import vista
    v = vista()
    for m in (EWMA(), BootstrapEstacionario(sims=400)):
        sola = correr(m, v, primero=600, paso=63)
        df, cola = correr_con_cola(m, v, primero=600, paso=63)
        assert df.equals(sola)                                  # mismas simulaciones
        assert list(cola.columns[:5]) == list(df.columns[:5])
        assert [c for c in cola.columns if c.startswith("c_")] == [f"c_{t:g}" for t in NIVELES_COLA]
        assert len(cola) == len(df) and (cola.origen == df.origen).all() and (cola.y == df.y).all()
        # coherencia con la principal y orden: ES más extremo que el VaR del mismo nivel
        assert np.allclose(cola["c_0.025"], df["q_0.025"]) and np.allclose(cola["c_0.99"], df["q_0.99"])
        assert (cola.es_inf < cola["c_0.025"]).all() and (cola.es_sup > cola["c_0.975"]).all()
    # EWMA es normal: ES = ∓σ·φ(z)/α y VaR = ∓σ·z → cociente ES/VaR = φ(z)/(α·z) = 1,1928
    z = stats.norm.ppf(1 - ALFA_ES)
    df, cola = correr_con_cola(EWMA(), v, primero=600, paso=63)
    assert np.allclose(cola.es_inf / cola["c_0.025"], stats.norm.pdf(z) / (ALFA_ES * z), rtol=0.005)
    q = RegresionCuantiles()
    assert not q.cola_defendible and "11 niveles" in q.motivo_sin_cola
    assert correr_con_cola(q, v, primero=600, paso=63, ultimo=640)[1] is None


def test_todo_modelo_del_catalogo_da_cola_o_declara_el_motivo():
    """Cada clase del catálogo corto: tabla de cola finita y ordenada, o «no aplica» con motivo."""
    from laboratorio.backtest.catalogo import FABRICAS as CATALOGO
    from laboratorio.backtest.corredor import correr_con_cola
    from test_sin_fuga import FABRICAS as CANARIO, vista
    v = vista()
    clases = {type(f()) for f, _ in CATALOGO.values()}
    vistos = set()
    for nombre, fab in CANARIO.items():
        m = fab()
        if nombre.endswith("_largo") or type(m) not in clases:
            continue
        vistos.add(type(m))
        df, cola = correr_con_cola(m, v, primero=600, paso=63, ultimo=620)
        if not m.cola_defendible:
            assert cola is None and m.motivo_sin_cola, nombre
            continue
        c = cola.filter(regex="^c_").to_numpy()
        assert np.isfinite(c).all() and (np.diff(c, axis=1) >= -1e-12).all(), nombre
        assert (cola.es_inf <= cola["c_0.025"]).all() and (cola.es_sup >= cola["c_0.975"]).all(), nombre
        assert np.allclose(cola["c_0.01"], df["q_0.01"], rtol=1e-9, atol=1e-12), nombre
    assert vistos == clases
