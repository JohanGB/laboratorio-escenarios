"""Ejecución de un modelo del catálogo y escritura de sus resultados (CSV + JSON de metadatos).

La usan la corrida de desarrollo (`__main__`) y la prueba final (`final`): el mismo código produce
los dos conjuntos de resultados; solo cambian la vista de datos y el primer origen.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from .corredor import correr_con_cola
from .datos import Vista
from .particion import INICIO_DESARROLLO, INICIO_PRUEBA_FINAL


def hash_archivo(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def correr_uno(nombre: str, catalogo: dict, vista: Vista, out: Path, raiz: Path, largo: bool = False,
               forzar: bool = False, primero: int | None = None, extra: dict | None = None) -> bool:
    """Corre `nombre` y guarda <out>/<nombre>.csv.gz, .json y, si aplica, cola/<nombre>.csv.gz.

    Devuelve False si ya estaba en caché (y no se forzó). `primero` = índice del primer origen
    (por defecto, el inicio del desarrollo). `extra` se agrega a los metadatos.
    """
    csv, meta = out / f"{nombre}.csv.gz", out / f"{nombre}.json"
    fabrica, paso = catalogo[nombre]
    m = fabrica()
    con_cola = (not largo) and m.cola_defendible
    csv_cola = out / "cola" / f"{nombre}.csv.gz"
    if csv.exists() and meta.exists() and (csv_cola.exists() or not con_cola) and not forzar:
        print(f"{nombre}: en caché")
        return False
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    df, cola = correr_con_cola(m, vista, primero=primero, paso=paso, con_cola=con_cola)
    seg = time.perf_counter() - t0
    df.to_csv(csv, index=False, compression="gzip")
    if cola is not None:
        csv_cola.parent.mkdir(exist_ok=True)
        cola.to_csv(csv_cola, index=False, compression="gzip")
    info = {"modelo": nombre, "parametros": m.parametros(), "paso_reajuste": paso,
            "segundos": round(seg, 1), "fallos_estimacion": getattr(m, "fallos", 0),
            "reajustes": getattr(m, "reajustes", None), "n_origenes": int(df["origen"].nunique()),
            "horizontes": list(m.horizontes),
            "es": ("aplica" if cola is not None else
                   "no aplica: " + (m.motivo_sin_cola or "no se calcula en la corrida larga")),
            "primer_origen": str(df["fecha"].min())[:10], "ultimo_origen": str(df["fecha"].max())[:10],
            "inicio_desarrollo": INICIO_DESARROLLO, "corte_prueba_final": INICIO_PRUEBA_FINAL,
            "ultimo_dato_cargado": str(vista.fechas.max())[:10],
            "hash_trm_csv": hash_archivo(raiz / "data/processed/trm.csv"), **(extra or {})}
    meta.write_text(json.dumps(info, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"{nombre}: {seg:.0f} s, fallos={info['fallos_estimacion']}", flush=True)
    return True
