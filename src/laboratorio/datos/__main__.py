"""Uso: python -m laboratorio.datos [--raw data/raw] [--salida data]"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .divisas import CORTE_VISTO, desde_lecturas, es_divisa_nueva, validar_divisas
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

    # Divisas nuevas: desde CORTE_VISTO, solo conteos (ningún valor; ver divisas.CORTE_VISTO).
    informe = {r.name: validar_archivo(lecturas[r.name][0], fecha_descarga(r),
                                       CORTE_VISTO if es_divisa_nueva(r.name) else None)
               for r in listar_raw(a.raw)}
    informe["processed/divisas.csv"] = validar_divisas(desde_lecturas(lecturas))
    (a.salida / "validacion.json").write_text(
        json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")

    for archivo, series in informe.items():
        print(f"\n{archivo}")
        if archivo.startswith("processed/"):
            print(f"  filas={series['filas']} duplicados={series['duplicados']} "
                  f"saltos>8%={len(series['saltos_8pct'])} antes de "
                  f"{series['saltos_8pct_desde_corte']['corte']} y "
                  f"{sum(series['saltos_8pct_desde_corte']['conteo_por_divisa'].values())} "
                  f"desde entonces (solo conteo; revisión manual, no se borran)")
            continue
        for nombre, r in series.items():
            if r["duplicadas"] or r["huecos"] or r["saltos"] or r["fechas_futuras"]:
                print(f"  {nombre[:58]:58} dup={r['duplicadas']} huecos={r['huecos']} "
                      f"saltos={r['saltos']} futuras={r['fechas_futuras']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
