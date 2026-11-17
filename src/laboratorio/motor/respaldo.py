"""Respaldo fuera de muestra del caso: qué midió la prueba final sobre lo que el caso muestra.

`generar` resume UNA vez los resultados de la prueba final (runs/prueba_final y
runs/prueba_final_largo, ya cerrados con HECHO.json) en un archivo pequeño y versionado,
`data/respaldo/prueba_final.json`, usando las mismas funciones del reporte final
(`cobertura_motor`, `confirmar`, `pruebas_var`). No calcula nada nuevo ni elige nada.

El caso lo lee con `cargar` y convierte cada número en una cifra con fuente y hash; el archivo
entra en el hash de datos de la corrida. Si no existe, el caso declara «sin respaldo fuera de
muestra» en todo.

F6 agrega la sección `posterior` del archivo: un «análisis posterior (no confirmatorio)» que NO
estaba en el prerregistro. `asimetria_motor` cuenta, con los mismos resultados de la prueba
final, de qué lado quedó la TRM real frente a la banda del motor: bajo la mediana, bajo el
límite inferior y sobre el límite superior, por horizonte. La cobertura del intervalo del 95 %
junta las dos colas y no deja ver si la banda está corrida hacia un lado. Usa el mismo n
efectivo y el mismo intervalo binomial que la cobertura (`cobertura_n_efectivo`). A 126 y 252
días hay tan pocas ventanas independientes que es un indicio, no una prueba.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .cifras import Cifra
from .ficha import hash_archivo, normalizar

ARCHIVO = "respaldo/prueba_final.json"            # nombre con el que entra en hashes y apéndice
RUTA = Path("data") / "respaldo" / "prueba_final.json"
CAMPOS_COBERTURA = ("cobertura", "n", "n_efectivo", "ic_inf", "ic_sup", "compatible")
CAMPOS_CONFIRMATORIA = ("campeon", "base", "relativo", "p_holm", "n", "exito")
TITULO_POSTERIOR = "análisis posterior (no confirmatorio)"
# medida → proporción esperada si la banda del motor estuviera bien centrada y calibrada
MEDIDAS_ASIMETRIA = {"bajo_mediana": 0.5, "bajo_inferior": 0.025, "sobre_superior": 0.025}
CAMPOS_ASIMETRIA = ("proporcion", "esperado", "ic_inf", "ic_sup", "compatible")


def asimetria_motor(res: dict, res_largo: dict, motor: str, horizontes, horizontes_largos) -> dict:
    """Análisis posterior: de qué lado de la banda del motor quedó el valor real, por horizonte.

    Para cada h: proporción de orígenes con y < mediana, y < cuantil 0,025 e y > cuantil 0,975
    (y = rendimiento acumulado real; cuantiles = los que el motor pronosticó en ese origen).
    Cada proporción lleva su valor esperado y el intervalo binomial exacto con n efectivo = n/h
    (`cobertura_n_efectivo`, la misma función de la cobertura publicada). Cobertura del 95 % =
    1 − bajo_inferior − sobre_superior.
    """
    from ..evaluacion.cobertura import cobertura_n_efectivo
    out = {}
    for fuente, hs in ((res, horizontes), (res_largo, horizontes_largos)):
        if motor not in fuente:
            continue
        d = fuente[motor]
        for h in hs:
            s = d[d["h"] == h]
            if len(s) == 0:
                continue
            y, lo, med, hi = (s[c].to_numpy(float) for c in ("y", "q_0.025", "q_0.5", "q_0.975"))
            fila = {}
            for medida, ocurre in (("bajo_mediana", y < med), ("bajo_inferior", y < lo),
                                   ("sobre_superior", y > hi)):
                # la proporción de unos es la «cobertura» del intervalo [0,5; 1,5] sobre el indicador
                c = cobertura_n_efectivo(ocurre.astype(float), 0.5, 1.5, MEDIDAS_ASIMETRIA[medida], int(h))
                fila[medida] = {"proporcion": c["cobertura"], "esperado": c["nominal"],
                                "ic_inf": c["ic_inf"], "ic_sup": c["ic_sup"],
                                "compatible": c["compatible"]}
                fila["n"], fila["n_efectivo"] = c["n"], c["n_efectivo"]
            out[str(int(h))] = fila
    return out


def generar(raiz: str | Path = ".") -> Path:
    """Escribe data/respaldo/prueba_final.json a partir de la prueba final ya terminada."""
    from ..backtest.final import (CONFIRMATORIAS, MOTOR_CASO, MOTOR_SENSIBILIDAD, SALIDA_FINAL,
                                  SALIDA_FINAL_LARGO)
    from ..backtest.particion import HORIZONTES, HORIZONTES_LARGOS
    from ..reportes.fase2 import cargar as cargar_resultados, pruebas_var
    from ..reportes.prueba_final import NOMINAL_MOTOR, cobertura_motor, confirmar

    raiz = Path(raiz)
    hecho = raiz / SALIDA_FINAL / "HECHO.json"
    if not hecho.exists():
        raise FileNotFoundError(f"no existe {hecho}: la prueba final no ha terminado")
    res, meta = cargar_resultados(raiz / SALIDA_FINAL)
    largo_dir = raiz / SALIDA_FINAL_LARGO
    res_largo = cargar_resultados(largo_dir)[0] if largo_dir.exists() else {}
    md = next(iter(meta.values()), {})
    cobertura = {}
    for motor in (MOTOR_CASO, MOTOR_SENSIBILIDAD):
        cm = cobertura_motor(res, res_largo, motor)
        cobertura[motor] = {str(int(r.h)): {k: getattr(r, k) for k in CAMPOS_COBERTURA}
                            for r in cm.itertuples()}
    conf = confirmar(res, CONFIRMATORIAS)
    confirmatorias = {str(int(r.h)): {k: getattr(r, k) for k in CAMPOS_CONFIRMATORIA}
                      for r in conf.itertuples()}
    var_h1 = {}
    for r in conf.itertuples():                      # colas a 1 día de los campeones con éxito
        if int(r.h) == 1 and bool(r.exito):
            var_h1[r.campeon] = {cola: {"tasa": tasa, "p_kupiec": puc}
                                 for cola, (tasa, puc, _, _) in pruebas_var(res[r.campeon]).items()}
    datos = {"fuente": f"{SALIDA_FINAL.as_posix()} y {SALIDA_FINAL_LARGO.as_posix()}",
             "sha256_hecho": hash_archivo(hecho), "hash_codigo": md.get("hash_codigo"),
             "hash_trm_csv": md.get("hash_trm_csv"), "nominal": NOMINAL_MOTOR,
             "cobertura": cobertura, "confirmatorias": confirmatorias, "var_h1": var_h1,
             "posterior": {
                 "titulo": TITULO_POSTERIOR,
                 "nota": "Calculado después de terminar la prueba final, con sus mismos resultados. "
                         "No estaba en el prerregistro: no confirma ni rechaza nada.",
                 "asimetria": {motor: asimetria_motor(res, res_largo, motor, HORIZONTES, HORIZONTES_LARGOS)
                               for motor in (MOTOR_CASO, MOTOR_SENSIBILIDAD)}}}
    destino = raiz / RUTA
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(normalizar(datos), ensure_ascii=False, indent=1,
                                  sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return destino


@dataclass(frozen=True)
class Respaldo:
    datos: dict
    hash: str                                      # SHA-256 del archivo

    def _cifra(self, valor, unidad: str, ubicacion: str) -> Cifra:
        return Cifra.de_dato(valor, unidad, ARCHIVO, ubicacion, self.hash)

    def cobertura(self, motor: str, h: int) -> dict[str, Cifra] | None:
        """Cobertura medida del intervalo del 95 % del motor a h pasos (None si no se midió)."""
        f = self.datos.get("cobertura", {}).get(motor, {}).get(str(h))
        if f is None:
            return None
        u = f"cobertura;motor={motor};h={h};campo="
        out = {k: self._cifra(f[k], "adimensional", u + k) for k in ("cobertura", "ic_inf", "ic_sup")}
        out["n_efectivo"] = self._cifra(int(f["n_efectivo"]), "ventanas", u + "n_efectivo")
        out["nominal"] = self._cifra(self.datos["nominal"], "adimensional", "nominal")
        return out

    def exito(self, h: int) -> dict[str, Cifra] | None:
        """La confirmatoria de h si fue ÉXITO: campeón, línea base, CRPS/base y n (None si no)."""
        f = self.datos.get("confirmatorias", {}).get(str(h))
        if f is None or not f["exito"]:
            return None
        u = f"confirmatorias;h={h};campo="
        return {"campeon": self._cifra(f["campeon"], "", u + "campeon"),
                "base": self._cifra(f["base"], "", u + "base"),
                "relativo": self._cifra(f["relativo"], "adimensional", u + "relativo"),
                "n": self._cifra(int(f["n"]), "orígenes", u + "n")}

    def var_h1(self, modelo: str, cola: str) -> dict[str, Cifra] | None:
        """Tasa de excesos del VaR a 1 día y p de Kupiec de `modelo` en `cola` (p. ej. 'sup 5 %')."""
        f = self.datos.get("var_h1", {}).get(modelo, {}).get(cola)
        if f is None:
            return None
        u = f"var_h1;modelo={modelo};cola={cola};campo="
        return {"tasa": self._cifra(f["tasa"], "adimensional", u + "tasa"),
                "p_kupiec": self._cifra(f["p_kupiec"], "adimensional", u + "p_kupiec")}

    def asimetria(self, motor: str, h: int) -> dict[str, dict[str, Cifra]] | None:
        """Análisis posterior: {medida: {proporcion, esperado, ic_inf, ic_sup, compatible}} del
        motor a h pasos, con medida en MEDIDAS_ASIMETRIA. None si el archivo no lo trae."""
        f = self.datos.get("posterior", {}).get("asimetria", {}).get(motor, {}).get(str(h))
        if f is None:
            return None
        out = {}
        for medida in MEDIDAS_ASIMETRIA:
            u = f"posterior;asimetria;motor={motor};h={h};medida={medida};campo="
            out[medida] = {k: self._cifra("sí" if f[medida][k] else "no", "", u + k) if k == "compatible"
                           else self._cifra(f[medida][k], "adimensional", u + k)
                           for k in CAMPOS_ASIMETRIA}
        return out


def cargar(ruta: str | Path | None) -> Respaldo | None:
    if ruta is None or not Path(ruta).exists():
        return None
    return Respaldo(json.loads(Path(ruta).read_text(encoding="utf-8")), hash_archivo(ruta))
