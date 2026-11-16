"""O1: fallos de convergencia de la familia GARCH antes y después del arranque en caliente.

Solo estima (no pronostica): recorre los mismos índices de reajuste que la corrida corta
(desde INICIO_DESARROLLO, paso 21, embargo 63) con datos de desarrollo (< 2020-01-01).
«Antes» = arranque en frío (lo que hacía el código hasta F1); «después» = caliente con respaldo
en frío. Escribe reports/o1_convergencia.md.

  PYTHONPATH=src python -m laboratorio.reportes.convergencia
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from ..backtest.corredor import primer_origen
from ..backtest.datos import cargar_desarrollo
from ..backtest.particion import HORIZONTES, PASO_REAJUSTE
from ..evaluacion.origen_movil import bloques, ultimo_origen
from ..modelos.garch import TOL_PERSISTENCIA, GarchT

CONFIGS = [("GARCH", "t"), ("GJR", "t"), ("EGARCH", "t"), ("GJR", "skewt"), ("EGARCH", "skewt")]
LAM_EWMA = 0.94
# Escrita tras ver la corrida del 15-nov-2026 (datos fijos de desarrollo).
LECTURA = '**Lectura.** El arranque en caliente casi no ayuda (38 → 36, 28 → 25): la causa era la tolerancia. Con ella, GARCH y GJR quedan sin fallos por explosividad, pero su persistencia es 1 en todos los reajustes: en la práctica son IGARCH, como EWMA. La diferencia con RiskMetrics está en la reacción: α ≈ 0,18-0,20 frente a 0,06 de EWMA, o sea que el GARCH estimado responde unas tres veces más a cada choque y olvida más rápido (β ≈ 0,82 frente a 0,94). EGARCH no es integrado (β ≈ 0,95-0,98). En GJR, γ sale levemente negativo: las alzas del dólar suben la volatilidad un poco más que las bajas. La t asimétrica estima λ ≈ 0 (casi sin asimetría en las innovaciones), así que no es de esperar que corrija sola la cola superior; la FHS, con residuos empíricos, es la otra apuesta. Lo decide el backtest (O3).'


def reajustes(vista) -> list[int]:
    ult = ultimo_origen(vista.n, max(HORIZONTES))
    return [b.reajuste for b in bloques(primer_origen(vista), ult, PASO_REAJUSTE)]


VARIANTES = {  # nombre: (arranque, tolerancia de persistencia)
    "antes": ("frio", 1e-6), "solo caliente": ("caliente", 1e-6),
    "después": ("caliente", TOL_PERSISTENCIA)}


def recorrer(vista, tipo, dist, arranque, tol, idx):
    m = GarchT(tipo, dist=dist, arranque=arranque, tol_persistencia=tol, sims=1)
    t0 = time.perf_counter()
    for t in idx:
        m.ajustar(vista.hasta(t))
    return m, time.perf_counter() - t0


def _fmt(x, d=4):
    return "—" if x is None or not np.isfinite(x) else f"{x:.{d}f}".replace(".", ",")


def generar(raiz: Path = Path(".")) -> str:
    vista = cargar_desarrollo(raiz)
    idx = reajustes(vista)
    filas, pers = [], []
    for tipo, dist in CONFIGS:
        res = {}
        for var, (arr, tol) in VARIANTES.items():
            m, seg = recorrer(vista, tipo, dist, arr, tol, idx)
            res[var] = m
            print(f"{m.nombre} {var}: fallos={m.fallos}/{m.reajustes} {seg:.0f} s", flush=True)
        mf, mc = res["antes"], res["después"]
        causas = lambda m: ", ".join(f"{k} {v}" for k, v in sorted(m.causas.items())) or "—"
        filas.append(f"| {mc.nombre} | {mf.reajustes} | {mf.fallos} ({causas(mf)}) | "
                     f"{res['solo caliente'].fallos} | {mc.fallos} ({causas(mc)}) | {mc.rescates} |")
        ok = [h for h in mc.historial if not h["fallo"]]
        p = np.array([h["persistencia"] for h in ok])
        ult = ok[-1]
        pers.append(f"| {mc.nombre} | {_fmt(np.median(p))} | {_fmt(p.min())} – {_fmt(p.max())} | "
                    f"{(p > 0.999).mean():.0%} | {_fmt(ult['alpha'], 3)} | {_fmt(ult['beta'], 3)} | "
                    f"{_fmt(ult.get('gamma', np.nan), 3)} | {_fmt(ult['nu'], 1)} | "
                    f"{_fmt(ult.get('lam', np.nan), 3)} |")
    md = [
        "# O1 · Convergencia de la familia GARCH (desarrollo)", "",
        f"Reajustes: {len(idx)} (paso {PASO_REAJUSTE}, {str(vista.fechas[idx[0]])[:10]} a "
        f"{str(vista.fechas[idx[-1]])[:10]}), ventana expansiva desde 1991, r·100, media cero.",
        "«Antes» = arranque en frío (valores iniciales de `arch`) y persistencia aceptada hasta "
        "1 + 1e-6, igual al código de la fase 2. «Solo caliente» = parte de los parámetros del "
        "reajuste anterior (si falla, reintenta en frío), misma tolerancia. «Después» = caliente "
        f"y tolerancia 1 + {TOL_PERSISTENCIA:.0e} (lo que usa el catálogo desde O1). Un fallo "
        "conserva los parámetros previos.", "",
        "| modelo | reajustes | fallos antes (causas) | solo caliente | fallos después (causas) | rescatados por el frío |",
        "|---|---|---|---|---|---|", *filas, "",
        "Causas: `no_convergio` = el optimizador no cerró; `explosivo` = persistencia > 1 + tolerancia; "
        "`nu_fuera` = grados de libertad fuera de [2,1; 200]; `excepcion` = error de `arch`.", "",
        "## Persistencia (reajustes aceptados, después)", "",
        "Persistencia = α + γ/2 + β (GARCH, GJR) o β (EGARCH). Último reajuste a la derecha.", "",
        "| modelo | mediana | rango | % > 0,999 | α | β | γ | ν | λ (skewt) |",
        "|---|---|---|---|---|---|---|---|---|", *pers, "",
        f"Referencia EWMA {_fmt(LAM_EWMA, 2)} (RiskMetrics) = IGARCH sin estimar: ω = 0, α = "
        f"{_fmt(1 - LAM_EWMA, 2)}, β = {_fmt(LAM_EWMA, 2)}, persistencia exactamente 1.", "",
        LECTURA, "",
    ]
    texto = "\n".join(md)
    ruta = raiz / "reports" / "o1_convergencia.md"
    ruta.write_bytes(texto.encode("utf-8"))
    return texto


if __name__ == "__main__":
    generar()
