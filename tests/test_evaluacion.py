import numpy as np
import pytest
from scipy import stats

from laboratorio.evaluacion.cobertura import calibracion, cobertura_intervalo, cobertura_intervalos
from laboratorio.evaluacion.origen_movil import (Bloque, bloques, indices_entrenamiento,
                                                  ultimo_origen, verificar_sin_solape)
from laboratorio.evaluacion.perdidas import (crps_cuantiles, crps_muestras, pinball,
                                             pinball_medio, puntaje_intervalo, reordenar,
                                             verificar_cuantiles)

rng = np.random.default_rng(0)
NIV = np.array([0.1, 0.5, 0.9])


# --- pinball -----------------------------------------------------------------------------
def test_pinball_valores_conocidos():
    # y=2, q=1 -> y>q: L = tau*(y-q);  y=0, q=1 -> y<q: L = (1-tau)*(q-y)
    L = pinball([2.0, 0.0], [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]], NIV)
    assert L[0] == pytest.approx(NIV * 1.0)
    assert L[1] == pytest.approx((1 - NIV) * 1.0)


def test_pinball_es_cero_si_y_igual_al_cuantil_y_no_negativo():
    q = np.tile([1.0, 2.0, 3.0], (5, 1))
    assert np.all(pinball(np.full(5, 2.0), q, NIV)[:, 1] == 0.0)
    assert np.all(pinball(rng.normal(size=5), q, NIV) >= 0)


def test_pinball_mediana_es_la_mitad_del_error_absoluto():
    y = rng.normal(size=200)
    q = rng.normal(size=(200, 1))
    assert pinball(y, q, [0.5])[:, 0] == pytest.approx(0.5 * np.abs(y - q[:, 0]))


def test_el_cuantil_verdadero_minimiza_la_perdida_esperada():
    y = rng.normal(size=200_000)
    z = stats.norm.ppf(NIV)
    base = pinball_medio(y, np.tile(z, (len(y), 1)), NIV)
    for d in (-0.2, 0.2):
        assert np.all(pinball_medio(y, np.tile(z + d, (len(y), 1)), NIV) > base)


# --- CRPS -----------------------------------------------------------------------------------
def crps_normal(y, mu=0.0, s=1.0):
    z = (np.asarray(y) - mu) / s
    return s * (z * (2 * stats.norm.cdf(z) - 1) + 2 * stats.norm.pdf(z) - 1 / np.sqrt(np.pi))


def test_crps_cuantiles_aproxima_el_crps_normal_con_rejilla_fina():
    t = np.linspace(0.001, 0.999, 999)
    q = np.tile(stats.norm.ppf(t), (5, 1))
    y = np.array([-2.0, -0.5, 0.0, 0.7, 1.5])
    assert crps_cuantiles(y, q, t) == pytest.approx(crps_normal(y), abs=2e-3)


def test_crps_cuantiles_con_pocos_niveles_subestima_pero_es_positivo():
    q = np.tile(stats.norm.ppf(NIV), (4, 1))
    c = crps_cuantiles([0.0, 1.0, -1.0, 2.0], q, NIV)
    assert np.all(c > 0) and np.all(c < crps_normal([0.0, 1.0, -1.0, 2.0]) + 1e-12)


def test_crps_muestras_coincide_con_la_formula_cerrada():
    x = rng.normal(size=20_000)
    for y in (-1.0, 0.3, 2.0):
        assert crps_muestras(y, x)[0] == pytest.approx(crps_normal(y), abs=0.01)


def test_crps_muestras_identidades():
    # predictiva degenerada en a: CRPS = |a - y|
    assert crps_muestras([3.0], np.full(50, 1.0))[0] == pytest.approx(2.0)
    # dos puntos (0, 2): E|X-y| para y=1 es 1; E|X-X'| = 1 -> CRPS = 1 - 0.5 = 0.5
    assert crps_muestras([1.0], np.array([0.0, 2.0]))[0] == pytest.approx(0.5)
    with pytest.raises(ValueError):
        crps_muestras([1.0, 2.0], np.zeros((3, 4)))


def test_crps_premia_la_predictiva_correcta_sobre_la_demasiado_ancha_o_sesgada():
    y = rng.normal(size=20_000)
    t = np.linspace(0.01, 0.99, 99)
    buena = np.tile(stats.norm.ppf(t), (len(y), 1))
    ancha = np.tile(3 * stats.norm.ppf(t), (len(y), 1))
    sesgada = np.tile(stats.norm.ppf(t) + 1, (len(y), 1))
    c = lambda q: crps_cuantiles(y, q, t).mean()          # noqa: E731
    assert c(buena) < c(ancha) and c(buena) < c(sesgada)


# --- puntaje de intervalo --------------------------------------------------------------------
def test_puntaje_intervalo_casos():
    assert puntaje_intervalo([0.5], [0.0], [1.0], 0.1)[0] == pytest.approx(1.0)          # dentro
    assert puntaje_intervalo([-1.0], [0.0], [1.0], 0.1)[0] == pytest.approx(1.0 + 20.0)  # debajo
    assert puntaje_intervalo([2.0], [0.0], [1.0], 0.2)[0] == pytest.approx(1.0 + 10.0)   # encima
    with pytest.raises(ValueError):
        puntaje_intervalo([0.0], [1.0], [0.0], 0.1)
    with pytest.raises(ValueError):
        puntaje_intervalo([0.0], [0.0], [1.0], 1.5)


