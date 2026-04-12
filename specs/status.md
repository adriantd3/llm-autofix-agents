# Estado

## Hecho
- Estructura base del proyecto disponible (uv, Makefile, lint, typecheck, entrypoint).
- Skill de elicitacion actualizado para exigir opciones recomendadas en cada pregunta.
- Registro completo de decisiones en SPEC-001.
- Lista de tasks por subhitos creada para SPEC-001.
- Convencion de carpetas por spec adoptada: specs/<NNN-slug>/{spec.md,tasks.md}.
- H39 cerrado con OA-001.A (versionado por run).
- Politica de red cerrada: internet libre con auditoria.
- SH1 completado: imagen base Docker, runner efimero, bind mount, limites dinamicos y smoke test con logs/timeout.
- SH2 completado: contratos Pydantic v2 para input/output, IDs reproducibles y modelo de errores con smoke de validacion.
- Validacion reforzada: pruebas unitarias base y pipeline `make validate` para lint, typecheck, tests y smoke Docker.

## En curso
- Spec activa: specs/001-mono-agente-entorno/spec.md
- Tasks activas: specs/001-mono-agente-entorno/tasks.md
- Subhito activo: SH3 - Flujo mono-agente baseline.
- Task activa: SH3-T01 Integrar openai-agents-sdk en version baseline.

## Siguiente
- Implementar SH3-T02 (localizacion heuristica por stacktrace/tests).
- Implementar SH3-T03 (iteracion max 3 con criterio de no progreso).
- Implementar SH3-T04 y SH3-T05 (parches multiarchivo + rechazo de regresiones).
