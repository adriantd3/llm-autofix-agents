# SPEC-005: Dataset Adapter Architecture

## Metadata
- Fecha: 2026-05-02
- Estado: Completado
- Owner: adriantd3
- Spec activa para desarrollo: refactor de ejecucion batch dataset-agnostic

## Objetivo de la spec
- Refactorizar `autofix batch` para que diferentes datasets APR (QuixBugs, BugsInPy, SWE-bench Lite) se ejecuten a traves de un contrato normalizado `PreparedExecutionCase`.
- Eliminar logica dataset-specific de `BatchRunner`, agentes y runtime.
- Cada bug se ejecuta en un contenedor Docker efimero desde cero (sandbox model).

## Alcance confirmado
- Adapter pattern con `DatasetAdapter` (Protocol), `PreparedExecutionCase` y `DatasetPreparationContext`.
- Registry de adapters (`quixbugs`, `bugsinpy`).
- Refactor de `BatchRunner` para depender unicamente de `PreparedExecutionCase`.
- Refactor de esquema `DatasetConfig`/`BugEntry` con campos genericos y `metadata` para datos dataset-specific.
- Workspaces preparados bajo `./benchmark-workspaces/<batch_id>/<case_id>/` y montados en el contenedor.
- `RUN_BRANCH` opcional para workspaces locales montados.
- Prompt generation basada en `prompt_variables` proveidas por el adapter.
- Handling de errores de preparacion como `infra_failure` por caso sin detener el batch.
- Tests unitarios de adapters, registry, config schema y prompt generation.

## Fuera de alcance
- Implementacion de SWE-bench Lite adapter (dejado para fase posterior).
- Importacion completa de todos los bugs de BugsInPy (solo smoke case).
- Caching/reutilizacion de workspaces clonados.
- Instalacion de BugsInPy tools en el host (se ejecutan dentro de Docker).

## Registro completo de decisiones

### A) Modelo de ejecucion sandbox
- A1: El agente APR **nunca** ejecuta en el host. Cada bug obtiene un contenedor Docker fresco via `docker compose run --rm`.
- A2: El host solo orquesta: prepara workspace, captura error output pre-run, construye env vars, lanza contenedor, parsea resultado, limpia workspace.
- A3: Todo el trabajo del agente (git branches, file edits, tests) ocurre dentro del contenedor sobre un workspace montado por volumen.
- A4: Un contenedor por bug garantiza aislamiento completo: sin estado residual entre bugs.

### B) Contrato PreparedExecutionCase
- B5: Cada adapter produce un `PreparedExecutionCase` con `host_workspace` (ruta host) y `container_workspace` (ruta dentro del contenedor).
- B6: `host_workspace` debe vivir bajo `./benchmark-workspaces/<batch_id>/<case_id>/` para que Docker pueda montarlo.
- B7: `container_workspace` es `/benchmark-workspaces/<batch_id>/<case_id>/`.
- B8: El adapter define `prompt_variables`; `BatchRunner` no conoce nombres de variables como `{bug_id}` o `{program}`.
- B9: `cleanup_paths` permite al adapter registrar paths a limpiar tras el run.

### C) Esquema de configuracion
- C10: `DatasetConfig` ahora requiere `type` (string) para dispatch al adapter.
- C11: `DatasetConfig.repository` es `RepositoryConfig | None` (no obligatorio para todos los datasets).
- C12: `DatasetConfig.test` es `TestConfig | None` con `command_template`.
- C13: `DatasetConfig.tooling` es `dict[str, Any]` para comandos dataset-specific (ej. `bugsinpy-checkout`).
- C14: `BugEntry.program` y `BugEntry.test` son opcionales.
- C15: `BugEntry.metadata` almacena datos dataset-specific (ej. `project`, `bug_id`, `version` para BugsInPy).

