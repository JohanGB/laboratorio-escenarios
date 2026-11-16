"""Caso 1 (sección 8): comprar todos los dólares hoy vs. compras escalonadas.

Entrega: costo por escenario determinista, reproducción de ventanas históricas con nombre
(2015 y fin de 2022) y la distribución empírica sobre TODAS las ventanas reales del régimen
de flotación (costo esperado, percentil 95, probabilidad de pasarse del presupuesto).
Cada cifra del reporte lleva su fuente y su hash (ver `cifras.Reporte`).
Comprar hoy tiene costo cierto; el riesgo está del lado del plan escalonado.

F5 agrega el Monte Carlo por bloques (`montecarlo.py`): el motor prerregistrado
(`bootstrap_est_filtrado`), la sensibilidad (`bootstrap_est`) y el abanico de la TRM. Cada cifra
principal dice qué evaluación de la prueba final la respalda (`respaldo.py`) o «sin respaldo
fuera de muestra». Semilla y número de trayectorias van en la ficha, no en los supuestos.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ...backtest.final import HORIZONTES_ADVERTENCIA, MOTOR_CASO, MOTOR_SENSIBILIDAD
from ...backtest.particion import HORIZONTES, HORIZONTES_LARGOS
from .. import montecarlo as mc_
from ..cifras import Cifra, Reporte, formatear
from ..datos import DatosTRM
from ..deterministas import ESCENARIOS, correr, id_deriva
from ..ficha import (EntradaCambio, Ficha, construir_ficha, guardar, hash_codigo,
                     reproducir as reproducir_ficha)
from ..historica import (DistribucionHistorica, distribucion, desplazar_meses, pasos_por_compra,
                         ratios_ventana, ratios_todas, reproducir)
from ..plan import PlanCompra
from ..respaldo import ARCHIVO as ARCHIVO_RESPALDO, RUTA as RUTA_RESPALDO, Respaldo
from ..respaldo import cargar as cargar_respaldo
from ..supuestos import ConjuntoSupuestos, Registro

CASO = "compra_dolares"
MODO = "determinista+historica+montecarlo"
HORIZONTES_EVALUADOS = tuple(HORIZONTES) + tuple(HORIZONTES_LARGOS)
SIN_RESPALDO = "sin respaldo fuera de muestra"
COLAS_REFERENCIA = (("sup5", "sup 5 %"), ("sup1", "sup 1 %"))
FIGURA = "compra_dolares_abanico.png"
ILUSTRATIVO = ("Valor ilustrativo definido por el autor del laboratorio; reemplazar por la "
               "meta real antes de usar los resultados.")
FIJOS = [  # id, valor, unidad
    ("caso.meta_usd", 10000, "USD"),
    ("caso.n_compras", 12, "compras"),
    ("caso.intervalo_meses", 1, "meses"),
    ("caso.presupuesto_margen_pct", 5, "%"),
    ("historica.desde", "1999-09-25", "fecha"),
    ("historica.ventana.2015", "2015-01-02", "fecha"),
    ("historica.ventana.fin_2022", "2022-10-03", "fecha"),
]
JUSTIFICACION = {
    "historica.desde": "Inicio de la flotación cambiaria (ver data/processed/trm.csv, columna regimen).",
    "historica.ventana.2015": "Primer día hábil de 2015: la TRM se depreció con la caída del petróleo.",
    "historica.ventana.fin_2022": "Primer día hábil de oct-2022: el tramo con el pico de la TRM de fin de 2022.",
}
PERCENTILES = {"optimista": 5, "base": 50, "estres": 95}
VENTANAS = ("2015", "fin_2022")
ETIQUETA = {"optimista": "Optimista", "base": "Base", "estres": "Estrés",
            "2015": "Año 2015", "fin_2022": "Fin de 2022"}


# --- supuestos ------------------------------------------------------------------------
def estimar_derivas(datos: DatosTRM, desde: str) -> dict[str, float]:
    """Percentiles 5/50/95 de ln(TRM(t+12m)/TRM(t)) en todas las ventanas desde `desde`."""
    _, r = ratios_todas(datos.trm, PlanCompra((0, 12), (1.0, 1.0)), desde)
    g = np.log(r[:, 1])
    return {n: round(float(np.percentile(g, q)), 4) for n, q in PERCENTILES.items()}


def _existe(reg: Registro, id: str) -> bool:
    try:
        reg.vigente(id)
        return True
    except KeyError:
        return False


def sembrar(reg: Registro, datos: DatosTRM, autor: str,
            actualizar_derivas: bool = False) -> list[tuple[str, bool]]:
    """Registra los supuestos del caso que FALTEN (nunca pisa ediciones del usuario).

    Las derivas (calculadas de los datos) solo se reestiman, como versión nueva, si
    `actualizar_derivas` es True. Devuelve [(id, se_agregó)].
    """
    hecho = []
    desde = next(v for i, v, _ in FIJOS if i == "historica.desde")
    for id, valor, unidad in FIJOS:
        if _existe(reg, id):
            hecho.append((id, False))
            continue
        reg.agregar(id, valor, unidad, "ilustrativo (definido por el autor)",
                    JUSTIFICACION.get(id, ILUSTRATIVO), autor)
        hecho.append((id, True))
    for nombre, g in estimar_derivas(datos, desde).items():
        id = id_deriva(nombre)
        if _existe(reg, id) and not (actualizar_derivas and reg.vigente(id).valor != g):
            hecho.append((id, False))
            continue
        reg.agregar(id, g, "1/año (log)",
                    f"cálculo: percentil {PERCENTILES[nombre]} de ln(TRM(t+12m)/TRM(t)), ventanas "
                    f"desde {desde}, processed/trm.csv sha256 {datos.hash_trm[:16]}",
                    "Deriva anual logarítmica observada en el régimen de flotación; el escenario "
                    f"{nombre} usa el percentil {PERCENTILES[nombre]} de las ventanas de 12 meses.",
                    autor)
        hecho.append((id, True))
    return hecho


def derivas_desactualizadas(reg: Registro, datos: DatosTRM) -> list[str]:
    """Derivas vigentes que difieren de lo que dan hoy los datos (se avisa; no se cambian solas)."""
    desde = reg.vigente("historica.desde").valor
    return [id_deriva(n) for n, g in estimar_derivas(datos, desde).items()
            if reg.vigente(id_deriva(n)).valor != g]


def ids_del_caso() -> list[str]:
    return [i for i, _, _ in FIJOS] + [id_deriva(n) for n in ESCENARIOS]


# --- cálculo ---------------------------------------------------------------------------
def _montecarlo(K: dict[str, Cifra], datos: DatosTRM, plan: PlanCompra, serie: Cifra, desde: Cifra,
                ins: list[Cifra], sims: int, semilla: int, respaldo: Respaldo | None) -> dict:
    """Agrega a K las cifras del Monte Carlo (`mc.*`, `sens.*`, `abanico.*`, `resp.*`, `ref.*`).

    Devuelve el abanico completo (TRM por paso y nivel) para la figura y el hash del resultado.
    """
    if sims < 2:
        raise ValueError("se requieren al menos 2 trayectorias")
    D = Cifra.derivada
    trm0, costo_hoy, presupuesto = K["trm0"].valor, K["costo_hoy"].valor, K["presupuesto"].valor
    pasos = pasos_por_compra(datos.trm, plan, desde.valor)
    largo = max(max(pasos), mc_.LARGO_MIN)
    vista = mc_.vista_trm(datos.df)
    K["serie"], K["desde"] = serie, desde
    K["serie_inicio"] = D(str(datos.trm.index[0].date()), "fecha", "primera fecha de la serie", [serie])
    K["mc.pasos_ultima"] = D(pasos[-1], "días con TRM",
                             "mediana, en las ventanas históricas, de las observaciones entre el "
                             "inicio y la última compra", [serie, desde, K["n"], K["intervalo"]])
    motor = None
    for pref, nombre in (("mc", MOTOR_CASO), ("sens", MOTOR_SENSIBILIDAD)):
        sim = mc_.simular(vista, nombre, sims, semilla, largo)
        costos = mc_.costos(plan, trm0, sim.acum, pasos)
        d = DistribucionHistorica(pd.DatetimeIndex([]), costos, costo_hoy)
        cola = f", {sims} trayectorias de {nombre} (semilla {semilla}, {largo} pasos)"
        for k, formula, valor in (("media", "media del costo", float(costos.mean())),
                                  ("p5", "percentil 5 del costo", d.percentil(5)),
                                  ("p50", "percentil 50 (mediana) del costo", d.percentil(50)),
                                  ("p95", "percentil 95 del costo", d.percentil(95))):
            K[f"{pref}.{k}"] = D(valor, "COP", formula + cola, ins)
        K[f"{pref}.prob_superar"] = D(d.prob_superar(presupuesto) * 100, "%",
                                      "100 × fracción de trayectorias con costo > presupuesto" + cola,
                                      ins + [K["presupuesto"]])
        K[f"{pref}.prob_mas_barato"] = D(d.prob_mas_barato_que_hoy() * 100, "%",
                                         "100 × fracción de trayectorias con costo < costo hoy" + cola,
                                         ins + [K["costo_hoy"]])
        K[f"{pref}.deriva_252"] = D(
            100 * float(np.expm1(np.median(sim.acum[mc_.LARGO_MIN - 1]))), "%",
            f"100 × (mediana de la TRM simulada a {mc_.LARGO_MIN} pasos / TRM_hoy − 1)" + cola,
            [K["trm0"], serie])
        if pref == "mc":
            motor = (sim, costos, d, cola)
    sim, costos, d, cola = motor
    K["mc.dif_media"] = D(K["mc.media"].valor - costo_hoy, "COP",
                          "costo esperado simulado − costo hoy", [K["mc.media"], K["costo_hoy"]])
    K["mc.dif_p95"] = D(K["mc.p95"].valor - costo_hoy, "COP",
                        "percentil 95 simulado − costo hoy", [K["mc.p95"], K["costo_hoy"]])
    K["mc.ee_media"] = D(float(costos.std(ddof=1) / np.sqrt(sims)), "COP",
                         "desvío del costo / √trayectorias" + cola, ins)
    pp = [d.prob_superar(presupuesto), d.prob_mas_barato_que_hoy()]
    K["mc.ee_prob"] = D(100 * float(max(np.sqrt(p * (1 - p) / sims) for p in pp)), "puntos porcentuales",
                        "100 × máximo de √(p(1−p)/trayectorias) entre las dos probabilidades" + cola,
                        [K["mc.prob_superar"], K["mc.prob_mas_barato"]])
    K["mc.bloque"] = D(sim.bloque, "días", "longitud media de bloque de Politis-White (máximo entre la "
                       f"serie y su valor absoluto), {MOTOR_CASO}", [serie])
    K["mc.sigma_origen"] = D(sim.sigma_origen * 100, "% diario",
                             "100 × desvío diario EWMA(0,94) en la última observación", [serie])
    K["mc.sigma_largo"] = D(sim.sigma_largo * 100, "% diario",
                            "100 × raíz de la media de r² en toda la historia", [serie])

    b = mc_.bandas(sim.acum, trm0)                           # (largo + 1, niveles)
    for h in HORIZONTES_EVALUADOS:
        for nombre, j in (("inf", 0), ("med", 2), ("sup", 4)):
            K[f"abanico.{h}.{nombre}"] = D(
                float(b[h, j]), "COP/USD",
                f"TRM_hoy × exp(cuantil {mc_.NIVELES_ABANICO[j]} del rendimiento acumulado a {h} pasos)"
                + cola, [K["trm0"], serie])
        cob = respaldo.cobertura(MOTOR_CASO, h) if respaldo else None
        if cob:
            for k, cifra in cob.items():
                K[f"resp.{h}.{k}"] = cifra
            dentro = cob["ic_inf"].valor <= cob["nominal"].valor <= cob["ic_sup"].valor
            K[f"resp.{h}.compatible"] = D("sí" if dentro else "no", "", "ic_inf ≤ nominal ≤ ic_sup",
                                          [cob["ic_inf"], cob["nominal"], cob["ic_sup"]])
    ex = respaldo.exito(1) if respaldo else None             # único horizonte con modelo de referencia
    if ex:
        for k, cifra in ex.items():
            K[f"ref.1.{k}"] = cifra
        for corto, etiqueta in COLAS_REFERENCIA:
            v = respaldo.var_h1(ex["campeon"].valor, etiqueta)
            if v:
                K[f"ref.1.tasa_{corto}"] = D(v["tasa"].valor * 100, "%", "100 × tasa de excesos del VaR",
                                             [v["tasa"]])
                K[f"ref.1.p_{corto}"] = v["p_kupiec"]
    return {"niveles": list(mc_.NIVELES_ABANICO), "pasos_compra": list(pasos), "trm": b}


def calcular(datos: DatosTRM, c: ConjuntoSupuestos, mc: dict | None = None,
             respaldo: Respaldo | None = None) -> tuple[dict, dict[str, Cifra]]:
    """Devuelve (resultado numérico para el hash, cifras con linaje).

    `mc` = {"trayectorias": N, "semilla": s} agrega el Monte Carlo; None lo omite.
    """
    S = lambda id: Cifra.de_supuesto(c.supuesto(id))          # noqa: E731
    D = Cifra.derivada
    meta, n, inter, marg = (S("caso.meta_usd"), S("caso.n_compras"),
                            S("caso.intervalo_meses"), S("caso.presupuesto_margen_pct"))
    desde = S("historica.desde")
    fecha0, _ = datos.ultima()
    trm0 = datos.cifra(fecha0)
    serie = Cifra.de_dato(len(datos.trm), "observaciones", "processed/trm.csv",
                          "columna=trm;serie completa", datos.hash_trm)
    plan_esc = PlanCompra.escalonado(meta.valor, int(n.valor), int(inter.valor))
    base = [meta, n, inter, trm0]
    K: dict[str, Cifra] = {"meta": meta, "n": n, "intervalo": inter, "margen": marg,
                           "trm0": trm0, "fecha_trm0": D(str(fecha0.date()), "fecha",
                                                          "fecha de la TRM de hoy", [trm0])}
    K["costo_hoy"] = D(meta.valor * trm0.valor, "COP", "meta_usd × TRM_hoy", [meta, trm0])
    K["presupuesto"] = D(K["costo_hoy"].valor * (1 + marg.valor / 100), "COP",
                         "costo_hoy × (1 + margen/100)", [K["costo_hoy"], marg])

    def veredicto(costo: Cifra) -> Cifra:
        return D("Sí" if costo.valor > K["presupuesto"].valor else "No", "",
                 "costo > presupuesto", [costo, K["presupuesto"]])

    for nombre in ESCENARIOS:                                   # deterministas
        g = S(id_deriva(nombre))
        r = correr(plan_esc, trm0.valor, c, nombre)
        K[f"det.{nombre}.g"] = g
        K[f"det.{nombre}.costo"] = D(r.costo_cop, "COP",
                                     "Σ (meta/n)·TRM_hoy·exp(g·m_i/12), m_i = i·intervalo",
                                     base + [g])
        K[f"det.{nombre}.medio"] = D(r.costo_medio, "COP/USD", "costo / meta_usd",
                                     [K[f"det.{nombre}.costo"], meta])
        K[f"det.{nombre}.dif"] = D(r.costo_cop - K["costo_hoy"].valor, "COP",
                                   "costo escalonado − costo hoy",
                                   [K[f"det.{nombre}.costo"], K["costo_hoy"]])
        K[f"det.{nombre}.pasa"] = veredicto(K[f"det.{nombre}.costo"])

    for clave in VENTANAS:                                      # ventanas con nombre
        ini = S(f"historica.ventana.{clave}")
        r = reproducir(plan_esc, datos.trm, ini.valor, "movimientos", trm0.valor)
        fin = desplazar_meses(ini.valor, plan_esc.horizonte_meses)
        ratio_fin = float(ratios_ventana(datos.trm, ini.valor, [plan_esc.horizonte_meses])[0])
        p = f"hist.{clave}"
        K[f"{p}.inicio"] = ini
        K[f"{p}.fin"] = D(str(fin.date()), "fecha", "inicio + horizonte del plan", [ini, n, inter])
        K[f"{p}.ratio"] = D(ratio_fin, "adimensional",
                            "TRM(inicio + horizonte) / TRM(inicio)", [ini, n, inter, serie])
        K[f"{p}.costo"] = D(r.costo_cop, "COP",
                            "Σ (meta/n)·TRM_hoy·TRM(inicio+m_i)/TRM(inicio)",
                            base + [ini, serie])
        K[f"{p}.dif"] = D(r.costo_cop - K["costo_hoy"].valor, "COP",
                          "costo escalonado − costo hoy", [K[f"{p}.costo"], K["costo_hoy"]])
        K[f"{p}.pasa"] = veredicto(K[f"{p}.costo"])

    dist = distribucion(plan_esc, datos.trm, trm0.valor, desde.valor)   # todas las ventanas
    res = dist.resumen(K["presupuesto"].valor)
    ins = base + [serie, desde, marg]
    span_meses = (dist.inicios[-1].year - dist.inicios[0].year) * 12 + (
        dist.inicios[-1].month - dist.inicios[0].month) + plan_esc.horizonte_meses
    for k, formula, unidad in (
            ("media", "media del costo en todas las ventanas", "COP"),
            ("p5", "percentil 5 del costo", "COP"), ("p50", "percentil 50 (mediana) del costo", "COP"),
            ("p95", "percentil 95 del costo", "COP"), ("min", "mínimo del costo", "COP"),
            ("max", "máximo del costo", "COP")):
        K[f"dist.{k}"] = D(res[k], unidad, formula, ins)
    K["dist.ventanas"] = D(res["ventanas"], "ventanas", "número de fechas de inicio con ventana completa", ins)
    K["dist.independientes"] = D(int(span_meses // max(1, plan_esc.horizonte_meses)), "ventanas",
                                 "meses cubiertos / horizonte (ventanas sin traslape)",
                                 [K["dist.ventanas"], n, inter])
    K["dist.inicio_min"] = D(str(res["inicio_min"].date()), "fecha", "inicio de la ventana de menor costo", ins)
    K["dist.inicio_max"] = D(str(res["inicio_max"].date()), "fecha", "inicio de la ventana de mayor costo", ins)
    K["dist.prob_superar"] = D(res["prob_superar_presupuesto"] * 100, "%",
                               "100 × fracción de ventanas con costo > presupuesto",
                               ins + [K["presupuesto"]])
    K["dist.prob_mas_barato"] = D(res["prob_mas_barato_que_hoy"] * 100, "%",
                                  "100 × fracción de ventanas con costo < costo hoy",
                                  ins + [K["costo_hoy"]])
    K["dist.dif_media"] = D(res["media"] - K["costo_hoy"].valor, "COP",
                            "costo esperado escalonado − costo hoy", [K["dist.media"], K["costo_hoy"]])
    K["dist.dif_p95"] = D(res["p95"] - K["costo_hoy"].valor, "COP",
                          "percentil 95 escalonado − costo hoy", [K["dist.p95"], K["costo_hoy"]])
    abanico = None
    if mc is not None:
        abanico = _montecarlo(K, datos, plan_esc, serie, desde, ins, int(mc["trayectorias"]),
                              int(mc["semilla"]), respaldo)
    resultado = {k: v.valor for k, v in K.items()}
    if abanico is not None:
        resultado["abanico"] = abanico
    return resultado, K


# --- reporte -------------------------------------------------------------------------------
def _reporte_md(K: dict[str, Cifra], ficha: Ficha) -> str:
    rep = Reporte()
    cop = lambda c: rep.r(c, 0)                      # noqa: E731
    pct = lambda c: rep.r(c, 1)                      # noqa: E731
    f = lambda c: rep.r(c, 0, unidad=False)          # noqa: E731  (fechas y textos)
    nu = lambda c, d=0: rep.r(c, d, unidad=False)    # noqa: E731  (conteos con sustantivo propio)
    det = "\n".join(
        f"| {ETIQUETA[n]} | {nu(K[f'det.{n}.g'], 4)} | {cop(K[f'det.{n}.costo'])} | "
        f"{rep.r(K[f'det.{n}.medio'])} | {cop(K[f'det.{n}.dif'])} | {f(K[f'det.{n}.pasa'])} |"
        for n in ESCENARIOS)
    hist = "\n".join(
        f"| {ETIQUETA[k]} | {f(K[f'hist.{k}.inicio'])} | {f(K[f'hist.{k}.fin'])} | "
        f"{rep.r(K[f'hist.{k}.ratio'], 3)} | {cop(K[f'hist.{k}.costo'])} | "
        f"{cop(K[f'hist.{k}.dif'])} | {f(K[f'hist.{k}.pasa'])} |" for k in VENTANAS)
    sims = ficha.parametros["trayectorias"]
    hay = "resp.1.cobertura" in K                    # ¿hay archivo de respaldo?
    c3 = lambda c: rep.r(c, 3, unidad=False)         # noqa: E731  (coberturas y p-valores)
    mc = "\n".join(
        f"| {etq} | {fmt(K[f'mc.{k}'])} | {fmt(K[f'sens.{k}'])} | {fmt(K[f'dist.{k}'])} | {SIN_RESPALDO} |"
        for etq, k, fmt in (("Costo esperado (media)", "media", cop), ("Mediana", "p50", cop),
                            ("Percentil 5", "p5", cop), ("Percentil 95", "p95", cop),
                            ("Probabilidad de superar el presupuesto", "prob_superar", pct),
                            ("Probabilidad de salir más barato que comprar hoy", "prob_mas_barato", pct)))
    if hay:
        indirecto = ("ese horizonte queda entre 126 y 252 días, que en la prueba final son solo "
                     "descriptivos (cobertura medida del intervalo del 95 %: "
                     f"{c3(K['resp.126.cobertura'])} con {nu(K['resp.126.n_efectivo'])} ventanas "
                     f"independientes y {c3(K['resp.252.cobertura'])} con "
                     f"{nu(K['resp.252.n_efectivo'])})")
    else:
        indirecto = ("ese horizonte queda entre 126 y 252 días, que en la prueba final son solo "
                     "descriptivos (no hay archivo de respaldo: no se citan coberturas)")

    def fila_abanico(h: int) -> str:
        siempre = h in HORIZONTES_ADVERTENCIA
        if hay:
            desc = "descriptiva, " if h in HORIZONTES_LARGOS else ""
            ev = (f"prueba final, {desc}cobertura medida {c3(K[f'resp.{h}.cobertura'])} "
                  f"(n efectivo {nu(K[f'resp.{h}.n_efectivo'])}; intervalo de confianza "
                  f"{rep.r(K[f'resp.{h}.ic_inf'], 2, unidad=False)} a "
                  f"{rep.r(K[f'resp.{h}.ic_sup'], 2, unidad=False)})")
            if siempre:
                adv = (f"**siempre**: solo {nu(K[f'resp.{h}.n_efectivo'])} ventanas independientes; "
                       "que la cobertura nominal quepa en el intervalo no prueba que la banda esté "
                       "bien calibrada")
            elif K[f"resp.{h}.compatible"].valor == "sí":
                adv = "no hace falta"
            else:
                adv = "**la cobertura nominal queda fuera del intervalo**"
        else:
            ev = SIN_RESPALDO
            adv = "**siempre** (pocas ventanas independientes)" if siempre else "—"
        return (f"| {h} | {rep.r(K[f'abanico.{h}.inf'])} | {rep.r(K[f'abanico.{h}.med'])} | "
                f"{rep.r(K[f'abanico.{h}.sup'])} | {ev} | {adv} |")

    abanico = "\n".join(fila_abanico(h) for h in HORIZONTES_EVALUADOS)
    if "ref.1.campeon" in K:
        colas = ""
        if "ref.1.tasa_sup5" in K and "ref.1.tasa_sup1" in K:
            colas = (" Su cola superior quedó subcubierta en la prueba final: el VaR superior del "
                     f"5 % se superó el {pct(K['ref.1.tasa_sup5'])} de los días y el del 1 % el "
                     f"{rep.r(K['ref.1.tasa_sup1'])} (Kupiec p = {c3(K['ref.1.p_sup5'])} y "
                     f"{c3(K['ref.1.p_sup1'])}).")
        referencia = (f"Solo a 1 día un modelo superó a su línea base en la prueba final: "
                      f"`{K['ref.1.campeon'].valor}` (CRPS/base {c3(K['ref.1.relativo'])}, "
                      f"{nu(K['ref.1.n'])} orígenes).{colas} Este caso no lo usa para simular ni "
                      "calcula su banda: se cita como referencia de ese horizonte. En los demás "
                      "horizontes ningún modelo se distinguió de las líneas base y no se cita ninguno.")
    else:
        referencia = "Sin archivo de respaldo de la prueba final no se cita ningún modelo."
    md = f"""# Caso: compra de dólares para una meta — comprar hoy vs. compras escalonadas

