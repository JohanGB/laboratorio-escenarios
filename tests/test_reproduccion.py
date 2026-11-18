"""Reproducción de fichas (requisitos a y b de M5, corregidos el 17-nov-2026; docs/reproduccion.md).

a) Cada ficha de runs/*/ficha.json tiene la etiqueta `corrida-<id>` y el `hash_codigo` del árbol
   de ese commit (leído con git, sin checkout) es el de la ficha. No está marcada `lento` (tarda
   menos de un segundo) para que la integración continua la corra: una ficha nueva sin etiqueta
   rompe la CI.
b) No regresión en main: el caso, con la semilla y los parámetros de la ficha vigente
   6506dbba3261, da su resultado.json campo por campo, con tolerancia 0, sin pasar por el
   chequeo de `hash_codigo`. Corre en la CI (unos 5 s). Solo se excluyen los campos que son
   hashes de archivos (`es_hash`); hoy resultado.json no tiene ninguno.
   `motor/ficha.hash_archivo` depende del fin de línea: la ficha hasheó data/processed/trm.csv
   escrito en Windows (CRLF) y la CI (Linux) lo reconstruye con LF. Por eso «mismos datos» se
   comprueba con el contenido llevado a CRLF, y la igualdad de los hashes tal cual se comprueba
   aparte, cuando el archivo tiene CRLF (Windows).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import pytest

from laboratorio.motor.casos import compra_dolares as caso
from laboratorio.motor.datos import DatosTRM
from laboratorio.motor.ficha import (cargar, hash_archivo, hash_codigo_commit, hash_datos,
                                     normalizar)
from laboratorio.motor.supuestos import Registro

RAIZ = Path(__file__).resolve().parents[1]
VIGENTE = "6506dbba3261"

# Fichas sin commit de reproducción posible (docs/reproduccion.md). Solo se admite una ficha
# con `commit` nulo, creada antes del primer commit del repositorio.
SIN_COMMIT = {"d6f052613b7a": "creada antes del primer commit; ningún commit tiene su hash_codigo"}


def _git(*args) -> str:
    r = subprocess.run(["git", "-C", str(RAIZ), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


_HEX64 = re.compile(r"[0-9a-f]{64}")


def es_hash(clave: str, valor) -> bool:
    """¿Es un hash de archivo (o un `#hash` de cifra, que depende de él)?"""
    return clave == "hash" or clave.startswith("hash_") or (
        isinstance(valor, str) and bool(_HEX64.fullmatch(valor)))


def diferencias(a, b, ruta="resultado", excluir_hashes: bool = False):
    """Rutas donde `a` y `b` difieren (tolerancia 0, tipos incluidos)."""
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if excluir_hashes and es_hash(k, a.get(k, b.get(k))):
                continue
            if k not in a or k not in b:
                yield f"{ruta}.{k}: falta en {'el nuevo' if k not in a else 'el guardado'}"
            else:
                yield from diferencias(a[k], b[k], f"{ruta}.{k}", excluir_hashes)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield f"{ruta}: largo {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            yield from diferencias(x, y, f"{ruta}[{i}]", excluir_hashes)
    elif type(a) is not type(b) or a != b:
        yield f"{ruta}: {a!r} != {b!r}"


def test_diferencias_detecta_cambios_minimos():
    assert list(diferencias({"x": [1.0, 2.0]}, {"x": [1.0, 2.0]})) == []
    assert list(diferencias({"x": [1.0, 2.0]}, {"x": [1.0, 2.0000000000001]}))
    assert list(diferencias({"x": 1}, {"x": 1.0}))
    assert list(diferencias({"x": 1}, {"y": 1}))
    a, b = {"v": 1.5, "hash": "a" * 64, "c": {"hash_datos": "x"}}, {"v": 1.5, "hash": "b" * 64, "c": {"hash_datos": "y"}}
    assert list(diferencias(a, b)) and not list(diferencias(a, b, excluir_hashes=True))
    assert list(diferencias({"v": 1.5, "hash": "a"}, {"v": 1.6, "hash": "a"}, excluir_hashes=True))


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


def _ficha_y_entradas():
    ficha = cargar(RAIZ / "runs" / VIGENTE / "ficha.json")
    p = caso.rutas(RAIZ)
    datos = DatosTRM(p["procesado"], p["raw"])
    return ficha, p, datos, caso._archivos(datos, p)


CRLF_B, LF_B = b"\r\n", b"\n"


def _hash_en_crlf(ruta: Path) -> str:
    """SHA-256 del archivo con fines de línea CRLF (como lo escribe Windows)."""
    b = ruta.read_bytes().replace(CRLF_B, LF_B).replace(LF_B, CRLF_B)
    return hashlib.sha256(b).hexdigest()


def test_no_regresion_de_la_ficha_vigente_en_main():
    ficha, p, datos, archivos = _ficha_y_entradas()
    conjunto = Registro(p["registro"]).conjunto(ficha.pins_supuestos)
    # Mismos datos (contenido, con independencia del fin de línea) y mismos supuestos; el código
    # no se compara.
    assert set(archivos) == set(ficha.datos)
    for nombre, ruta in archivos.items():
        assert ficha.datos[nombre] in (hash_archivo(ruta), _hash_en_crlf(ruta)), nombre
    assert conjunto.hash == ficha.hash_supuestos
    mc = {"trayectorias": ficha.parametros["trayectorias"], "semilla": ficha.semilla}
    resultado, _ = caso.calcular(datos, conjunto, mc, caso.cargar_respaldo(p["respaldo"]))
    nuevo = json.loads(json.dumps(normalizar(resultado), ensure_ascii=False))
    guardado = json.loads((RAIZ / "runs" / VIGENTE / "resultado.json").read_text(encoding="utf-8"))
    assert len(guardado) > 200
    difs = list(diferencias(nuevo, guardado, excluir_hashes=True))
    assert not difs, f"{len(difs)} diferencias; primeras: " + " | ".join(difs[:20])


def test_hashes_de_archivo_de_la_ficha_vigente_con_crlf():
    """Con CRLF (Windows) los hashes de archivo coinciden tal cual. Con LF (Linux) coinciden
    una vez llevado el contenido a CRLF: la diferencia es solo el fin de línea."""
    ficha, _, _, archivos = _ficha_y_entradas()
    iguales = 0
    for nombre, ruta in archivos.items():
        if hash_archivo(ruta) == ficha.datos[nombre]:       # mismos bytes (p. ej., archivos versionados)
            iguales += 1
            continue
        assert CRLF_B not in ruta.read_bytes(), f"{nombre}: tiene CRLF y aun así su hash no coincide"
        assert _hash_en_crlf(ruta) == ficha.datos[nombre], f"{nombre}: difiere más que el fin de línea"
    if iguales == len(archivos):                            # Windows: todo coincide tal cual
        assert hash_datos(archivos)[0] == ficha.hash_datos
