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
