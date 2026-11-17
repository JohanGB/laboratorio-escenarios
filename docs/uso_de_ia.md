# Uso de IA

Este proyecto se construyó con ayuda de modelos de IA (Claude, de Anthropic) mediante Claude Code.
El autor define las preguntas, aprueba las decisiones y ejecuta las corridas finales.

## Qué hizo la IA
- Escribió el código de datos, modelos, backtest, motor Monte Carlo y reportes.
- Propuso el diseño del protocolo y del prerregistro, y revisó adversarialmente versiones del
  borrador (candado por hash, caché, interrupciones, fin de línea).
- Redactó los documentos, que el autor leyó y aprobó.

## Qué decidió y verificó el autor
- La pregunta, el caso de uso, los supuestos ilustrativos y los umbrales del prerregistro.
- Cerrar el prerregistro y hacer los commits y las etiquetas.
- Correr en su propio equipo la prueba final y la simulación de 10.000 trayectorias, y comprobar
  que los SHA-256 coinciden.

## Límites que se declaran
- Los modelos de IA que escribieron el código conocen en términos generales la TRM de 2020-2026.
  La prueba final **no es una muestra ciega**; lo que nadie había visto es cómo les iba a los
  modelos prerregistrados en ella.
- Una pasada de revisión adversarial con un modelo distinto sobre el código final queda
  pendiente de documentar si se hace.
- Nada de esto es asesoría financiera.