### D) Adapters implementados
- D16: `QuixBugsAdapter`: requiere `repository.url` + `branch`; shallow clone por caso; prompt vars: `bug_id`, `program`, `test`, `test_command`, `dataset_name`.
- D17: `BugsInPyAdapter`: lee `metadata.project`, `metadata.bug_id`, `metadata.version`; ejecuta `checkout_command_template` + `compile_command` opcional; prompt vars extendidas con `project`, `bug_id_raw`, `version`.
- D18: Registry como dict simple con `register`/`get`/`available_types`. Sin metaprogramacion ni descubrimiento automatico.

### E) Local mounted workspaces
- E19: `repo_source.prepare_target_repository` acepta `branch: str | None`.
- E20: Si `repository` es un directorio local existente, se retorna directamente y se ignora `branch`.
- E21: Si es remoto, se clona y `branch` es obligatorio.
- E22: `ContainerInstantiation.branch` es `str | None`; `from_env` normaliza string vacio a `None`.

### F) Manejo de errores
- F23: Un fallo de preparacion en un caso produce `BugRunResult(status="infra_failure", error_message=...)` y continua el batch.
- F24: Solo fallos de Docker build o carga de configuracion detienen el batch completo.

### G) Servicios Docker dataset-specific
- G25: `runner` es el servicio generico para datasets que no necesitan herramientas adicionales (QuixBugs).
- G26: `bugsinpy-runner` es un servicio dedicado que extiende la imagen base con las herramientas `bugsinpy-*` clonadas desde `soarsmu/BugsInPy`.
- G27: Cada adapter declara `runner_service` en el `PreparedExecutionCase`; `BatchRunner` lo usa en `docker compose run`.
- G28: `BugsInPyAdapter` ejecuta `bugsinpy-checkout` y `bugsinpy-compile` dentro de contenedores `bugsinpy-runner`, no en el host.
- G29: El contenedor `bugsinpy-runner` hereda los volumenes del servicio (`/benchmark-workspaces`, `/results`) y corre con `--user $(id -u):$(id -g)` para permisos correctos sobre el workspace montado.
- G30: `/opt/bugsinpy` en la imagen tiene permisos `a+w` y `git config --system safe.directory` para permitir ejecucion como usuario no-root.

## Criterios de aceptacion de la spec
- [x] `BatchRunner` no contiene logica dataset-specific ni branches `if dataset.type == ...`.
- [x] `QuixBugsAdapter` prepara workspace clonado y produce `PreparedExecutionCase` valido.
- [x] `BugsInPyAdapter` prepara workspace con checkout en Docker y produce `PreparedExecutionCase` valido.
- [x] `DatasetConfig` carga desde YAML con nuevo esquema (`type`, `repository`, `test`, `tooling`, `metadata`).
- [x] `BugEntry` acepta campos opcionales y `metadata`.
- [x] Prompt generation usa `case.prompt_variables` sin hardcodear nombres de variables.
- [x] `RUN_REPOSITORY` apunta a workspace local montado (`/benchmark-workspaces/...`) con `RUN_BRANCH=""`.
- [x] Preparation error en un caso reporta `infra_failure` y no detiene el batch.
- [x] Tests unitarios pasan: adapters, registry, config schema, prompt generation, repo_source local.
- [x] Dry-run funciona con configs QuixBugs existentes y nuevas.
- [x] Lint limpio (ruff check sin errores).
- [x] BugsInPy no requiere `bugsinpy-*` en el host (ejecuta dentro de `bugsinpy-runner`).
- [x] `BatchRunner` usa `case.runner_service` para `docker compose run`.
- [x] Validacion real end-to-end: QuixBugs `gcd` y BugsInPy `youtube-dl-2` en success.

## Relacion con specs anteriores
- Depende de SPEC-001 (mono-agente baseline) y SPEC-003 (multi-agent handoff) para el runtime interno del contenedor.
- No modifica logica de agentes, arquitecturas ni observabilidad.
- Solo refactoriza la capa de orquestacion batch y preparacion de datasets.