Reporte generado por `python -m laboratorio.motor compra_dolares`. Los rangos describen
incertidumbre (histórica y simulada); no son pronóstico ni asesoría financiera. Cada cifra
termina en un código `#hash` que remite al apéndice con su fuente y su hash SHA-256. Bajo cada
bloque de cifras se dice qué evaluación fuera de muestra lo respalda, o «{SIN_RESPALDO}».

## Planteamiento

- Meta: {rep.r(K['meta'], 0)}. Plan A: comprarlos todos hoy. Plan B: {nu(K['n'])} compras
  iguales, una cada {nu(K['intervalo'])} mes(es), la primera hoy.
- TRM de hoy ({f(K['fecha_trm0'])}): {rep.r(K['trm0'])}.
- Costo del Plan A (cierto): {cop(K['costo_hoy'])}. Presupuesto: {cop(K['presupuesto'])}
  (costo de comprar hoy más un margen de {pct(K['margen'])}).
- Las cifras de meta, número de compras, margen y ventanas son valores ilustrativos del autor.

## 1. Escenarios deterministas del Plan B

La TRM sigue `TRM0·exp(g·m/12)`; g (logarítmica anual) toma los percentiles 5, 50 y 95 de la
variación anual observada desde la flotación. Diferencia = costo de B menos costo de A (positivo = B más caro).

