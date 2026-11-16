"""F4 (R3): código de la prueba final probado SOLO con datos sintéticos.

Ninguna prueba llama a `cargar_prueba_final` ni a `correr_final` sobre la raíz real del proyecto:
los datos reales desde 2020 no se abren aquí.
"""
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from laboratorio.backtest import final
from laboratorio.backtest.datos import cargar_desarrollo
from laboratorio.backtest.particion import HORIZONTES, HORIZONTES_LARGOS, INICIO_PRUEBA_FINAL
from laboratorio.modelos.bootstrap import BootstrapEstacionario
from laboratorio.modelos.lineas_base import EWMA, CaminataAleatoria, SimulacionHistorica
from laboratorio.reportes.prueba_final import cobertura_motor, confirmar

CAT = {"caminata_aleatoria": (lambda: CaminataAleatoria(), 21),
       "sim_hist_pond": (lambda: SimulacionHistorica(ventana=None, lam=0.994), 21),
       "ewma_0.94": (lambda: EWMA(0.94), 21),
       "bootstrap_est_filtrado": (lambda: BootstrapEstacionario(filtrado=True, sims=300), 63)}
_L = HORIZONTES_LARGOS
CAT_L = {"caminata_aleatoria": (lambda: CaminataAleatoria(horizontes=_L), 21),
         "ewma_0.94": (lambda: EWMA(0.94, horizontes=_L), 21),
         "bootstrap_est_filtrado": (lambda: BootstrapEstacionario(filtrado=True, sims=300, horizontes=_L), 63)}
CONF = ((1, "ewma_0.94", "sim_hist_pond"), (5, "ewma_0.94", "sim_hist_pond"),
        (21, "ewma_0.94", "sim_hist_pond"), (63, "ewma_0.94", "caminata_aleatoria"))


def _raiz_sintetica(tmp: Path, con_prerregistro: bool = True) -> Path:
    """Proyecto de mentira: TRM GARCH simulada de 2014 a 2022, código falso y prerregistro."""
    rng = np.random.default_rng(7)
    idx = pd.bdate_range("2014-01-02", "2022-12-30")
    n = len(idx)
    v, r = 0.5, np.empty(n)
    for k in range(n):
        r[k] = np.sqrt(v) * rng.standard_normal()
        v = 0.03 + 0.08 * r[k] ** 2 + 0.89 * v
    est = np.where((idx >= "2020-02-20") & (idx <= "2020-06-30"), "covid_2020", "")
    proc = tmp / "data" / "processed"
    proc.mkdir(parents=True)
    pd.DataFrame({"fecha": idx, "trm": 3000 * np.exp(np.cumsum(r / 100)), "regimen": "flotacion",
                  "estres": est}).to_csv(proc / "trm.csv", index=False)
    pd.DataFrame({"fecha": idx, "brent_usd": 60.0, "dolar_amplio": 100.0, "fed_funds": 1.0}).to_csv(
        proc / "externas_diario.csv", index=False)
    pd.DataFrame({"fecha": idx, "politica": 4.0}).to_csv(proc / "tasas_diarias.csv", index=False)
    src = tmp / "src_falso"
    (src / "paquete").mkdir(parents=True)
    (src / "paquete" / "a.py").write_bytes(b"x = 1\n")
    (src / "b.py").write_bytes(b"y = 2\n")
    if con_prerregistro:
        _escribir_prerregistro(tmp, final.hashes_actuales(tmp, src))
    return tmp


def _escribir_prerregistro(raiz: Path, hashes: dict) -> None:
    (raiz / "docs").mkdir(exist_ok=True)
    (raiz / final.PRERREGISTRO).write_text(
        "# Prerregistro\n\ntexto\n\n" + "\n".join(f"- `{k}`: `{v}`" for k, v in hashes.items()) + "\n",
        encoding="utf-8")


