"""Uso: python -m laboratorio.datos [--raw data/raw] [--salida data]"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .lectores import fecha_descarga, leer_archivo
from .manifiesto import construir_manifiesto, escribir_manifiesto, listar_raw
from .validacion import validar_archivo


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", default="data/raw", type=Path)
    p.add_argument("--salida", default="data", type=Path)
    a = p.parse_args(argv)

    lecturas = {r.name: leer_archivo(r) for r in listar_raw(a.raw)}
    escribir_manifiesto(construir_manifiesto(a.raw, lecturas), a.salida / "manifest.json")

    informe = {r.name: validar_archivo(lecturas[r.name][0], fecha_descarga(r))
               for r in listar_raw(a.raw)}
    (a.salida / "validacion.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")

    for archivo, series in informe.items():
        print(f"\n{archivo}")
        for nombre, r in series.items():
            if r["duplicadas"] or r["huecos"] or r["saltos"] or r["fechas_futuras"]:
                print(f"  {nombre[:58]:58} dup={r['duplicadas']} huecos={r['huecos']} "
                      f"saltos={r['saltos']} futuras={r['fechas_futuras']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