| Escenario | Deriva anual g | Costo Plan B | Costo medio | Diferencia vs. A | ¿Se pasa del presupuesto? |
|---|---:|---:|---:|---:|---|
{det}

Respaldo: {SIN_RESPALDO} (las derivas son supuestos; no es un pronóstico evaluado).

## 2. Reproducción histórica con nombre

Se aplican al Plan B, desde la TRM de hoy, los movimientos reales de cada ventana.

| Ventana | Inicio | Fin | TRM fin / TRM inicio | Costo Plan B | Diferencia vs. A | ¿Se pasa? |
|---|---|---|---:|---:|---:|---|
{hist}

Respaldo: {SIN_RESPALDO} (repite dos episodios del pasado; no es un pronóstico).

## 3. Todas las ventanas históricas del régimen de flotación

Hay {nu(K['dist.ventanas'])} ventanas de inicio. La más barata empieza el {f(K['dist.inicio_min'])}
y la más cara el {f(K['dist.inicio_max'])}. Se traslapan: equivalen a solo
{nu(K['dist.independientes'])} ventanas sin traslape, así que los percentiles extremos
descansan en pocos episodios.

| Medida del Plan B | Valor | Diferencia vs. A |
|---|---:|---:|
| Costo esperado (media) | {cop(K['dist.media'])} | {cop(K['dist.dif_media'])} |
| Mediana | {cop(K['dist.p50'])} | |
| Percentil 5 | {cop(K['dist.p5'])} | |
| Percentil 95 | {cop(K['dist.p95'])} | {cop(K['dist.dif_p95'])} |
| Mínimo | {cop(K['dist.min'])} | |
| Máximo | {cop(K['dist.max'])} | |
| Probabilidad de superar el presupuesto | {pct(K['dist.prob_superar'])} | |
| Probabilidad de salir más barato que comprar hoy | {pct(K['dist.prob_mas_barato'])} | |

