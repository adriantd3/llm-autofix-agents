# Tasks - Spec 010: Planner-Executor Architecture

## Implementacion

- [x] Crear `architectures/planner_executor.py` con pipeline planner → executor.
- [x] Crear instrucciones genericas para planner y executor.
- [x] Crear perfiles de tools planner y executor.
- [x] Registrar en factory y __init__.
- [x] Tests unitarios de factory dispatch y wiring.
- [x] Batch config para BugsInPy.

## Correccion handoff (reversion de overfitting)

- [x] Revertir max_turns, timeout, max_iterations a valores razonables.
- [x] Restaurar patcher tools (execute_command, run_test_target).
- [x] Simplificar patcher instructions (genéricos, sin truth table).

## Fix de infraestructura

- [x] Resolver circular import datasets.base → batch → datasets.base.

## Validacion pendiente

- [ ] Ejecutar `make batch BATCH_CONFIG=batches/bugsinpy-planner-executor-local.yaml`.
- [ ] Comparar resultados con handoff en youtube-dl-1.
- [ ] Registrar evidencia y lecciones en specs/lessons.md.
