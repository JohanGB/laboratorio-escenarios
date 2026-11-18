"""Reporte de M2: la TRM del motor conjunto frente al motor evaluado en la prueba final.

Uso (desde la raíz del proyecto):
    PYTHONPATH=src python -m laboratorio.reportes.m2_conjunto [--trayectorias 10000]
Entrada: data/processed/divisas.csv y data/processed/trm.csv. Salida: reports/m2_conjunto.md.

Solo muestra cifras de la TRM. El motor conjunto se corre con las siete divisas (eso fija la
muestra común y las fechas comunes), pero ninguna cifra de las divisas nuevas sale en el reporte:
desde 2020 no se muestran (regla de la revisión de M1) y antes de M3 no se evalúan. Cada cifra
lleva `#hash` (motor/cifras.py) y su respaldo.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from laboratorio.backtest.final import MOTOR_CASO
from laboratorio.modelos.bootstrap import residuos_estandarizados
from laboratorio.motor import conjunto as C
from laboratorio.motor import montecarlo as MC
from laboratorio.motor.cifras import Cifra, Reporte, formatear
from laboratorio.motor.ficha import hash_archivo

SIETE = ("USD", "EUR", "MXN", "JPY", "CNY", "CHF", "BRL")
HORIZONTES = (1, 5, 21, 63, 126, 252)
NIVELES = (0.025, 0.5, 0.975)
AVISO = ("**No es asesoría financiera**; los rangos describen incertidumbre estadística, no "
         "promesas.")
SIN_RESPALDO = "sin evaluación fuera de muestra hasta M3"
RESPALDO_EVALUADO = ("límites: cobertura del 95 % evaluada en la prueba final "
                     "(`data/respaldo/prueba_final.json`); mediana: sin respaldo fuera de muestra")


def generar(raiz: str | Path = ".", trayectorias: int = C.TRAYECTORIAS,
            semilla: int = C.SEMILLA) -> Path:
    raiz = Path(raiz)
    proc = raiz / "data" / "processed"
    df = pd.read_csv(proc / "divisas.csv", parse_dates=["fecha"])
    trm_df = pd.read_csv(proc / "trm.csv", parse_dates=["fecha"], index_col="fecha")
    trm_df["estres"] = trm_df["estres"].fillna("")
    ins = [Cifra.de_dato(len(df), "filas", "processed/divisas.csv", "todas las filas",
                         hash_archivo(proc / "divisas.csv")),
           Cifra.de_dato(len(trm_df), "filas", "processed/trm.csv", "todas las filas",
                         hash_archivo(proc / "trm.csv"))]
    rep = Reporte()

    def c(valor, unidad, formula):
        return Cifra.derivada(valor, unidad, formula, ins)

    vistas = C.vistas_divisas(df)
    sc = C.simular_conjunto(vistas, SIETE, MOTOR_CASO, sims=trayectorias, semilla=semilla,
                            largo=max(HORIZONTES))
    origen = pd.Timestamp(sc.muestra_hasta)
    vista = MC.vista_trm(trm_df[trm_df.index <= origen])
    se = MC.simular(vista, MOTOR_CASO, sims=trayectorias, semilla=semilla, largo=max(HORIZONTES))
    trm0 = float(trm_df.loc[:origen, "trm"].iloc[-1])
    assert abs(trm0 - sc.nivel0["USD"]) < 1e-9 * trm0, "el origen de los dos motores no coincide"

    k_usd = sc.divisas.index("USD")
    filas = []
    for h in HORIZONTES:
        qe = trm0 * np.exp(np.quantile(se.acum[h - 1], NIVELES))
        qc = trm0 * np.exp(np.quantile(sc.acum[h - 1, :, k_usd], NIVELES))
        ce = [c(float(v), "COP", f"TRM, percentil {100 * p:g} a {h} pasos, motor evaluado ({MOTOR_CASO}, "
                                 f"toda la historia), {trayectorias} trayectorias, semilla {semilla}")
              for v, p in zip(qe, NIVELES)]
        cc = [c(float(v), "COP", f"TRM, percentil {100 * p:g} a {h} pasos, {C.ETIQUETA} ({MOTOR_CASO}, "
                                 f"muestra común de {', '.join(SIETE)}), {trayectorias} trayectorias, "
                                 f"semilla {semilla}") for v, p in zip(qc, NIVELES)]
        dif = c(100 * (qc[1] / qe[1] - 1), "%", f"diferencia de la mediana a {h} pasos, conjunto vs evaluado")
        ancho = c(float((qc[2] - qc[0]) / (qe[2] - qe[0])), "veces",
                  f"ancho de la banda del 95 % a {h} pasos, conjunto / evaluado")
        filas.append(f"| {h} | {rep.r(ce[1], 0, False)} | {rep.r(ce[0], 0, False)} – {rep.r(ce[2], 0, False)} "
                     f"| {rep.r(cc[1], 0, False)} | {rep.r(cc[0], 0, False)} – {rep.r(cc[2], 0, False)} "
                     f"| {rep.r(dif, 1)} | {rep.r(ancho, 2)} |")

    # Deriva con que entra cada muestra: media del choque estandarizado × σ de largo plazo.
    z_ev = residuos_estandarizados(vista.r)
    z_ev = z_ev[np.isfinite(z_ev)]
    niv = C.niveles_factores(vistas, SIETE, sc.muestra_desde)
    r_c = np.r_[np.nan, np.diff(np.log(niv["TRM"].to_numpy()))]
    z_c = residuos_estandarizados(r_c)
    z_c = z_c[np.isfinite(z_c)]
    deriva_ev = c(100 * float(z_ev.mean()) * se.sigma_largo, "% diario",
                  "media de z de toda la historia × σ de largo plazo, motor evaluado")
    deriva_c = c(100 * float(z_c.mean()) * sc.sigma_largo["TRM"], "% diario",
                 f"media de z de la TRM en la muestra común × σ de largo plazo, {C.ETIQUETA}")
    n_ev = c(int(se.n_muestra), "obs.", "rendimientos de la TRM que remuestrea el motor evaluado")
    n_c = c(int(sc.n), "obs.", f"fechas comunes que remuestrea el {C.ETIQUETA}")
    b_ev = c(float(se.bloque), "días", "longitud media de bloque, motor evaluado (Politis-White, toda la historia)")
    b_c = c(float(sc.bloque), "días", "longitud media de bloque común: Politis-White de la TRM en la muestra común")
    s_ev = c(100 * float(se.sigma_origen), "% diario", "σ EWMA prevista en el origen, motor evaluado")
    s_c = c(100 * sc.sigma_origen["TRM"], "% diario", "σ EWMA de la TRM prevista en el origen, muestra común")
    trm0_c = c(trm0, "COP", f"TRM en el origen ({origen.date()})")

    md = f"""# Motor conjunto (M2): la TRM frente al motor evaluado