Respaldo: {SIN_RESPALDO} (frecuencias del pasado con ventanas traslapadas; nunca se evaluó como pronóstico).

## 4. Monte Carlo por bloques

Se simulan {formatear(sims, 0)} trayectorias de la TRM (semilla {ficha.semilla}) con
`{MOTOR_CASO}`, el motor fijado en el prerregistro antes de la prueba final. Es un bootstrap
estacionario (Politis-Romano): remuestrea por bloques de longitud media
{rep.r(K['mc.bloque'], 1)} (Politis-White) los rendimientos diarios divididos por la volatilidad
de su momento, y los reescala con la volatilidad de hoy ({rep.r(K['mc.sigma_origen'], 3)}), que
vuelve poco a poco a la de largo plazo ({rep.r(K['mc.sigma_largo'], 3)}). La sensibilidad usa
`{MOTOR_SENSIBILIDAD}` (los rendimientos tal cual, sin filtrar). El tiempo avanza en días con
TRM: la última compra cae a {rep.r(K['mc.pasos_ultima'], 0)} (el prerregistro decía «unos 230»;
la serie trae unas 20 observaciones por mes, no 21).

**Por qué toda la historia y no solo la flotación.** El remuestreo usa las
{nu(K['serie'])} observaciones de la serie, desde {f(K['serie_inicio'])} (banda cambiaria
incluida); la sección 3, en cambio, solo usa ventanas desde {f(K['desde'])}. Tres motivos:
(a) es exactamente el modelo que se evaluó en la prueba final: con otra muestra, las coberturas
medidas que se citan en la sección 5 no respaldarían estas cifras; (b) la banda aporta la
crisis de 1997-1999, uno de los pocos episodios de estrés que hay; (c) el motor remuestrea
choques ya divididos por la volatilidad de su época, así que el nivel de volatilidad de los
años de banda no se traslada a hoy: la escala la pone la volatilidad actual. En la sensibilidad
sin filtrar el motivo (c) no aplica.

