"""Ficha de corrida (sección 5.2): misma entrada -> mismo resultado -> mismo hash.

hash_entrada  = H(caso, hash de datos, hash de supuestos, hash de código, semilla, parámetros)
hash_resultado = H(resultado normalizado)
hash_ficha    = H(hash_entrada, hash_resultado)
No entran en ningún hash: la fecha de creación, el entorno (versiones) ni el commit de git;
se guardan solo como información.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

from .supuestos import ConjuntoSupuestos, canonico, sha256_texto


# --- hashes de entrada ---------------------------------------------------------------
def hash_archivo(ruta: str | Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def hash_datos(archivos: Mapping[str, str | Path]) -> tuple[str, dict[str, str]]:
    """Hash de los archivos de datos usados. Devuelve (hash global, {nombre: sha256})."""
    por_archivo = {n: hash_archivo(p) for n, p in sorted(archivos.items())}
    return sha256_texto(canonico(por_archivo)), por_archivo


def hash_codigo(raiz: str | Path) -> str:
    """Hash del contenido de todos los .py bajo `raiz` (independiente de CRLF/LF)."""
    raiz = Path(raiz)
    partes = []
    for p in sorted(raiz.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        contenido = p.read_bytes().replace(b"\r\n", b"\n")
        partes.append([p.relative_to(raiz).as_posix(), hashlib.sha256(contenido).hexdigest()])
    return sha256_texto(canonico(partes))


def commit_git(raiz: str | Path) -> str | None:
    """Commit actual si `raiz` está en un repositorio git (informativo; no entra en hashes)."""
    try:
        r = subprocess.run(["git", "-C", str(raiz), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


# --- resultado normalizado ------------------------------------------------------------
def normalizar(obj, cifras: int = 12):
    """Convierte a tipos JSON estables: floats a `cifras` significativas, numpy a Python."""
    if hasattr(obj, "item") and not isinstance(obj, (list, tuple, dict)) and getattr(obj, "ndim", 1) == 0:
        obj = obj.item()
    if hasattr(obj, "tolist") and getattr(obj, "ndim", 0) > 0:
        obj = obj.tolist()
    if isinstance(obj, bool) or obj is None or isinstance(obj, (int, str)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj):
            return "NaN"
        if math.isinf(obj):
            return "Infinity" if obj > 0 else "-Infinity"
        return float(f"{obj:.{cifras}g}")
    if isinstance(obj, Mapping):
        return {str(k): normalizar(v, cifras) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [normalizar(v, cifras) for v in obj]
    if isinstance(obj, Path):
        return obj.as_posix()
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"no se puede normalizar {type(obj).__name__}")


def hash_resultado(resultado) -> str:
    return sha256_texto(canonico(normalizar(resultado)))


def entorno() -> dict:
    import numpy
    import pandas
    return {"python": sys.version.split()[0], "numpy": numpy.__version__,
            "pandas": pandas.__version__, "plataforma": platform.platform()}


# --- ficha ------------------------------------------------------------------------------
@dataclass(frozen=True)
class Ficha:
    caso: str
    semilla: int | None
    parametros: dict
    datos: dict[str, str]
    pins_supuestos: dict[str, int]
    hash_datos: str
    hash_supuestos: str
    hash_codigo: str
    hash_entrada: str
    hash_resultado: str
    hash_ficha: str
    creada_en: str = field(default="")      # informativo
    commit: str | None = None               # informativo
    entorno: dict = field(default_factory=dict)  # informativo

    @property
    def run_id(self) -> str:
        return self.hash_entrada[:12]

    def a_dict(self) -> dict:
        return asdict(self)


def calcular_hash_entrada(caso, hash_datos_, hash_supuestos, hash_codigo_, semilla, parametros) -> str:
    return sha256_texto(canonico({
        "caso": caso, "hash_datos": hash_datos_, "hash_supuestos": hash_supuestos,
        "hash_codigo": hash_codigo_, "semilla": semilla, "parametros": normalizar(parametros)}))


def construir_ficha(caso: str, datos: Mapping[str, str | Path], supuestos: ConjuntoSupuestos,
                    semilla: int | None, parametros: dict, resultado,
                    raiz_codigo: str | Path) -> Ficha:
    hd, por_archivo = hash_datos(datos)
    hc = hash_codigo(raiz_codigo)
    he = calcular_hash_entrada(caso, hd, supuestos.hash, hc, semilla, parametros)
    hr = hash_resultado(resultado)
    return Ficha(caso=caso, semilla=semilla, parametros=normalizar(parametros), datos=por_archivo,
                 pins_supuestos=dict(supuestos.pins), hash_datos=hd, hash_supuestos=supuestos.hash,
                 hash_codigo=hc, hash_entrada=he, hash_resultado=hr,
                 hash_ficha=sha256_texto(canonico([he, hr])),
                 creada_en=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 commit=commit_git(raiz_codigo), entorno=entorno())


def guardar(ficha: Ficha, resultado, carpeta_runs: str | Path) -> Path:
    destino = Path(carpeta_runs) / ficha.run_id
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "ficha.json").write_text(
        json.dumps(ficha.a_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    (destino / "resultado.json").write_text(
        json.dumps(normalizar(resultado), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8")
    return destino / "ficha.json"


def cargar(ruta: str | Path) -> Ficha:
    return Ficha(**json.loads(Path(ruta).read_text(encoding="utf-8")))


class EntradaCambio(RuntimeError):
    """Los datos, supuestos o el código ya no son los de la ficha."""


def reproducir(ficha: Ficha, ejecutar: Callable[[Ficha], object],
               datos: Mapping[str, str | Path], supuestos: ConjuntoSupuestos,
               raiz_codigo: str | Path) -> tuple[bool, str]:
    """Verifica que la entrada actual coincide con la ficha, reejecuta y compara resultados.

    `ejecutar(ficha)` debe devolver el resultado usando ficha.semilla y ficha.parametros.
    Devuelve (coincide, hash_resultado_nuevo).
    """
    hd, _ = hash_datos(datos)
    hc = hash_codigo(raiz_codigo)
    actual = calcular_hash_entrada(ficha.caso, hd, supuestos.hash, hc, ficha.semilla,
                                   ficha.parametros)
    if actual != ficha.hash_entrada:
        cambios = [n for n, a, b in (("datos", hd, ficha.hash_datos),
                                      ("supuestos", supuestos.hash, ficha.hash_supuestos),
                                      ("código", hc, ficha.hash_codigo)) if a != b]
        raise EntradaCambio(f"la entrada cambió: {', '.join(cambios) or 'parámetros'}")
    nuevo = hash_resultado(ejecutar(ficha))
    return nuevo == ficha.hash_resultado, nuevo
