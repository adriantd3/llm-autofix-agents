# SPEC-003: Arquitectura multi-agente handoff (pipeline)

## Metadata
- Fecha: 2026-04-30
- Estado: **Descartada** (2026-05-16)
- Owner: adriantd3
- Tipo: arquitectura multi-agente (handoff)

## Contexto
Hasta ahora existe solo la arquitectura mono-agente. El objetivo del proyecto es comparar arquitecturas APR basadas en roles, por lo que se necesita el primer baseline multi-agente. El enfoque elegido para esta fase es handoff: un pipeline de agentes con responsabilidades acotadas que delegan el control al siguiente agente.

## Objetivo
Implementar una arquitectura multi-agente basada en handoff usando OpenAI Agents SDK (0.14+), con un pipeline de roles APR, seleccionable por configuracion de runtime, y validada end-to-end sobre QuixBugs.

## Principios y restricciones
- Usar OpenAI Agents SDK 0.14+ y seguir el enfoque documentation-first del proyecto.
- Mantener el enfoque autonomy-first: el flujo interno se decide por los agentes con tools locales, no por heuristicas del orquestador.
- Las iteraciones son ejecuciones completas del pipeline (incluyen handoffs internos).
- Mantener el contrato de salida actual (AgentFixIterationRecord), para integrarse con el loop existente.
- No introducir MCP servers ni websearch en esta fase.
- La arquitectura debe implementarse como Strategy y ser seleccionable por configuracion.

## Alcance confirmado
- Analisis del estado del arte en APR (docs/deep-research-report.md) para derivar roles y prompts handoff.
- Uso de ejemplos de handoff en SDK (demo notebook y openai-examples/handoffs) para asegurar implementacion correcta.
- Nueva arquitectura handoff (handoff.py) que construya los agentes, tools y el facade agent.
- Adaptacion de la seleccion de estrategia (RUN_ARCHITECTURE) para permitir la arquitectura handoff.
- Ajustes de observabilidad/telemetria para registrar multiples agentes y transiciones de handoff.
- Validacion end-to-end en QuixBugs con el pipeline handoff.

## Fuera de alcance
- Arquitecturas orchestrator o hibridas.
- Nuevas tools externas o MCP servers.
- Optimizaciones de coste/latencia mas alla de los limites existentes.

## Arquitectura handoff propuesta
Justificacion (estado del arte):
- El baseline minimo recomendado en APR separa localizacion, reparacion y validacion; eso reduce sobreajuste y mejora trazabilidad.
- Localizer es el rol critico para rendimiento: sin buena localizacion, el patcher tiende a fallar aunque razone bien.
- Un pipeline handoff es adecuado como baseline porque cada fase cambia de contrato (objetivo, herramientas y criterio de parada).

Pipeline inicial (roles y responsabilidades):

1. Explorador/Triage
   - Analiza prompt, test y contexto.
   - Recolecta señales iniciales (archivos/sintomas).
   - Handoff al Localizer.

2. Localizer
   - Identifica archivos/simbolos sospechosos con evidencia.
   - Limita el espacio de busqueda.
   - Handoff al Patcher.

3. Patcher
   - Propone cambios minimos y aplica la solucion.
   - Usa tools de edicion y validacion basica.
   - Handoff al Validator.

4. Validator/Reporter
   - Ejecuta validacion final y resume resultado.
   - Emite salida final en el contrato AgentFixIterationRecord.

Nota: el pipeline puede refinarse, pero la primera version debe ser estable y controlable.

Lineamientos SDK para handoff (0.14+):
- Definir `handoff_description` corta y concreta por rol para ayudar al enrutado.
- Hacer handoff explicito con `handoffs=[...]` y reforzar en instrucciones: cada rol debe transferir al siguiente y no resolver todo por su cuenta.
- El ultimo rol no debe declarar `handoffs` (finaliza el pipeline).
- Usar `handoff()` con `input_filter` para reducir ruido (ej. `handoff_filters.remove_all_tools`) cuando el historial de tools no aporta a la nueva fase.
- Evitar filtros agresivos si el modelo necesita historial completo; ajustar el filtro por modelo si hace falta.
- Usar `input_type` para metadata de transferencia (fase, razon, resumen), sin reemplazar el input principal.
- Evitar handoffs anidados profundos en la primera version; mantener un flujo lineal para control y observabilidad.

