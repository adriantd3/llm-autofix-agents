## Contexto del proyecto

Este pryecto tiene como objetivo la creación de un sistema de **autocorrección de errores en software** (APR) basado en LLMs y agentes, capaz de analizar fallos (tests, logs) y proponer modificaciones automáticas sobre el código.
El sistema ejecuta el proceso completo en entornos aislados mediante Docker, incluyendo ejecución de tests y verificación de resultados.
Se diseñan y comparan distintas arquitecturas (mono-agente y multi-agente) bajo un mismo entorno experimental.
El objetivo es evaluar cómo influyen la orquestación de agentes y el tipo de modelo en la eficacia, coste y robustez de la autocorrección.

Para tener una informacion completa sobre el contexto del proyecto, accede a la carpeta `docs`

## Flujo de trabajo - Spec Driven Development

Usar la carpeta `specs/` como registro de trabajo vivo:

- `specs/status.md`: lo hecho, en curso y siguiente.
- `specs/requirements.md`: requisitos confirmados y alcance.
- `specs/lessons.md`: errores cometidos por el camino de los que dejamos constancia para que no vuelvan a ocurrir.

Regla minima:

1. Leer `specs/status.md` al iniciar una tarea.
2. Implementar y validar los cambios.
3. Actualizar `specs/status.md` al cerrar la tarea. Esto debe hacerse únicamente se ha validado que se ha implementado todo correctamente, es funcional y el usuario confirma que todo funciona según lo esperado.
4. Si cambia el alcance del proyecto, actualizar `specs/requirements.md`.

Para elicitar, aclarar y priorizar requisitos de forma sistematica, usar el skill `requirements-elicitation`. Para planear e implementar usa y `python-design-patterns`.