## Proyecto

Sistema de autocorreccion de errores (APR) con LLMs y agentes para analizar fallos (tests/logs), proponer parches y validarlos. El proyecto se usa como plataforma experimental para comparar arquitecturas de agentes y modelos.

Contexto funcional: `docs/general-definition.md` y `docs/anteproyecto.md`.

## SDD simple (imprescindible)

1. Usar `specs/` como registro minimo vivo.
2. Si `specs/` no existe, crearla con:
	- `specs/status.md` (Hecho / En curso / Siguiente)
	- `specs/requirements.md` (alcance confirmado)
	- `specs/lessons.md` (errores y aprendizaje)
3. Cada spec debe vivir en su propia carpeta con convencion `specs/<NNN-slug>/` y archivos minimos `spec.md` y `tasks.md`.
4. Antes de implementar: revisar `specs/status.md`.
5. Despues de implementar: validar cambios y actualizar `specs/status.md`.
6. Si cambia el alcance: actualizar `specs/requirements.md`.
7. Considerar siempre las lecciones aprendidas en `specs/lessons.md`

## Regla tecnica

Este proyecto usa **uv**: usar siempre `uv` para entorno, dependencias y ejecucion (`uv sync`, `uv add`, `uv run ...`).

Tambien usa **Makefile** para la ejecucion de ciertos comandos de manera sencilla (lint, checker, ejecucion del sistema...)

## Regla OpenAI Agents SDK (documentation-first)

Referencia oficial obligatoria (version 0.14+):
- https://openai.github.io/openai-agents-python/

Politica obligatoria para cualquier implementacion del flujo de agente:
1. Antes de implementar una capacidad nueva, verificar primero si ya existe en el SDK oficial.
2. Si la capacidad existe en el SDK, priorizar su uso directo sobre implementaciones ad-hoc.
3. Si la capacidad no existe o no es facilmente aplicabe a APR, implementar extension handcrafted y documentar por que.
4. Siempre revisar la documentacion teniendo en cuenta la version más actualizada (0.14+)

## Regla de disenio y calidad de codigo

Aplicar siempre, con cambios minimos y bien justificados:
1. Favorecer diseno modular con principios SOLID (en especial SRP y DIP).
2. Evitar duplicacion (DRY) y centralizar logica comun en componentes reutilizables.
3. Considerar patrones de diseno cuando simplifiquen extension, testabilidad y mantenimiento.
4. Revisar cada cambio con criterio de staff engineer: claridad, robustez, trazabilidad y facilidad de evolucion.