{AVISO}

**Etiqueta de todas las cifras del motor conjunto: {C.ETIQUETA}.** No es el motor evaluado en la
prueba final: no incluye la banda cambiaria colombiana y nunca se evaluó fuera de muestra.

## 1. Qué se compara

- **Motor evaluado** (`{MOTOR_CASO}`, `montecarlo.simular`): remuestrea toda la historia de la TRM,
  banda incluida (desde 1991). Es el que se evaluó en la prueba final.
- **Motor conjunto** (`{MOTOR_CASO}`, `conjunto.simular_conjunto`): simula la TRM y cada «USD por
  X» con una sola secuencia de índices de bloque, desde la muestra común de las siete divisas
  ({', '.join(SIETE)}): del {sc.muestra_desde} al {sc.muestra_hasta}. Los cruces X/COP salen de
  multiplicar, así que la triangulación es exacta en cada trayectoria.

Mismo origen ({origen.date()}, TRM {rep.r(trm0_c, 2)}), mismas trayectorias
({formatear(trayectorias, 0)}) y misma semilla ({semilla}). Solo se muestran cifras de la TRM.

| | Motor evaluado | Motor conjunto |
|---|---:|---:|
| Rendimientos que remuestrea | {rep.r(n_ev, 0)} | {rep.r(n_c, 0)} |
| Longitud media de bloque | {rep.r(b_ev, 1)} | {rep.r(b_c, 1)} |
| σ diaria prevista en el origen | {rep.r(s_ev, 3)} | {rep.r(s_c, 3)} |
| Deriva con que entra la muestra | {rep.r(deriva_ev, 4)} | {rep.r(deriva_c, 4)} |

## 2. TRM proyectada (COP por USD)

Respaldo: motor evaluado, {RESPALDO_EVALUADO}. Motor conjunto, **{SIN_RESPALDO}**.

| h (días con TRM) | Evaluado: mediana | Evaluado: banda del 95 % | Conjunto: mediana | Conjunto: banda del 95 % | Mediana, conjunto vs evaluado | Ancho de banda, conjunto / evaluado |
|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(filas)}

## 3. Por qué difieren

La diferencia sale de la muestra, no del método: los dos son el mismo bootstrap estacionario
filtrado. El conjunto usa solo las fechas comunes con las seis series H.10 (un rendimiento puede
abarcar un festivo de EE. UU.) y su longitud de bloque se estima en esa muestra. El motor evaluado remuestrea también 1991-2005, con la banda cambiaria; el análisis
posterior de F5b (`reports/compra_dolares.md`) mostró que la deriva de la banda entra al motor
amplificada unas 2,1 veces. La fila «deriva con que entra la muestra» es esa cantidad para cada
motor (media del choque estandarizado por σ de largo plazo). Las bandas también cambian con la
longitud de bloque y con la σ de largo plazo de cada muestra.

## 4. Lo que este reporte no muestra

- Ninguna cifra de EUR, MXN, JPY, CNY, CHF ni BRL. Desde 2020 sus valores no se muestran hasta
  el prerregistro de M3, y el motor conjunto no tiene evaluación fuera de muestra.
- La sensibilidad con la mediana de las longitudes de bloque (`bloque="mediana"`): depende de las
  series de las divisas nuevas hasta el origen y se reportará en M3.

## Reproducir

```
PYTHONPATH=src python -m laboratorio.reportes.m2_conjunto --trayectorias {trayectorias} --semilla {semilla}
```

## Apéndice: fuente y hash de cada cifra

{rep.apendice()}
"""
    salida = raiz / "reports" / "m2_conjunto.md"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(md, encoding="utf-8")
    return salida


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raiz", default=".")
    p.add_argument("--trayectorias", type=int, default=C.TRAYECTORIAS)
    p.add_argument("--semilla", type=int, default=C.SEMILLA)
    a = p.parse_args(argv)
    print(generar(a.raiz, a.trayectorias, a.semilla))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
