"""Respaldo fuera de muestra del caso: qué midió la prueba final sobre lo que el caso muestra.

`generar` resume UNA vez los resultados de la prueba final (runs/prueba_final y
runs/prueba_final_largo, ya cerrados con HECHO.json) en un archivo pequeño y versionado,
`data/respaldo/prueba_final.json`, usando las mismas funciones del reporte final
(`cobertura_motor`, `confirmar`, `pruebas_var`). No calcula nada nuevo ni elige nada.

El caso lo lee con `cargar` y convierte cada número en una cifra con fuente y hash; el archivo
entra en el hash de datos de la corrida. Si no existe, el caso declara «sin respaldo fuera de
muestra» en todo.
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


def generar(raiz: str | Path = ".") -> Path:
    """Escribe data/respaldo/prueba_final.json a partir de la prueba final ya terminada."""
    from ..backtest.final import (CONFIRMATORIAS, MOTOR_CASO, MOTOR_SENSIBILIDAD, SALIDA_FINAL,
                                  SALIDA_FINAL_LARGO)
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
             "cobertura": cobertura, "confirmatorias": confirmatorias, "var_h1": var_h1}
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


def cargar(ruta: str | Path | None) -> Respaldo | None:
    if ruta is None or not Path(ruta).exists():
        return None
    return Respaldo(json.loads(Path(ruta).read_text(encoding="utf-8")), hash_archivo(ruta))
