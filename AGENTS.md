## Proyecto

Sistema de autocorreccion de errores (APR) con LLMs y agentes para analizar fallos (tests/logs), proponer parches y validarlos. El proyecto se usa como plataforma experimental para comparar arquitecturas de agentes y modelos.

Contexto funcional: `docs/general-definition.md` y `docs/anteproyecto.md`.

## SDD simple (imprescindible)

1. Usar `specs/` como registro minimo vivo.
2. Si `specs/` no existe, crearla con:
	- `specs/status.md` (Hecho / En curso / Siguiente)
	- `specs/requirements.md` (alcance confirmado)
	- `specs/lessons.md` (errores y aprendizaje)
3. Antes de implementar: revisar `specs/status.md`.
4. Despues de implementar: validar cambios y actualizar `specs/status.md`.
5. Si cambia el alcance: actualizar `specs/requirements.md`.

## Regla tecnica

Este proyecto usa **uv**: usar siempre `uv` para entorno, dependencias y ejecucion (`uv sync`, `uv add`, `uv run ...`).