# SPEC-002 - Tasks

## Fase 1 - Simplificacion de flujo
- [X] Consolidar `IterationRunner` con sus colaboradores (context builder, recorder, outcome handler).
- [X] Reducir `AgentIterationContext` a campos esenciales para ejecucion.
- [X] Mantener logs y telemetria sin perder datos.

## Fase 2 - Interfaz de configuracion
- [X] Definir interfaz simple para crear agente y asignar tools (sin acoplarse a un patron multi-agente).
- [X] Centralizar la ejecucion de agente en un helper reutilizable.
- [X] Mantener el entrypoint actual con configuracion desacoplada de la arquitectura.

## Fase 3 - Ajustes de contrato
- [ ] Revisar contratos de iteracion para asegurar que no bloquean variantes futuras.
- [ ] Ajustar tests de flujo afectados por la simplificacion.

## Fase 4 - Validacion
- [ ] Verificar `make quixbugs-gcd-run` con un par de ejecuciones completas para garantizar el correcto funcionamiento del agente