Roles, tools y criterio de handoff (v1):
- Explorador/Triage: diagnostico inicial y factibilidad; tools de lectura/consulta basica; handoff al Localizer cuando hay sintomas o candidatos.
- Localizer: evidencia de archivos/simbolos; tools de lectura, busqueda y trazas; handoff al Patcher al acotar la zona sospechosa.
- Patcher: propone diff minimo; tools de edicion y checks basicos; handoff al Validator cuando hay parche candidato.
- Validator/Reporter: ejecuta validacion final y resume resultado; tools de test/ejecucion; emite AgentFixIterationRecord y termina.

## Decisiones clave
- El facade agent de la arquitectura es el primer agente del pipeline (Explorador/Triage).
- La politica de modelos por rol usa keys simples (triage, localizer, patcher, validator) con fallback a "main" y luego a LLMSettings.model.
- La seleccion de arquitectura usa un enum con valores "mono_agent" y "multi_agent_handoff" (sin aliases).

## Criterios de aceptacion
- La estrategia "multi_agent_handoff" se puede seleccionar por RUN_ARCHITECTURE y ejecuta el pipeline completo.
- Se registran en observabilidad todos los agentes del pipeline con su rol y orden.
- Las tool calls quedan asociadas al agente ejecutor (o se registra la transicion de handoff de forma equivalente).
- Se valida al menos 1 caso QuixBugs end-to-end con la arquitectura handoff y se guarda evidencia (diff, tests, summary).
- No se rompen las ejecuciones mono-agente ni los tests actuales.

## Riesgos y mitigaciones
- Modelos locales pueden no seguir handoffs consistentemente.
  - Mitigacion: instrucciones mas estrictas, limites de tools y tests de humo.
- Sobrecoste de tokens por historial acumulado.
  - Mitigacion: prompts concisos y handoff filters si aplica.

## Preguntas abiertas
- Roles finales del pipeline: mantener 4 o agregar un Writer separado.
- Registro de eventos de handoff: aprovechar hooks del SDK o introducir evento propio.

## Veredicto final (2026-05-16)

Arquitectura **descartada** de la evaluación comparativa. Se mantiene el código implementado pero no se incluirá en batches ni en la memoria como arquitectura evaluada.

### Razones técnicas

1. **El pipeline nunca se ejecuta realmente.** Los casos marcados como éxito (QuixBugs 3/3) se produjeron gracias al fallback de `MaxTurnsExceeded`, no porque el pipeline triage→localizer→patcher→validator completara sus handoffs. El mecanismo de éxito es el mismo que el del mono-agente, no el del pipeline.

2. **APR es intensivo en herramientas por naturaleza.** Cada agente del pipeline necesita leer código, buscar símbolos y ejecutar tests. Eso consume turnos antes de que el modelo llegue a invocar `transfer_to_<next>`. El handoff requiere que el modelo concluya una fase con pocas tool calls, lo cual es incompatible con la naturaleza exploratoria de APR.

3. **El patrón requiere modelos con fuerte seguimiento de instrucciones.** Con modelos locales (qwen3.5:9b, qwen3-coder:30b vía Ollama) los agentes ignoran la instrucción de handoff o la producen como texto en lugar de llamar la herramienta. Con modelos frontier (GPT-4, Claude) el handoff funciona, pero eso cambia la variable experimental y no añade valor comparativo sobre el orquestador.

4. **El orquestador cubre el mismo espacio de diseño con mejores resultados.** El patrón orchestrator (agents-as-tools) separa roles igualmente pero mantiene control central, evita inflación de historial y es más compatible con modelos locales. El propio `deep-research-report.md` recomienda orchestrator como mejor baseline multiagente para APR.

### Valor como resultado negativo

El fracaso de la arquitectura handoff es un hallazgo legítimo y documentable:
- Confirma empíricamente la incompatibilidad entre pipelines de ownership fuerte y flujos APR intensivos en herramientas.
- Refuerza la ventaja del orquestador al mantener control central.
- Las lecciones aprendidas (ver `specs/lessons.md`) cubren los anti-patrones concretos que causan el fallo.
- Este resultado apoya la conclusión de que la especialización por roles en APR debe implementarse como tools (orchestrator), no como transferencia de ownership (handoff).
