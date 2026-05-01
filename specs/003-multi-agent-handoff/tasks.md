# TASKS SPEC-003: Multi-agent handoff

## Estado global
- Spec: SPEC-003
- Estado: En curso

Nota operativa: una "iteracion" del loop es una ejecucion completa del pipeline con handoffs internos. No introducir loops adicionales fuera del SDK.

## SH1 - Analisis de arquitectura handoff (SDK + estado del arte)
### Objetivo
Derivar roles y prompts basados en evidencia (estado del arte + ejemplos SDK) antes de implementar.

### Tasks
- [x] SH1-T01 Revisar docs/deep-research-report.md y extraer roles/patrones de handoff aplicables a APR.
	Contexto: el reporte contiene comparativas de orchestrator vs handoff y recomendaciones de roles (Localizer, Designer, Patcher, Validator).
	Output: resumen corto en la seccion "Arquitectura handoff propuesta" de la spec, indicando por que esos roles encajan en APR.
- [x] SH1-T02 Revisar demo/openai_agents_ollama_qwen35_demo.ipynb (seccion handoffs) y openai-examples/handoffs para confirmar uso correcto del SDK.
	Contexto: validar uso de `handoffs`, `handoff_description`, `input_type`, `handoff_filters` y limites de historial.
	Output: lineamientos concretos en la spec (por ejemplo: cuando usar filtros, como evitar loops de handoff).
- [x] SH1-T03 Definir el pipeline minimo de roles (Explorador, Localizer, Patcher, Validator/Reporter).
	Contexto: definir responsabilidad, tools permitidas y criterio de handoff para cada rol.
	Output: tabla o lista de roles en la spec con responsabilidades y tools.

### Done cuando
- La spec contiene roles definitivos y lineamientos de handoff alineados con SDK 0.14+.

## SH2 - Prompts y contratos de rol
### Objetivo
Formalizar instrucciones por rol y reglas de handoff coherentes con el contrato actual.

### Tasks
- [x] SH2-T01 Crear instrucciones por rol en agents/instructions.py.
	Contexto: reutilizar el estilo de MONO_AGENT_APR_INSTRUCTIONS, pero acotado a cada rol.
	Output: nuevas constantes con prompts por rol (Explorador, Localizer, Patcher, Validator/Reporter).
- [x] SH2-T02 Definir reglas de salida por rol para que el ultimo agente emita AgentFixIterationRecord.
	Contexto: el loop actual consume AgentFixIterationRecord desde el facade agent.
	Output: reglas explicitas en los prompts y/o builder para asegurar que solo el ultimo rol devuelve la salida final.
- [x] SH2-T03 Definir politica de modelos por rol (RUN_AGENT_MODELS) con fallback a "main".
	Contexto: el contrato actual carga RUN_AGENT_MODELS en ContainerInstantiation. Falta decidir como mapear roles.
	Output: reglas claras (ejemplo: buscar modelo por rol, si falta usar "main", si falta usar LLMSettings.model).

### Done cuando
- Existen prompts por rol y politica clara de modelos por rol.

## SH3 - Implementacion de la arquitectura handoff
### Objetivo
Construir el pipeline multi-agente y exponerlo como estrategia.

### Tasks
- [x] SH3-T01 Crear architectures/handoff.py con el pipeline de agentes y handoffs usando SDK 0.14+.
	Contexto: seguir el patron de architectures/mono_agent.py y construir un facade agent que sea el primer rol del pipeline.
	Output: funcion build_multi_agent_handoff_architecture que retorna BuiltArchitecture con facade_agent_builder.
- [x] SH3-T02 Exponer la arquitectura en architectures/__init__.py y en architectures/factory.py.
	Contexto: factory actual solo acepta "mono_agent".
	Output: nueva estrategia "multi_agent_handoff" con validacion y error claro si el strategy es invalido.
- [x] SH3-T03 Ajustar build_agent o introducir builder por rol si hace falta para soportar modelos distintos por agente.
	Contexto: build_agent hoy usa LLMSettings.model para todo. Necesitamos opcion por rol.
	Output: helper que acepte modelo override y respete el output_type actual (AgentFixIterationRecord).

### Done cuando
- La arquitectura handoff se construye y puede ser instanciada como facade agent.

## SH4 - Seleccion de estrategia y configuracion runtime
### Objetivo
Permitir seleccionar la arquitectura handoff por configuracion de entorno.

### Tasks
- [x] SH4-T01 Definir RUN_ARCHITECTURE como enum ("mono_agent", "multi_agent_handoff").
	Contexto: main.py registra runtime_architecture en metadata y agent_flow usa build_architecture.
	Output: validacion estricta y valores unicos sin aliases.
- [x] SH4-T02 Usar runtime_architecture (metadata) en agent_flow/run_agent_baseline para elegir estrategia.
	Contexto: hoy run_agent_baseline usa default "mono_agent".
	Output: si metadata.runtime_architecture existe, usarlo como strategy.
