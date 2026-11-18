# Supuestos

Lista de supuestos que condicionan los resultados. Los marcados «autor» son decisiones
editables; el resto salen de los datos o del protocolo.

## Datos
- **TRM (Superfinanciera)**: 1991-12-02 a 2026-11-14, 8.387 observaciones (≈ 20 por mes). Cada fila es una vigencia; el intervalo entre observaciones es de 1 día, 3 (fines de semana) u otro (festivos). No se anualiza ni se reescala por días.
- **Régimen** (autor): banda cambiaria hasta el 24-sep-1999; flotación desde el 25-sep-1999.
- **Periodos de estrés** (autor): crisis 2008 (2008-09-15 a 2009-03-31), petróleo 2014-2015 (2014-06-01 a 2015-12-31), covid 2020 (2020-02-20 a 2020-06-30) y estrés 2022 (2022-06-01 a 2022-12-31).
- Los datos crudos son inmutables y están versionados; los procesados se regeneran.

## Evaluación
- Origen móvil desde 2005-01-03, ventana expansiva, reajuste cada 21 días (LightGBM cada 63), purga y embargo según el horizonte máximo del modelo.
- Desarrollo 2005-2019; prueba final desde 2020-01-01, corrida una sola vez.
- Métrica principal: CRPS aproximado con 11 cuantiles. Comparación por Diebold-Mariano con corrección HLN; cuatro hipótesis ajustadas por Holm (α = 0,05).
- 126 y 252 días: solo descriptivos (11 y 5 ventanas independientes en la prueba).

## Caso «compra de dólares»
- Meta de 10.000 USD, 12 compras mensuales iguales y margen del 5 % sobre el costo de comprar hoy: **valores ilustrativos del autor**, no una situación real.
- Motor Monte Carlo: `bootstrap_est_filtrado`, 10.000 trayectorias, semilla 20240501.
- No se incluyen comisiones, impuestos, diferencia compra-venta ni el costo de oportunidad del dinero.
- La deriva de la TRM que supone cada método es el supuesto que más mueve la probabilidad de superar el presupuesto (25,5 %, 31,5 % o 45,4 %).

## Divisas (M1, Vektor FX)
- **Fuente**: FRED, tasas H.10 de la Reserva Federal (mediodía en Nueva York): `DEXUSEU` (USD por EUR), `DEXMXUS`, `DEXJPUS`, `DEXCHUS` (yuan en tierra, no CNH), `DEXSZUS` y `DEXBZUS` (X por USD, se invierten). Descargadas el 17-nov-2026; URL y SHA-256 en `data/raw/MANIFEST.csv`.
- **Cruce**: X/COP = TRM × (USD por X). Sin interpolar ni arrastrar: unión interna por fecha.
- **Alineación** (supuesto `divisas.desfase_fred` = −1 del registro): la TRM con fecha *t* (vigencia, de martes a sábado) se calcula con las operaciones del día hábil anterior, así que se cruza con el precio H.10 del día hábil (lunes a viernes) anterior a *t*. Elegido por calendario y comprobado con la correlación de rendimientos con datos hasta el 31-dic-2019: el desfase −1 es el de mayor |r| en las seis divisas (EUR −0,231; MXN −0,291; JPY +0,047; CNY −0,201; CHF −0,110; BRL −0,378; cifras del supuesto v1, hash `97dcd329487b…`, y con `#hash` propio en `reports/fase0_divisas.md`). Con el yen la correlación es débil en todos los desfases.
- **Días perdidos**: los festivos de EE. UU. eliminan la fila (≈ 1-2 % de las fechas de TRM por divisa; detalle en `data/processed/limpieza.json` y en `reports/fase0_divisas.md`).
- **Regímenes** (autor, editables en `datos/divisas.py`): CNY fijo hasta el 21-jul-2005 y flotación administrada después; CHF con piso de 1,20 por EUR del 6-sep-2011 al 14-ene-2015; BRL en flotación desde el 18-ene-1999; MXN desde el 22-dic-1994; EUR desde el 4-ene-1999. Durante la banda colombiana (hasta el 24-sep-1999) toda fila se marca `banda_cop`.
- **Saltos diarios > 8 %**: se listan en `data/validacion.json` para revisión manual y no se borran.
