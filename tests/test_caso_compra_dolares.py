import json
import math
import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from laboratorio.motor.casos import compra_dolares as caso
from laboratorio.motor.datos import DatosTRM
from laboratorio.motor.deterministas import id_deriva
from laboratorio.motor.ficha import EntradaCambio, cargar
from laboratorio.motor.historica import desplazar_meses, distribucion
from laboratorio.motor.plan import PlanCompra
from laboratorio.motor.supuestos import Registro

RAIZ = Path(__file__).resolve().parents[1]
N_MC = 300          # trayectorias del Monte Carlo en las pruebas (la corrida real usa 10.000)
pytestmark = pytest.mark.skipif(not (RAIZ / "data/processed/trm.csv").exists(), reason="sin datos")


@pytest.fixture(scope="module")
def proyecto(tmp_path_factory):
    """Copia mínima del proyecto: datos, código y registro vacío."""
    r = tmp_path_factory.mktemp("proy")
    (r / "data/processed").mkdir(parents=True)
    (r / "data/raw").mkdir(parents=True)
    shutil.copy(RAIZ / "data/processed/trm.csv", r / "data/processed/trm.csv")
    for p in (RAIZ / "data/raw").glob("trm_superfinanciera_*.csv"):
        shutil.copy(p, r / "data/raw" / p.name)
    shutil.copytree(RAIZ / "src/laboratorio", r / "src/laboratorio",
                    ignore=shutil.ignore_patterns("__pycache__"))
    return r


@pytest.fixture(scope="module")
def corrida(proyecto):
    return caso.ejecutar(proyecto, trayectorias=N_MC)


def _conjunto_y_datos(proyecto):
    datos = DatosTRM(proyecto / "data/processed", proyecto / "data/raw")
    reg = Registro(proyecto / "data/supuestos/registro.jsonl")
    return datos, reg


def test_01_dos_ejecuciones_dan_mismos_hashes_y_mismo_reporte(proyecto, corrida):
    ficha, _, ruta_rep = corrida
    antes = ruta_rep.read_bytes()
    f2, _, _ = caso.ejecutar(proyecto, trayectorias=N_MC)
    assert (f2.hash_entrada, f2.hash_resultado, f2.hash_ficha) == (
        ficha.hash_entrada, ficha.hash_resultado, ficha.hash_ficha)
    assert ruta_rep.read_bytes() == antes


def test_02_reproducir_desde_la_ficha_guardada(proyecto, corrida):
    _, ruta_ficha, _ = corrida
    ok, _ = caso.reproducir_corrida(ruta_ficha, proyecto)
    assert ok


def test_03_cada_cifra_numerica_del_reporte_tiene_hash_y_esta_en_el_apendice(corrida):
    _, _, ruta_rep = corrida
    _revisar_hashes(ruta_rep.read_text(encoding="utf-8"))


def _revisar_hashes(md: str) -> None:
    cuerpo, apendice = md.split("## Apéndice")
    cuerpo = cuerpo.split("## Ficha de la corrida")[0]
    revisadas = 0
    for linea in cuerpo.splitlines():
        if linea.startswith("|") and not set(linea) <= set("|-: "):
            for c in [c.strip() for c in linea.strip("|").split("|")][1:]:
                if re.search(r"\d", c):
                    assert re.search(r"`#[0-9a-f]{10}`", c), f"cifra sin hash: {c}"
                    revisadas += 1
    assert revisadas >= 60   # que la revisión no pase en vacío (30 antes de F5 + Monte Carlo y abanico)
    usados = set(re.findall(r"`#([0-9a-f]{10})`", cuerpo))
    en_apendice = set(re.findall(r"\| `#([0-9a-f]{10})` \|", apendice))
    assert usados and usados <= en_apendice
    filas = [f for f in apendice.splitlines() if f.startswith("| `#")]
    assert len(filas) == len(en_apendice)
    for fila in filas:
        assert re.search(r"`[0-9a-f]{64}`", fila)
        assert any(o in fila for o in ("| dato |", "| supuesto |", "| calculo |"))


