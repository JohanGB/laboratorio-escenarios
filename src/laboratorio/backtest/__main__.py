"""Backtest de desarrollo (`correr`, `reporte`: nunca tocan la prueba final) y prueba final.

  PYTHONPATH=src python -m laboratorio.backtest correr [modelo ...] [--forzar] [--largo]
  PYTHONPATH=src python -m laboratorio.backtest reporte
  PYTHONPATH=src python -m laboratorio.backtest final [--hashes | --verificar]   (ver backtest/final.py)
Resultados por modelo en runs/backtest_desarrollo/<modelo>.csv.gz + <modelo>.json (caché).
Con --largo: horizontes 126 y 252 (FABRICAS_LARGOS) en runs/backtest_largo/, corrida aparte
con su propio embargo (no altera los orígenes de la corrida corta).
Corrida corta: además runs/backtest_desarrollo/cola/<modelo>.csv.gz con NIVELES_COLA y el ES
(F2), para los modelos que pueden darlo; si falta ese archivo el modelo se vuelve a correr.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .catalogo import FABRICAS, FABRICAS_LARGOS
from .datos import cargar_desarrollo
from .ejecucion import correr_uno

SALIDA = Path("runs") / "backtest_desarrollo"
SALIDA_LARGO = Path("runs") / "backtest_largo"


def correr_modelos(raiz: Path, nombres: list[str], forzar: bool = False, largo: bool = False) -> None:
    vista = cargar_desarrollo(raiz)
    catalogo = FABRICAS_LARGOS if largo else FABRICAS
    out = raiz / (SALIDA_LARGO if largo else SALIDA)
    for nombre in nombres:
        correr_uno(nombre, catalogo, vista, out, raiz, largo=largo, forzar=forzar)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="laboratorio.backtest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("correr"); c.add_argument("modelos", nargs="*"); c.add_argument("--forzar", action="store_true")
    c.add_argument("--largo", action="store_true")
    sub.add_parser("reporte")
    f = sub.add_parser("final"); f.add_argument("--verificar", action="store_true")
    f.add_argument("--hashes", action="store_true")
    a = ap.parse_args(argv)
    raiz = Path(".")
    if a.cmd == "correr":
        cat = FABRICAS_LARGOS if a.largo else FABRICAS
        correr_modelos(raiz, a.modelos or list(cat), a.forzar, a.largo)
    elif a.cmd == "final":
        from .final import main_final
        main_final(raiz, solo_verificar=a.verificar, solo_hashes=a.hashes)
    else:
        from ..reportes.fase2 import generar
        print(generar(raiz))


if __name__ == "__main__":
    main()
