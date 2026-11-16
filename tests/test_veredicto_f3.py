"""F3: Holm contra un cálculo a mano, regla del veredicto (MCS + Holm) y conclusiones con hash."""
import numpy as np
import pandas as pd
import pytest

from laboratorio.evaluacion.pruebas import holm
from laboratorio.reportes.fase2 import conclusiones
from laboratorio.reportes.pruebas_f2 import seccion_veredicto, veredicto


def test_holm_a_mano():
    # Ordenados: 0,01·4 = 0,04; 0,02·3 = 0,06; 0,03·2 = 0,06; 0,20·1 = 0,20 (monótono: ya lo es).
    assert holm([0.03, 0.01, 0.20, 0.02]) == pytest.approx([0.06, 0.04, 0.20, 0.06])
    # Monotonía: 0,01·3 = 0,03; 0,011·2 = 0,022 → sube a 0,03; 0,5.
    assert holm([0.011, 0.5, 0.01]) == pytest.approx([0.03, 0.5, 0.03])
    assert holm([0.4, 0.9]) == pytest.approx([0.8, 0.9])          # tope en 1 y sin bajar
    assert holm([0.6, 0.7]) == pytest.approx([1.0, 1.0])
    assert holm([0.04]) == pytest.approx([0.04])                  # una sola prueba: sin ajuste
    for malo in ([], [np.nan], [1.2], [-0.1]):
        with pytest.raises(ValueError):
            holm(malo)


def _mcs(h_dentro: dict[str, bool]) -> pd.DataFrame:
    return pd.DataFrame({"modelo": list(h_dentro), "perdida": 1.0,
                         "p_mcs": [0.5 if e else 0.01 for e in h_dentro.values()],
                         "en_mcs": list(h_dentro.values())})


def test_veredicto_exige_mcs_sin_lineas_base_y_holm():
    bases = ("base",)
    tablas = {1: _mcs({"a": True, "b": False, "c": True, "base": False}),     # horizonte con modelo útil
              5: _mcs({"a": True, "b": True, "c": True, "base": True})}       # la base sigue en el MCS
    cmp_ = pd.DataFrame([
        {"modelo": "a", "h": 1, "dm_p": 0.001, "relativo": 0.96},   # Holm 0,002 → sobrevive
        {"modelo": "a", "h": 5, "dm_p": 0.010, "relativo": 0.98},   # pasa Holm, pero la base está en el MCS
        {"modelo": "b", "h": 1, "dm_p": 0.001, "relativo": 0.97},   # pasa Holm, pero fuera del MCS
        {"modelo": "b", "h": 5, "dm_p": 0.300, "relativo": 0.99},
        {"modelo": "c", "h": 1, "dm_p": 0.030, "relativo": 0.98},   # casi: 0,03·2 = 0,06 → no se rescata
        {"modelo": "c", "h": 5, "dm_p": 0.040, "relativo": 0.99},
    ])
    v = veredicto(tablas, cmp_, bases).set_index(["modelo", "h"])
    assert v.loc[("a", 1), "sobrevive"] and v.loc[("a", 1), "dm_p_holm"] == pytest.approx(0.002)
    assert not v.loc[("a", 5), "sobrevive"] and v.loc[("a", 5), "base_en_mcs"]
    assert not v.loc[("b", 1), "sobrevive"]
    assert v.loc[("c", 1), "dm_p_holm"] == pytest.approx(0.06) and not v.loc[("c", 1), "sobrevive"]
    assert int(v["sobrevive"].sum()) == 1
    texto = "\n".join(seccion_veredicto(v.reset_index()))
    assert "| 1 | 2 | **no** | `a` |" in texto and "| 5 | 3 | sí | ninguno |" in texto


def test_veredicto_no_premia_un_crps_peor_que_la_base():
    tablas = {1: _mcs({"a": True, "base": False})}
    cmp_ = pd.DataFrame([{"modelo": "a", "h": 1, "dm_p": 0.001, "relativo": 1.01}])
    assert not veredicto(tablas, cmp_, ("base",)).sobrevive.iloc[0]


def test_conclusiones_solo_se_incluyen_si_el_hash_coincide(tmp_path):
    f = tmp_path / "c.md"
    assert "Sin conclusiones" in "\n".join(conclusiones(f, {"abc"}))
    f.write_text("<!-- hash_trm_csv: abc -->\n1. Solo h = 1 tiene modelo útil.\n", encoding="utf-8")
    ok = "\n".join(conclusiones(f, {"abc"}))
    assert "Solo h = 1 tiene modelo útil" in ok and "obsoletas" not in ok
    viejo = "\n".join(conclusiones(f, {"otro"}))
    assert "obsoletas" in viejo and "Solo h = 1" not in viejo
    assert "obsoletas" in "\n".join(conclusiones(f, {"abc", "otro"}))      # corridas mezcladas
