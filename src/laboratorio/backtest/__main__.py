"""Backtest de desarrollo (nunca toca la prueba final).

  PYTHONPATH=src python -m laboratorio.backtest correr [modelo ...] [--forzar] [--largo]
  PYTHONPATH=src python -m laboratorio.backtest reporte
Resultados por modelo en runs/backtest_desarrollo/<modelo>.csv.gz + <modelo>.json (caché).
Con --largo: horizontes 126 y 252 (FABRICAS_LARGOS) en runs/backtest_largo/, corrida aparte
con su propio embargo (no altera los orígenes de la corrida corta).
Corrida corta: además runs/backtest_desarrollo/cola/<modelo>.csv.gz con NIVELES_COLA y el ES
(F2), para los modelos que pueden darlo; si falta ese archivo el modelo se vuelve a correr.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from .catalogo import FABRICAS, FABRICAS_LARGOS
from .corredor import correr_con_cola
from .datos import cargar_desarrollo
from .particion import INICIO_DESARROLLO, INICIO_PRUEBA_FINAL

SALIDA = Path("runs") / "backtest_desarrollo"
SALIDA_LARGO = Path("runs") / "backtest_largo"


def hash_archivo(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def correr_modelos(raiz: Path, nombres: list[str], forzar: bool = False, largo: bool = False) -> None:
    vista = cargar_desarrollo(raiz)
    catalogo = FABRICAS_LARGOS if largo else FABRICAS
    out = raiz / (SALIDA_LARGO if largo else SALIDA)
    out.mkdir(parents=True, exist_ok=True)
    for nombre in nombres:
        csv, meta = out / f"{nombre}.csv.gz", out / f"{nombre}.json"
        fabrica, paso = catalogo[nombre]
        m = fabrica()
        con_cola = (not largo) and m.cola_defendible
        csv_cola = out / "cola" / f"{nombre}.csv.gz"
        if csv.exists() and meta.exists() and (csv_cola.exists() or not con_cola) and not forzar:
            print(f"{nombre}: en caché"); continue
        t0 = time.perf_counter()
        df, cola = correr_con_cola(m, vista, paso=paso, con_cola=con_cola)
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
                "hash_trm_csv": hash_archivo(raiz / "data/processed/trm.csv")}
        meta.write_text(json.dumps(info, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        print(f"{nombre}: {seg:.0f} s, fallos={info['fallos_estimacion']}", flush=True)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="laboratorio.backtest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("correr"); c.add_argument("modelos", nargs="*"); c.add_argument("--forzar", action="store_true")
    c.add_argument("--largo", action="store_true")
    sub.add_parser("reporte")
    a = ap.parse_args(argv)
    raiz = Path(".")
    if a.cmd == "correr":
        cat = FABRICAS_LARGOS if a.largo else FABRICAS
        correr_modelos(raiz, a.modelos or list(cat), a.forzar, a.largo)
    else:
        from ..reportes.fase2 import generar
        print(generar(raiz))


if __name__ == "__main__":
    main()
