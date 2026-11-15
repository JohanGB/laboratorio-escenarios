"""Caso 1 (sección 8): comprar todos los dólares hoy vs. compras escalonadas.

Entrega: costo por escenario determinista, reproducción de ventanas históricas con nombre
(2015 y fin de 2022) y la distribución empírica sobre TODAS las ventanas reales del régimen
de flotación (costo esperado, percentil 95, probabilidad de pasarse del presupuesto).
Cada cifra del reporte lleva su fuente y su hash (ver `cifras.Reporte`).
Comprar hoy tiene costo cierto; el riesgo está del lado del plan escalonado.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from ..cifras import Cifra, Reporte
from ..datos import DatosTRM
from ..deterministas import ESCENARIOS, correr, id_deriva
from ..ficha import (EntradaCambio, Ficha, construir_ficha, guardar, hash_codigo,
                     reproducir as reproducir_ficha)
from ..historica import distribucion, desplazar_meses, ratios_ventana, ratios_todas, reproducir
from ..plan import PlanCompra
from ..supuestos import ConjuntoSupuestos, Registro

CASO = "compra_dolares"
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
def calcular(datos: DatosTRM, c: ConjuntoSupuestos) -> tuple[dict, dict[str, Cifra]]:
    """Devuelve (resultado numérico para el hash, cifras con linaje)."""
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
    resultado = {k: v.valor for k, v in K.items()}
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
    md = f"""# Caso: compra de dólares para una meta — comprar hoy vs. compras escalonadas

Reporte generado por `python -m laboratorio.motor compra_dolares`. Los rangos describen
incertidumbre histórica; no son pronóstico ni asesoría financiera. Cada cifra termina en un
código `#hash` que remite al apéndice con su fuente y su hash SHA-256.

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

## 2. Reproducción histórica con nombre

Se aplican al Plan B, desde la TRM de hoy, los movimientos reales de cada ventana.

| Ventana | Inicio | Fin | TRM fin / TRM inicio | Costo Plan B | Diferencia vs. A | ¿Se pasa? |
|---|---|---|---:|---:|---:|---|
{hist}

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

## Limitaciones

- No se modela el rendimiento del dinero mientras espera (costo de oportunidad ni tasas COP/USD).
- La distribución usa solo el pasado del régimen de flotación y supone que se repetirá; los
  episodios no vistos (ni su magnitud) no están incluidos.
- Los percentiles extremos dependen de pocos episodios (ver ventanas sin traslape).
- La TRM es la de la Superfinanciera (una fila por vigencia); el precio real de compra
  incluye comisiones y diferencial que no se modelan.

## Ficha de la corrida

- Corrida: `{ficha.run_id}`; caso `{ficha.caso}`; semilla: ninguna (cálculo determinista).
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
            "runs": raiz / "runs", "reporte": raiz / "reports" / "compra_dolares.md",
            "codigo": raiz / "src" / "laboratorio"}


def ejecutar(raiz: str | Path = ".", autor: str = "analista",
             actualizar_derivas: bool = False) -> tuple[Ficha, Path, Path]:
    p = rutas(Path(raiz))
    datos = DatosTRM(p["procesado"], p["raw"])
    reg = Registro(p["registro"])
    sembrar(reg, datos, autor, actualizar_derivas)
    conjunto = reg.conjunto_vigente(ids_del_caso())
    resultado, K = calcular(datos, conjunto)
    ficha = construir_ficha(CASO, datos.archivos(), conjunto, None, {"modo": "determinista+historica"},
                            resultado, p["codigo"])
    ruta_ficha = guardar(ficha, resultado, p["runs"])
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
    return reproducir_ficha(ficha, lambda f: calcular(datos, conjunto)[0],
                            datos.archivos(), conjunto, p["codigo"])
