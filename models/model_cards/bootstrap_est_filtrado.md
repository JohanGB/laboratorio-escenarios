# Ficha de modelo · `bootstrap_est_filtrado` (motor del caso)

Datos de desarrollo con hash 641393c5df0c869b (trm.csv). Corridas: runs/backtest_desarrollo/ y runs/backtest_largo/.
Los rangos describen incertidumbre estadística; no son recomendaciones financieras.

**Estado (actualizado el 16-nov-2026, tras la prueba final):** NO supera a las líneas base en ningún
horizonte, ni en desarrollo ni en la prueba final. Se documenta porque es el **motor del caso**: da
trayectorias y fue el de cobertura más cercana a la nominal en desarrollo. No tenía hipótesis
confirmatoria en la prueba final: allí solo se midió la cobertura de su intervalo del 95 %
(a 126 y 252 días, descriptiva).

## Qué es
Bootstrap estacionario por bloques (Politis y Romano) sobre los residuos z = r/σ, con σ = EWMA(0,94).
Las trayectorias se reescalan con una volatilidad que parte de la del día de origen y vuelve a la de
largo plazo con persistencia ρ estimada (≈ 0,98). Longitud de bloque de Politis-White (máximo entre
la serie y su valor absoluto). 4000 simulaciones, semilla 20240501, reajuste cada 21 orígenes.

## Datos
Solo la TRM diaria desde 1991, banda incluida (conserva 1997-1999, 2008 y 2014-2015 como episodios).

## Supuestos
- El futuro se parece a bloques del pasado: no puede producir un movimiento mayor que los ya vistos (salvo por la escala).
- **Deriva implícita hacia arriba.** No está construido para predecir dirección, pero sus trayectorias
  no están centradas en cero: la mediana de la TRM a 252 días queda ≈ 9 % por encima de la de hoy
  (reports/compra_dolares.md, sección 4). Causa: al dividir cada rendimiento por la volatilidad de
  su época y multiplicarlo por la de hoy, la depreciación de los años de banda cambiaria (23 % de
  las observaciones, baja volatilidad) entra amplificada unas 2 veces. Remuestreando solo la
  flotación la mediana queda ≈ 2 % por encima (análisis posterior, no confirmatorio).
- La volatilidad vuelve a su promedio de largo plazo a la velocidad ρ.

## Métricas de desarrollo (2005-2019; 3493 orígenes a 1-63 días, 3304 a 126-252)
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

## Prueba final (2020-01-03 a 2026-08-12; reports/prueba_final.md)
| horizonte | CRPS / línea base del horizonte | cobertura 95 % | ventanas independientes | intervalo de la cobertura |
|---|---|---|---|---|
| 1 | 0,994 | 0,950 | 1564 | 0,94 – 0,96 |
| 5 | 1,002 | 0,961 | 313 | 0,93 – 0,98 |
| 21 | 1,028 | 0,968 | 74 | 0,91 – 1,00 |
| 63 | 1,110 | 0,960 | 25 | 0,80 – 1,00 |
| 126 | descriptivo | 0,992 | 11 | 0,72 – 1,00 |
| 252 | descriptivo | 0,932 | 5 | 0,48 – 1,00 |

A 63, 126 y 252 días hay tan pocas ventanas independientes que «0,95 cabe en el intervalo» no
prueba que la banda esté bien calibrada. A 1 día, fuera del MCS (p = 0,025); dentro a 5, 21 y 63,
junto con las líneas base.

**Análisis posterior (no confirmatorio)**, data/respaldo/prueba_final.json: proporción de veces
que la TRM real quedó bajo la mediana del modelo (lo esperado es 0,50): 0,542; 0,568; 0,620;
0,663; 0,710 y 0,801 a 1, 5, 21, 63, 126 y 252 días. A 252 días quedó bajo el límite inferior el
6,8 % de las veces y sobre el superior el 0,0 % (lo esperado es 2,5 % por lado). Apunta a una
banda corrida hacia arriba, como la que produce la deriva implícita; a 63, 126 y 252 días es un
indicio, no una prueba, y un solo periodo no basta para atribuirlo a esa causa.

## Cuándo falla
- **Centro de la distribución**: la mediana arrastra la deriva implícita (ver Supuestos). La cobertura
  del intervalo del 95 % respalda los límites, no la mediana.
- **Violaciones en racimo**: al 5 % la independencia de Christoffersen se rechaza (p < 0,001). Acierta cuántas, no cuándo.
- **Horizontes largos**: en desarrollo, a 126 y 252 días el intervalo del 95 % cubrió 0,90 y 0,88; en la
  prueba final, 0,99 y 0,93 con 11 y 5 ventanas independientes. No se puede decir si los rangos son
  estrechos o anchos.
- **Estrés largo**: en 2014-2015 (374 orígenes), a 63 días cubrió 0,848 del 95 %; en 2008, 0,891.
- **Precisión**: a 63 días su CRPS es 5 % peor que la caminata aleatoria: bandas bien cubiertas pero anchas.

## Cuándo no usarlo
- Como pronóstico de hacia dónde va el dólar: su deriva hacia arriba es un artefacto del filtrado y de
  los años de banda, no una opinión de dirección, y en la prueba final la TRM real quedó bajo su
  mediana más de la mitad de las veces.
- Para leer su mediana, su costo esperado o una probabilidad de «superar el presupuesto» como cifra
  única: cambian mucho con la muestra que se remuestrea (45 % frente a 32 % en el caso).
- Para afirmar probabilidades a un año con precisión: con 13 ventanas independientes no se puede verificar.
- Ante un cambio de régimen sin precedente en la historia (otra banda, controles de capital).
- Sin decir, junto a cada cifra a 63, 126 o 252 días, cuántas ventanas independientes la respaldan.