# --- validaciones de forma ------------------------------------------------------------------
def test_validaciones_de_forma_y_cuantiles_cruzados():
    with pytest.raises(ValueError):
        pinball([1.0, 2.0], np.zeros((3, 3)), NIV)
    with pytest.raises(ValueError):
        pinball([1.0], np.zeros((1, 2)), [0.5, 0.1])        # niveles no crecientes
    with pytest.raises(ValueError):
        pinball([1.0], np.zeros((1, 1)), [1.0])             # nivel fuera de (0,1)
    verificar_cuantiles([[1.0, 2.0, 3.0]], NIV)
    with pytest.raises(ValueError, match="cruzados"):
        verificar_cuantiles([[1.0, 3.0, 2.0]], NIV)
    with pytest.raises(ValueError, match="NaN"):
        verificar_cuantiles([[1.0, np.nan, 3.0]], NIV)
    assert np.array_equal(reordenar([[1.0, 3.0, 2.0]]), [[1.0, 2.0, 3.0]])


# --- cobertura y calibración ---------------------------------------------------------------
def test_cobertura_intervalo_cuenta_los_extremos():
    assert cobertura_intervalo([0, 1, 2, 3], [0, 0, 0, 0], [1, 1, 1, 1]) == 0.5


def test_calibracion_de_un_modelo_correcto_cae_dentro_del_ic_y_no_rechaza():
    y = rng.normal(size=20_000)
    t = np.array([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    c = calibracion(y, np.tile(stats.norm.ppf(t), (len(y), 1)), t)
    assert np.all((c.nivel >= c.ic_inf - 1e-9) & (c.nivel <= c.ic_sup + 1e-9))
    assert c.p_binomial.min() > 0.001
    assert np.all(np.abs(c.error) < 0.01)


def test_calibracion_detecta_un_modelo_sesgado_y_n_efectivo_ensancha_el_ic():
    y = rng.normal(size=5_000)
    t = np.array([0.5])
    q = np.full((len(y), 1), 0.5)                              # mediana desplazada
    c1 = calibracion(y, q, t)
    assert c1.p_binomial[0] < 1e-6 and c1.error[0] > 0.1
    c2 = calibracion(y, q, t, n_efectivo=50)
    assert (c2.ic_sup[0] - c2.ic_inf[0]) > (c1.ic_sup[0] - c1.ic_inf[0])


def test_cobertura_intervalos_nominal_y_observado():
    y = rng.normal(size=20_000)
    t = np.array([0.025, 0.05, 0.5, 0.95, 0.975])
    tab = cobertura_intervalos(y, np.tile(stats.norm.ppf(t), (len(y), 1)), t)
    assert set(np.round(tab.nominal, 3)) == {0.9, 0.95}
    assert np.allclose(tab.observado, tab.nominal, atol=0.01)
    assert np.all(tab.ancho_medio > 0)


# --- origen móvil -----------------------------------------------------------------------------
def test_bloques_cubren_todo_sin_solapes_y_con_reajuste_al_inicio():
    bs = bloques(10, 100, 21)
    todos = np.concatenate([b.origenes for b in bs])
    assert np.array_equal(todos, np.arange(10, 101))
    assert all(len(b.origenes) <= 21 and b.reajuste == b.origenes[0] for b in bs)
    assert len(bs[-1].origenes) == (100 - 10 + 1) % 21 or len(bs[-1].origenes) == 21
    with pytest.raises(ValueError):
        bloques(10, 5, 21)
    with pytest.raises(ValueError):
        Bloque(3, np.array([4, 5]))


def test_purga_el_objetivo_de_toda_muestra_de_entrenamiento_es_conocido_en_t():
    for t in (100, 500):
        for h in (1, 5, 21, 63):
            s = indices_entrenamiento(t, h)
            assert s.max() + h <= t and s.min() == 0
    assert len(indices_entrenamiento(100, 5, primero=50)) == 100 - 5 - 50 + 1
    assert len(indices_entrenamiento(10, 63)) == 0


def test_embargo_ningun_objetivo_de_desarrollo_toca_la_prueba_final():
    corte, hmax = 1000, 63
    u = ultimo_origen(corte, hmax)
    assert u + hmax == corte - 1
    for b in bloques(100, u, 21):
        for h in (1, 5, 21, 63):
            verificar_sin_solape(b.origenes, h, corte)
    with pytest.raises(ValueError, match="prueba final"):
        verificar_sin_solape([u + 1], hmax, corte)


def test_evaluacion_no_depende_del_dominio():
    import laboratorio.evaluacion as ev
    import pathlib
    for f in pathlib.Path(ev.__file__).parent.glob("*.py"):
        texto = f.read_text(encoding="utf-8").lower()
        assert "trm" not in texto.replace("trapecio", "") and "laboratorio.motor" not in texto
        assert "laboratorio.datos" not in texto and "laboratorio.modelos" not in texto
