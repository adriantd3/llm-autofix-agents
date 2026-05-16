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
7. Considerar siempre las lecciones aprendidas en `specs/lessons.md`. Las lessons son para fallos criticos en el desarrollo a nivel de experiencia usuario-agente, no de bugs del código.

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
5. SIEMPRE cumplir con las convenciones codigo para planear, desarrollar y refactorizar expuestos en `specs/conventions.md`.
6. No apliques cambios que sobreajusten el flujo a un bug en concreto. No añadas referencias ni instrucciones en nada que consuma el agente que incluya aspectos especificos de un caso. Los agentes deben ser agnosticos a cada dataset o bug.

## Notas de tests

- Los tests deben validar la funcionalidad general.
- Ubicar tests en una ruta similar a la clase objetivo (ejemplo: `tests/unit/llm_autofix_agents/flow/iteration/test_runner.py`).
- Buscar buena cobertura sin obsesionarse.

## Criterios de evaluacion APR (arquitecturas de agentes)

El rendimiento de una arquitectura no se mide unicamente por el pass/fail del test. Hay dos dimensiones igualmente importantes:

### 1. Eficiencia del procedimiento

Un agente eficiente usa las tools exactamente cuando las necesita y no mas:
- **Sobreuso**: llamar a la misma tool dos veces con los mismos argumentos, explorar codigo que ya se ha leido, ejecutar el test antes de hacer ningun cambio, usar `execute_command` para explorar cuando `read_file` o `search_files` son suficientes.
- **Infrauso**: editar sin leer primero, proponer un fix sin validar, ignorar propagacion de cambios a otros modulos.

El consumo de tokens (input + output) es el proxy cuantitativo de eficiencia. Menos tokens para el mismo resultado = mejor arquitectura. Al comparar arquitecturas hay que medir tokens por run y por iteracion, no solo el resultado final.

### 2. Calidad del fix

Un fix correcto no es el que hace pasar el test — es el que restaura el comportamiento intencionado de la funcion:
- **El test es un validador, no un oraculo.** Un agente que adapta el codigo a las aserciones del test sin entender la funcion esta sobreajustando (test overfitting). El fix puede pasar el test y ser semanticamente incorrecto.
- **El agente debe entender el contexto** del repositorio y el proposito de la funcion antes de proponer el parche. El traceback indica donde falla; la funcion fuente define que debe hacer.
- **La calidad del codigo importa.** El parche debe ser minimal, consistente con el estilo del repositorio, sin introducir ruido (whitespace incorrecto, imports innecesarios, logica redundante).

Un fix de calidad se reconoce porque: (a) la logica del parche tiene sentido independientemente del test, (b) se puede explicar por que el codigo original estaba mal y por que el nuevo es correcto, (c) no rompe ningun otro comportamiento del modulo.