def test_04_cifras_derivadas_llegan_solo_a_datos_y_supuestos(proyecto, corrida):
    datos, reg = _conjunto_y_datos(proyecto)
    _, K = caso.calcular(datos, reg.conjunto_vigente(caso.ids_del_caso()))
    for k, c in K.items():
        assert all(h.origen in ("dato", "supuesto") for h in c.hojas()), k
    assert {h.origen for h in K["dist.p95"].hojas()} == {"dato", "supuesto"}
    assert K["trm0"].referencia.startswith("processed/trm.csv#fecha=2026-11-14")


def test_05_cifra_de_estres_coincide_con_calculo_independiente(proyecto, corrida):
    datos, reg = _conjunto_y_datos(proyecto)
    c = reg.conjunto_vigente(caso.ids_del_caso())
    res, _ = caso.calcular(datos, c)
    g, t0, meta = c.valor(id_deriva("estres")), float(datos.trm.iloc[-1]), c.valor("caso.meta_usd")
    esperado = sum(meta / 12 * t0 * math.exp(g * m / 12) for m in range(12))
    assert res["det.estres.costo"] == pytest.approx(esperado, rel=1e-12)
    assert res["costo_hoy"] == pytest.approx(meta * t0)


def test_06_distribucion_coincide_con_bucle_independiente(proyecto, corrida):
    datos, _ = _conjunto_y_datos(proyecto)
    plan = PlanCompra.escalonado(10000, 12)
    t0 = float(datos.trm.iloc[-1])
    d = distribucion(plan, datos.trm, t0, "1999-09-25")
    for i in range(0, len(d), 97):
        ini = d.inicios[i]
        costo = sum(10000 / 12 * t0 * datos.trm.asof(desplazar_meses(ini, m)) / datos.trm.asof(ini)
                    for m in range(12))
        assert d.costos[i] == pytest.approx(costo, rel=1e-10)


def test_07_derivas_vienen_de_los_datos_y_estan_ordenadas(proyecto, corrida):
    datos, _ = _conjunto_y_datos(proyecto)
    g = caso.estimar_derivas(datos, "1999-09-25")
    assert g["optimista"] < g["base"] < g["estres"]
    assert caso.estimar_derivas(datos, "1999-09-25") == g


def test_08_sembrar_es_idempotente(proyecto, corrida):
    datos, reg = _conjunto_y_datos(proyecto)
    n = len(reg._leer())
    assert not any(nuevo for _, nuevo in caso.sembrar(reg, datos, "analista"))
    assert len(reg._leer()) == n
    reg.verificar()


def test_08b_sembrar_no_pisa_ediciones_del_usuario_y_avisa_si_los_datos_cambian(tmp_path, proyecto):
    r = tmp_path / "p"
    shutil.copytree(proyecto, r, ignore=shutil.ignore_patterns("supuestos", "runs", "reports"))
    caso.ejecutar(r, trayectorias=N_MC)
    reg = Registro(r / "data/supuestos/registro.jsonl")
    reg.agregar("caso.meta_usd", 777, "USD", "manual", "edición del usuario", "analista")
    caso.ejecutar(r, trayectorias=N_MC)                                    # no debe revertir la edición
    assert reg.vigente("caso.meta_usd").valor == 777 and len(reg.historial("caso.meta_usd")) == 2
    p = r / "data/processed/trm.csv"
    df = pd.read_csv(p)
    df.loc[df.index[-3000:], "trm"] *= 1.4              # cambio grande de datos
    df.to_csv(p, index=False)
    _, _, ruta_rep = caso.ejecutar(r, trayectorias=N_MC)                   # datos nuevos: avisa, no cambia derivas
    assert "**Aviso:**" in ruta_rep.read_text(encoding="utf-8")
    assert len(reg.historial(id_deriva("base"))) == 1
    caso.ejecutar(r, actualizar_derivas=True, trayectorias=N_MC)           # ahora sí, versión nueva
    assert len(reg.historial(id_deriva("base"))) == 2
    assert "**Aviso:**" not in (r / "reports/compra_dolares.md").read_text(encoding="utf-8")


def test_09_si_cambian_los_datos_la_ficha_vieja_no_es_reproducible(proyecto, corrida):
    _, ruta_ficha, _ = corrida
    p = proyecto / "data/processed/trm.csv"
    original = p.read_text(encoding="utf-8")
    try:
        p.write_text(original + "2026-11-15,3320,1,0.001,flotacion,\n", encoding="utf-8")
        with pytest.raises(EntradaCambio, match="datos"):
            caso.reproducir_corrida(ruta_ficha, proyecto)
    finally:
        p.write_text(original, encoding="utf-8")


