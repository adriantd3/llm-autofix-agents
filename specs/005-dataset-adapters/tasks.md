# TASKS SPEC-005: Dataset Adapter Architecture

## Estado global
- Spec: SPEC-005
- Subhito activo: SH1 (unico subhito para esta spec)
- Estado: Completado

## SH1 - Refactor de ejecucion batch dataset-agnostic
### Objetivo
Eliminar logica dataset-specific de BatchRunner y habilitar ejecucion de multiples datasets a traves de adapters normalizados.

### Tasks
- [x] SH1-T01 Actualizar `docker-compose.yml` para montar `./benchmark-workspaces:/benchmark-workspaces`.
- [x] SH1-T02 Refactorizar `repo_source.prepare_target_repository` para aceptar `branch: str | None` y directorios locales.
- [x] SH1-T03 Actualizar `ContainerInstantiation` para permitir `RUN_BRANCH` opcional.
- [x] SH1-T04 Actualizar `main.py` para mensaje de error consistente con branch opcional.
- [x] SH1-T05 Refactorizar esquema `DatasetConfig`: agregar `type`, `repository: RepositoryConfig | None`, `test: TestConfig | None`, `tooling`.
- [x] SH1-T06 Refactorizar esquema `BugEntry`: hacer `program`/`test` opcionales, agregar `metadata`.
- [x] SH1-T07 Implementar `PreparedExecutionCase` (frozen dataclass) con host/container workspace, prompt_variables, cleanup_paths.
- [x] SH1-T08 Implementar `DatasetPreparationContext` con batch_id, workspace roots, dataset, batch config.
- [x] SH1-T09 Implementar `DatasetAdapter` Protocol.
- [x] SH1-T10 Implementar `DatasetAdapterRegistry` con `register`/`get`/`available_types`.
- [x] SH1-T11 Implementar `QuixBugsAdapter` con shallow clone por caso.
- [x] SH1-T12 Implementar `BugsInPyAdapter` con checkout/compile/test configurable.
- [x] SH1-T13 Refactorizar `BatchRunner` para usar adapter pattern.
- [x] SH1-T14 Refactorizar `generate_prompt` para usar `case.prompt_variables`.
- [x] SH1-T15 Implementar cleanup per-case inmediato tras ejecucion.
- [x] SH1-T16 Implementar handling de preparation failure como `infra_failure` por caso.
- [x] SH1-T17 Crear configs de ejemplo: `configs/datasets/quixbugs.yml`, `configs/datasets/bugsinpy.yml`, `configs/batches/quixbugs-smoke.yml`, `configs/batches/bugsinpy-smoke.yml`.
- [x] SH1-T18 Actualizar dataset YAML existente `datasets/quixbugs.yaml` al nuevo esquema.
- [x] SH1-T19 Crear dataset YAML `datasets/bugsinpy.yaml` con smoke case.
- [x] SH1-T20 Agregar `.gitignore` entry para `benchmark-workspaces/`.
- [x] SH1-T21 Escribir tests unitarios para nuevo schema, adapters, registry, prompt generation, repo_source local.
- [x] SH1-T22 Validar dry-run con configs QuixBugs existentes.
- [x] SH1-T23 Validar lint limpio (ruff check).
- [x] SH1-T24 Ejecutar suite completa de tests (159 pasan).
- [x] SH1-T25 Crear `docker/bugsinpy.Dockerfile` con herramientas BugsInPy clonadas desde `soarsmu/BugsInPy`.
- [x] SH1-T26 Agregar servicio `bugsinpy-runner` a `docker-compose.yml` con volumenes y permisos correctos.
- [x] SH1-T27 Agregar `runner_service` a `PreparedExecutionCase` (default `"runner"`).
- [x] SH1-T28 Actualizar `QuixBugsAdapter` para usar `runner_service="runner"`.
- [x] SH1-T29 Actualizar `BugsInPyAdapter` para ejecutar checkout/compile dentro de contenedores `bugsinpy-runner`.
- [x] SH1-T30 Actualizar `BugsInPyAdapter` para usar `runner_service="bugsinpy-runner"`.
- [x] SH1-T31 Actualizar `BatchRunner._docker_run` para usar `case.runner_service`.
- [x] SH1-T32 Actualizar `BatchRunner._docker_build` para construir todas las imagenes.
- [x] SH1-T33 Validar QuixBugs real end-to-end sigue funcionando.
- [x] SH1-T34 Validar BugsInPy real end-to-end (`youtube-dl-2`) con preparacion y ejecucion en Docker.

### Done cuando
- `BatchRunner` depende unicamente de `PreparedExecutionCase`, no de campos dataset-specific.
- QuixBugs y BugsInPy se preparan a traves de sus adapters sin logica condicional en el runner.
- Un contenedor Docker efimero se lanza por bug con workspace montado.
- Tests unitarios cubren schema, adapters, registry y prompt generation.
- Lint limpio y suite completa en verde.

## Lecciones aplicadas de specs anteriores
- Aplicada leccion 2026-05-02 (sandbox Docker): el agente siempre corre dentro de contenedor efimero; host nunca ejecuta logica del agente.
- Aplicada leccion 2026-05-02 (no ejecutar en repo de desarrollo): workspaces aislados bajo `benchmark-workspaces/`, nunca `$(pwd)`.