**Lo que esa decisión cuesta: la deriva.** El promedio histórico de los choques (incluida la
depreciación sostenida de los años noventa) sí entra en las trayectorias. La mediana simulada
de la TRM a 252 días queda {pct(K['mc.deriva_252'])} por encima de la de hoy
({pct(K['sens.deriva_252'])} en la sensibilidad), mientras que el escenario base de la sección 1,
que solo mira la flotación, supone una deriva logarítmica anual de {nu(K['det.base.g'], 4)}. Esa
deriva empuja hacia arriba el costo esperado y la probabilidad de superar el presupuesto frente
a las ventanas históricas. No es un pronóstico de dirección: es una propiedad del modelo
evaluado, que se deja a la vista y no se corrige aquí porque el motor quedó fijado antes de
la prueba final.

| Medida del Plan B | Monte Carlo (motor) | Sensibilidad (sin filtrar) | Ventanas históricas | Evaluación que la respalda |
|---|---:|---:|---:|---|
{mc}

Diferencia frente al Plan A: costo esperado {cop(K['mc.dif_media'])}; percentil 95
{cop(K['mc.dif_p95'])}. Error de Monte Carlo (solo por simular un número finito de trayectorias;
no mide el error del modelo): ± {cop(K['mc.ee_media'])} en la media y a lo sumo
± {rep.r(K['mc.ee_prob'], 2)} en las probabilidades.