def test_10_editar_un_supuesto_crea_corrida_nueva_y_la_vieja_sigue_reproducible(proyecto, corrida):
    ficha, ruta_ficha, _ = corrida
    _, reg = _conjunto_y_datos(proyecto)
    reg.agregar("caso.meta_usd", 20000, "USD", "ilustrativo (definido por el autor)",
                "prueba de edición", "analista")
    f2, _, _ = caso.ejecutar(proyecto, trayectorias=N_MC)
    assert f2.hash_supuestos != ficha.hash_supuestos and f2.run_id != ficha.run_id
    assert f2.pins_supuestos["caso.meta_usd"] == 2
    assert cargar(ruta_ficha).pins_supuestos["caso.meta_usd"] == 1
    ok, _ = caso.reproducir_corrida(ruta_ficha, proyecto)   # la corrida vieja usa v1
    assert ok


# ---- F5: Monte Carlo en el caso -------------------------------------------------------------------
def _fila(md: str, seccion: str, etiqueta: str) -> list[str]:
    """Celdas de la fila de tabla que empieza por `etiqueta` dentro de la sección `seccion`."""
    cuerpo = md.split(seccion, 1)[1].split("\n## ", 1)[0]
    fila = next(l for l in cuerpo.splitlines() if l.startswith(f"| {etiqueta} |"))
    return [c.strip() for c in fila.strip("|").split("|")]


def test_11_el_monte_carlo_queda_en_la_ficha_el_reporte_y_la_figura(proyecto, corrida):
    ficha, ruta_ficha, ruta_rep = corrida
    assert ficha.semilla == 20240501 and ficha.parametros["trayectorias"] == N_MC
    assert ficha.parametros["motor"] == "bootstrap_est_filtrado"
    assert ficha.parametros["sensibilidad"] == "bootstrap_est"
    md = ruta_rep.read_text(encoding="utf-8")
    for etiqueta in ("Costo esperado (media)", "Mediana", "Percentil 5", "Percentil 95",
                     "Probabilidad de superar el presupuesto",
                     "Probabilidad de salir más barato que comprar hoy"):
        celdas = _fila(md, "## 4. Monte Carlo", etiqueta)
        assert len(celdas) == 5 and all("`#" in c for c in celdas[1:4])   # motor, sensibilidad, histórica
        assert celdas[4] == "sin respaldo fuera de muestra"
    assert "Por qué toda la historia y no solo la flotación" in md
    assert "Lo que esa decisión cuesta: la deriva" in md
    assert (proyecto / "reports/figs/compra_dolares_abanico.png").stat().st_size > 1000
    assert "figs/compra_dolares_abanico.png" in md
    res = json.loads(ruta_ficha.with_name("resultado.json").read_text(encoding="utf-8"))
    assert res["mc.p5"] <= res["mc.p50"] <= res["mc.p95"]
    assert res["mc.deriva_252"] == pytest.approx(100 * (res["abanico.252.med"] / res["trm0"] - 1), rel=1e-9)
    assert 0 <= res["mc.prob_superar"] <= 100 and 0 <= res["mc.prob_mas_barato"] <= 100
    ab = res["abanico"]
    assert ab["pasos_compra"][0] == 0 and 200 <= ab["pasos_compra"][-1] <= 240
    assert len(ab["trm"]) == 253 and ab["trm"][0] == [res["trm0"]] * 5
    assert res["abanico.252.inf"] < res["abanico.21.inf"] < res["trm0"] < res["abanico.21.sup"] < res["abanico.252.sup"]


def test_12_sin_archivo_de_respaldo_todo_queda_sin_respaldo_fuera_de_muestra(corrida):
    _, _, ruta_rep = corrida
    md = ruta_rep.read_text(encoding="utf-8")
    for h in (1, 5, 21, 63, 126, 252):
        celdas = _fila(md, "## 5. Abanico", str(h))
        assert celdas[4] == "sin respaldo fuera de muestra"
        assert celdas[5].startswith("**siempre**") == (h in (63, 126, 252))
    assert "no se cita ningún modelo" in md and "lightgbm" not in md
    assert md.count("sin respaldo fuera de muestra") >= 6 + 6 + 3


