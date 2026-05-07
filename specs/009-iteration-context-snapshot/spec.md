# Spec 009: Iteration Continuation Snapshot

## Objetivo

Mejorar el contexto de iteraciones 2+ para que el agente continue con evidencia real del runtime, evitando perder tiempo reconstruyendo lo ya hecho.

## Contexto

El prompt de iteraciones posteriores solo incluye un resumen breve del agente y una instruccion generica. Cuando el agente arranca con contexto limpio, esto causa re-trabajo y degradacion progresiva.

## Alcance

- Incluir un snapshot de continuidad basado en evidencia del runtime.
- Mostrar el ultimo resultado de tests (compactado) y los archivos cambiados observados.
- Distinguir claramente entre lo que el agente reporto y lo que el runtime observo.
- Mantener el prompt compacto (sin diff completo).

## Cambios

- Nuevo snapshot con seccion "Observed continuation snapshot (runtime evidence)".
- `build_iteration_input` incluye summary agent-reported + snapshot runtime evidence.
- Guidance explicita para que `notes` incluya bullets breves: inspected, attempted, changes, results, next.

## No Alcance

- No incluir diff completo ni excerpt en el prompt.
- No modificar la politica de validacion ni el flujo de tests.

## Validacion

- Tests unitarios de iteracion actualizados.
- E2E: `make batch` con `batches/quixbugs-mono-local-sample.yaml` y verificacion manual de `live.md`.
