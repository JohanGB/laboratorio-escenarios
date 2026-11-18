# Reproducción de las fichas de corrida

Una ficha (`runs/<id>/ficha.json`) es un registro: no se reescribe. Su `hash_entrada` incluye
el `hash_codigo` (todos los `.py` de `src/laboratorio`), así que en `main` una ficha deja de
reproducirse en cuanto cambia cualquier archivo de código, y `reproducir` lo dice
(«NO REPRODUCIBLE: la entrada cambió: código»). Eso es lo esperado.

**La reproducción exacta de una ficha se hace en una copia limpia del commit cuyo código tiene
el `hash_codigo` de la ficha.** Ese commit lleva la etiqueta `corrida-<id>`. El campo `commit`
de la ficha es informativo y puede no ser ese commit (ver 6506dbba3261).

| Ficha | Campo `commit` | Commit de reproducción (etiqueta) | `hash_codigo` | Resultado verificado | Nota |
|---|---|---|---|---|---|
| `6506dbba3261` (vigente) | `037f784` | `d4c6f25` (`corrida-6506dbba3261`) | `6aed58e0b63462e1…` | COINCIDE (17-nov-2026) | Hallazgo H5 de `docs/auditoria_independiente.md`: la corrida se hizo con cambios sin commit, un minuto antes de `d4c6f25`. En `037f784` (su campo `commit`) da NO REPRODUCIBLE (datos y código). |
| `200b84c2c1a1` (histórica) | `a05380b` | `a05380b` (`corrida-200b84c2c1a1`) | `eb779fe22e24b162…` | COINCIDE (17-nov-2026) | No reproduce en `main` desde el 16-nov: F5b (`d4c6f25`) cambió `data/respaldo/prueba_final.json` (`de961f69…` → `eabb756d…`) y el motor (`montecarlo.py`, `compra_dolares.py`, `respaldo.py`). Reproducción solo por etiqueta. |
| `d6f052613b7a` (histórica) | nulo | ninguno | `8ac96d6514444c1f…` | no reproducible | Creada el 15-nov-2026 a las 02:43 UTC, antes del primer commit (`f51d1a8`); ningún commit del historial tiene su `hash_codigo` (comprobado el 17-nov-2026). Sin etiqueta. |

Desde M2, `python -m laboratorio.motor compra_dolares` no escribe una ficha si hay cambios sin
commit en `src/` o `data/`, y al guardarla crea la etiqueta `corrida-<id>` en HEAD (lo que
evita otro H5).

## Cómo reproducir (un comando por paso)

La ficha se lee de `main`: el commit de reproducción puede no contenerla (la de `200b84c2c1a1`
se versionó después de `a05380b`).

```powershell
git worktree add ..\repro-6506 corrida-6506dbba3261
cd ..\repro-6506
pip install -e ".[dev]" -c requirements-prueba-final.txt
$env:PYTHONPATH = "src"
python -m laboratorio.datos.limpieza
git show main:runs/6506dbba3261/ficha.json > ficha_6506.json
python -m laboratorio.motor reproducir ficha_6506.json
```

Debe imprimir `COINCIDE  hash resultado nuevo fd0721b8…`. Para `200b84c2c1a1`, lo mismo con la
etiqueta `corrida-200b84c2c1a1` (debe dar `7fece992…`).

## Pruebas

- `tests/test_reproduccion.py::test_cada_ficha_tiene_etiqueta_y_su_commit_tiene_su_codigo`:
  cada ficha de `runs/*/ficha.json` tiene su etiqueta y el `hash_codigo` del árbol de ese commit
  (leído con `git ls-tree` y `git cat-file`, sin checkout) es el de la ficha. La única excepción
  admitida es `d6f052613b7a` (commit nulo, anterior al primer commit). Corre en la CI.
- `tests/test_reproduccion.py::test_no_regresion_de_la_ficha_vigente_en_main` (`lento`, fuera de la
  CI: la ficha hashea `data/processed/trm.csv` escrito en Windows, con CRLF; en Linux se
  reconstruye con LF y el hash de datos no coincide; corre en la suite local completa): el caso
  con la semilla y los parámetros de `6506dbba3261` da su `resultado.json` campo por campo, con
  tolerancia 0 (valores normalizados a 12 cifras significativas, como se guardaron), sin pasar
  por el chequeo de `hash_codigo`.
