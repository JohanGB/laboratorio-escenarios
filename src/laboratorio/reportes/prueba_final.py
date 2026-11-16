"""Reporte de la prueba final (reports/prueba_final.md): exactamente lo prerregistrado.

Lo escribe `backtest.final.correr_final` al terminar la corrida. Contenido fijo:
1. Declaraciones (qué datos son, hashes, orígenes).
2. Pruebas confirmatorias: una por horizonte (campeón de desarrollo contra la línea base fijada
   en desarrollo), Diebold-Mariano unilateral con Holm entre las cuatro, α = 0,05.
3. Motor del caso por horizonte, según la regla prerregistrada.
4. Descriptivo, para los 17 modelos: CRPS y cobertura por horizonte, covid 2020 y estrés 2022
   aparte, VaR en dos colas, MCS, Basilea, ES/Z2, PIT, dirección, y 126/252 con n efectivo.
No hay ninguna cifra que dependa de una elección hecha después de ver los resultados.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..backtest.corredor import resumen
from ..backtest.final import (ALFA_CONFIRMATORIA, CONFIRMATORIAS, MOTOR_CASO, MOTOR_SENSIBILIDAD,
                              SALIDA_FINAL, SALIDA_FINAL_LARGO)
from ..backtest.particion import HORIZONTES, HORIZONTES_LARGOS, INICIO_PRUEBA_FINAL
from ..evaluacion.cobertura import cobertura_n_efectivo
from ..evaluacion.mcs import REPS_MCS
from ..evaluacion.pruebas import diebold_mariano, holm
from .fase2 import _f, _p, cargar, crps_por_origen, pruebas_var, tabla
from .pruebas_f2 import secciones

EPISODIOS = ("covid_2020", "estres_2022")
NOMINAL_MOTOR = 0.95


def confirmar(res: dict[str, pd.DataFrame], confirmatorias=CONFIRMATORIAS,
              alfa: float = ALFA_CONFIRMATORIA) -> pd.DataFrame:
    """Una fila por hipótesis: CRPS del campeón y de la base, DM unilateral, Holm y veredicto.

    Éxito en h ⇔ CRPS del campeón menor que el de la base Y p de Holm < alfa.
    """
    filas = []
    for h, campeon, base in confirmatorias:
        for m in (campeon, base):
            if m not in res:
                raise RuntimeError(f"falta el resultado de {m}: la lista de modelos es cerrada")
        a, b = crps_por_origen(res[campeon], h), crps_por_origen(res[base], h)
        if not a.index.equals(b.index):
            raise RuntimeError(f"orígenes distintos entre {campeon} y {base} en h={h}")
        dm = diebold_mariano(a.to_numpy(), b.to_numpy(), h=h)
        filas.append({"h": h, "campeon": campeon, "base": base, "crps": float(a.mean()),
                      "crps_base": float(b.mean()), "relativo": float(a.mean() / b.mean()),
                      "dm_t": dm.estadistico, "p": dm.p_valor, "n": len(a)})
    df = pd.DataFrame(filas)
    df["p_holm"] = holm(df["p"].to_numpy())
    df["exito"] = (df["relativo"] < 1) & (df["p_holm"] < alfa)
    return df


def cobertura_motor(res: dict, res_largo: dict, motor: str = MOTOR_CASO) -> pd.DataFrame:
    """Cobertura del intervalo del 95 % del motor del caso en cada horizonte, con n efectivo."""
    filas = []
    for fuente, hs in ((res, HORIZONTES), (res_largo, HORIZONTES_LARGOS)):
        if motor not in fuente:
            continue
        d = fuente[motor]
        for h in hs:
            s = d[d["h"] == h]
            if len(s) == 0:
                continue
            c = cobertura_n_efectivo(s["y"].to_numpy(), s["q_0.025"].to_numpy(),
                                     s["q_0.975"].to_numpy(), NOMINAL_MOTOR, h)
            filas.append({"h": h, **c})
    return pd.DataFrame(filas)


def generar(raiz: str | Path = ".", directorio: str | Path | None = None,
            directorio_largo: str | Path | None = None, salida: str | Path | None = None,
            confirmatorias=CONFIRMATORIAS, reps_mcs: int = REPS_MCS) -> Path:
    raiz = Path(raiz)
    directorio = Path(directorio) if directorio else raiz / SALIDA_FINAL
    directorio_largo = Path(directorio_largo) if directorio_largo else raiz / SALIDA_FINAL_LARGO
    salida = Path(salida) if salida else raiz / "reports" / "prueba_final.md"
    res, meta = cargar(directorio)
    if not res:
        raise FileNotFoundError(f"sin resultados en {directorio}")
    res_largo = cargar(directorio_largo)[0] if directorio_largo.exists() else {}
    ej = next(iter(res.values()))
    if str(ej["fecha"].min())[:10] < INICIO_PRUEBA_FINAL:
        raise RuntimeError("los resultados contienen orígenes de desarrollo: no es la prueba final")
    md = next(iter(meta.values()), {})
    conf = confirmar(res, confirmatorias)
    base_h = {int(r.h): r.base for r in conf.itertuples()}

    L = ["# Prueba final (una sola corrida, prerregistrada)", "",
         "Distribuciones de pronóstico del rendimiento logarítmico de la TRM. Los rangos describen "
         "incertidumbre estadística; no son recomendaciones financieras.", "",
         "## Declaraciones", "",
         f"- Orígenes: {str(ej['fecha'].min())[:10]} a {str(ej['fecha'].max())[:10]} "
         f"({ej['origen'].nunique()} por horizonte en la corrida corta). Cada modelo se estimó solo "
         "con datos anteriores a cada origen.",
         "- Estos datos **no se usaron para elegir ni ajustar ningún modelo**, pero **no son datos "
         "nunca vistos**: el análisis exploratorio (reports/fase0.md) y el caso «compra de dólares» "
         "los mostraron antes del prerregistro.",
         "- Este reporte contiene exactamente lo fijado en docs/prerregistro.md. Cualquier cálculo "
         "posterior es «análisis posterior (no confirmatorio)».",
         f"- Hash del código: {md.get('hash_codigo', '—')}. Hash de trm.csv: "
         f"{md.get('hash_trm_csv', '—')}.", "",
         "## Pruebas confirmatorias", "",
         "Una hipótesis por horizonte, fijada antes de abrir los datos: el campeón de desarrollo "
         "tiene menor CRPS que la línea base de referencia de desarrollo. Diebold-Mariano "
         "unilateral (HAC, corrección HLN); las cuatro forman una familia y se ajustan por Holm. "
         "**Éxito** = CRPS menor y p de Holm < " + f"{ALFA_CONFIRMATORIA:.2f}".replace(".", ",") + ".", "",
         tabla(pd.DataFrame([[r.h, r.campeon, r.base, _f(100 * r.crps, 4), _f(100 * r.crps_base, 4),
                              _f(r.relativo, 3), _f(r.dm_t, 2), _p(r.p), _p(r.p_holm), r.n,
                              "**ÉXITO**" if r.exito else "**no confirmado**"]
                             for r in conf.itertuples()],
                            columns=["h", "campeón", "línea base", "CRPS", "CRPS base", "CRPS/base",
                                     "t (HLN)", "p", "p (Holm)", "n", "resultado"])), "",
         "## Motor del caso por horizonte", "",
         f"Regla prerregistrada: el caso usa `{MOTOR_CASO}` en todos sus horizontes (necesita "
         f"trayectorias) y `{MOTOR_SENSIBILIDAD}` como sensibilidad. Donde la prueba confirmatoria "
         "tuvo éxito, el campeón se cita como pronóstico de referencia de ese horizonte; donde "
         "no, no se cita ningún modelo. El motor no se cambia a la vista de estos resultados: si "
         "su cobertura queda fuera del intervalo, se publica como límite junto a cada cifra del caso.", ""]
    if MOTOR_CASO not in res:
        raise RuntimeError(f"falta el resultado del motor del caso ({MOTOR_CASO})")
    cm = cobertura_motor(res, res_largo)
    exito_h = {int(r.h): bool(r.exito) for r in conf.itertuples()}
    filas = []
    for r in cm.itertuples():
        ref = (f"`{dict((int(c.h), c.campeon) for c in conf.itertuples())[r.h]}`" if exito_h.get(r.h)
               else "ninguno" if r.h in exito_h else "ninguno (descriptivo)")
        filas.append([r.h, f"`{MOTOR_CASO}`", ref, _f(r.cobertura, 3), r.n, r.n_efectivo,
                      f"{_f(r.ic_inf, 2)} – {_f(r.ic_sup, 2)}",
                      "sí" if r.compatible else "**no: decirlo en el caso**"])
    L += [tabla(pd.DataFrame(filas, columns=["h", "motor", "modelo de referencia", "cobertura 95 % del motor",
                                             "n", "n efectivo", "IC 95 % (n ef.)", "compatible con 0,95"])), "",
          "A 126 y 252 días la fila es **descriptiva** (R5): con tan pocas ventanas independientes "
          "no hay aprobado ni rechazado.", ""]

    res_sum = {m: resumen(d, episodios=True) for m, d in res.items()}
    for h in HORIZONTES:
        base = base_h.get(h)
        cb = float(crps_por_origen(res[base], h).mean()) if base in res else float("nan")
        L += [f"## Horizonte h = {h} (descriptivo)", ""]
        filas = []
        for m in res:
            r = res_sum[m].query(f"h=={h} and grupo=='todo'").iloc[0]
            filas.append([m, _f(100 * r.crps, 4), _f(r.crps / cb, 3), _f(r.cob90, 3), _f(r.cob95, 3),
                          _f(r.cob98, 3)])
        filas.sort(key=lambda f: float(f[1]))
        L += [tabla(pd.DataFrame(filas, columns=["modelo", "CRPS", f"CRPS/{base}", "cob90", "cob95",
                                                 "cob98"])), "", "Por episodio (covid 2020 y estrés 2022 aparte):", ""]
        grupos = ["normal", *EPISODIOS]
        filas = []
        for m in res:
            s = res_sum[m].query(f"h=={h}").set_index("grupo")
            fila = [m]
            for g in grupos:
                fila += [_f(100 * s.loc[g, "crps"], 4), _f(s.loc[g, "cob95"], 3)] if g in s.index else ["—", "—"]
            filas.append(fila)
        n_g = res_sum[next(iter(res))].query(f"h=={h}").set_index("grupo")["n"]
        L += [tabla(pd.DataFrame(filas, columns=["modelo"] + [f"{x} {g}" for g in grupos
                                                              for x in ("CRPS", "cob95")])), "",
              "n por grupo: " + ", ".join(f"{g} = {int(n_g[g]) if g in n_g.index else 0}" for g in grupos), ""]

    L += ["## Pruebas de VaR al 95 % y 99 % en ambas colas, h = 1 (Kupiec y Christoffersen)", "",
          "Cola inf = caída del dólar; sup = alza. p < 0,05 rechaza la calibración de esa cola.", ""]
    filas = []
    for m in res:
        for cola, (tasa, puc, pind, pcc) in pruebas_var(res[m]).items():
            filas.append([m, cola, _f(tasa, 4), _p(puc), _p(pind), _p(pcc)])
    L += [tabla(pd.DataFrame(filas, columns=["modelo", "cola", "tasa", "p_uc", "p_ind", "p_cc"])), ""]
    L += secciones(res, meta, directorio / "cola", res_largo, salida.parent / "figs",
                   reps_mcs=reps_mcs, nombre_fig="prueba_final_pit.png")
    L += ["## Reproducir", "", "```", "PYTHONPATH=src python -m laboratorio.backtest final --verificar",
          "```", "", "La corrida no se repite: `runs/prueba_final/HECHO.json` lo impide.", ""]
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_bytes("\n".join(L).encode("utf-8"))
    return salida
