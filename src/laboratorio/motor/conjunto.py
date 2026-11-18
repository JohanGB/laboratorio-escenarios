"""Motor conjunto multidivisa (M2): trayectorias conjuntas de la TRM y de cada «USD por X».

Todas sus salidas llevan la etiqueta `ETIQUETA`: «motor conjunto, sin evaluación fuera de muestra
hasta M3». No es el motor evaluado en la prueba final: no incluye la banda cambiaria colombiana
(ver «Muestra común») y no se ha evaluado fuera de muestra. No modifica `montecarlo.simular`.

Diseño (docs/prompts/PROMPT_VEKTOR_FX.md, M2; decisiones en docs/decisiones.md):
1. **Factores, no cruces.** Se simulan los rendimientos logarítmicos de la TRM (COP por USD) y de
   cada «USD por X». El cruce sale de sumar logaritmos: X/COP = TRM × USD por X, así que la
   triangulación EUR/COP ÷ USD/COP = USD por EUR se cumple en cada trayectoria (hay prueba).
   «USD por X» = (X/COP) ÷ TRM en la misma fecha de TRM de `divisas.csv` (alineación de M1).
2. **Índices de fecha compartidos.** Se sortea UNA secuencia de índices del bootstrap estacionario
   (`modelos.bootstrap.indices_bloques`) y se aplica a todas las series (`aplicar_indices`): se
   conserva la correlación contemporánea y de corto plazo tal como fue en la muestra.
3. **Variante filtrada** (`bootstrap_est_filtrado`): cada serie se estandariza con su propia σ
   EWMA (z = r/σ_{t−1}) y se reescala con su propia trayectoria de σ desde el origen (σ̄², ρ de
   `BootstrapEstacionario.ajustar`), como el motor de una sola serie. `bootstrap_est` remuestrea
   los rendimientos tal cual.
4. **Bloque común.** Por defecto, la longitud de Politis-White de la TRM en la muestra común (el
   máximo entre la serie y su valor absoluto, como en `ajustar`). Alternativa para sensibilidad:
   `bloque="mediana"`, la mediana de las longitudes de los factores de la corrida.
5. **Muestra común.** Desde la primera fecha en que flotan TODAS las divisas de la corrida y ya no
   rige la banda colombiana: la primera fecha posterior a la última fila con régimen
   `NO_FLOTA` de cada divisa (con CNY, 2005-07-23: TRM del sábado 23 con el H.10 del viernes 22).
   El piso suizo (2011-2015) queda dentro: es un episodio, no un régimen sin flotación.
   Fechas comunes sin relleno (unión interna); un rendimiento va de una fecha común a la
   siguiente.
6. **Sin fuga.** Con `origen`, todo dato posterior se descarta antes de calcular nada; sin él, el
   origen es la última fecha común. Generador `default_rng([semilla, n_fechas − 1])`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from ..backtest.final import MOTOR_CASO, MOTOR_SENSIBILIDAD
from ..modelos.bootstrap import (MIN_OBS, BootstrapEstacionario, _sigma2_ewma, aplicar_indices,
                                 indices_bloques, residuos_estandarizados)

ETIQUETA = "motor conjunto, sin evaluación fuera de muestra hasta M3"
FILTRADO = {MOTOR_CASO: True, MOTOR_SENSIBILIDAD: False}
NO_FLOTA = frozenset({"fijo", "banda", "banda_cop"})
REGLAS_BLOQUE = ("trm", "mediana")
SEMILLA = 20240501
TRAYECTORIAS = 10_000
LARGO = 252


class _SerieComoVista:
    """Lo que `BootstrapEstacionario.ajustar` lee de una vista: r (r[0] = NaN) y n."""

    def __init__(self, r: np.ndarray) -> None:
        self.r, self.n = r, len(r)


@dataclass(frozen=True)
class SimulacionConjunta:
    motor: str
    divisas: tuple[str, ...]
    acum: np.ndarray                    # (largo, sims, divisas): log acumulado de X/COP
    factores: tuple[str, ...]           # ("TRM", "USD por EUR", ...)
    acum_factores: np.ndarray           # (largo, sims, factores)
    nivel0: dict[str, float]            # X/COP en el origen
    nivel0_factores: dict[str, float]   # factores en el origen
    bloque: float                       # longitud media de bloque común
    regla_bloque: str                   # "trm", "mediana" o "fijo"
    bloques_factor: dict[str, float]    # Politis-White de cada factor (máx. serie, |serie|)
    sigma_origen: dict[str, float] | None   # σ diaria prevista en el origen (solo filtrado)
    sigma_largo: dict[str, float] | None    # σ diaria de largo plazo (solo filtrado)
    rho: dict[str, float] | None            # persistencia diaria de la varianza (solo filtrado)
    muestra_desde: str                  # primera fecha (de nivel) de la muestra común
    muestra_hasta: str                  # origen
    n: int                              # rendimientos que entran al remuestreo
    semilla: int
    etiqueta: str = ETIQUETA

    @property
    def sims(self) -> int:
        return self.acum.shape[1]

    @property
    def largo(self) -> int:
        return self.acum.shape[0]

    def niveles(self) -> np.ndarray:
        """X/COP por paso, (largo + 1, sims, divisas); la fila 0 es el origen."""
        return _niveles(self.acum, [self.nivel0[d] for d in self.divisas])

    def niveles_factores(self) -> np.ndarray:
        return _niveles(self.acum_factores, [self.nivel0_factores[f] for f in self.factores])


def _niveles(acum: np.ndarray, nivel0: Sequence[float]) -> np.ndarray:
    n0 = np.asarray(nivel0, float)
    return n0 * np.exp(np.concatenate([np.zeros((1, *acum.shape[1:])), acum]))


# --- vistas y muestra ----------------------------------------------------------------------------
def vistas_divisas(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """{divisa: DataFrame indexado por fecha con cop_por_unidad y regimen} desde divisas.csv."""
    out = {}
    for divisa, g in df.groupby("divisa", sort=False):
        g = g.assign(fecha=pd.to_datetime(g["fecha"])).set_index("fecha").sort_index()
        out[str(divisa)] = g[["cop_por_unidad", "regimen"]]
    return out


def _con_usd(divisas: Sequence[str]) -> tuple[str, ...]:
    return ("USD", *[d for d in divisas if d != "USD"])


def inicio_flotacion(vista: pd.DataFrame) -> pd.Timestamp:
    """Primera fecha posterior a la última fila con régimen sin flotación (`NO_FLOTA`)."""
    no = vista["regimen"].isin(NO_FLOTA).to_numpy()
    if not no.any():
        return pd.Timestamp(vista.index[0])
    ultima = int(np.flatnonzero(no)[-1])
    if ultima + 1 >= len(vista):
        raise ValueError("la divisa no flota en ninguna fecha de la vista")
    return pd.Timestamp(vista.index[ultima + 1])


def muestra_comun(vistas: Mapping[str, pd.DataFrame], divisas: Sequence[str]) -> pd.Timestamp:
    """Primera fecha en que flotan todas las divisas de la corrida (y la TRM ya sin banda)."""
    return max(inicio_flotacion(vistas[d]) for d in _con_usd(divisas))


def _validar(vistas, divisas, motor, sims, largo) -> tuple[str, ...]:
    if motor not in FILTRADO:
        raise ValueError(f"motor desconocido: {motor!r} (use {tuple(FILTRADO)})")
    if sims < 1 or largo < 1:
        raise ValueError("sims y largo deben ser >= 1")
    divisas = tuple(divisas)
    if not divisas or len(set(divisas)) != len(divisas):
        raise ValueError("divisas vacías o repetidas")
    faltan = [d for d in _con_usd(divisas) if d not in vistas]
    if faltan:
        raise ValueError(f"sin vista para la divisa: {', '.join(faltan)}")
    return divisas


def _recortar(vistas, origen):
    if origen is None:
        return dict(vistas)
    o = pd.Timestamp(origen)
    return {d: v[v.index <= o] for d, v in vistas.items()}


def niveles_factores(vistas: Mapping[str, pd.DataFrame], divisas: Sequence[str], desde,
                     origen=None) -> pd.DataFrame:
    """Niveles de los factores (TRM, USD por X) en las fechas comunes con desde ≤ fecha ≤ origen."""
    vistas = _recortar(vistas, origen)
    trm = vistas["USD"]["cop_por_unidad"].astype(float)
    cols = {"TRM": trm}
    for d in divisas:
        if d != "USD":
            x = vistas[d]["cop_por_unidad"].astype(float)
            cols[f"USD por {d}"] = x / trm.reindex(x.index)
    df = pd.DataFrame(cols).dropna()                      # unión interna, sin relleno
    return df[df.index >= pd.Timestamp(desde)]


def rendimientos_muestra(vistas: Mapping[str, pd.DataFrame], divisas: Sequence[str], desde,
                         origen=None) -> pd.DataFrame:
    """Rendimientos logarítmicos históricos de cada X/COP en la muestra común (fechas comunes)."""
    lf = np.log(niveles_factores(vistas, divisas, desde, origen))
    cruces = pd.DataFrame({d: lf["TRM"] if d == "USD" else lf["TRM"] + lf[f"USD por {d}"]
                           for d in divisas})
    return cruces.diff().iloc[1:]


# --- simulación ----------------------------------------------------------------------------------
def simular_conjunto(vistas: Mapping[str, pd.DataFrame], divisas: Sequence[str],
                     motor: str = MOTOR_CASO, sims: int = TRAYECTORIAS, semilla: int = SEMILLA,
                     largo: int = LARGO, desde=None, origen=None,
                     bloque: str | float = "trm") -> SimulacionConjunta:
    """`sims` trayectorias conjuntas de `largo` pasos desde el origen (ver el docstring del módulo).

    vistas: `vistas_divisas(divisas.csv)`; debe incluir USD (la TRM).
    divisas: las X/COP de la salida, en orden (USD = la TRM misma).
    desde: inicio de la muestra; None = `muestra_comun`. Antes de ella es un error (incluiría
    regímenes sin flotación). origen: última fecha que entra; None = la última fecha común.
    bloque: "trm" (por defecto), "mediana" o una longitud fija (> 0).
    """
    divisas = _validar(vistas, divisas, motor, sims, largo)
    vistas = _recortar(vistas, origen)                    # fuga: nada posterior al origen
    comun = muestra_comun(vistas, divisas)
    if desde is None:
        desde = comun
    elif pd.Timestamp(desde) < comun:
        raise ValueError(f"desde {pd.Timestamp(desde).date()} es anterior a la muestra común "
                         f"({comun.date()}): incluiría regímenes sin flotación")
    if not (bloque in REGLAS_BLOQUE or (isinstance(bloque, (int, float)) and bloque > 0)):
        raise ValueError(f"bloque inválido: {bloque!r} (use {REGLAS_BLOQUE} o un número > 0)")

    niv = niveles_factores(vistas, divisas, desde)
    nombres = tuple(niv.columns)
    if len(niv) - 1 < MIN_OBS:
        raise ValueError(f"solo {len(niv) - 1} rendimientos en la muestra común; se requieren {MIN_OBS}")
    R = np.diff(np.log(niv.to_numpy()), axis=0)            # (n, k)
    filtrado = FILTRADO[motor]

    modelos, columnas = [], []
    for j in range(len(nombres)):
        r = np.r_[np.nan, R[:, j]]                         # formato de Vista: r[0] = NaN
        m = BootstrapEstacionario(filtrado=filtrado, sims=sims, semilla=semilla)
        m.ajustar(_SerieComoVista(r))
        modelos.append((m, r))
        columnas.append(_serie_alineada(m, r))
    X = np.column_stack(columnas)
    X = X[np.isfinite(X).all(axis=1)]                      # filas con todos los factores

    bloques = {n: float(m.bloque) for n, (m, _) in zip(nombres, modelos)}
    if bloque == "trm":
        b, regla = bloques["TRM"], "trm"
    elif bloque == "mediana":
        b, regla = float(np.median(list(bloques.values()))), "mediana"
    else:
        b, regla = float(bloque), "fijo"

    escala = sig_o = sig_l = rho = None
    if filtrado:
        s2o = {n: float(_sigma2_ewma(r)[-1]) for n, (_, r) in zip(nombres, modelos)}
        escala = np.column_stack([m.escala(s2o[n], largo) for n, (m, _) in zip(nombres, modelos)])
        sig_o = {n: float(np.sqrt(v)) for n, v in s2o.items()}
        sig_l = {n: float(np.sqrt(m.sigma2_largo)) for n, (m, _) in zip(nombres, modelos)}
        rho = {n: float(m.rho) for n, (m, _) in zip(nombres, modelos)}

    rng = np.random.default_rng([semilla, len(niv) - 1])
    idx = indices_bloques(rng, len(X), largo, sims, b)
    acum_f = aplicar_indices(X, idx, escala)               # (largo, sims, k)
    acum = np.stack([acum_f[..., 0] if d == "USD"
                     else acum_f[..., 0] + acum_f[..., nombres.index(f"USD por {d}")]
                     for d in divisas], axis=2)
    ultimo = niv.iloc[-1]
    nivel0 = {d: float(ultimo["TRM"] if d == "USD" else ultimo["TRM"] * ultimo[f"USD por {d}"])
              for d in divisas}
    return SimulacionConjunta(
        motor=motor, divisas=divisas, acum=acum, factores=nombres, acum_factores=acum_f,
        nivel0=nivel0, nivel0_factores={n: float(ultimo[n]) for n in nombres}, bloque=b,
        regla_bloque=regla, bloques_factor=bloques, sigma_origen=sig_o, sigma_largo=sig_l, rho=rho,
        muestra_desde=str(niv.index[0].date()), muestra_hasta=str(niv.index[-1].date()),
        n=int(len(X)), semilla=int(semilla))


def _serie_alineada(m: BootstrapEstacionario, r: np.ndarray) -> np.ndarray:
    """La serie que remuestrea el motor (z = r/σ_{t−1} o r), SIN descartar los NaN: así las
    columnas de todos los factores quedan alineadas por fecha antes de quitar filas."""
    return residuos_estandarizados(r) if m.filtrado else r[1:]