**Respaldo de estas cifras: indirecto.** Ninguna tiene una evaluación directa fuera de muestra.
El caso reparte la compra en {nu(K['n'])} cuotas: la última cae a
{rep.r(K['mc.pasos_ultima'], 0)} y la cifra que se reporta es el costo total, una suma sobre toda
la trayectoria. La prueba final no evalúa ni ese horizonte ni esa suma: evalúa el rendimiento
acumulado a 1, 5, 21, 63, 126 y 252 días, cada uno por separado. Dos límites: {indirecto}; y
acertar cada horizonte por separado no garantiza acertar la trayectoria completa de la que
depende el costo total.

## 5. Abanico de la TRM y evaluación que lo respalda

![Abanico de la TRM proyectada](figs/{FIGURA})

Límites = percentiles 2,5 y 97,5 de las trayectorias del motor (la banda del 95 %), en los
horizontes que evaluó la prueba final. «Cobertura medida» = fracción de las veces, entre 2020 y
2026, en que la TRM real cayó dentro de la banda del 95 % del mismo modelo (lo ideal es 0,95).
El intervalo de confianza usa el n efectivo (ventanas sin traslape).

| Horizonte (días con TRM) | Límite inferior | Mediana | Límite superior | Evaluación que la respalda | Advertencia |
|---:|---:|---:|---:|---|---|
{abanico}

