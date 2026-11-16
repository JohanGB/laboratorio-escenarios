"""O1: simulación histórica filtrada."""
import numpy as np
import pytest

from laboratorio.backtest.corredor import correr, resumen
from laboratorio.backtest.particion import NIVELES
from laboratorio.modelos.fhs import FHS
from laboratorio.modelos.lineas_base import SimulacionHistorica
from test_garch import simular_garch, vista_de


@pytest.fixture(scope="module")
def datos():
    return vista_de(simular_garch(2500, a=0.05, g=0.06, seed=1))


def test_volatilidad_constante_h1_coincide_con_simulacion_historica(datos):
    """λ = 1 → σ constante → FHS = simulación histórica de toda la historia (exacto a h = 1)."""
    o = np.array([1500, 1800, 2100])
    f = FHS("ewma", lam=1.0, sims=500); f.ajustar(datos.hasta(1500))
    hs = SimulacionHistorica(ventana=None)
    qf = f.pronosticar(datos.hasta(2100), o, NIVELES)
    qh = hs.pronosticar(datos.hasta(2100), o, NIVELES)
    assert qf[1] == pytest.approx(qh[1], rel=1e-10, abs=1e-14)


def test_volatilidad_constante_h_mayor_es_remuestreo_iid_de_rendimientos(datos):
    o, sims = 1700, 800
    f = FHS("ewma", lam=1.0, sims=sims); f.ajustar(datos.hasta(1500))
    q = f.pronosticar(datos.hasta(o), np.array([o]), NIVELES)
    r = datos.r[1: o + 1]
    rng = np.random.default_rng([f.semilla, o])
    acum = np.cumsum(r[rng.integers(0, len(r), size=(max(f.horizontes), sims))], axis=0)
    for h in f.horizontes[1:]:
        assert q[h][0] == pytest.approx(np.quantile(acum[h - 1], NIVELES), rel=1e-9, abs=1e-14)


@pytest.mark.parametrize("filtro", ["ewma", "gjr"])
def test_escalar_los_datos_escala_los_cuantiles(filtro):
    """Equivarianza: con r·c los cuantiles salen ×c (el ajuste GJR es invariante por escala)."""
    r = simular_garch(1600, a=0.05, g=0.06, seed=3)
    a, b = vista_de(r), vista_de(r * 2.0)
    fa, fb = FHS(filtro, sims=600), FHS(filtro, sims=600)
    fa.ajustar(a.hasta(1500)); fb.ajustar(b.hasta(1500))
    o = np.array([1500, 1550])
    qa, qb = fa.pronosticar(a.hasta(1550), o, NIVELES), fb.pronosticar(b.hasta(1550), o, NIVELES)
    tol = 1e-8 if filtro == "ewma" else 2e-2
    for h in fa.horizontes:
        assert qb[h] == pytest.approx(2.0 * qa[h], rel=tol, abs=1e-12)


@pytest.mark.parametrize("filtro", ["ewma", "gjr"])
def test_responde_a_la_volatilidad_actual(datos, filtro):
    f = FHS(filtro, sims=2000); f.ajustar(datos.hasta(2000))
    q = f.pronosticar(datos.hasta(2000), np.array([2000]), NIVELES)
    r = datos.r.copy()[: 2001]; r[-1] = 0.08
    q2 = f.pronosticar(vista_de(np.nan_to_num(r)), np.array([2000]), NIVELES)
    for h in (1, 5):
        assert (q2[h][0, -2] - q2[h][0, 1]) > 1.5 * (q[h][0, -2] - q[h][0, 1])
    anchos = [q[h][0, -2] - q[h][0, 1] for h in f.horizontes]
    assert anchos == sorted(anchos)


def test_fhs_gjr_calibrado_en_su_proceso_generador():
    r = simular_garch(3200, w=0.02, a=0.04, b=0.90, g=0.08, nu=6, seed=11)
    m = FHS("gjr", sims=1500)
    res = resumen(correr(m, vista_de(r), primero=1200, paso=63, ultimo=2900))
    for h in (1, 5, 21):
        f = res[(res.h == h) & (res.grupo == "todo")].iloc[0]
        assert abs(f.cob95 - 0.95) < 0.03 and abs(f.cob90 - 0.90) < 0.04, (h, f.cob95, f.cob90)
    assert m.fallos == 0 and m.reajustes > 0


def test_sin_ajustar_falla(datos):
    with pytest.raises(RuntimeError):
        FHS("ewma").pronosticar(datos, np.array([1000]), NIVELES)
    with pytest.raises(ValueError):
        FHS("otro")
