"""Uso:
    python -m laboratorio.motor compra_dolares [--raiz .] [--autor analista]
    python -m laboratorio.motor reproducir runs/<corrida>/ficha.json [--raiz .]
(con PYTHONPATH=src, o tras `pip install -e .`)
"""
from __future__ import annotations

import argparse
import sys

from .ficha import EntradaCambio


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="laboratorio.motor", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("compra_dolares", help="ejecuta el caso y escribe el reporte")
    a.add_argument("--raiz", default=".")
    a.add_argument("--autor", default="analista")
    a.add_argument("--actualizar-derivas", action="store_true",
                   help="reestima las derivas con los datos actuales (versión nueva del supuesto)")
    r = sub.add_parser("reproducir", help="reejecuta una ficha y compara el hash del resultado")
    r.add_argument("ficha")
    r.add_argument("--raiz", default=".")
    args = p.parse_args(argv)

    from .casos import compra_dolares as caso
    if args.cmd == "compra_dolares":
        ficha, ruta_ficha, ruta_rep = caso.ejecutar(args.raiz, args.autor, args.actualizar_derivas)
        print(f"corrida      {ficha.run_id}")
        print(f"ficha        {ruta_ficha}")
        print(f"reporte      {ruta_rep}")
        print(f"hash datos      {ficha.hash_datos}")
        print(f"hash supuestos  {ficha.hash_supuestos}")
        print(f"hash código     {ficha.hash_codigo}")
        print(f"hash resultado  {ficha.hash_resultado}")
        return 0
    try:
        ok, nuevo = caso.reproducir_corrida(args.ficha, args.raiz)
    except EntradaCambio as e:
        print(f"NO REPRODUCIBLE: {e}", file=sys.stderr)
        return 2
    print(("COINCIDE" if ok else "DIFIERE") + f"  hash resultado nuevo {nuevo}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
