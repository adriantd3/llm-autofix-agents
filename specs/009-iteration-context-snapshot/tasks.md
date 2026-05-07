# Tasks - Spec 009: Iteration Continuation Snapshot

## Implementacion

- [x] Añadir snapshot de continuidad basado en evidencia del runtime.
- [x] Actualizar prompt de iteraciones 2+ para incluir snapshot y clarificar agent-reported vs runtime evidence.
- [x] Añadir guidance de `notes` en el prompt inicial.
- [x] Actualizar tests de build_iteration_input.

## Validacion pendiente

- [x] `make batch batches/quixbugs-mono-local-sample.yaml`
- [x] Revisar `live.md` del run para confirmar el prompt y ausencia de excepciones runtime en el input
