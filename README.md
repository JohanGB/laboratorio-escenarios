# Laboratorio de Escenarios

En el [portafolio](https://johangb.github.io) aparece como **Vektor FX**.

Proyecto de portafolio que responde, con la TRM (pesos por dólar), una pregunta práctica:
**¿qué rango de resultados es razonable esperar, y qué tan confiable es ese rango?**
El caso de uso es «compra de dólares»: comprar todo hoy frente a comprar en cuotas.

> **No es asesoría financiera.** Los rangos describen incertidumbre estadística; no son
> pronósticos ni recomendaciones. Las cifras de meta, número de compras y margen del caso
> son valores ilustrativos del autor.

## El resultado, sin adornos

El proyecto se diseñó para poder decir «no» con honestidad. Se probaron 17 modelos de
distribución del cambio diario y acumulado de la TRM (líneas base, GARCH/GJR/EGARCH, Markov,
regresión por cuantiles, LightGBM, bootstrap por bloques) con origen móvil y sin fugas de
información. Luego se corrió **una sola vez** una prueba final prerregistrada (2020-2026).

| Horizonte | Hipótesis prerregistrada | Resultado |
|---|---|---|
| 1 día | LightGBM por cuantiles mejora a la línea base (CRPS/base 0,977; p de Holm < 0,001) | **Confirmada**, mejora pequeña (≈ 2 %) |
| 5, 21 y 63 días | EWMA 0,94 mejora a su línea base | **No confirmada** (p de Holm 0,493) |
| 126 y 252 días | — | Solo descriptivo: caben 11 y 5 ventanas independientes |

- Solo a un día hay un modelo útil, y sus colas quedan cortas: sirve como pronóstico central,
  no como medida de riesgo extremo.
- A horizontes largos **ningún modelo supera a una línea base simple** y los rangos del motor
  pueden ser estrechos: en desarrollo la cobertura del 95 % fue 0,90 y 0,88; en la prueba final
  fue 0,992 y 0,932, pero con solo 11 y 5 ventanas independientes esa cifra no permite concluir
  nada. Se publican ambas.
- Los datos de la prueba final no son «nunca vistos»: el análisis exploratorio y el caso los
  mostraron antes del prerregistro. Está declarado en el reporte.

### La cifra que más cuidado merece

La probabilidad de que las compras en cuotas superen el presupuesto es **25,5 %**
(ventanas históricas), **31,5 %** (motor remuestreando solo la flotación) o **45,4 %**
(motor prerregistrado). Las tres difieren sobre todo por la deriva que cada método supone: el
motor prerregistrado arrastra, amplificada unas 2,1 veces, la depreciación de los años de
banda cambiaria (1991-1999, 23 % de los datos). **Ninguna tiene respaldo fuera de muestra** y
el reporte las presenta juntas. Se publicó el hallazgo en vez de esconderlo.

## Cómo se garantiza que no se hizo trampa

- **Prerregistro con candado por hash** (`docs/prerregistro.md`, etiquetas git
  `prerregistro-final` y `prerregistro-adenda-1`): modelos, hipótesis y métricas fijados antes
  de abrir los datos de prueba. El comando de la prueba final no corre si cambia el código, el
  entorno o los datos.
- **Corrida única** (`INICIADA.json` y `HECHO.json` con SHA-256 de cada resultado). Una
  corrida abortada por un fallo de programa se documentó como adenda y sus resultados parciales
  no se abrieron (`docs/decisiones.md`).
- **Cada cifra del caso** termina en un `#hash` que remite a su fuente, y dice qué evaluación
  fuera de muestra la respalda o «sin respaldo fuera de muestra».
- **Auditoría independiente** de la prueba final (`docs/auditoria_independiente.md`): sus
  hallazgos se corrigieron o quedaron cubiertos por pruebas (`tests/test_auditoria_h1.py`).
- 410 pruebas automáticas (`pytest`), incluidas pruebas de fuga de información; la integración
  continua de GitHub corre todas salvo las dos marcadas como lentas.

## Ejecutarlo (Windows, PowerShell)

```powershell
pip install -e ".[dev]"
pytest -q
$env:PYTHONPATH = "src"
python -m laboratorio.motor compra_dolares --trayectorias 10000 --semilla 20240501
```

**Reproducir la prueba final.** La verificación de hashes (`python -m laboratorio.backtest final
--verificar`) solo pasa con el código y el entorno tal como estaban al correrla. Hazlo en una copia
limpia de la etiqueta (`git checkout prerregistro-adenda-1`), con Python 3.11.9 y las versiones
exactas de [`requirements-prueba-final.txt`](requirements-prueba-final.txt):
`pip install -e ".[dev]" -c requirements-prueba-final.txt`. En la rama actual falla a propósito,
porque el motor del caso cambió después de la prueba (ver `docs/decisiones.md`).

Si falta `data/processed`, las pruebas lo reconstruyen al iniciar desde `data/raw` (versionado),
con `python -m laboratorio.datos.limpieza`; ninguna prueba se salta por falta de datos. Los
resultados de la prueba final (`runs/prueba_final*/`, archivos `.csv.gz`) no están en git por
tamaño; ver `docs/decisiones.md` para verificar sus SHA-256.

## Estructura

```
data/raw/            datos originales, inmutables
data/processed/      se regenera desde raw
data/respaldo/       resumen de la prueba final, con hash
docs/                prerregistro, decisiones, supuestos, uso de IA, estado
docs/prompts/        instrucciones de trabajo dadas a la IA, por versión
reports/             fase 0 (exploración), fase 2 (desarrollo), prueba final, caso
src/laboratorio/     datos · modelos · backtest · motor · reportes
tests/
```

Documentos clave: [prerregistro](docs/prerregistro.md) · [decisiones](docs/decisiones.md) ·
[supuestos](docs/supuestos.md) · [uso de IA](docs/uso_de_ia.md) ·
[auditoría independiente](docs/auditoria_independiente.md) ·
[reporte de la prueba final](reports/prueba_final.md) · [caso compra de dólares](reports/compra_dolares.md)

## Limitaciones

- Una sola serie (TRM) y un solo régimen de flotación de 27 años: pocos episodios de estrés.
- A 63 días o más hay muy pocas ventanas independientes; casi cualquier cobertura es «compatible».
- Las variables externas y las tasas entran por rezago; sus revisiones no se modelan.
- Proyecto personal de portafolio, sin respaldo de ninguna entidad financiera.

## Licencia

- **Código** (`src/`, `tests/` y archivos de configuración como `pyproject.toml`,
  `requirements-prueba-final.txt` y `.github/`): [MIT](LICENSE).
- **Reportes, documentación y figuras** (`reports/`, incluidas sus figuras, y `docs/`):
  [CC BY 4.0](LICENSE-docs).
- **Resultados y supuestos del proyecto** (`runs/`, `data/respaldo/` y `data/supuestos/`):
  [CC BY 4.0](LICENSE-docs), como los reportes. `runs/` y `data/respaldo/` se calculan a partir
  de los datos públicos de abajo; la licencia cubre lo que aporta el proyecto, y las cifras
  de origen siguen sujetas a los términos de sus fuentes.
- **Datos de `data/raw/`**: no les aplica ninguna de las dos. Conservan los términos de sus
  fuentes (Superintendencia Financiera de Colombia, Banco de la República, DANE y FRED del
  Banco de la Reserva Federal de San Luis); consúltalos en cada fuente antes de reutilizarlos.
  Lo mismo vale para `data/processed/`, que se deriva de ellos.
