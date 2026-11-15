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
    return caso.ejecutar(proyecto)


def _conjunto_y_datos(proyecto):
    datos = DatosTRM(proyecto / "data/processed", proyecto / "data/raw")
    reg = Registro(proyecto / "data/supuestos/registro.jsonl")
    return datos, reg


def test_01_dos_ejecuciones_dan_mismos_hashes_y_mismo_reporte(proyecto, corrida):
    ficha, _, ruta_rep = corrida
    antes = ruta_rep.read_bytes()
    f2, _, _ = caso.ejecutar(proyecto)
    assert (f2.hash_entrada, f2.hash_resultado, f2.hash_ficha) == (
        ficha.hash_entrada, ficha.hash_resultado, ficha.hash_ficha)
    assert ruta_rep.read_bytes() == antes


def test_02_reproducir_desde_la_ficha_guardada(proyecto, corrida):
    _, ruta_ficha, _ = corrida
    ok, _ = caso.reproducir_corrida(ruta_ficha, proyecto)
    assert ok


def test_03_cada_cifra_numerica_del_reporte_tiene_hash_y_esta_en_el_apendice(corrida):
    _, _, ruta_rep = corrida
    md = ruta_rep.read_text(encoding="utf-8")
    cuerpo, apendice = md.split("## Apéndice")
    cuerpo = cuerpo.split("## Ficha de la corrida")[0]
    revisadas = 0
    for linea in cuerpo.splitlines():
        if linea.startswith("|") and not set(linea) <= set("|-: "):
            for c in [c.strip() for c in linea.strip("|").split("|")][1:]:
                if re.search(r"\d", c):
                    assert re.search(r"`#[0-9a-f]{10}`", c), f"cifra sin hash: {c}"
                    revisadas += 1
    assert revisadas >= 30   # que la revisión no pase en vacío
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
    caso.ejecutar(r)
    reg = Registro(r / "data/supuestos/registro.jsonl")
    reg.agregar("caso.meta_usd", 777, "USD", "manual", "edición del usuario", "analista")
    caso.ejecutar(r)                                    # no debe revertir la edición
    assert reg.vigente("caso.meta_usd").valor == 777 and len(reg.historial("caso.meta_usd")) == 2
    p = r / "data/processed/trm.csv"
    df = pd.read_csv(p)
    df.loc[df.index[-3000:], "trm"] *= 1.4              # cambio grande de datos
    df.to_csv(p, index=False)
    _, _, ruta_rep = caso.ejecutar(r)                   # datos nuevos: avisa, no cambia derivas
    assert "**Aviso:**" in ruta_rep.read_text(encoding="utf-8")
    assert len(reg.historial(id_deriva("base"))) == 1
    caso.ejecutar(r, actualizar_derivas=True)           # ahora sí, versión nueva
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
    f2, _, _ = caso.ejecutar(proyecto)
    assert f2.hash_supuestos != ficha.hash_supuestos and f2.run_id != ficha.run_id
    assert f2.pins_supuestos["caso.meta_usd"] == 2
    assert cargar(ruta_ficha).pins_supuestos["caso.meta_usd"] == 1
    ok, _ = caso.reproducir_corrida(ruta_ficha, proyecto)   # la corrida vieja usa v1
    assert ok
