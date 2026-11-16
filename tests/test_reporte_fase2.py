import numpy as np
import pandas as pd

from laboratorio.backtest.corredor import correr
from laboratorio.backtest.datos import construir_vista
from laboratorio.modelos.base import Pronosticador
from laboratorio.modelos.garch import t_estandarizada
from laboratorio.modelos.lineas_base import EWMA, CaminataAleatoria, SimulacionHistorica
from laboratorio.reportes.fase2 import comparar, generar


class Ancho(Pronosticador):
    """Candidato deliberadamente malo: EWMA con intervalos 3 veces más anchos."""
    def pronosticar(self, vista, origenes, niveles):
        q = EWMA().pronosticar(vista, origenes, niveles)
        return {h: 3 * v for h, v in q.items()}


def vista_garch(n=2500, seed=2):
    rng = np.random.default_rng(seed)
    z = t_estandarizada(rng, 6, n); v = 0.5; r = np.empty(n)
    for k in range(n):
        r[k] = np.sqrt(v) * z[k]; v = 0.03 + 0.08 * r[k] ** 2 + 0.89 * v
    idx = pd.bdate_range("2004-01-02", periods=n)
    est = np.array([""] * n, dtype=object); est[1500:1600] = "crisis_x"
    trm = pd.DataFrame({"trm": 3000 * np.exp(np.cumsum(r / 100)), "regimen": "flotacion", "estres": est}, index=idx)
    ext = pd.DataFrame({"brent_usd": 1.0, "dolar_amplio": 1.0, "fed_funds": 1.0, "politica": 1.0}, index=idx)
    return construir_vista(trm, ext)


def test_reporte_marca_descartado_al_candidato_que_no_supera_la_base(tmp_path):
    v = vista_garch()
    d = tmp_path / "runs"; d.mkdir()
    for nombre, m in {"caminata_aleatoria": CaminataAleatoria(), "sim_hist_756": SimulacionHistorica(756),
                      "ewma_0.94": EWMA(), "ancho": Ancho()}.items():
        correr(m, v, primero=800, paso=63).to_csv(d / f"{nombre}.csv.gz", index=False, compression="gzip")
    from laboratorio.reportes.fase2 import cargar
    c = comparar(cargar(d)[0])
    assert set(c[c.modelo == "ancho"].estado) == {"descartado"}
    assert c[(c.modelo == "ewma_0.94") & (c.h == 1)].estado.iloc[0] == "supera"
    from laboratorio.backtest.corredor import correr_con_cola
    from laboratorio.backtest.particion import HORIZONTES_LARGOS
    (d / "cola").mkdir()
    correr_con_cola(EWMA(), v, primero=800, paso=63)[1].to_csv(
        d / "cola" / "ewma_0.94.csv.gz", index=False, compression="gzip")
    largo = tmp_path / "backtest_largo"; largo.mkdir()
    correr(EWMA(horizontes=HORIZONTES_LARGOS), v, primero=800, paso=63).to_csv(
        largo / "ewma_0.94.csv.gz", index=False, compression="gzip")
    out = generar(tmp_path, directorio=d, salida=tmp_path / "fase2.md", reps_mcs=300)
    texto = out.read_text(encoding="utf-8")
    # F2: secciones nuevas
    for titulo in ("## Model Confidence Set", "## Semáforo de Basilea", "## Expected Shortfall",
                   "## Uniformidad del PIT", "## Acierto direccional", "## Horizontes largos",
                   "## Veredicto por horizonte (MCS y Holm)", "## Conclusiones"):
        assert titulo in texto, titulo
    mcs = texto.split("## Model Confidence Set")[1].split("## Semáforo")[0]
    assert "| ancho |" in mcs and "| no |" in mcs               # el candidato malo sale del MCS
    es = texto.split("## Expected Shortfall")[1].split("## Uniformidad")[0]
    assert "| ewma_0.94 | inferior |" in es and "`ancho`: no aplica" in es
    assert "| ewma_0.94 | 252 | 95 % |" in texto.split("## Horizontes largos")[1]
    assert (tmp_path / "figs" / "fase2_pit.png").exists()
    # caminata y EWMA tienen mediana cero: sin dirección
    assert "| caminata_aleatoria | no aplica |" in texto.split("## Acierto direccional")[1]
    assert "| ancho | candidato | ninguno | **DESCARTADO**" in texto
    assert "crisis_x" in texto and "Kupiec" in texto and "## Horizonte h = 63" in texto
    assert "## Pruebas de VaR al 95 % y 99 % en ambas colas" in texto
    assert "línea base" in texto