**Modelo de referencia.** {referencia}

## Limitaciones

- No se modela el rendimiento del dinero mientras espera (costo de oportunidad ni tasas COP/USD).
- La distribución histórica usa solo el pasado del régimen de flotación y supone que se
  repetirá; el Monte Carlo remuestrea choques ya ocurridos: ninguno de los dos contiene
  episodios más grandes que los vistos.
- Los percentiles extremos dependen de pocos episodios (ver ventanas sin traslape).
- El costo total simulado no tiene evaluación directa fuera de muestra (sección 4).
- La TRM es la de la Superfinanciera (una fila por vigencia); el precio real de compra
  incluye comisiones y diferencial que no se modelan.

## Ficha de la corrida

- Corrida: `{ficha.run_id}`; caso `{ficha.caso}`; semilla: {ficha.semilla}; trayectorias:
  {formatear(sims, 0)}; motor `{MOTOR_CASO}`, sensibilidad `{MOTOR_SENSIBILIDAD}`.
- Hash de datos `{ficha.hash_datos}`
- Hash de supuestos `{ficha.hash_supuestos}`
- Hash de código `{ficha.hash_codigo}`
- Hash de entrada `{ficha.hash_entrada}`
- Hash de resultado `{ficha.hash_resultado}`

## Apéndice: fuente y hash de cada cifra

