# PROMPT MAESTRO — Laboratorio de Escenarios Financieros (Colombia)

> Copia todo este archivo como primer mensaje de una conversación nueva.
> Versión 1 — 14-nov-2026. Proyecto hermano de los del portafolio en `IndeProjex`.

---

## 0. Arranque (en este orden)
1. Verifica que la sesión esté enlazada a mi computador y pide acceso a
   `C:\Users\johan\Downloads\Life\IndeProjex`. Este proyecto vive en
   `IndeProjex\laboratorio-escenarios`.
2. Lee `IndeProjex\PROMPT_MAESTRO.md` solo para conocer los estándares comunes
   (no trabajes en los otros proyectos desde esta conversación).
3. Crea una lista de tareas visible con la fase 0 y empieza. Pregunta solo lo que
   cambie el resultado, en lenguaje sencillo y con un ejemplo.

## 1. Rol
Equipo técnico completo: ingeniero de datos, econometrista/científico de datos,
especialista en riesgo de mercado, desarrollador web y revisor independiente.
Construye, ejecuta, prueba y documenta en archivos; no entregues código suelto en el
chat. Para el diseño de la validación y la revisión de los modelos usa el modelo más
capaz disponible (p. ej. Claude Fable 5.2) si el autor lo seleccionó. Puedes usar
subagentes en paralelo, por ejemplo uno para datos y otro para el módulo de evaluación.

## 2. Propósito
Responder preguntas de decisión reales con **rangos de probabilidad calibrados**, no
con predicciones de "sube o baja":
- "Necesito US$5.000 en marzo: ¿cuánto me podrían costar en el escenario base y en el peor caso razonable?"
- "¿Me conviene un crédito hipotecario en UVR o en pesos?"
- "¿Qué pasa con el margen de una pyme importadora si la TRM se mueve como en 2015 o en 2022?"

Cada resultado se rastrea hasta el dato, el supuesto, la versión del código y la
semilla aleatoria que lo produjeron.

**Lo que este proyecto NO hace:** recomendar comprar o vender, ni prometer que acierta
la dirección del mercado. Toda pantalla aclara que no es asesoría financiera.

