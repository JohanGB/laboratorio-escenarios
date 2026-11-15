"""data/manifest.json: hash SHA-256, filas y rango de fechas de cada archivo crudo."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .lectores import fecha_descarga, leer_archivo

IGNORAR = {"MANIFEST.csv"}


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _urls(raw: Path) -> dict[str, str]:
    """URLs registradas a mano en data/raw/MANIFEST.csv (si existe)."""
    f = raw / "MANIFEST.csv"
    if not f.exists():
        return {}
    with open(f, encoding="utf-8", newline="") as fh:
        return {r["archivo"]: r["url"] for r in csv.DictReader(fh)}


def listar_raw(raw: Path) -> list[Path]:
    return sorted(p for p in raw.iterdir() if p.is_file() and p.name not in IGNORAR)


def construir_manifiesto(raw: Path, lecturas: dict | None = None) -> dict:
    """`lecturas` opcional: {nombre: (series, filas)} para no releer los archivos."""
    urls = _urls(raw)
    archivos = []
    for ruta in listar_raw(raw):
        series, filas = (lecturas or {}).get(ruta.name) or leer_archivo(ruta)
        fmin = min(s.index.min() for s in series.values())
        fmax = max(s.index.max() for s in series.values())
        fd = fecha_descarga(ruta)
        archivos.append({
            "archivo": ruta.name,
            "url": urls.get(ruta.name),
            "fecha_descarga": fd.date().isoformat() if fd is not None else None,
            "sha256": sha256(ruta),
            "bytes": ruta.stat().st_size,
            "filas": int(filas),
            "series": len(series),
            "fecha_min": fmin.date().isoformat(),
            "fecha_max": fmax.date().isoformat(),
        })
    return {"generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "archivos": archivos}


def escribir_manifiesto(manifiesto: dict, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2),
                       encoding="utf-8")
