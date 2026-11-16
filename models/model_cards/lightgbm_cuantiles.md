# Ficha de modelo · `lightgbm_cuantiles`

Datos de desarrollo con hash 641393c5df0c869b (trm.csv). Corrida: runs/backtest_desarrollo/lightgbm_cuantiles.json.
Los rangos describen incertidumbre estadística; no son recomendaciones financieras.

**Estado:** sobrevive solo a **1 día** (único modelo en el MCS, Holm p < 0,001). Sin confirmar: falta la prueba final.

## Qué es
Un modelo LightGBM por cuantil (11 niveles, de 1 % a 99 %) y por horizonte. Predice el rendimiento
estandarizado z = y/(σ·√h), con σ = volatilidad EWMA(0,94) conocida en el origen, y lo devuelve a
la escala original. Hiperparámetros fijados de antemano, sin ajuste con los datos: 150 árboles,
tasa 0,03, 7 hojas, mínimo 100 datos por hoja, submuestreo 0,8, λ = 5, semilla 20240501.

## Datos
- TRM diaria desde 1991 (la banda cambiaria entra, con su bandera). Ventana expansiva, reajuste cada 63 orígenes.
- 14 variables causales: volatilidad y rendimientos recientes de la TRM, distancia al máximo de un año,
  bandera de banda, Brent, dólar amplio, tasa de la Fed y tasa de política (con rezago de publicación).
- `dolar30` y `pol90` no existen antes de 2006 y 1998: entran como faltantes (docs/decisiones.md, N5).

## Supuestos
- La relación entre las variables y la distribución de mañana es estable en el tiempo.
- σ·√h es la escala correcta (razonable a 1 día; falla a 63, ver abajo).

## Métricas (desarrollo, 2005-01-04 a 2019-09-26, 3493 orígenes, h = 1)
| métrica | valor | referencia |
|---|---|---|
| CRPS (puntos porcentuales) | 0,3593 | mejor línea base 0,3730 (−3,7 %) |
| Cobertura del intervalo 90 % / 95 % / 98 % | 0,880 / 0,932 / 0,966 | nominal |
| Violaciones del VaR 1 % (baja / alza) | 1,9 % / 1,5 % | 1 %; Kupiec p < 0,001 y p = 0,004 |
| Violaciones del VaR 5 % (baja / alza) | 5,8 % / 6,2 % | 5 %; Kupiec p = 0,046 y p = 0,002 |
| Semáforo de Basilea, cola de baja | 51 % verde, 46 % amarillo, 3 % rojo | — |
| Acierto de signo de la mediana | 55,0 % | 50 %; Pesaran-Timmermann p < 0,001 |
| Expected Shortfall | no aplica | solo se entrena en los 11 niveles |

## Cuándo falla
- **Colas**: los cuantiles extremos quedan cortos en las dos direcciones (tabla). No mide riesgo extremo.
- **Crisis de 2008** (128 orígenes): CRPS 0,7725; mejor que la línea base (0,7868) pero peor que EGARCH (0,7595).
- **Más de 1 día**: a 5 días no se distingue de la línea base; a 21 y 63 es peor (1,052 y 1,137) por
  sobreajuste y, a 63, por la estandarización (reports/f3_lightgbm.md).

## Cuándo no usarlo
- Para cualquier horizonte mayor a 1 día, incluidos los del caso (126 y 252).
- Para VaR, ES o cualquier cifra de cola.
- Para simular trayectorias: da cuantiles por horizonte, no caminos.
- Si alguna de sus series externas deja de publicarse o cambia de definición.
