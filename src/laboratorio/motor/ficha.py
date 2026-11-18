"""Ficha de corrida (sección 5.2): misma entrada -> mismo resultado -> mismo hash.

hash_entrada  = H(caso, hash de datos, hash de supuestos, hash de código, semilla, parámetros)
hash_resultado = H(resultado normalizado)
hash_ficha    = H(hash_entrada, hash_resultado)
No entran en ningún hash: la fecha de creación, el entorno (versiones) ni el commit de git;
se guardan solo como información.

Desde M2 (prevención del hallazgo H5), `registrar` solo escribe la ficha si no hay cambios sin
commit en src/ ni data/, y crea la etiqueta `corrida-<id>` en HEAD: la reproducción exacta se
hace en ese commit (docs/reproduccion.md).
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


def hash_codigo_commit(repo: str | Path, commit: str, sub: str = "src/laboratorio") -> str:
    """`hash_codigo` del árbol de `commit` bajo `sub`, leído con git (sin checkout).

    Mismo cálculo que `hash_codigo`: los .py fuera de __pycache__, ruta relativa a `sub`,
    contenido con CRLF -> LF, y el mismo orden (el de `Path`).
    """
    def git(*args, entrada: bytes | None = None) -> bytes:
        r = subprocess.run(["git", "-C", str(repo), *args], input=entrada, capture_output=True)
        if r.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)}: {r.stderr.decode(errors='replace').strip()}")
        return r.stdout

    filas = git("ls-tree", "-r", "-z", commit, "--", sub).split(b"\0")
    blobs = {}
    for fila in filter(None, filas):
        meta, ruta = fila.split(b"\t", 1)
        modo, tipo, sha = meta.split()
        ruta = ruta.decode("utf-8")
        if tipo == b"blob" and ruta.endswith(".py") and "__pycache__" not in ruta.split("/"):
            blobs[ruta[len(sub) + 1:]] = sha.decode()
    salida = git("cat-file", "--batch", entrada="".join(f"{s}\n" for s in blobs.values()).encode())
    contenidos, i = {}, 0
    for rel, sha in blobs.items():
        fin = salida.index(b"\n", i)
        tamano = int(salida[i:fin].split()[2])
        contenidos[rel] = salida[fin + 1: fin + 1 + tamano]
        i = fin + 1 + tamano + 1
    partes = [[rel, hashlib.sha256(contenidos[rel].replace(b"\r\n", b"\n")).hexdigest()]
              for rel in sorted(contenidos, key=Path)]
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


# --- registro con commit limpio (prevención del hallazgo H5) ------------------------------------
CARPETAS_VERSIONADAS = ("src", "data")      # data/ incluye data/supuestos/ y data/raw/
PREFIJO_ETIQUETA = "corrida-"


class ArbolSucio(RuntimeError):
    """No se escribe la ficha: hay cambios sin commit (o no hay git) y su commit no la reproduciría."""


def _git(raiz: str | Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(raiz), *args], capture_output=True, text=True,
                          encoding="utf-8", timeout=60)


def cambios_sin_commit(raiz: str | Path, carpetas=CARPETAS_VERSIONADAS) -> list[str]:
    """Líneas de `git status --porcelain` (incluye archivos nuevos) bajo `carpetas`."""
    r = _git(raiz, "status", "--porcelain", "--untracked-files=all", "--", *carpetas)
    if r.returncode != 0:
        raise ArbolSucio(f"{Path(raiz).resolve()} no es un repositorio git: la ficha no tendría un "
                         "commit con su código y sus datos. No se escribió la ficha.")
    return [l for l in r.stdout.splitlines() if l.strip()]


def exigir_arbol_limpio(raiz: str | Path, contexto: str = "") -> None:
    sucios = cambios_sin_commit(raiz)
    if not sucios:
        return
    lista = "\n".join(f"  {l}" for l in sucios[:15]) + ("\n  …" if len(sucios) > 15 else "")
    pista = ""
    if any("registro.jsonl" in l for l in sucios):
        pista = ("\nSi el registro cambió en esta misma ejecución (supuestos sembrados o "
                 "--actualizar-derivas), haga commit de data/supuestos/registro.jsonl y vuelva a "
                 "correr sin --actualizar-derivas.")
    raise ArbolSucio(
        f"No se escribió la ficha{contexto}: hay cambios sin commit en src/ o data/:\n{lista}\n"
        "La ficha debe apuntar a un commit que contenga su código, sus datos y sus supuestos "
        f"(hallazgo H5, docs/reproduccion.md). Haga commit y vuelva a correr.{pista}")


def etiquetar(raiz: str | Path, run_id: str, commit: str) -> str:
    """Crea la etiqueta `corrida-<run_id>` en `commit`. Si ya existe, la deja como está."""
    nombre = PREFIJO_ETIQUETA + run_id
    if _git(raiz, "rev-parse", "--verify", "--quiet", f"{nombre}^{{commit}}").returncode == 0:
        return nombre          # misma corrida (mismo hash de entrada, mismo código): ya etiquetada
    r = _git(raiz, "tag", "-a", nombre, commit, "-m",
             f"Corrida {run_id}: commit cuyo código tiene el hash_codigo de runs/{run_id}/ficha.json")
    if r.returncode != 0:
        raise RuntimeError(f"no se pudo crear la etiqueta {nombre}: {r.stderr.strip()}")
    return nombre


def registrar(ficha: Ficha, resultado, raiz: str | Path) -> Path:
    """Guarda la ficha en `raiz/runs` SOLO con el árbol limpio y la etiqueta en HEAD.

    Todo caso que escriba fichas debe usar esta función, no `guardar` directamente.
    """
    exigir_arbol_limpio(raiz)
    head = commit_git(raiz)
    if not head or ficha.commit != head:
        raise ArbolSucio(f"No se escribió la ficha: HEAD ({head}) no es el commit con que se "
                         f"construyó ({ficha.commit}).")
    ruta = guardar(ficha, resultado, Path(raiz) / "runs")
    etiquetar(raiz, ficha.run_id, head)
    return ruta


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
