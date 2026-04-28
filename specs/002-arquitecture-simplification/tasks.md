# SPEC-002 - Tasks

## Fase 1 - Simplificacion de flujo
- [ ] Consolidar `IterationRunner` con sus colaboradores (context builder, recorder, outcome handler).
- [ ] Reducir `AgentIterationContext` a campos esenciales para ejecucion.
- [ ] Mantener logs y telemetria sin perder datos.

## Fase 2 - Interfaz de configuracion
- [ ] Definir interfaz simple para crear agente y asignar tools (sin acoplarse a un patron multi-agente).
- [ ] Centralizar la ejecucion de agente en un helper reutilizable.
- [ ] Mantener el entrypoint actual con configuracion desacoplada de la arquitectura.

## Fase 3 - Ajustes de contrato
- [ ] Revisar contratos de iteracion para asegurar que no bloquean variantes futuras.
- [ ] Ajustar tests de flujo afectados por la simplificacion.

## Fase 4 - Validacion
- [ ] Verificar `autofix run` con una ejecucion basica local.
