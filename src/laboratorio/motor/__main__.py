"""Uso:
    python -m laboratorio.motor compra_dolares [--raiz .] [--autor analista]
                                               [--trayectorias 10000] [--semilla 20240501]
    python -m laboratorio.motor reproducir runs/<corrida>/ficha.json [--raiz .]
    python -m laboratorio.motor respaldo [--raiz .]
(con PYTHONPATH=src, o tras `pip install -e .`)

`respaldo` resume la prueba final ya terminada en data/respaldo/prueba_final.json (una vez).
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
    a.add_argument("--trayectorias", type=int, default=None,
                   help="trayectorias del Monte Carlo (por defecto 10000)")
    a.add_argument("--semilla", type=int, default=None, help="semilla del Monte Carlo")
    r = sub.add_parser("reproducir", help="reejecuta una ficha y compara el hash del resultado")
    r.add_argument("ficha")
    r.add_argument("--raiz", default=".")
    s = sub.add_parser("respaldo", help="resume la prueba final para las líneas de respaldo del caso")
    s.add_argument("--raiz", default=".")
    args = p.parse_args(argv)

    if args.cmd == "respaldo":
        from . import respaldo
        ruta = respaldo.generar(args.raiz)
        r_ = respaldo.cargar(ruta)
        print(f"respaldo     {ruta}")
        print(f"sha256       {r_.hash}")
        for motor, por_h in r_.datos["cobertura"].items():
            print(motor + ": " + "  ".join(
                f"h={h} {v['cobertura']:.3f} (n ef. {v['n_efectivo']})"
                for h, v in sorted(por_h.items(), key=lambda kv: int(kv[0]))))
        for h, v in sorted(r_.datos["confirmatorias"].items(), key=lambda kv: int(kv[0])):
            print(f"confirmatoria h={h}: {v['campeon']} CRPS/base {v['relativo']:.3f} "
                  f"{'confirmada' if v['exito'] else 'no confirmada'}")
        for m, colas in r_.datos["var_h1"].items():
            print(m + " VaR h=1: " + "  ".join(
                f"{c} {v['tasa']:.4f} (p {v['p_kupiec']:.3f})" for c, v in colas.items()))
        return 0

    from . import montecarlo
    from .casos import compra_dolares as caso
    if args.cmd == "compra_dolares":
        ficha, ruta_ficha, ruta_rep = caso.ejecutar(
            args.raiz, args.autor, args.actualizar_derivas,
            montecarlo.TRAYECTORIAS if args.trayectorias is None else args.trayectorias,
            montecarlo.SEMILLA if args.semilla is None else args.semilla)
        print(f"corrida      {ficha.run_id}")
        print(f"ficha        {ruta_ficha}")
        print(f"reporte      {ruta_rep}")
        print(f"trayectorias {ficha.parametros['trayectorias']}  semilla {ficha.semilla}")
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
