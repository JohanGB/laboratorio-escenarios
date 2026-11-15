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
    out = generar(tmp_path, directorio=d, salida=tmp_path / "fase2.md")
    texto = out.read_text(encoding="utf-8")
    assert "| ancho | candidato | ninguno | **DESCARTADO**" in texto
    assert "crisis_x" in texto and "Kupiec" in texto and "## Horizonte h = 63" in texto
    assert "línea base" in texto