RESPALDO = {
    "nominal": 0.95, "sha256_hecho": "0" * 64,
    "cobertura": {"bootstrap_est_filtrado": {
        str(h): {"cobertura": c, "n": 1500, "n_efectivo": max(1500 // h, 1), "ic_inf": lo, "ic_sup": hi,
                 "compatible": lo <= 0.95 <= hi}
        for h, c, lo, hi in ((1, 0.951, 0.94, 0.96), (5, 0.90, 0.86, 0.93), (21, 0.97, 0.9, 1.0),
                             (63, 0.96, 0.8, 1.0), (126, 0.99, 0.7, 1.0), (252, 0.93, 0.5, 1.0))}},
    "confirmatorias": {"1": {"campeon": "lightgbm_cuantiles", "base": "sim_hist_pond", "relativo": 0.977,
                             "p_holm": 0.0005, "n": 1500, "exito": True},
                       "5": {"campeon": "ewma_0.94", "base": "sim_hist_pond", "relativo": 0.994,
                             "p_holm": 0.49, "n": 1500, "exito": False}},
    "var_h1": {"lightgbm_cuantiles": {"sup 5 %": {"tasa": 0.0678, "p_kupiec": 0.002},
                                      "sup 1 %": {"tasa": 0.0185, "p_kupiec": 0.0021}}},
}


def test_13_con_respaldo_cada_horizonte_cita_su_cobertura_y_la_advertencia_va_siempre_a_63_126_252(
        tmp_path, proyecto):
    r = tmp_path / "p"
    shutil.copytree(proyecto, r, ignore=shutil.ignore_patterns("supuestos", "runs", "reports"))
    sin, _, _ = caso.ejecutar(r, trayectorias=N_MC)
    (r / "data/respaldo").mkdir()
    (r / "data/respaldo/prueba_final.json").write_text(json.dumps(RESPALDO), encoding="utf-8")
    ficha, ruta_ficha, ruta_rep = caso.ejecutar(r, trayectorias=N_MC)
    assert "respaldo/prueba_final.json" in ficha.datos and ficha.hash_datos != sin.hash_datos
    md = ruta_rep.read_text(encoding="utf-8")
    _revisar_hashes(md)
    for h in (1, 5, 21, 63, 126, 252):
        celdas = _fila(md, "## 5. Abanico", str(h))
        cob = RESPALDO["cobertura"]["bootstrap_est_filtrado"][str(h)]
        assert "prueba final" in celdas[4] and f"{cob['cobertura']:.3f}".replace(".", ",") in celdas[4]
        assert f"n efectivo {cob['n_efectivo']:,}".replace(",", ".") in celdas[4]
        if h in (63, 126, 252):
            assert celdas[5].startswith("**siempre**") and f"solo {cob['n_efectivo']} " in celdas[5]
        elif h == 5:                                    # 0,95 fuera de [0,86; 0,93]
            assert "fuera del intervalo" in celdas[5]
        else:
            assert celdas[5] == "no hace falta"
    assert _fila(md, "## 4. Monte Carlo", "Percentil 95")[4] == "sin respaldo fuera de muestra"
    assert "Respaldo de estas cifras: indirecto" in md and "0,990" in md and "0,930" in md   # 126 y 252
    ref = md.split("**Modelo de referencia.**", 1)[1].split("\n\n", 1)[0].replace("\n", " ")
    assert "`lightgbm_cuantiles`" in ref and "0,977" in ref and "6,8 %" in ref and "1,85 %" in ref
    assert "0,002" in ref and "no lo usa para simular ni calcula su banda" in ref
    assert "ewma_0.94" not in md                        # lo no confirmado no se cita
    ok, _ = caso.reproducir_corrida(ruta_ficha, r)
    assert ok
    otra, _, _ = caso.ejecutar(r, trayectorias=N_MC, semilla=7)          # otra semilla: otra corrida
    assert otra.hash_resultado != ficha.hash_resultado and otra.run_id != ficha.run_id
    (r / "data/respaldo/prueba_final.json").write_text(
        json.dumps({**RESPALDO, "nominal": 0.9}), encoding="utf-8")     # el respaldo es dato de entrada
    with pytest.raises(EntradaCambio, match="datos"):
        caso.reproducir_corrida(ruta_ficha, r)