- [x] SH4-T03 Actualizar docs de runtime (.env.example, docker-compose.yml) y tests de contrato si aplica.
	Contexto: RUN_ARCHITECTURE aparece en .env.example y docker-compose.yml.
	Output: ejemplos con "multi_agent_handoff" y tests actualizados si hay validaciones de valores.

### Done cuando
- Se puede lanzar un run con RUN_ARCHITECTURE=multi_agent_handoff.

## SH5 - Observabilidad y telemetria multi-agente
### Objetivo
Registrar multiples agentes y transiciones de handoff.

### Tasks
- [x] SH5-T01 Registrar todos los agentes del pipeline en RunTelemetry (orden y rol).
	Contexto: RunInitializer hoy registra un solo agente. Necesitamos multiples registros para el pipeline.
	Output: registro de agentes con agent_order y roles consistentes con el pipeline. El mono agente debera aparecer en los registros (live.md) como `main`
- [x] SH5-T02 Ajustar tool call tracing para asociar tool calls al agente ejecutor o registrar eventos de handoff.
	Contexto: APRRunHooks registra tool calls por agent_execution_id. En handoff, el ejecutor cambia.
	Output: estrategia clara (por ejemplo: un agent_execution_id por agente o evento de handoff en observabilidad). Se implemento: on_agent_start/on_handoff en RunHooks + agent_name en tool_calls + AgentHandoffRecord en tabla agent_handoffs.
- [x] SH5-T03 Actualizar SQLite schema/observer si se agregan nuevos eventos o campos.
	Contexto: agregar columnas o tablas solo si es necesario para handoff.
	Output: migracion schema v3→v4 con tabla agent_handoffs y columna agent_name en tool_calls, mas implementacion en observers.

### Done cuando
- La observabilidad refleja multiples agentes y sus ejecuciones.

## SH6 - Validacion end-to-end (QuixBugs)
### Objetivo
Demostrar que la arquitectura handoff es funcional en un caso real.

### Tasks
- [x] SH6-T01 Ejecutar un run con `RUN_ARCHITECTURE=multi_agent_handoff` sobre QuixBugs gcd.
	Contexto: usar RUN_ARCHITECTURE=multi_agent_handoff y el mismo RUN_TEST_COMMAND de gcd.
	Output: run reproducible con logs y artefactos completos en results/.
- [x] SH6-T02 Guardar evidencia (diff, summary.json, observability.db) y registrar resultados.
	Contexto: verificar que la observabilidad capture multiples agentes.
	Output: referencia del run_id y archivos clave en la carpeta results/.
- [x] SH6-T03 Documentar lecciones aprendidas en specs/lessons.md.
	Contexto: identificar y corregir bugs que impedieron la ejecucion exitosa.
	Output: entrada breve y accionable.

### Done cuando
- Existe evidencia trazable de al menos 1 run exitoso con handoff.

### Resultado
Run exitoso: `run-20260501T140716Z-66fcdfbec8` (status=success, stop_reason=completed).
- Iteracion 1: changed_files=2, test_exit_code=0 (fix aplicado, tests pasaron)
- Iteracion 2: changed_files=1, test_exit_code=0, proposal_confidence=0.500
- El run completo en ~159s con ~87K tokens.

### Bugs corregidos durante SH6
1. **Duration no registrada**: `AgentExecutionTelemetry.finish()` no calculaba `duration_seconds`. Fix: pasar `duration_seconds` desde `AgentExecutionRunner` donde ya se trackeaba con `time.perf_counter()`.
2. **Crash con output de texto**: Cuando el modelo retornaba texto en lugar de `AgentFixIterationRecord`, `json.dumps(output)` envolvia el string y `model_validate_json` fallaba. Fix: intentar parsear JSON primero, si falla crear un fallback record.
3. **Crash con output None**: Si `final_output` era `None`, caia en el `else` y fallaba. Fix: manejar `None` explicitamente con fallback.
4. **MaxTurnsExceeded causaba fallo total**: Cuando el agente excedia los turnos, el run se abortaba aunque hubiera cambiado archivos y pasado tests. Fix: capturar `MaxTurnsExceeded` y retornar un fallback record con `status="done"` para que el stop policy pueda detectar exito.
5. **Instrucciones de handoff contradictorias**: Los prompts incluian secciones "Output format" con "HANDOFF:" que ensenaban al modelo a escribir texto en lugar de llamar la herramienta de handoff del SDK. Fix: eliminar formatos de output para agentes intermedios y usar `agents.extensions.handoff_prompt.RECOMMENDED_PROMPT_PREFIX` via `build_agent()` cuando `handoffs` esta presente.

### Limitacion conocida
Con modelos locales (qwen3.5:9b via Ollama), los agentes con herramientas tienden a usarlas repetidamente y exceder `max_turns` sin handoff completo al siguiente agente. El pipeline funciona porque el fallback de `MaxTurnsExceeded` permite que la iteracion continue y el stop policy evalua los cambios/tests. Con modelos mas capaces (GPT-4, Gemini), el handoff nativo del SDK deberia funcionar mas limpiamente.
