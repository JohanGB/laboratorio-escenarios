"""Backtest de desarrollo (nunca toca la prueba final).

  PYTHONPATH=src python -m laboratorio.backtest correr [modelo ...] [--forzar]
  PYTHONPATH=src python -m laboratorio.backtest reporte
Resultados por modelo en runs/backtest_desarrollo/<modelo>.csv.gz + <modelo>.json (caché).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from .catalogo import FABRICAS
from .corredor import correr
from .datos import cargar_desarrollo
from .particion import INICIO_DESARROLLO, INICIO_PRUEBA_FINAL

SALIDA = Path("runs") / "backtest_desarrollo"


def hash_archivo(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def correr_modelos(raiz: Path, nombres: list[str], forzar: bool = False) -> None:
    vista = cargar_desarrollo(raiz)
    out = raiz / SALIDA
    out.mkdir(parents=True, exist_ok=True)
    for nombre in nombres:
        csv, meta = out / f"{nombre}.csv.gz", out / f"{nombre}.json"
        if csv.exists() and meta.exists() and not forzar:
            print(f"{nombre}: en caché"); continue
        fabrica, paso = FABRICAS[nombre]
        m = fabrica()
        t0 = time.time()
        df = correr(m, vista, paso=paso)
        seg = time.time() - t0
        df.to_csv(csv, index=False, compression="gzip")
        info = {"modelo": nombre, "parametros": m.parametros(), "paso_reajuste": paso,
                "segundos": round(seg, 1), "fallos_estimacion": getattr(m, "fallos", 0),
                "reajustes": getattr(m, "reajustes", None), "n_origenes": int(df["origen"].nunique()),
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
    sub.add_parser("reporte")
    a = ap.parse_args(argv)
    raiz = Path(".")
    if a.cmd == "correr":
        correr_modelos(raiz, a.modelos or list(FABRICAS), a.forzar)
    else:
        from ..reportes.fase2 import generar
        print(generar(raiz))


if __name__ == "__main__":
    main()