# ---- hash del código ------------------------------------------------------------------------------
def test_hash_codigo_cambia_con_un_byte_y_con_un_nombre_pero_no_con_otros_archivos(tmp_path):
    src = _raiz_sintetica(tmp_path) / "src_falso"
    h0 = final.hash_codigo(src)
    assert len(h0) == 64 and h0 == final.hash_codigo(src)
    (src / "notas.txt").write_text("no cuenta")
    (src / "paquete" / "__pycache__").mkdir()
    (src / "paquete" / "__pycache__" / "a.cpython-311.pyc").write_bytes(b"\0")
    assert final.hash_codigo(src) == h0
    (src / "paquete" / "a.py").write_bytes(b"x = 2\n")
    h1 = final.hash_codigo(src)
    assert h1 != h0
    (src / "paquete" / "a.py").write_bytes(b"x = 1\n")
    assert final.hash_codigo(src) == h0
    (src / "b.py").rename(src / "c.py")                           # mismo contenido, otro nombre
    assert final.hash_codigo(src) != h0
    with pytest.raises(FileNotFoundError):
        final.hash_codigo(tmp_path / "data")


def test_hash_codigo_real_cubre_el_paquete_y_este_modulo():
    base = Path(final.__file__).resolve().parents[2]
    assert (base / "laboratorio" / "backtest" / "final.py").exists()
    assert (base / "laboratorio" / "reportes" / "prueba_final.py").exists()
    assert len(final.hash_codigo()) == 64


# ---- candado del prerregistro ---------------------------------------------------------------------
def test_sin_prerregistro_no_se_abre_la_prueba_final(tmp_path):
    raiz = _raiz_sintetica(tmp_path, con_prerregistro=False)
    with pytest.raises(RuntimeError, match="sin prerregistro"):
        final.cargar_prueba_final(raiz, raiz / "src_falso")
    with pytest.raises(RuntimeError, match="sin prerregistro"):
        final.correr_final(raiz, raiz / "src_falso", CAT, CAT_L, CONF)
    assert not (raiz / "runs").exists()


@pytest.mark.parametrize("que", ["codigo", "trm", "externas", "tasas", "falta_clave", "repetida", "entorno"])
def test_cualquier_hash_distinto_detiene_todo(tmp_path, que, monkeypatch):
    raiz = _raiz_sintetica(tmp_path)
    src = raiz / "src_falso"
    assert final.verificar_prerregistro(raiz, src) == final.hashes_actuales(raiz, src)
    assert set(final.hashes_actuales(raiz, src)) == {"hash_codigo", "hash_entorno", "hash_trm_csv",
                                                     "hash_externas_diario_csv", "hash_tasas_diarias_csv"}
    if que == "entorno":                                     # otra versión de una biblioteca
        monkeypatch.setattr(final, "entorno", lambda: {"python": "3.11.9", "numpy": "9.9.9"})
    elif que == "codigo":
        (src / "b.py").write_bytes(b"y = 3\n")
    elif que == "falta_clave":
        h = final.hashes_actuales(raiz, src); h.pop("hash_tasas_diarias_csv")
        _escribir_prerregistro(raiz, h)
    elif que == "repetida":
        p = raiz / final.PRERREGISTRO
        p.write_text(p.read_text(encoding="utf-8") + "- `hash_codigo`: `abc`\n", encoding="utf-8")
    else:
        f = raiz / "data" / "processed" / {"trm": "trm.csv", "externas": "externas_diario.csv",
                                           "tasas": "tasas_diarias.csv"}[que]
        f.write_bytes(f.read_bytes() + b"\n")
    with pytest.raises(RuntimeError):
        final.cargar_prueba_final(raiz, src)
    with pytest.raises(RuntimeError):
        final.correr_final(raiz, src, CAT, CAT_L, CONF)
    assert not (raiz / "runs").exists()


def test_cargar_prueba_final_entrega_toda_la_historia_y_el_primer_origen(tmp_path):
    raiz = _raiz_sintetica(tmp_path)
    vista, primero = final.cargar_prueba_final(raiz, raiz / "src_falso")
    corte = pd.Timestamp(INICIO_PRUEBA_FINAL)
    assert vista.fechas[primero] >= corte > vista.fechas[primero - 1]
    assert vista.fechas.max() == pd.Timestamp("2022-12-30")
    # El cargador de desarrollo sigue sin ver nada desde el corte, con los mismos archivos.
    dev = cargar_desarrollo(raiz)
    assert dev.fechas.max() < corte and dev.n == primero
    assert np.array_equal(dev.logp, vista.logp[:primero])


