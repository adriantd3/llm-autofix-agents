# Spec 008: Limpieza de Ejecución Legada Single-Run

## Objetivo

Eliminar todo el flujo de ejecución legada (`autofix run`) que dependía de variables de entorno RUN_*, ahora que toda la ejecución se orquesta via batch config.

## Contexto

La arquitectura anterior permitía:
- Ejecución directa con `autofix run` usando variables de entorno RUN_REPOSITORY, RUN_BRANCH, RUN_ARCHITECTURE, etc.
- Preparación de repositorio vía `prepare_target_repository()` dentro del CLI host.
- Contrato `ContainerInstantiation` para cargar config desde env.

Ahora:
- **Todo se ejecuta via batch config YAML** (`autofix batch <config.yaml>`)
- **Batch runner** prepara workspaces y lanza Docker Compose por cada caso
- **ContainerInstantiation** solo se necesita como contrato interno dentro del runtime Docker
- **prepare_target_repository** se usa en dataset adapters para preparar workspaces locales

## Cambios implementados

### 1. Eliminar comando `autofix run` de main.py

**Archivo**: `src/llm_autofix_agents/main.py`

- Remover `_RUNTIME_CONTRACT_KEYS` constante (no se usa más)
- Remover `_has_runtime_contract_env()` función (solo verificaba contrato de run)
- Remover `_run_run()` función completa (70+ líneas)
- Remover condición `if args.command_name == "run"` de `app()`
- Remover `subcommands.add_parser("run", ...)` de `_build_parser()`
- Remover imports: `ContainerInstantiation`, `RunInput`, `prepare_target_repository`

Mantener:
- `_run_batch()` y todo lo relacionado con batch
- `_configure_logging()` (usado por batch)
- `_resolve_optional_text()` (para parsing general)
- `_hard_exit()` (usado en app)

### 2. Mantener ContainerInstantiation como contrato interno

**Archivo**: `src/llm_autofix_agents/contracts.py`

- `ContainerInstantiation` se mantiene como clase (es el contrato que lee el runtime Docker).
- Removido de exports públicos si estaba (no debería ser importado por CLI host, solo por runtime).
- Tests de `ContainerInstantiation` se actualizan para reflejar que es legado/interno.

### 3. Mantener prepare_target_repository para adapters

**Archivo**: `src/llm_autofix_agents/repo_source.py`

- Se mantiene intacta (usada por dataset adapters en batch runner).
- Tests existentes no cambian.

### 4. Actualizar tests

**Archivos**: `tests/test_main.py`, `tests/test_contracts.py`

- Remover 4 tests de `_run_run` de `tests/test_main.py`.
- **Mantener** tests de `ContainerInstantiation.from_env` en `tests/test_contracts.py` (es el contrato interno que usa el runtime Docker).
- Agregar nuevos tests de `batch` command en `tests/test_main.py` para validar parser y `_run_batch()`.

## Rationale

- **Claridad**: El flujo ahora es unidireccional: `autofix batch YAML` → prepara workspaces → lanza Docker → ejecuta.
- **Menos código**: Eliminadas ~80 líneas de código legado + funciones helper innecesarias.
- **Separación de responsabilidades**: CLI host solo orquesta batches; runtime Docker maneja contrato RUN_*.
- **Facilita evolución**: Futuras arquitecturas solo agregan batches YAML; no tocan CLI.

## Cambios por archivo

| Archivo | Cambios |
|---------|---------|
| `src/llm_autofix_agents/main.py` | Eliminar `_run_run`, `_RUNTIME_CONTRACT_KEYS`, `_has_runtime_contract_env`, comando "run", imports legados |
| `tests/test_main.py` | Remover 4 tests de `_run_run` |
| `tests/test_contracts.py` | Remover tests de `ContainerInstantiation.from_env` (o marcar como legacy) |

## Validación

- [ ] `make lint` en verde
- [ ] `make typecheck` en verde
- [ ] Tests unitarios en verde
- [ ] Verificar que `autofix batch` aún funciona con batch config

## Corrección post-implementación

El comando `autofix run` fue eliminado del CLI, pero los Dockerfiles (`runtime.Dockerfile`, `bugsinpy.Dockerfile`) aún usaban `CMD ["uv", "run", "autofix", "run"]` como entrypoint del contenedor. Esto causaba que el batch runner lanzara contenedores que fallaban inmediatamente con:

```
autofix: error: argument command_name: invalid choice: 'run' (choose from batch)
```

### Solución aplicada

1. **Nuevo módulo `batch/executor.py`**: encapsula la lógica de ejecución single-run (lo que antes hacía `_run_run()` en `main.py`). Es un módulo `__main__` puro, no un comando CLI.
2. **Dockerfiles actualizados**: `CMD` ahora apunta a `uv run python -m llm_autofix_agents.batch.executor`.
3. **`BatchRunner._docker_run` explícito**: en lugar de depender del `CMD` del Dockerfile, el runner pasa el comando directamente al contenedor, haciendo el contrato explícito y robusto.

### Arquitectura resultante

```
main.py              → CLI usuario: solo `autofix batch`
batch/runner.py      → Orquesta ejecución de múltiples bugs
batch/executor.py    → Ejecuta un único bug dentro del contenedor
```

Esta separación es más clara: el CLI host solo orquesta batches; el runtime Docker ejecuta el módulo directamente sin pasar por argparse.

## Notas para futuro

- Si se necesita ejecución ad-hoc en el futuro, usar `autofix batch` con un YAML single-case en lugar de resucitar `autofix run`.
- El runtime Docker sigue usando `ContainerInstantiation` vía `RUN_*` env vars, que está bien (es interno).
