"""Reproducción de fichas (requisitos a y b de M5, corregidos el 17-nov-2026; docs/reproduccion.md).

a) Cada ficha de runs/*/ficha.json tiene la etiqueta `corrida-<id>` y el `hash_codigo` del árbol
   de ese commit (leído con git, sin checkout) es el de la ficha. No está marcada `lento` (tarda
   menos de un segundo) para que la integración continua la corra: una ficha nueva sin etiqueta
   rompe la CI.
b) No regresión en main: el caso, con la semilla y los parámetros de la ficha vigente
   6506dbba3261, da su resultado.json campo por campo, con tolerancia 0, sin pasar por el
   chequeo de `hash_codigo`. Tarda unos 5 s, pero va marcada `lento` (fuera de la CI): el
   `hash_datos` de la ficha se calculó en Windows sobre data/processed/trm.csv con CRLF, y la
   CI (Linux) lo reconstruye con LF, así que la condición «mismos datos» no se cumple allí.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from laboratorio.motor.casos import compra_dolares as caso
from laboratorio.motor.datos import DatosTRM
from laboratorio.motor.ficha import cargar, hash_codigo_commit, hash_datos, normalizar
from laboratorio.motor.supuestos import Registro

RAIZ = Path(__file__).resolve().parents[1]
VIGENTE = "6506dbba3261"

# Fichas sin commit de reproducción posible (docs/reproduccion.md). Solo se admite una ficha
# con `commit` nulo, creada antes del primer commit del repositorio.
SIN_COMMIT = {"d6f052613b7a": "creada antes del primer commit; ningún commit tiene su hash_codigo"}


def _git(*args) -> str:
    r = subprocess.run(["git", "-C", str(RAIZ), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def diferencias(a, b, ruta="resultado"):
    """Rutas donde `a` y `b` difieren (tolerancia 0, tipos incluidos)."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                yield f"{ruta}.{k}: falta en {'el nuevo' if k not in a else 'el guardado'}"
            else:
                yield from diferencias(a[k], b[k], f"{ruta}.{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield f"{ruta}: largo {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            yield from diferencias(x, y, f"{ruta}[{i}]")
    elif type(a) is not type(b) or a != b:
        yield f"{ruta}: {a!r} != {b!r}"


def test_diferencias_detecta_cambios_minimos():
    assert list(diferencias({"x": [1.0, 2.0]}, {"x": [1.0, 2.0]})) == []
    assert list(diferencias({"x": [1.0, 2.0]}, {"x": [1.0, 2.0000000000001]}))
    assert list(diferencias({"x": 1}, {"x": 1.0}))
    assert list(diferencias({"x": 1}, {"y": 1}))


def test_cada_ficha_tiene_etiqueta_y_su_commit_tiene_su_codigo():
    rutas = sorted(RAIZ.glob("runs/*/ficha.json"))
    assert rutas
    primer_commit = _git("log", "--reverse", "--format=%cI").splitlines()[0]
    fallos = []
    for ruta in rutas:
        rid = ruta.parent.name
        f = cargar(ruta)
        if f.run_id != rid:
            fallos.append(f"{rid}: la carpeta no es el run_id {f.run_id}")
            continue
        etiqueta = f"corrida-{rid}"
        commit = _git("rev-parse", "--verify", "--quiet", f"{etiqueta}^{{commit}}")
        if rid in SIN_COMMIT:
            from datetime import datetime
            antes = datetime.fromisoformat(f.creada_en) < datetime.fromisoformat(primer_commit)
            if f.commit is not None or not antes or commit:
                fallos.append(f"{rid}: excepción inválida (commit={f.commit}, etiqueta={bool(commit)})")
            continue
        if not commit:
            fallos.append(f"{rid}: falta la etiqueta {etiqueta} (ver docs/reproduccion.md)")
            continue
        hc = hash_codigo_commit(RAIZ, commit)
        if hc != f.hash_codigo:
            fallos.append(f"{rid}: {etiqueta} tiene hash_codigo {hc[:12]}, la ficha {f.hash_codigo[:12]}")
    assert not fallos, "\n".join(fallos)


def test_reproduccion_md_lista_cada_ficha():
    texto = (RAIZ / "docs/reproduccion.md").read_text(encoding="utf-8")
    for ruta in RAIZ.glob("runs/*/ficha.json"):
        assert ruta.parent.name in texto
    assert "docs/reproduccion.md" in (RAIZ / "README.md").read_text(encoding="utf-8")


@pytest.mark.lento
def test_no_regresion_de_la_ficha_vigente_en_main():
    ficha = cargar(RAIZ / "runs" / VIGENTE / "ficha.json")
    p = caso.rutas(RAIZ)
    datos = DatosTRM(p["procesado"], p["raw"])
    conjunto = Registro(p["registro"]).conjunto(ficha.pins_supuestos)
    # Los datos y los supuestos sí deben ser los de la ficha; el código no se compara.
    assert hash_datos(caso._archivos(datos, p))[0] == ficha.hash_datos
    assert conjunto.hash == ficha.hash_supuestos
    mc = {"trayectorias": ficha.parametros["trayectorias"], "semilla": ficha.semilla}
    resultado, _ = caso.calcular(datos, conjunto, mc, caso.cargar_respaldo(p["respaldo"]))
    nuevo = json.loads(json.dumps(normalizar(resultado), ensure_ascii=False))
    guardado = json.loads((RAIZ / "runs" / VIGENTE / "resultado.json").read_text(encoding="utf-8"))
    difs = list(diferencias(nuevo, guardado))
    assert not difs, f"{len(difs)} diferencias; primeras: " + "\n".join(difs[:20])