def test_sin_datos_posteriores_al_corte_falla(tmp_path):
    raiz = _raiz_sintetica(tmp_path)
    proc = raiz / "data" / "processed"
    for a in final.ARCHIVOS_DATOS:
        d = pd.read_csv(proc / a)
        d[d["fecha"] < INICIO_PRUEBA_FINAL].to_csv(proc / a, index=False)
    _escribir_prerregistro(raiz, final.hashes_actuales(raiz, raiz / "src_falso"))
    with pytest.raises(RuntimeError, match="no hay datos posteriores"):
        final.cargar_prueba_final(raiz, raiz / "src_falso")


# ---- corrida única y reporte ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def corrida(tmp_path_factory):
    raiz = _raiz_sintetica(tmp_path_factory.mktemp("final"))
    salida = final.correr_final(raiz, raiz / "src_falso", CAT, CAT_L, CONF)
    return raiz, salida


def test_la_corrida_final_solo_tiene_origenes_desde_el_corte_y_respeta_el_embargo(corrida):
    raiz, _ = corrida
    vista, primero = final.cargar_prueba_final(raiz, raiz / "src_falso")
    for carpeta, hmax, cat in ((final.SALIDA_FINAL, max(HORIZONTES), CAT),
                               (final.SALIDA_FINAL_LARGO, max(HORIZONTES_LARGOS), CAT_L)):
        for m in cat:
            d = pd.read_csv(raiz / carpeta / f"{m}.csv.gz", parse_dates=["fecha"])
            assert d["fecha"].min() == vista.fechas[primero] >= pd.Timestamp(INICIO_PRUEBA_FINAL)
            assert d["origen"].min() == primero and d["origen"].max() == vista.n - 1 - hmax
            assert d["y"].notna().all()
            j = json.loads((raiz / carpeta / f"{m}.json").read_text(encoding="utf-8"))
            assert j["prueba_final"] is True and j["hash_codigo"] == final.hash_codigo(raiz / "src_falso")
    # Un pronóstico de la prueba final coincide con el del mismo modelo sobre la vista recortada
    # en el origen: no usa nada posterior.
    d = pd.read_csv(raiz / final.SALIDA_FINAL / "ewma_0.94.csv.gz")
    o = int(d["origen"].iloc[100])
    from laboratorio.backtest.particion import NIVELES
    q = EWMA(0.94).pronosticar(vista.hasta(o), np.array([o]), NIVELES)[1][0]
    assert np.allclose(d[(d.origen == o) & (d.h == 1)].filter(like="q_").to_numpy()[0], q)


def test_la_prueba_final_no_se_puede_repetir(corrida):
    raiz, _ = corrida
    hecho = json.loads((raiz / final.SALIDA_FINAL / "HECHO.json").read_text(encoding="utf-8"))
    assert hecho["modelos"] == list(CAT) and hecho["hash_codigo"]
    antes = (raiz / "reports" / "prueba_final.md").read_bytes()
    with pytest.raises(RuntimeError, match="ya se corrió"):
        final.correr_final(raiz, raiz / "src_falso", CAT, CAT_L, CONF)
    assert (raiz / "reports" / "prueba_final.md").read_bytes() == antes


def test_el_reporte_final_trae_exactamente_lo_prerregistrado(corrida):
    raiz, salida = corrida
    texto = salida.read_text(encoding="utf-8")
    for titulo in ("## Declaraciones", "## Pruebas confirmatorias", "## Motor del caso por horizonte",
                   "## Horizonte h = 1 (descriptivo)", "## Horizonte h = 63 (descriptivo)",
                   "## Pruebas de VaR", "## Model Confidence Set", "## Semáforo de Basilea",
                   "## Expected Shortfall", "## Uniformidad del PIT", "## Horizontes largos"):
        assert titulo in texto, titulo
    assert "no son datos nunca vistos" in texto                    # R2
    assert "covid_2020" in texto and "estres_2022" in texto        # episodios aparte (aunque uno esté vacío)
    conf = texto.split("## Pruebas confirmatorias")[1].split("## Motor")[0]
    assert conf.count("| ewma_0.94 |") == 4 and "p (Holm)" in conf
    motor = texto.split("## Motor del caso por horizonte")[1].split("## Horizonte h = 1")[0]
    assert motor.count("| `bootstrap_est_filtrado` |") == 6 and "| 252 | `bootstrap_est_filtrado` | ninguno (descriptivo) |" in motor
    assert (raiz / "reports" / "figs" / "prueba_final_pit.png").exists()
    assert not (raiz / "reports" / "figs" / "fase2_pit.png").exists()   # no pisa la figura de desarrollo
    assert "## Veredicto" not in texto and "## Conclusiones" not in texto   # nada de criterios de desarrollo


