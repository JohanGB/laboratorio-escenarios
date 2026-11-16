"""Prueba final: una sola corrida, atada al prerregistro (docs/prerregistro.md).

  PYTHONPATH=src python -m laboratorio.backtest final --hashes      (imprime los hashes actuales)
  PYTHONPATH=src python -m laboratorio.backtest final --verificar   (solo compara hashes)
  PYTHONPATH=src python -m laboratorio.backtest final               (corre; UNA sola vez)

Candados (R3):
- `cargar_prueba_final` es la ÚNICA función que entrega datos con fecha ≥ INICIO_PRUEBA_FINAL y
  solo lo hace si los hashes del código (src/**/*.py), de los datos y del entorno (versiones de
  Python y de las bibliotecas numéricas) coinciden con los escritos en el prerregistro. Sin
  prerregistro, o con un byte de código o de datos distinto, falla.
- La corrida completa deja `runs/prueba_final/HECHO.json`; con ese archivo el comando se niega a
  correr otra vez. No existe opción para forzar. Una corrida interrumpida se puede reanudar
  (cada modelo es determinista: mismas semillas, mismo resultado).
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
from datetime import datetime
from pathlib import Path

import pandas as pd

from .catalogo import FABRICAS, FABRICAS_LARGOS
from .datos import Vista, construir_vista
from .ejecucion import correr_uno, hash_archivo
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

SALIDA_FINAL = Path("runs") / "prueba_final"
SALIDA_FINAL_LARGO = Path("runs") / "prueba_final_largo"
PRERREGISTRO = Path("docs") / "prerregistro.md"
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
    ruta relativa (con /) + contenido, en orden alfabético de ruta. 64 hex."""
    base = Path(dir_src) if dir_src else Path(__file__).resolve().parents[2]
    h = hashlib.sha256()
    archivos = sorted(base.rglob("*.py"), key=lambda p: p.relative_to(base).as_posix())
    if not archivos:
        raise FileNotFoundError(f"sin archivos .py en {base}")
    for p in archivos:
        h.update(p.relative_to(base).as_posix().encode("utf-8") + b"\0")
        h.update(p.read_bytes() + b"\0")
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


def verificar_prerregistro(raiz: str | Path = ".", dir_src: str | Path | None = None) -> dict[str, str]:
    """Devuelve los hashes si TODOS coinciden con el prerregistro; si no, falla y dice cuáles."""
    registrado = leer_prerregistro(Path(raiz) / PRERREGISTRO)
    actual = hashes_actuales(raiz, dir_src)
    malos = [f"{k}: prerregistro {registrado.get(k, 'AUSENTE')} ≠ actual {v}"
             for k, v in actual.items() if registrado.get(k) != v]
    if malos:
        raise RuntimeError("los hashes no coinciden con el prerregistro; NO se corre nada:\n  "
                           + "\n  ".join(malos))
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
    vista, primero = cargar_prueba_final(raiz, dir_src)
    hashes = hashes_actuales(raiz, dir_src)
    cat = {m: FABRICAS[m] for m in MODELOS_FINAL} if catalogo is None else catalogo
    cat_l = {m: FABRICAS_LARGOS[m] for m in MODELOS_FINAL_LARGOS} if catalogo_largo is None else catalogo_largo
    extra = {"prueba_final": True, **hashes}
    for nombre in cat:
        correr_uno(nombre, cat, vista, raiz / SALIDA_FINAL, raiz, primero=primero, extra=extra)
    for nombre in cat_l:
        correr_uno(nombre, cat_l, vista, raiz / SALIDA_FINAL_LARGO, raiz, largo=True,
                   primero=primero, extra=extra)
    salida = generar(raiz, confirmatorias=CONFIRMATORIAS if confirmatorias is None else confirmatorias)
    hecho.write_text(json.dumps({"terminada": datetime.now().isoformat(timespec="seconds"),
                                 "modelos": list(cat), "modelos_largos": list(cat_l), **hashes},
                                indent=2, ensure_ascii=False), encoding="utf-8")
    return salida


def lineas_hashes(raiz: str | Path = ".", dir_src: str | Path | None = None) -> list[str]:
    """Las líneas que van en la sección de hashes del prerregistro (no lee datos: solo bytes)."""
    return [f"- `{k}`: `{v}`" for k, v in hashes_actuales(raiz, dir_src).items()]


def main_final(raiz: Path, solo_verificar: bool = False, solo_hashes: bool = False) -> None:
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
    if solo_verificar:
        return
    print(correr_final(raiz))
