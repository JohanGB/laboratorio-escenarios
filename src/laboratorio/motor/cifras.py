"""Cifras trazables: cada número muestra su fuente y su hash.

Tres orígenes:
- dato:    valor leído de un archivo (hash = H(valor, archivo, ubicación, sha256 del archivo)).
- supuesto: valor del registro de supuestos (hash = hash del registro de esa versión).
- calculo: valor derivado (hash = H(valor, fórmula, hashes de los insumos)).
Si cambia cualquier dato, supuesto o fórmula de la que depende, cambia el hash de la cifra.
"""
from __future__ import annotations

from dataclasses import dataclass

from .ficha import normalizar
from .supuestos import Supuesto, canonico, sha256_texto

LARGO_CORTO = 10


class CifraError(ValueError):
    pass


@dataclass(frozen=True)
class Cifra:
    valor: float | int | str
    unidad: str
    origen: str            # "dato" | "supuesto" | "calculo"
    referencia: str        # archivo#ubicación | id@vN | fórmula
    hash: str
    insumos: tuple["Cifra", ...] = ()

    @property
    def corto(self) -> str:
        return self.hash[:LARGO_CORTO]

    # --- constructores -------------------------------------------------------------
    @staticmethod
    def de_dato(valor, unidad: str, archivo: str, ubicacion: str, hash_archivo: str) -> "Cifra":
        if not (archivo and ubicacion and hash_archivo):
            raise CifraError("un dato necesita archivo, ubicación y hash del archivo")
        ref = f"{archivo}#{ubicacion}"
        h = sha256_texto(canonico(["dato", normalizar(valor), unidad, ref, hash_archivo]))
        return Cifra(valor, unidad, "dato", ref, h)

    @staticmethod
    def de_supuesto(s: Supuesto) -> "Cifra":
        return Cifra(s.valor, s.unidad, "supuesto", f"{s.id}@v{s.version}", s.hash)

    @staticmethod
    def derivada(valor, unidad: str, formula: str, insumos: list["Cifra"]) -> "Cifra":
        if not formula.strip() or not insumos:
            raise CifraError("una cifra derivada necesita fórmula e insumos")
        h = sha256_texto(canonico(["calculo", normalizar(valor), unidad, formula,
                                   [c.hash for c in insumos]]))
        return Cifra(valor, unidad, "calculo", formula, h, tuple(insumos))

    # --- linaje ---------------------------------------------------------------------
    def hojas(self) -> list["Cifra"]:
        """Datos y supuestos de los que depende (sin repetir)."""
        if self.origen != "calculo":
            return [self]
        vistas, out = set(), []
        for c in self.insumos:
            for h in c.hojas():
                if h.hash not in vistas:
                    vistas.add(h.hash)
                    out.append(h)
        return out


def formatear(valor, decimales: int = 2) -> str:
    """Formato es-CO: 3.316,70."""
    if isinstance(valor, str):
        return valor
    if isinstance(valor, int) and decimales == 0:
        return f"{valor:,}".replace(",", ".")
    s = f"{valor:,.{decimales}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


class Reporte:
    """Acumula las cifras mostradas y arma el apéndice de fuentes y hashes."""

    def __init__(self) -> None:
        self._cifras: dict[str, Cifra] = {}

    def r(self, c: Cifra, decimales: int = 2, unidad: bool = True) -> str:
        previa = self._cifras.get(c.corto)
        if previa is not None and previa.hash != c.hash:
            raise CifraError(f"colisión de hash corto {c.corto}")
        self._cifras[c.corto] = c
        txt = formatear(c.valor, decimales)
        if unidad and c.unidad and c.unidad != "adimensional":
            txt += f" {c.unidad}"
        return f"{txt} `#{c.corto}`"

    def apendice(self) -> str:
        filas = ["| Cifra | Origen | Fuente / fórmula | Hash SHA-256 |", "|---|---|---|---|"]
        for corto, c in sorted(self._cifras.items(), key=lambda kv: (kv[1].origen, kv[1].referencia)):
            ref = c.referencia.replace("|", "\\|")
            filas.append(f"| `#{corto}` | {c.origen} | {ref} | `{c.hash}` |")
        return "\n".join(filas)

    def cifras(self) -> list[Cifra]:
        return list(self._cifras.values())