def test_confirmar_aplica_holm_y_exige_crps_menor(corrida):
    raiz, _ = corrida
    from laboratorio.reportes.fase2 import cargar
    res = cargar(raiz / final.SALIDA_FINAL)[0]
    c = confirmar(res, CONF)
    from laboratorio.evaluacion.pruebas import holm
    assert np.allclose(c["p_holm"], holm(c["p"].to_numpy())) and (c["p_holm"] >= c["p"]).all()
    assert list(c["exito"]) == list((c["relativo"] < 1) & (c["p_holm"] < 0.05))
    # Un campeón contra sí mismo no puede tener éxito; un modelo ausente es un error (lista cerrada).
    with pytest.raises(Exception):
        confirmar(res, ((1, "ewma_0.94", "ewma_0.94"),))
    with pytest.raises(RuntimeError, match="lista de modelos es cerrada"):
        confirmar(res, ((1, "no_existe", "sim_hist_pond"),))
    # DM es unilateral: invertir campeón y base da p complementario.
    a = confirmar(res, ((1, "ewma_0.94", "sim_hist_pond"),))
    b = confirmar(res, ((1, "sim_hist_pond", "ewma_0.94"),))
    assert a["p"].iloc[0] + b["p"].iloc[0] == pytest.approx(1.0, abs=1e-9)
    assert not (a["exito"].iloc[0] and b["exito"].iloc[0])


def test_cobertura_del_motor_usa_n_efectivo(corrida):
    raiz, _ = corrida
    from laboratorio.reportes.fase2 import cargar
    res = cargar(raiz / final.SALIDA_FINAL)[0]
    largo = cargar(raiz / final.SALIDA_FINAL_LARGO)[0]
    cm = cobertura_motor(res, largo, motor="ewma_0.94").set_index("h")
    assert list(cm.index) == [1, 5, 21, 63, 126, 252]
    assert cm.loc[252, "n_efectivo"] == cm.loc[252, "n"] // 252
    assert (cm["ic_inf"] <= cm["cobertura"]).all() and (cm["cobertura"] <= cm["ic_sup"]).all()


def test_lo_fijado_en_el_codigo_es_coherente_con_el_catalogo():
    from laboratorio.backtest.catalogo import FABRICAS, FABRICAS_LARGOS, LINEAS_BASE
    assert set(final.MODELOS_FINAL) == set(FABRICAS) and len(final.MODELOS_FINAL) == 17
    assert set(final.MODELOS_FINAL_LARGOS) == set(FABRICAS_LARGOS)
    assert [h for h, _, _ in final.CONFIRMATORIAS] == list(HORIZONTES)
    for _, campeon, base in final.CONFIRMATORIAS:
        assert campeon in FABRICAS and campeon not in LINEAS_BASE and base in LINEAS_BASE
    assert final.MOTOR_CASO in FABRICAS and final.MOTOR_CASO in FABRICAS_LARGOS


def test_el_comando_final_no_tiene_opcion_de_forzar():
    from laboratorio.backtest.__main__ import main
    with pytest.raises(SystemExit):
        main(["final", "--forzar"])


def test_main_final_verificar_no_corre_nada(tmp_path, monkeypatch, capsys):
    raiz = _raiz_sintetica(tmp_path)
    shutil.rmtree(raiz / "src_falso")
    (raiz / "docs" / "prerregistro.md").unlink()
    _escribir_prerregistro(raiz, final.hashes_actuales(raiz))      # hash del código real
    final.main_final(raiz, solo_verificar=True)
    assert "prerregistro verificado" in capsys.readouterr().out
    final.main_final(raiz, solo_hashes=True)                       # las líneas que se pegan al cerrar
    salida = capsys.readouterr().out
    assert final.leer_prerregistro(raiz / final.PRERREGISTRO) == dict(final._CLAVE.findall(salida))
    assert not (raiz / "runs").exists()