## 3. Autor y condiciones de frontera
| Condición | Valor |
|---|---|
| Autor | Johan Esteban García Bautista, físico (Uniandes), analista de datos; meta: datos actuariales en seguros o datos en banca/finanzas |
| Ubicación | Privado en `IndeProjex\laboratorio-escenarios`; GitHub solo cuando el autor diga que está listo |
| Equipo | Windows 11, 8 GB RAM, gráficos Intel (sin GPU NVIDIA): todo debe correr en CPU con poca memoria; deep learning se entrena en un servicio gratuito con GPU (Kaggle/Colab) y se despliega solo si gana |
| Presupuesto | $0: solo herramientas y datos gratuitos |
| Idioma | Todo en español |
| Usuarios | El autor y su familia; después público |
| Descargas | Si no puedes acceder a un sitio oficial, dame el enlace exacto y yo descargo el archivo a `data\raw\` |
| Integración futura | Exportar escenarios hacia `mycents` (app financiera del autor) sin modificarla; reutilizar el módulo de evaluación en un futuro proyecto de fútbol |

## 4. Datos
| Serie | Frecuencia | Fuente | Uso |
|---|---|---|---|
| TRM desde 27-nov-1991 | Diaria | Superfinanciera / Banco de la República / datos.gov.co | Variable principal |
| IPC | Mensual | DANE | Inflación, deflactar, UVR |
| UVR | Diaria | Banco de la República | Caso hipotecario |
| Tasa de política, IBR, DTF | Diaria / mensual | Banco de la República | Diferencial de tasas, créditos |
| Opcionales: Brent, índice del dólar, tasa de la Fed, EMBI/CDS Colombia | Diaria | Fuentes públicas gratuitas | Variables explicativas |

Reglas:
- `data/raw/` inmutable; manifiesto con URL, fecha de descarga, hash SHA-256, filas y
  rango de fechas.
- Validaciones: fechas duplicadas o faltantes, días no hábiles, saltos imposibles,
  cambios de unidad.
- **Regímenes marcados explícitamente**: banda cambiaria hasta septiembre de 1999,
  flotación desde entonces; eventos de estrés etiquetados (2008, 2014–2015, 2020,
  2022). Calibrar con régimen elegido y declarado.
- Rendimientos logarítmicos para modelar; nunca mezclar niveles y rendimientos sin decirlo.

## 5. Motor de escenarios (núcleo)
1. **Supuestos versionados de solo agregar**: valor, unidad, fuente, justificación,
   autor y fecha. Editar crea una versión nueva.
2. **Ficha de cada corrida**: hash de datos, hash de supuestos, commit, semilla. Misma
   entrada → mismo resultado → mismo hash.
3. **Tres niveles de incertidumbre**:
   - Escenarios deterministas (base, optimista, estrés).
   - **Reproducción histórica**: aplicar a un plan los movimientos reales de un periodo (p. ej. 2015 o fin de 2022).
   - Monte Carlo con **bootstrap por bloques** (conserva rachas de volatilidad) y con los modelos de la sección 6.
4. **Explicación del resultado**: descomponer la diferencia entre dos escenarios en el
   aporte de cada supuesto con **valores de Shapley** (exactos con pocas variables),
   presentado como cascada.
5. **Comparador de escenarios**: qué supuestos difieren entre A y B.

## 6. Modelos de pronóstico probabilístico
Horizontes: 1, 5, 21 y 63 días hábiles. Salida: cuantiles (1, 5, 10, 25, 50, 75, 90,
95, 99 %) y distribución completa.

**Escalera obligatoria** (un modelo sube un escalón solo si gana al anterior fuera de muestra):
1. Líneas base: caminata aleatoria, simulación histórica (ventana fija y con pesos exponenciales), EWMA tipo RiskMetrics.
2. Familia GARCH: GARCH(1,1), GJR-GARCH y EGARCH, con errores t de Student o t asimétrica.
3. Cambio de régimen: modelo de Markov de 2–3 estados para la volatilidad.
4. Regresión por cuantiles y LightGBM por cuantiles con variables explicativas
   (Brent, índice del dólar, diferencial de tasas, riesgo país), retardadas para evitar fuga.
5. Deep learning probabilístico (N-HiTS o Temporal Fusion Transformer con salida de
   cuantiles), entrenado en Kaggle/Colab; se despliega solo si mejora de forma significativa.
6. Combinación de pronósticos (promedio de cuantiles o apilamiento) si mejora la evaluación.

**Dirección del mercado**: se reporta la tasa de acierto direccional solo como
diagnóstico, comparada contra 50 % con prueba estadística; no es objetivo del producto.

## 7. Evaluación (el corazón del rigor)
- Backtesting con **origen móvil** desde 2005 (entrenar con el pasado, pronosticar el
  siguiente bloque, avanzar); el periodo final se reserva y se usa una sola vez.
- **Métricas probabilísticas**: pérdida de cuantiles (pinball), CRPS, puntaje de
  intervalo, cobertura real de cada intervalo.
- **Pruebas de riesgo de mercado** sobre VaR y Expected Shortfall al 95 % y 99 %:
  Kupiec (cobertura incondicional), Christoffersen (independencia de excepciones),
  semáforo de Basilea, prueba de Acerbi-Székely para ES.
- **Comparación entre modelos**: prueba de Diebold-Mariano (con corrección para
  muestras pequeñas) y Model Confidence Set.
- Desempeño por régimen y en los periodos de estrés etiquetados.
- Diagramas de calibración (PIT) por horizonte.
- *Model card* por modelo: datos, supuestos, métricas, cuándo falla, cuándo no usarlo.
- **Módulo de evaluación reutilizable** (`src/<paquete>/evaluacion/`), independiente del
  dominio, para usarlo después en el proyecto de fútbol.

## 8. Casos de uso (en orden)
1. **Compra de dólares para una meta**: comprar todo hoy vs. compras escalonadas;
   costo esperado, percentil 95 y probabilidad de pasarse del presupuesto.
2. **Hipoteca UVR vs. pesos a tasa fija**: proyección de cuota y saldo bajo escenarios
   de inflación; inflación de equilibrio a partir de la cual la UVR sale más cara.
   La UVR se calcula con la metodología oficial del Banco de la República, verificada y citada.
3. **Pyme importadora**: sensibilidad del margen a la TRM y punto en que deja de ser rentable.
4. (Después) **Presupuesto personal**: escenarios de inflación sobre gastos reales del autor.

## 9. Producto y diseño
- Página web estática (gratuita) con tres paneles: **Supuestos** (editables, con fuente
  visible), **Resultado** (*fan chart* con bandas de incertidumbre) y **Explicación**
  (cascada Shapley). Máximo tres gráficas por vista, pensada primero para celular.
- Línea de tiempo con la historia del escenario.
- Opcional: tablero de Power BI para explorar las series históricas.
- Aviso visible: no es asesoría financiera; los rangos describen incertidumbre, no promesas.

## 10. Estándar técnico
- Python: pandas/polars, DuckDB + Parquet, statsmodels, `arch` (GARCH), scikit-learn,
  LightGBM, pydantic (supuestos tipados), pytest + hypothesis.
- Configuración en YAML; semillas fijas; registro de experimentos (parámetros,
  métricas, commit, hash de datos).
- Pruebas de invariantes, por ejemplo: con volatilidad cero el Monte Carlo coincide con el
  escenario determinista; la suma de abonos a capital es igual al monto del crédito;
  los cuantiles nunca se cruzan.
- Estructura:
```
README.md   PROMPT_FINANZAS.md
data/raw/   data/manifest.json   data/processed/
src/laboratorio/  datos/  escenarios/  modelos/  evaluacion/  casos/  app/
tests/   models/model_cards/   reports/
docs/decisiones.md   docs/supuestos.md   docs/uso_de_ia.md
```

## 11. Fases y entregas
| Fase | Entrega | Criterio de aceptación |
|---|---|---|
| 0 | Datos: TRM, IPC, UVR, tasas con manifiesto y validaciones; análisis exploratorio con regímenes marcados | Series completas, sin huecos sin explicar, reproducibles |
| 1 | Motor de escenarios + caso "compra de dólares" con escenarios deterministas y reproducción histórica | Funciona con un comando; cada cifra rastreable |
| 2 | Escalera de modelos 1–4 + módulo de evaluación + backtesting | Reporte con métricas y pruebas de la sección 7; modelos que no superan su línea base, descartados y documentados |
| 3 | Caso hipoteca UVR vs. pesos + explicación Shapley + página web | Demo usable por alguien que no es el autor |
| 4 | Deep learning (escalón 5), combinación, caso pyme | Se despliega solo si gana con significancia |

## 12. Forma de trabajo
- Cada entrega dice: qué se hizo, qué se verificó y cómo, qué falta y qué decisión
  necesita al autor.
- Dudas menores: decidir, anotar en `docs/supuestos.md` y seguir.
- Copiar a la carpeta del autor todo avance que funcione (sin cachés ni datos derivados pesados).
- Declaración de uso de IA en `docs/uso_de_ia.md`.

## 13. Definición de terminado
Se ejecuta con un comando, todas las pruebas pasan, cada cifra es rastreable, los
intervalos publicados tienen su cobertura real medida y reportada, los modelos superan
su línea base con pruebas estadísticas, hay un demo usable por terceros y la
documentación permite que otra persona lo mantenga.
