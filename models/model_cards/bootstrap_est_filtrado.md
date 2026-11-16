# Ficha de modelo · `bootstrap_est_filtrado` (motor del caso)

Datos de desarrollo con hash 641393c5df0c869b (trm.csv). Corridas: runs/backtest_desarrollo/ y runs/backtest_largo/.
Los rangos describen incertidumbre estadística; no son recomendaciones financieras.

**Estado:** NO supera a las líneas base en ningún horizonte. Se documenta porque es el **motor por
defecto del caso**: da trayectorias y es el de cobertura más cercana a la nominal. Sin confirmar:
falta la prueba final (y a 126 y 252 días esa prueba será solo descriptiva).

## Qué es
Bootstrap estacionario por bloques (Politis y Romano) sobre los residuos z = r/σ, con σ = EWMA(0,94).
Las trayectorias se reescalan con una volatilidad que parte de la del día de origen y vuelve a la de
largo plazo con persistencia ρ estimada (≈ 0,98). Longitud de bloque de Politis-White (máximo entre
la serie y su valor absoluto). 4000 simulaciones, semilla 20240501, reajuste cada 21 orígenes.

## Datos
Solo la TRM diaria desde 1991, banda incluida (conserva 1997-1999, 2008 y 2014-2015 como episodios).

## Supuestos
- El futuro se parece a bloques del pasado: no puede producir un movimiento mayor que los ya vistos (salvo por la escala).
- Rendimiento esperado cercano al promedio histórico; no predice dirección.
- La volatilidad vuelve a su promedio de largo plazo a la velocidad ρ.

## Métricas (desarrollo; 3493 orígenes a 1-63 días, 3304 a 126-252)
| horizonte | CRPS / mejor línea base | cobertura 90 % | cobertura 95 % | en el MCS |
|---|---|---|---|---|
| 1 | 0,983 | 0,900 | 0,951 | no |
| 5 | 0,996 | 0,902 | 0,952 | sí (con líneas base) |
| 21 | 0,994 | 0,917 | 0,958 | sí (con líneas base) |
| 63 | 1,052 | 0,902 | 0,946 | sí (con líneas base) |
| 126 | descriptivo | 0,867 | 0,904 | — (26 ventanas independientes) |
| 252 | descriptivo | 0,860 | 0,880 | — (13 ventanas independientes) |

A 1 día: VaR 1 % con 0,86 % y 0,94 % de violaciones (Kupiec p = 0,39 y 0,74); Basilea 93 % y 92 % de
ventanas en verde, ninguna en rojo; ES 97,5 % con Z2 = −0,10 y 0,20 (no rechaza).

## Cuándo falla
- **Violaciones en racimo**: al 5 % la independencia de Christoffersen se rechaza (p < 0,001). Acierta cuántas, no cuándo.
- **Horizontes largos**: a 126 y 252 días el intervalo del 95 % cubrió 0,90 y 0,88. Rangos probablemente estrechos.
- **Estrés largo**: en 2014-2015 (374 orígenes), a 63 días cubrió 0,848 del 95 %; en 2008, 0,891.
- **Precisión**: a 63 días su CRPS es 5 % peor que la caminata aleatoria: bandas bien cubiertas pero anchas.

## Cuándo no usarlo
- Como pronóstico de hacia dónde va el dólar: no tiene opinión de dirección.
- Para afirmar probabilidades a un año con precisión: con 13 ventanas independientes no se puede verificar.
- Ante un cambio de régimen sin precedente en la historia (otra banda, controles de capital).
- Sin decir, junto a cada cifra a 126 o 252 días, que la cobertura observada fue menor que la nominal.
