# Spec 010: Arquitectura Planner-Executor

## Metadata
- Fecha: 2026-05-07
- Estado: En curso
- Owner: adriantd3
- Tipo: arquitectura multi-agente (planner-executor)

## Contexto

Tras analizar 8 ejecuciones del flujo handoff (4 agentes) con BugsInPy youtube-dl-1, se identificaron limitaciones estructurales que no son del modelo sino de la arquitectura:

1. **El patcher no handoffa al validator**: el modelo prefiere devolver texto en vez de llamar `transfer_to_validator`. Con `output_schema=None` (requerido para handoffs intermedios), el SDK permite terminar con texto libre.
2. **Fragmentacion del presupuesto de turns**: con 4 agentes, cada uno gasta turns reconstruyendo contexto. El patcher (fase critica) se queda sin turns o sin contexto.
3. **Perdida de contexto entre boundaries**: el `input_filter` transmite un resumen, pero el patcher pierde el test completo y el diff de cambios previos.
4. **Redundancia triage/localizer**: el localizer repite el trabajo del triage (releer codigo, re-ejecutar tests) consumiendo ~10 turns.

La solucion NO es "optimizar el handoff para este bug" (overfitting), sino crear una arquitectura genuinamente distinta que pueda compararse experimentalmente.

## Objetivo

Implementar una arquitectura planner-executor como cuarta opcion de arquitectura APR, seleccionable por configuracion, con filosofia de separacion de razonamiento y accion.

## Filosofia

La diferencia real entre las arquitecturas del proyecto:

| Arquitectura | Filosofia | Agentes | Control |
|---|---|---|---|
| mono_agent | Un agente hace todo | 1 | Maximo |
| multi_agent_handoff | Cada agente posee una fase | 4 (triage→localizer→patcher→validator) | Minimo (ownership distribuido) |
| multi_agent_orchestrator | Manager central delega a specialists | 1 manager + 3 tools | Centralizado |
| **planner_executor** | **Separacion razonamiento/accion** | **2 (planner→executor)** | **Equilibrado** |

La planner-executor es analoga a como trabajan los coding agents modernos (Claude Code, Copilot): primero entienden profundamente, luego actuan con autonomia completa.

## Principios de diseno (generalizabilidad)

1. **Sin overfitting a bugs concretos**: las instrucciones son genericas, no mencionan youtube-dl ni match_str.
2. **Autonomia del executor**: si el plan del planner falla, el executor puede adaptarse (hasta 2 reintentos).
3. **Planner con tools de ejecucion**: puede reproducir el bug y verificar hipotesis antes de planificar.
4. **Executor con toolset completo**: puede leer, editar, ejecutar, validar y reportar.
5. **Un solo boundary de handoff**: menos perdida de contexto que el handoff de 4 agentes.

## Arquitectura

### Planner
- **Responsabilidad**: Investigar, diagnosticar, producir un plan de reparacion completo.
- **Tools**: read, search, list, execute_command, run_test_target (puede reproducir el bug).
- **NO puede**: editar archivos.
- **Output**: handoff al executor con payload estructurado (diagnosis + plan exacto).

### Executor
- **Responsabilidad**: Ejecutar el plan, aplicar fix, validar con tests, reportar resultado.
- **Tools**: read, search, edit, execute, test, git (toolset completo).
- **Autonomia**: si el plan falla, puede adaptar el enfoque.
- **Output**: AgentFixIterationRecord (salida final estructurada).

## Cambios implementados

### Archivos nuevos
- `src/llm_autofix_agents/architectures/planner_executor.py`: modulo de arquitectura.
- `batches/bugsinpy-planner-executor-local.yaml`: configuracion de batch.

### Archivos modificados
- `src/llm_autofix_agents/agents/instructions.py`: PLANNER_INSTRUCTIONS, EXECUTOR_INSTRUCTIONS.
- `src/llm_autofix_agents/tools/profiles.py`: perfiles APR_PLANNER_TOOLS, APR_EXECUTOR_TOOLS.
- `src/llm_autofix_agents/architectures/factory.py`: registro de "planner_executor".
- `src/llm_autofix_agents/architectures/__init__.py`: export.
- `tests/test_architectures.py`: tests de factory dispatch y wiring.

### Cambios en handoff (reversion de overfitting)
- `batches/bugsinpy-handoff-local.yaml`: max_turns 35→25, timeout 600→300, max_iterations 5→3.
- `src/llm_autofix_agents/agents/instructions.py`: patcher instructions genéricos (sin truth table).
- `src/llm_autofix_agents/tools/profiles.py`: patcher tools restaurados (execute_command, run_test_target).

### Fix de circular import
- `src/llm_autofix_agents/batch/__init__.py`: lazy imports para BatchRunner y prompt (rompe cadena datasets.base → batch → datasets.base).

## Validacion

- 7 tests de arquitectura pasando (2 nuevos: factory dispatch + wiring).
- Lint limpio en todos los archivos nuevos/modificados.
- 7 failures pre-existentes en test suite (de cambios previos no commiteados, no relacionados).

## Criterios de aceptacion

- [x] La estrategia "planner_executor" se puede seleccionar por batch config.
- [x] Se registran en observabilidad ambos agentes (planner, executor) con su rol.
- [x] Tests unitarios validan factory dispatch y wiring de la arquitectura.
- [ ] Validacion end-to-end: `make batch BATCH_CONFIG=batches/bugsinpy-planner-executor-local.yaml`.
- [ ] Comparativa de resultados con handoff y mono_agent en al menos 1 caso.
