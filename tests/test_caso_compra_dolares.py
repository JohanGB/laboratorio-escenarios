import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from laboratorio.motor.casos import compra_dolares as caso
from laboratorio.motor.datos import DatosTRM
from laboratorio.motor.deterministas import id_deriva
from laboratorio.motor.ficha import ArbolSucio, EntradaCambio, cargar, hash_codigo_commit
from laboratorio.motor.historica import desplazar_meses, distribucion
from laboratorio.motor.plan import PlanCompra
from laboratorio.motor.supuestos import Registro

RAIZ = Path(__file__).resolve().parents[1]
N_MC = 300          # trayectorias del Monte Carlo en las pruebas (la corrida real usa 10.000)


def git(r: Path, *args: str) -> str:
    """git en un repositorio de prueba (identidad y firma locales al repositorio temporal)."""
    out = subprocess.run(["git", "-C", str(r), "-c", "user.name=pruebas",
                          "-c", "user.email=pruebas@ejemplo.invalid", "-c", "commit.gpgsign=false",
                          "-c", "tag.gpgsign=false", *args], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def confirmar(r: Path) -> None:
    """Commit de todo lo que haya cambiado (la regla H5 exige árbol limpio para escribir fichas)."""
    if not (r / ".git").exists():
        git(r, "init", "-q")
        for clave, valor in (("user.name", "pruebas"), ("user.email", "pruebas@ejemplo.invalid"),
                             ("commit.gpgsign", "false"), ("tag.gpgsign", "false")):
            git(r, "config", clave, valor)          # el repositorio temporal; la CI no tiene identidad
        (r / ".gitignore").write_text("data/processed/\nruns/\nreports/\n__pycache__/\n",
                                      encoding="utf-8")
    git(r, "add", "-A")
    if git(r, "status", "--porcelain"):
        git(r, "commit", "-q", "-m", "prueba")


def ejecutar(r: Path, actualizar_derivas: bool = False, **kw):
    """`caso.ejecutar` con commit previo. Si sembrar escribe supuestos, la ejecución se niega a
    escribir la ficha (H5): se hace commit del registro y se vuelve a correr, como haría el autor."""
    confirmar(r)
    try:
        return caso.ejecutar(r, actualizar_derivas=actualizar_derivas, **kw)
    except ArbolSucio as e:
        assert "registro.jsonl" in str(e)
        confirmar(r)
        return caso.ejecutar(r, **kw)


@pytest.fixture(scope="module")
def proyecto(tmp_path_factory):
    """Copia mínima del proyecto en un repositorio git: datos, código y registro vacío."""
    r = tmp_path_factory.mktemp("proy")
    (r / "data/processed").mkdir(parents=True)
    (r / "data/raw").mkdir(parents=True)
    shutil.copy(RAIZ / "data/processed/trm.csv", r / "data/processed/trm.csv")
    for p in (RAIZ / "data/raw").glob("trm_superfinanciera_*.csv"):
        shutil.copy(p, r / "data/raw" / p.name)
    shutil.copytree(RAIZ / "src/laboratorio", r / "src/laboratorio",
                    ignore=shutil.ignore_patterns("__pycache__"))
    confirmar(r)
    return r


@pytest.fixture(scope="module")
def corrida(proyecto):
    return ejecutar(proyecto, trayectorias=N_MC)


def _conjunto_y_datos(proyecto):
    datos = DatosTRM(proyecto / "data/processed", proyecto / "data/raw")
    reg = Registro(proyecto / "data/supuestos/registro.jsonl")
    return datos, reg


def test_01_dos_ejecuciones_dan_mismos_hashes_y_mismo_reporte(proyecto, corrida):
    ficha, _, ruta_rep = corrida
    antes = ruta_rep.read_bytes()
    f2, _, _ = ejecutar(proyecto, trayectorias=N_MC)
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
    ejecutar(r, trayectorias=N_MC)
    reg = Registro(r / "data/supuestos/registro.jsonl")
    reg.agregar("caso.meta_usd", 777, "USD", "manual", "edición del usuario", "analista")
    ejecutar(r, trayectorias=N_MC)                                    # no debe revertir la edición
    assert reg.vigente("caso.meta_usd").valor == 777 and len(reg.historial("caso.meta_usd")) == 2
    p = r / "data/processed/trm.csv"
    df = pd.read_csv(p)
    df.loc[df.index[-3000:], "trm"] *= 1.4              # cambio grande de datos
    df.to_csv(p, index=False)
    _, _, ruta_rep = ejecutar(r, trayectorias=N_MC)                   # datos nuevos: avisa, no cambia derivas
    assert "**Aviso:**" in ruta_rep.read_text(encoding="utf-8")
    assert len(reg.historial(id_deriva("base"))) == 1
    ejecutar(r, actualizar_derivas=True, trayectorias=N_MC)           # ahora sí, versión nueva
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
    f2, _, _ = ejecutar(proyecto, trayectorias=N_MC)
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


def test_12b_analisis_posterior_solo_flotacion_va_al_lado_del_motor_y_explica_la_causa(proyecto, corrida):
    ficha, ruta_ficha, ruta_rep = corrida
    md = ruta_rep.read_text(encoding="utf-8")
    res = json.loads(ruta_ficha.with_name("resultado.json").read_text(encoding="utf-8"))
    titulo = "### Análisis posterior (no confirmatorio): el mismo bootstrap solo con la flotación"
    assert titulo in md.split("## 4. Monte Carlo")[1].split("\n## ")[0]            # dentro de la sección 4
    assert "No reemplaza al motor, que sigue siendo el principal" in md
    assert "bootstrap_est_filtrado remuestreando solo desde" in ficha.parametros["analisis_posterior"]
    bloque = md.split(titulo)[1].split("\n## ")[0]
    for etiqueta in ("Mediana de la TRM a 252 días", "Probabilidad de superar el presupuesto"):
        celdas = _fila(md, titulo,etiqueta)
        assert len(celdas) == 4 and all("`#" in c for c in celdas[1:3])            # motor | solo flotación
        assert celdas[3] == "sin respaldo fuera de muestra"
    # la columna del motor es la misma cifra de la tabla principal (mismo hash)
    principal = _fila(md, "## 4. Monte Carlo", "Probabilidad de superar el presupuesto")[1]
    assert _fila(md, titulo,"Probabilidad de superar el presupuesto")[1] == principal
    datos, reg = _conjunto_y_datos(proyecto)
    assert res["flot.n_muestra"] == int((datos.trm.index >= "1999-09-25").sum())
    assert res["flot.deriva_252"] < res["mc.deriva_252"]    # sin la banda, menos deriva
    assert res["flot.deriva_252"] == pytest.approx(100 * (res["flot.med_252"] / res["trm0"] - 1), rel=1e-9)
    assert 0 <= res["flot.prob_superar"] <= 100 and res["flot.p5"] <= res["flot.p50"] <= res["flot.p95"]
    # causa: los dos tramos suman toda la serie y la banda entra amplificada al motor
    assert res["causa.antes.peso"] + res["causa.desde.peso"] == pytest.approx(100)
    assert res["causa.antes.aporte_z"] + res["causa.desde.aporte_z"] == pytest.approx(res["causa.media_z"])
    assert res["causa.antes.deriva_anual"] > res["causa.desde.deriva_anual"]
    assert res["causa.antes.vol_diaria"] < res["causa.desde.vol_diaria"]
    assert res["causa.antes.factor"] > res["causa.desde.factor"] > 0
    for tramo in ("Antes del 1999-09-25", "Desde el 1999-09-25"):
        fila = next(l for l in bloque.splitlines() if l.startswith(f"| {tramo}"))
        assert fila.count("`#") == 8                       # la fecha y las siete cifras, con hash
    # la frase inicial da las tres probabilidades y dice de dónde viene la diferencia
    inicio = md.split("## Planteamiento")[0]
    assert "**Antes de leer las cifras.**" in inicio and "deriva de la TRM que cada método supone" in inicio
    for k in ("mc.prob_superar", "flot.prob_superar", "dist.prob_superar"):
        assert f"{res[k]:.1f} %".replace(".", ",") in inicio
    assert "Ninguna de las tres cifras tiene respaldo fuera de muestra" in inicio
    assert "Es un error\nestándar, no una cota" in md and "a lo sumo" not in md   # I4
    # linaje: también las cifras del Monte Carlo y del análisis posterior llegan a datos y supuestos
    _, K = caso.calcular(datos, reg.conjunto(ficha.pins_supuestos), {"trayectorias": 50, "semilla": 1})
    nuevas = [k for k in K if k.startswith(("mc.", "sens.", "flot.", "causa.", "abanico."))]
    assert len(nuevas) > 60
    for k in nuevas:
        assert all(h.origen in ("dato", "supuesto") for h in K[k].hojas()), k


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
    sin, _, _ = ejecutar(r, trayectorias=N_MC)
    (r / "data/respaldo").mkdir()
    (r / "data/respaldo/prueba_final.json").write_text(json.dumps(RESPALDO), encoding="utf-8")
    ficha, ruta_ficha, ruta_rep = ejecutar(r, trayectorias=N_MC)
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
        assert celdas[4].startswith("límites: prueba final")          # la cobertura respalda los límites…
        assert celdas[4].endswith("Mediana: sin respaldo fuera de muestra")   # …no la mediana (F6)
    assert "La cobertura respalda los\nlímites de la banda, no la mediana" in md
    assert "de qué lado de la banda quedó la TRM real" not in md   # este respaldo no trae el análisis posterior
    assert _fila(md, "## 4. Monte Carlo", "Percentil 95")[4] == "sin respaldo fuera de muestra"
    assert "Respaldo de estas cifras: indirecto" in md and "0,990" in md and "0,930" in md   # 126 y 252
    ref = md.split("**Modelo de referencia.**", 1)[1].split("\n\n", 1)[0].replace("\n", " ")
    assert "`lightgbm_cuantiles`" in ref and "0,977" in ref and "6,8 %" in ref and "1,85 %" in ref
    assert "0,002" in ref and "no lo usa para simular ni calcula su banda" in ref
    assert "ewma_0.94" not in md                        # lo no confirmado no se cita
    ok, _ = caso.reproducir_corrida(ruta_ficha, r)
    assert ok
    otra, _, _ = ejecutar(r, trayectorias=N_MC, semilla=7)          # otra semilla: otra corrida
    assert otra.hash_resultado != ficha.hash_resultado and otra.run_id != ficha.run_id
    (r / "data/respaldo/prueba_final.json").write_text(
        json.dumps({**RESPALDO, "nominal": 0.9}), encoding="utf-8")     # el respaldo es dato de entrada
    with pytest.raises(EntradaCambio, match="datos"):
        caso.reproducir_corrida(ruta_ficha, r)


def _asimetria(h, bajo_mediana, ic, bajo_inferior, sobre_superior):
    campos = lambda p, esperado, lo, hi: {"proporcion": p, "esperado": esperado, "ic_inf": lo,   # noqa: E731
                                          "ic_sup": hi, "compatible": lo <= esperado <= hi}
    return {"n": 1500, "n_efectivo": max(1500 // h, 1), "bajo_mediana": campos(bajo_mediana, 0.5, *ic),
            "bajo_inferior": campos(bajo_inferior, 0.025, 0.0, 0.1),
            "sobre_superior": campos(sobre_superior, 0.025, 0.0, 0.1)}


def test_14_analisis_posterior_de_que_lado_quedo_la_trm_real_con_indicio_en_horizontes_largos(tmp_path, proyecto):
    r = tmp_path / "p"
    shutil.copytree(proyecto, r, ignore=shutil.ignore_patterns("supuestos", "runs", "reports"))
    post = {"titulo": "análisis posterior (no confirmatorio)", "asimetria": {"bootstrap_est_filtrado": {
        str(h): _asimetria(h, bm, ic, inf, sup) for h, bm, ic, inf, sup in (
            (1, 0.542, (0.517, 0.567), 0.025, 0.025), (5, 0.48, (0.42, 0.54), 0.02, 0.019),
            (21, 0.38, (0.27, 0.49), 0.016, 0.016), (63, 0.663, (0.465, 0.851), 0.029, 0.012),
            (126, 0.71, (0.39, 0.94), 0.007, 0.001), (252, 0.801, (0.284, 0.995), 0.068, 0.0))}}}
    (r / "data/respaldo").mkdir()
    (r / "data/respaldo/prueba_final.json").write_text(json.dumps({**RESPALDO, "posterior": post}),
                                                       encoding="utf-8")
    _, ruta_ficha, ruta_rep = ejecutar(r, trayectorias=N_MC)
    md = ruta_rep.read_text(encoding="utf-8")
    _revisar_hashes(md)
    titulo = "### Análisis posterior (no confirmatorio): de qué lado de la banda quedó la TRM real"
    assert titulo in md.split("## 5. Abanico")[1].split("\n## ")[0]                # dentro de la sección 5
    bloque = md.split(titulo)[1].split("\n## ")[0]
    assert "no estaba en el prerregistro" in bloque and "no confirma ni rechaza nada" in bloque
    lectura = {h: _fila(md, titulo,str(h)) for h in (1, 5, 21, 63, 126, 252)}
    assert all(len(c) == 7 for c in lectura.values())
    assert "0,542" in lectura[1][1] and "0,517" in lectura[1][2] and "0,567" in lectura[1][2]
    assert "0,068" in lectura[252][3] and "0,000" in lectura[252][4] and lectura[252][5].startswith("5 ")
    assert lectura[1][6].endswith("más de lo esperado")                # 0,5 fuera del intervalo, por arriba
    assert lectura[5][6] == "compatible con una banda bien centrada"
    assert lectura[21][6].endswith("menos de lo esperado")             # 0,5 fuera, por abajo
    for h, n in ((63, 23), (126, 11), (252, 5)):                       # pocas ventanas: nunca es prueba
        assert lectura[h][6].startswith(f"**indicio, no prueba**: solo {n} ")
    assert "**A 63, 126 y 252 días es un indicio, no una prueba**" in bloque
    assert "no apunta al mismo lado en todos los horizontes" in bloque  # 5 y 21 quedaron del otro lado
    ok, _ = caso.reproducir_corrida(ruta_ficha, r)
    assert ok


# ---- prevención de H5: sin cambios sin commit, ficha + etiqueta ----------------------------------
def _fichas(r: Path) -> set[Path]:
    return set(r.glob("runs/*/ficha.json"))


def test_15_arbol_limpio_escribe_ficha_y_etiqueta_corrida_en_head(tmp_path, proyecto):
    r = tmp_path / "p"
    shutil.copytree(proyecto, r, ignore=shutil.ignore_patterns("runs", "reports"))
    confirmar(r)
    caso.sembrar(Registro(r / "data/supuestos/registro.jsonl"),
                 DatosTRM(r / "data/processed", r / "data/raw"), "analista")
    confirmar(r)
    head = git(r, "rev-parse", "HEAD")
    ficha, ruta_ficha, _ = caso.ejecutar(r, trayectorias=N_MC)
    assert ruta_ficha.exists() and ficha.commit == head
    assert git(r, "rev-parse", f"corrida-{ficha.run_id}^{{commit}}") == head
    assert hash_codigo_commit(r, f"corrida-{ficha.run_id}") == ficha.hash_codigo
    etiquetas = git(r, "tag", "--list", "corrida-*")
    caso.ejecutar(r, trayectorias=N_MC)            # misma corrida otra vez: la etiqueta ya existe
    assert git(r, "tag", "--list", "corrida-*") == etiquetas


@pytest.mark.parametrize("ensuciar", ["src", "data_nuevo", "supuestos"])
def test_16_arbol_sucio_no_escribe_ficha_ni_etiqueta(tmp_path, proyecto, ensuciar):
    r = tmp_path / "p"
    shutil.copytree(proyecto, r, ignore=shutil.ignore_patterns("runs", "reports"))
    caso.sembrar(Registro(r / "data/supuestos/registro.jsonl"),
                 DatosTRM(r / "data/processed", r / "data/raw"), "analista")
    confirmar(r)
    if ensuciar == "src":
        with open(r / "src/laboratorio/motor/plan.py", "a", encoding="utf-8") as f:
            f.write("\n# cambio sin commit\n")
    elif ensuciar == "data_nuevo":
        (r / "data/raw/nuevo_20991231.csv").write_text("fecha,x\n", encoding="utf-8")
    else:
        Registro(r / "data/supuestos/registro.jsonl").agregar(
            "caso.meta_usd", 555, "USD", "manual", "sin commit", "analista")
    antes, etiquetas = _fichas(r), git(r, "tag", "--list", "corrida-*")
    with pytest.raises(ArbolSucio, match="cambios sin commit"):
        caso.ejecutar(r, trayectorias=N_MC)
    assert _fichas(r) == antes and git(r, "tag", "--list", "corrida-*") == etiquetas


def test_17_sembrar_que_cambia_el_registro_no_escribe_ficha(tmp_path, proyecto):
    r = tmp_path / "p"
    shutil.copytree(proyecto, r, ignore=shutil.ignore_patterns("supuestos", "runs", "reports"))
    confirmar(r)                                    # registro vacío y limpio
    etiquetas = git(r, "tag", "--list", "corrida-*")
    with pytest.raises(ArbolSucio, match="registro de supuestos cambió"):
        caso.ejecutar(r, trayectorias=N_MC)
    assert not _fichas(r) and git(r, "tag", "--list", "corrida-*") == etiquetas


def test_18_sin_git_no_escribe_ficha(tmp_path, proyecto):
    r = tmp_path / "p"
    shutil.copytree(proyecto, r, ignore=shutil.ignore_patterns(".git", "runs", "reports"))
    with pytest.raises(ArbolSucio, match="no es un repositorio git"):
        caso.ejecutar(r, trayectorias=N_MC)
    assert not _fichas(r)


def test_19_la_cli_explica_por_que_no_escribe_la_ficha(tmp_path, proyecto, capsys):
    from laboratorio.motor.__main__ import main
    r = tmp_path / "p"
    shutil.copytree(proyecto, r, ignore=shutil.ignore_patterns(".git", "runs", "reports"))
    assert main(["compra_dolares", "--raiz", str(r), "--trayectorias", str(N_MC)]) == 3
    assert "No se escribió la ficha" in capsys.readouterr().err
