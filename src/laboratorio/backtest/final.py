"""Prueba final: una sola corrida, atada al prerregistro (docs/prerregistro.md).

  PYTHONPATH=src python -m laboratorio.backtest final --hashes      (imprime los hashes actuales)
  PYTHONPATH=src python -m laboratorio.backtest final --verificar   (compara hashes y git; no corre)
  PYTHONPATH=src python -m laboratorio.backtest final               (corre; UNA sola vez)

Candados (R3):
- `cargar_prueba_final` es la ÚNICA función que entrega datos con fecha ≥ INICIO_PRUEBA_FINAL y
  solo lo hace si los hashes del código (src/**/*.py, con CRLF normalizado a LF), de los datos y
  del entorno (versiones de Python y de las bibliotecas numéricas) coinciden con los escritos en
  el prerregistro. Sin prerregistro, o con un byte de código o de datos distinto, falla.
- Git: `docs/prerregistro.md` debe ser idéntico al del commit etiquetado `prerregistro-final`,
  `src/` y `data/` deben ser idénticos a ese commit y no tener nada sin versionar. Así el
  prerregistro que se verifica es el que quedó fechado en la historia, no uno editado después.
- Al empezar se escribe `runs/prueba_final/INICIADA.json` (hora, hashes, commits) ANTES de leer
  los datos. Una corrida interrumpida se puede reanudar: cada reanudación queda anotada ahí y un
  resultado en caché solo vale si se produjo con los mismos hashes; si no, ese modelo se repite.
- La corrida completa deja `runs/prueba_final/HECHO.json`, con el SHA-256 de cada resultado; con
  ese archivo el comando se niega a correr otra vez. No existe opción para forzar. (Borrar el
  archivo a mano reabre el comando: es una puerta declarada en el prerregistro, no cerrada aquí.)
- La corrida no imprime cifras: solo el nombre y el estado de cada modelo y la ruta del reporte.
- Lo que se evalúa está fijado aquí (y por tanto dentro del hash): lista de modelos, hipótesis
  confirmatorias y motor del caso. El reporte (`reportes/prueba_final.py`) solo escribe esto.

Orígenes: desde el primer día de mercado ≥ INICIO_PRUEBA_FINAL hasta el último que permite el
embargo (n − 1 − h_max). Ventana expansiva: cada modelo se estima con toda la historia anterior
al origen (desarrollo incluido) y se reajusta con el mismo paso que en desarrollo.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd

from .catalogo import FABRICAS, FABRICAS_LARGOS
from .datos import Vista, construir_vista
from .ejecucion import correr_uno, hash_archivo, sha256_archivo
from .particion import INICIO_PRUEBA_FINAL

# ---- Fijado por el prerregistro (cambiar cualquier cosa cambia el hash del código) ----------------
MODELOS_FINAL = tuple(FABRICAS)                    # los 17 de la corrida corta
MODELOS_FINAL_LARGOS = tuple(FABRICAS_LARGOS)      # los 15 de la corrida larga (descriptiva)
# Hipótesis confirmatorias: (h, campeón de desarrollo, línea base de referencia en desarrollo).
# H1 en cada una: el campeón tiene menor CRPS esperado que la línea base (Diebold-Mariano
# unilateral). Las cuatro forman UNA familia: Holm, α = 0,05.
CONFIRMATORIAS = ((1, "lightgbm_cuantiles", "sim_hist_pond"),
                  (5, "ewma_0.94", "sim_hist_pond"),
                  (21, "ewma_0.94", "sim_hist_pond"),
                  (63, "ewma_0.94", "caminata_aleatoria"))
ALFA_CONFIRMATORIA = 0.05
MOTOR_CASO = "bootstrap_est_filtrado"              # motor del caso en todos sus horizontes
MOTOR_SENSIBILIDAD = "bootstrap_est"
# Horizontes en los que la advertencia de cobertura acompaña SIEMPRE a las cifras del caso, con
# su n efectivo, salga como salga la cobertura (pocas ventanas independientes).
HORIZONTES_ADVERTENCIA = (63, 126, 252)
# Episodios que se excluyen en la línea de sensibilidad de la confirmatoria de h = 1.
EPISODIOS = ("covid_2020", "estres_2022")

SALIDA_FINAL = Path("runs") / "prueba_final"
SALIDA_FINAL_LARGO = Path("runs") / "prueba_final_largo"
REPORTE_FINAL = Path("reports") / "prueba_final.md"
FIGURA_PIT = "prueba_final_pit.png"
PRERREGISTRO = Path("docs") / "prerregistro.md"
ETIQUETA = "prerregistro-final"                    # etiqueta de git del commit del prerregistro
RUTAS_LIMPIAS = ("src", "data")                    # deben ser idénticas a ese commit y sin extras
ARCHIVOS_DATOS = ("trm.csv", "externas_diario.csv", "tasas_diarias.csv")
PAQUETES = ("numpy", "pandas", "scipy", "statsmodels", "arch", "lightgbm")
_CLAVE = re.compile(r"^- `(hash_codigo|hash_entorno|hash_[a-z_]+_csv)`: `([0-9a-f]+)`\s*$", re.M)


def entorno() -> dict[str, str]:
    """Versiones de Python y de las bibliotecas de las que dependen los números."""
    import platform
    from importlib.metadata import version
    return {"python": platform.python_version(), **{p: version(p) for p in PAQUETES}}


def hash_entorno() -> str:
    txt = ";".join(f"{k}={v}" for k, v in entorno().items())
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()[:16]


def hash_codigo(dir_src: str | Path | None = None) -> str:
    """SHA-256 de todos los `*.py` bajo `dir_src` (por defecto, el paquete instalado `src/`):
    ruta relativa (con /) + contenido, en orden alfabético de ruta. 64 hex.

    El contenido se hashea con los fines de línea CRLF convertidos a LF: el mismo código da el
    mismo hash en cualquier sistema y con cualquier configuración de git.
    """
    base = Path(dir_src) if dir_src else Path(__file__).resolve().parents[2]
    h = hashlib.sha256()
    archivos = sorted(base.rglob("*.py"), key=lambda p: p.relative_to(base).as_posix())
    if not archivos:
        raise FileNotFoundError(f"sin archivos .py en {base}")
    for p in archivos:
        h.update(p.relative_to(base).as_posix().encode("utf-8") + b"\0")
        h.update(p.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def clave_datos(archivo: str) -> str:
    return "hash_" + archivo.replace(".", "_")


def hashes_actuales(raiz: str | Path = ".", dir_src: str | Path | None = None) -> dict[str, str]:
    proc = Path(raiz) / "data" / "processed"
    return {"hash_codigo": hash_codigo(dir_src), "hash_entorno": hash_entorno(),
            **{clave_datos(a): hash_archivo(proc / a) for a in ARCHIVOS_DATOS}}


def leer_prerregistro(archivo: Path) -> dict[str, str]:
    """Líneas «- `clave`: `valor`» del prerregistro. Una clave repetida es un error."""
    if not archivo.exists():
        raise RuntimeError(f"no existe {archivo}: sin prerregistro no se abre la prueba final")
    pares = _CLAVE.findall(archivo.read_text(encoding="utf-8"))
    claves = [k for k, _ in pares]
    if len(set(claves)) != len(claves):
        raise RuntimeError("prerregistro con claves de hash repetidas")
    return dict(pares)


# ---- git ------------------------------------------------------------------------------------------
def _git(raiz: Path, *args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", "-C", str(raiz), *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except OSError as e:
        raise RuntimeError("no se pudo ejecutar git: sin git no se abre la prueba final") from e


def verificar_git(raiz: str | Path = ".") -> str:
    """Exige que el prerregistro, `src/` y `data/` sean los del commit etiquetado. Devuelve su SHA.

    1. `raiz` es la raíz de un repositorio git y existe la etiqueta `prerregistro-final`.
    2. Ese commit contiene docs/prerregistro.md y el archivo actual es idéntico (git diff --quiet).
    3. `src/` y `data/` son idénticos a ese commit y no tienen archivos sin versionar
       (los ignorados, como data/processed/, los cubren los hashes, no git).
    """
    raiz = Path(raiz)
    r = _git(raiz, "rev-parse", "--show-prefix")
    if r.returncode != 0 or r.stdout.strip():
        raise RuntimeError(f"{raiz.resolve()} no es la raíz de un repositorio git: sin historia "
                           "que feche el prerregistro no se abre la prueba final")
    r = _git(raiz, "rev-parse", "--verify", "--quiet", f"refs/tags/{ETIQUETA}^{{commit}}")
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError(f"no existe la etiqueta de git «{ETIQUETA}»: el prerregistro debe estar "
                           "en un commit etiquetado antes de abrir la prueba final")
    commit = r.stdout.strip()
    pre = PRERREGISTRO.as_posix()
    if _git(raiz, "cat-file", "-e", f"{commit}:{pre}").returncode != 0:
        raise RuntimeError(f"el commit etiquetado «{ETIQUETA}» no contiene {pre}")
    malos = []
    if _git(raiz, "diff", "--quiet", commit, "--", pre).returncode != 0:
        malos.append(f"{pre} no coincide con el del commit etiquetado «{ETIQUETA}»")
    if _git(raiz, "diff", "--quiet", commit, "--", *RUTAS_LIMPIAS).returncode != 0:
        malos.append(f"{' y '.join(r + '/' for r in RUTAS_LIMPIAS)} no coinciden con el commit "
                     f"etiquetado «{ETIQUETA}»")
    s = _git(raiz, "status", "--porcelain", "--untracked-files=all", "--", *RUTAS_LIMPIAS)
    if s.returncode != 0:
        malos.append("git status falló: " + s.stderr.strip())
    elif s.stdout.strip():
        malos.append("árbol sucio (cambios o archivos sin versionar): "
                     + "; ".join(linea.strip() for linea in s.stdout.splitlines()[:10]))
    if malos:
        raise RuntimeError("git no coincide con el prerregistro; NO se corre nada:\n  "
                           + "\n  ".join(malos))
    return commit


def verificar_prerregistro(raiz: str | Path = ".", dir_src: str | Path | None = None) -> dict[str, str]:
    """Devuelve los hashes si TODOS coinciden con el prerregistro y git está en orden; si no, falla.

    No lee ningún dato: solo bytes para los hashes y el estado de git (`verificar_git`).
    """
    registrado = leer_prerregistro(Path(raiz) / PRERREGISTRO)
    actual = hashes_actuales(raiz, dir_src)
    malos = [f"{k}: prerregistro {registrado.get(k, 'AUSENTE')} ≠ actual {v}"
             for k, v in actual.items() if registrado.get(k) != v]
    if malos:
        raise RuntimeError("los hashes no coinciden con el prerregistro; NO se corre nada:\n  "
                           + "\n  ".join(malos))
    verificar_git(raiz)
    return actual


def cargar_prueba_final(raiz: str | Path = ".", dir_src: str | Path | None = None) -> tuple[Vista, int]:
    """(vista con TODA la historia, índice del primer origen de la prueba final).

    Verifica el prerregistro antes de leer un solo dato posterior al corte.
    """
    verificar_prerregistro(raiz, dir_src)
    proc = Path(raiz) / "data" / "processed"
    trm = pd.read_csv(proc / "trm.csv", parse_dates=["fecha"], index_col="fecha")
    ext = pd.read_csv(proc / "externas_diario.csv", parse_dates=["fecha"], index_col="fecha")
    tas = pd.read_csv(proc / "tasas_diarias.csv", parse_dates=["fecha"], index_col="fecha")
    externas = pd.concat([ext[["brent_usd", "dolar_amplio", "fed_funds"]], tas[["politica"]]],
                         axis=1, sort=True)
    vista = construir_vista(trm, externas)
    primero = int(vista.fechas.searchsorted(pd.Timestamp(INICIO_PRUEBA_FINAL)))
    if primero >= vista.n:
        raise RuntimeError("no hay datos posteriores al corte de la prueba final")
    return vista, primero


# ---- corrida única --------------------------------------------------------------------------------
def _ahora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def registrar_inicio(raiz: Path, hashes: dict[str, str], commits: dict[str, str]) -> dict:
    """Escribe (o amplía) runs/prueba_final/INICIADA.json: la prueba final quedó abierta.

    La primera vez guarda hora, hashes, entorno y commits. Si ya existe (reanudación de una
    corrida interrumpida) no se pisa: se agrega una entrada a «reanudaciones». Ilegible = error.
    """
    archivo = raiz / SALIDA_FINAL / "INICIADA.json"
    entrada = {**commits, **hashes, "entorno": entorno()}
    if archivo.exists():
        try:
            reg = json.loads(archivo.read_text(encoding="utf-8"))
        except ValueError as e:
            raise RuntimeError(f"{archivo} está dañado; no se corre nada hasta aclararlo") from e
        if not isinstance(reg, dict) or "iniciada" not in reg:
            raise RuntimeError(f"{archivo} no tiene el formato esperado; no se corre nada")
        reg.setdefault("reanudaciones", []).append({"hora": _ahora(), **entrada})
    else:
        archivo.parent.mkdir(parents=True, exist_ok=True)
        reg = {"iniciada": _ahora(), **entrada, "reanudaciones": []}
    archivo.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")
    return reg


def sha256_resultados(raiz: Path) -> dict[str, str]:
    """Ruta relativa (con /) → SHA-256 de cada archivo de resultados de la prueba final:
    todo lo que hay en runs/prueba_final/ y runs/prueba_final_largo/ (menos HECHO.json), el
    reporte y su figura."""
    archivos = [p for carpeta in (SALIDA_FINAL, SALIDA_FINAL_LARGO) if (raiz / carpeta).exists()
                for p in (raiz / carpeta).rglob("*") if p.is_file() and p.name != "HECHO.json"]
    archivos += [p for p in (raiz / REPORTE_FINAL, raiz / REPORTE_FINAL.parent / "figs" / FIGURA_PIT)
                 if p.exists()]
    return {p.relative_to(raiz).as_posix(): sha256_archivo(p)
            for p in sorted(archivos, key=lambda p: p.relative_to(raiz).as_posix())}


def correr_final(raiz: str | Path = ".", dir_src: str | Path | None = None,
                 catalogo: dict | None = None, catalogo_largo: dict | None = None,
                 confirmatorias=None) -> Path:
    """Corre la prueba final completa y escribe reports/prueba_final.md. Una sola vez.

    `catalogo`, `catalogo_largo` y `confirmatorias` existen solo para las pruebas con datos
    sintéticos; el comando usa siempre los fijados arriba.
    """
    from ..reportes.prueba_final import generar
    raiz = Path(raiz)
    hecho = raiz / SALIDA_FINAL / "HECHO.json"
    if hecho.exists():
        raise RuntimeError(f"la prueba final ya se corrió ({hecho}); no se repite. Cualquier "
                           "cálculo nuevo es «análisis posterior (no confirmatorio)».")
    hashes = verificar_prerregistro(raiz, dir_src)          # hashes y git; todavía sin leer datos
    commits = {"commit_prerregistro": verificar_git(raiz),
               "commit_head": _git(raiz, "rev-parse", "HEAD").stdout.strip()}
    inicio = registrar_inicio(raiz, hashes, commits)
    vista, primero = cargar_prueba_final(raiz, dir_src)
    cat = {m: FABRICAS[m] for m in MODELOS_FINAL} if catalogo is None else catalogo
    cat_l = {m: FABRICAS_LARGOS[m] for m in MODELOS_FINAL_LARGOS} if catalogo_largo is None else catalogo_largo
    extra = {"prueba_final": True, **hashes}
    for nombre in cat:
        correr_uno(nombre, cat, vista, raiz / SALIDA_FINAL, raiz, primero=primero, extra=extra,
                   exigir=extra, silencioso=True)
    for nombre in cat_l:
        correr_uno(nombre, cat_l, vista, raiz / SALIDA_FINAL_LARGO, raiz, largo=True,
                   primero=primero, extra=extra, exigir=extra, silencioso=True)
    salida = generar(raiz, confirmatorias=CONFIRMATORIAS if confirmatorias is None else confirmatorias)
    hecho.write_text(json.dumps({"iniciada": inicio["iniciada"], "terminada": _ahora(),
                                 "reanudaciones": len(inicio["reanudaciones"]),
                                 "modelos": list(cat), "modelos_largos": list(cat_l),
                                 **commits, **hashes, "sha256": sha256_resultados(raiz)},
                                indent=2, ensure_ascii=False), encoding="utf-8")
    return salida


def lineas_hashes(raiz: str | Path = ".", dir_src: str | Path | None = None) -> list[str]:
    """Las líneas que van en la sección de hashes del prerregistro (no lee datos: solo bytes)."""
    return [f"- `{k}`: `{v}`" for k, v in hashes_actuales(raiz, dir_src).items()]


def main_final(raiz: Path, solo_verificar: bool = False, solo_hashes: bool = False) -> None:
    """Salida del comando: hashes y commit verificados, estado de cada modelo y ruta del
    reporte. Nunca una cifra de resultados (están en el reporte y en los .json)."""
    if solo_hashes:
        for linea in lineas_hashes(raiz):
            print(linea)
        print("Entorno: " + ", ".join(f"{k} {v}" for k, v in entorno().items()) + ".")
        return
    hashes = verificar_prerregistro(raiz)
    print("prerregistro verificado:")
    for k, v in hashes.items():
        print(f"  {k}: {v}")
    print("  entorno: " + ", ".join(f"{k} {v}" for k, v in entorno().items()))
    print(f"  commit etiquetado «{ETIQUETA}»: {verificar_git(raiz)}")
    if solo_verificar:
        return
    print(correr_final(raiz))
