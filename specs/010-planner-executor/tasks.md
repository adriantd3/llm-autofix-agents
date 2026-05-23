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

- [x] Ejecutar batches end-to-end con BugsInPy hard (4 runs, gemma4-26b-ctx32k).
- [ ] Comparar resultados con handoff en youtube-dl-1.
- [x] Registrar evidencia y lecciones en spec.md (sección Context Engineering Fixes).

## Context Engineering Fixes (2026-05-23)

- [x] Identificar error 1: `transfer_to_executor` inexistente en planner instructions.
- [x] Fix error 1: reemplazar por "escribe tu plan como texto plano".
- [x] Identificar error 2: `FORBIDDEN: Producing the final iteration record` incorrecto para planner.
- [x] Fix error 2: eliminar instrucción confusa, añadir restricción correcta.
- [x] Identificar error 3: planner produce output vacío en bugs con fix obvio (sin primera tool call).
- [x] Fix error 3: añadir `Your FIRST response MUST be a tool call` al planner.
- [x] Validar: 145 tests pasan sin regresiones.
- [x] Resultado: 1/4 → 3/4 en batch hard BugsInPy.
