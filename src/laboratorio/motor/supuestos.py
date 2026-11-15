"""Registro de supuestos versionados, de solo agregar (sección 5.1).

Formato: JSON Lines, una línea por versión. Cada línea incluye el hash de la anterior
(cadena), de modo que cualquier edición manual se detecta con `Registro.verificar()`.
Editar un supuesto = agregar una versión nueva; las anteriores siguen consultables.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

GENESIS = "0" * 64
_ID = re.compile(r"^[a-z0-9_.]+$")
CAMPOS = ("id", "version", "valor", "unidad", "fuente", "justificacion", "autor",
          "fecha", "hash_prev")


class RegistroError(ValueError):
    """Violación de las reglas del registro (formato, cadena o versiones)."""


def canonico(obj) -> str:
    """JSON canónico (claves ordenadas, sin espacios) para hashear."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Supuesto:
    id: str
    version: int
    valor: float | int | str
    unidad: str
    fuente: str
    justificacion: str
    autor: str
    fecha: str
    hash_prev: str
    hash: str

    def sin_hash(self) -> dict:
        d = asdict(self)
        d.pop("hash")
        return d

    @staticmethod
    def calcular_hash(campos: dict) -> str:
        return sha256_texto(canonico({k: campos[k] for k in CAMPOS}))


@dataclass(frozen=True)
class ConjuntoSupuestos:
    """Supuestos fijados a una versión concreta; su hash identifica la entrada."""
    pins: dict[str, int]
    _supuestos: dict[str, Supuesto]

    @property
    def hash(self) -> str:
        return sha256_texto(canonico(sorted(
            [i, s.version, s.hash] for i, s in self._supuestos.items())))

    def supuesto(self, id: str) -> Supuesto:
        return self._supuestos[id]

    def valor(self, id: str):
        return self._supuestos[id].valor

    def __contains__(self, id: str) -> bool:
        return id in self._supuestos


class Registro:
    def __init__(self, ruta: str | Path):
        self.ruta = Path(ruta)

    # --- lectura -------------------------------------------------------------
    def _leer(self) -> list[Supuesto]:
        if not self.ruta.exists():
            return []
        out = []
        for n, linea in enumerate(self.ruta.read_text(encoding="utf-8").splitlines(), 1):
            if not linea.strip():
                raise RegistroError(f"línea {n}: vacía")
            try:
                out.append(Supuesto(**json.loads(linea)))
            except (TypeError, json.JSONDecodeError) as e:
                raise RegistroError(f"línea {n}: formato inválido ({e})") from e
        return out

    def historial(self, id: str) -> list[Supuesto]:
        return [s for s in self._leer() if s.id == id]

    def version(self, id: str, n: int) -> Supuesto:
        for s in self.historial(id):
            if s.version == n:
                return s
        raise KeyError(f"{id} v{n} no existe")

    def vigente(self, id: str, en: str | date | None = None) -> Supuesto:
        """Última versión (con fecha <= `en`, si se indica)."""
        h = self.historial(id)
        if en is not None:
            corte = en.isoformat() if isinstance(en, date) else str(en)
            h = [s for s in h if s.fecha <= corte]
        if not h:
            raise KeyError(f"{id}: sin versión vigente")
        return h[-1]

    def ids(self) -> list[str]:
        return sorted({s.id for s in self._leer()})

    # --- escritura (solo agregar) ---------------------------------------------
    def agregar(self, id: str, valor, unidad: str, fuente: str, justificacion: str,
                autor: str, fecha: str | date | None = None) -> Supuesto:
        if not _ID.match(id or ""):
            raise RegistroError(f"id inválido: {id!r} (use a-z, 0-9, _ y .)")
        for nombre, v in (("unidad", unidad), ("fuente", fuente),
                          ("justificacion", justificacion), ("autor", autor)):
            if not isinstance(v, str) or not v.strip():
                raise RegistroError(f"{nombre} es obligatorio")
        if isinstance(valor, bool) or not isinstance(valor, (int, float, str)):
            raise RegistroError("valor debe ser número o texto")
        if isinstance(valor, float) and valor != valor:
            raise RegistroError("valor no puede ser NaN")
        self.verificar()
        todos = self._leer()
        previos = [s for s in todos if s.id == id]
        if previos and previos[-1].valor == valor and previos[-1].unidad == unidad:
            raise RegistroError(f"{id}: sin cambios respecto de v{previos[-1].version}")
        f = fecha.isoformat() if isinstance(fecha, date) else (fecha or date.today().isoformat())
        campos = {"id": id, "version": len(previos) + 1, "valor": valor, "unidad": unidad,
                  "fuente": fuente, "justificacion": justificacion, "autor": autor,
                  "fecha": f, "hash_prev": todos[-1].hash if todos else GENESIS}
        s = Supuesto(**campos, hash=Supuesto.calcular_hash(campos))
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ruta, "a", encoding="utf-8", newline="\n") as f_out:
            f_out.write(canonico(asdict(s)) + "\n")
        return s

    # --- integridad -------------------------------------------------------------
    def verificar(self) -> None:
        prev, versiones = GENESIS, {}
        for n, s in enumerate(self._leer(), 1):
            if s.hash_prev != prev:
                raise RegistroError(f"línea {n}: cadena rota (hash_prev no coincide)")
            if Supuesto.calcular_hash(s.sin_hash()) != s.hash:
                raise RegistroError(f"línea {n}: contenido alterado (hash no coincide)")
            esperada = versiones.get(s.id, 0) + 1
            if s.version != esperada:
                raise RegistroError(f"línea {n}: {s.id} versión {s.version}, esperada {esperada}")
            versiones[s.id] = s.version
            prev = s.hash

    # --- conjuntos -----------------------------------------------------------------
    def conjunto(self, pins: dict[str, int]) -> ConjuntoSupuestos:
        self.verificar()
        return ConjuntoSupuestos(dict(pins), {i: self.version(i, v) for i, v in pins.items()})

    def conjunto_vigente(self, ids: list[str]) -> ConjuntoSupuestos:
        return self.conjunto({i: self.vigente(i).version for i in ids})