{rep.apendice()}
"""
    return md


# --- orquestación ------------------------------------------------------------------------------
def rutas(raiz: Path) -> dict[str, Path]:
    return {"procesado": raiz / "data" / "processed", "raw": raiz / "data" / "raw",
            "registro": raiz / "data" / "supuestos" / "registro.jsonl",
            "respaldo": raiz / RUTA_RESPALDO,
            "runs": raiz / "runs", "reporte": raiz / "reports" / "compra_dolares.md",
            "figura": raiz / "reports" / "figs" / FIGURA,
            "codigo": raiz / "src" / "laboratorio"}


def _archivos(datos: DatosTRM, p: dict[str, Path]) -> dict[str, Path]:
    """Archivos que entran en el hash de datos: la TRM y, si existe, el respaldo de la prueba final."""
    out = dict(datos.archivos())
    if p["respaldo"].exists():
        out[ARCHIVO_RESPALDO] = p["respaldo"]
    return out


def ejecutar(raiz: str | Path = ".", autor: str = "analista", actualizar_derivas: bool = False,
             trayectorias: int = mc_.TRAYECTORIAS, semilla: int = mc_.SEMILLA) -> tuple[Ficha, Path, Path]:
    p = rutas(Path(raiz))
    datos = DatosTRM(p["procesado"], p["raw"])
    reg = Registro(p["registro"])
    sembrar(reg, datos, autor, actualizar_derivas)
    conjunto = reg.conjunto_vigente(ids_del_caso())
    mc = {"trayectorias": int(trayectorias), "semilla": int(semilla)}
    resultado, K = calcular(datos, conjunto, mc, cargar_respaldo(p["respaldo"]))
    ficha = construir_ficha(CASO, _archivos(datos, p), conjunto, int(semilla),
                            {"modo": MODO, "trayectorias": int(trayectorias), "motor": MOTOR_CASO,
                             "sensibilidad": MOTOR_SENSIBILIDAD}, resultado, p["codigo"])
    ruta_ficha = guardar(ficha, resultado, p["runs"])
    ab = resultado["abanico"]
    mc_.figura_abanico(ab["trm"], ab["niveles"], ab["pasos_compra"], p["figura"],
                       f"TRM proyectada: {int(trayectorias)} trayectorias de {MOTOR_CASO}")
    md = _reporte_md(K, ficha)
    viejas = derivas_desactualizadas(reg, datos)
    if viejas:
        aviso = ("> **Aviso:** las derivas de los escenarios deterministas se estimaron con otra "
                 "versión de los datos. Para reestimarlas (versión nueva del supuesto) ejecute "
                 "con `--actualizar-derivas`.\n\n")
        md = md.replace("## Planteamiento", aviso + "## Planteamiento", 1)
    p["reporte"].parent.mkdir(parents=True, exist_ok=True)
    p["reporte"].write_text(md, encoding="utf-8")
    return ficha, ruta_ficha, p["reporte"]


def reproducir_corrida(ruta_ficha: str | Path, raiz: str | Path = ".") -> tuple[bool, str]:
    """Reejecuta una ficha guardada y compara el hash del resultado."""
    from ..ficha import cargar
    p = rutas(Path(raiz))
    ficha = cargar(ruta_ficha)
    datos = DatosTRM(p["procesado"], p["raw"])
    conjunto = Registro(p["registro"]).conjunto(ficha.pins_supuestos)
    mc = ({"trayectorias": ficha.parametros["trayectorias"], "semilla": ficha.semilla}
          if "trayectorias" in ficha.parametros else None)      # fichas anteriores a F5: sin Monte Carlo
    respaldo = cargar_respaldo(p["respaldo"])
    return reproducir_ficha(ficha, lambda f: calcular(datos, conjunto, mc, respaldo)[0],
                            _archivos(datos, p), conjunto, p["codigo"])
