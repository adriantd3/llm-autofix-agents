# Alcance Confirmado

## Contexto
- El proyecto es una plataforma experimental de APR con LLMs para comparar arquitecturas de agentes y modelos.

## Alcance base actual
- Arrancar por una arquitectura mono-agente simple y extensible.
- Definir entorno de ejecucion aislado y reproducible con Docker.
- Registrar decisiones y estado en la carpeta specs.
- Integrar QuixBugs como dataset inicial para baseline.
- Operar en modo autonomo con limites (max 3 iteraciones por run).
- Registrar resultados experimentales con trazabilidad (JSONL).
- Permitir acceso libre a internet en run con auditoria.
- Versionar por run la configuracion de prompt/agente en resultados.
- Mantener dual provider en SH3 (OpenAI y Gemini) con adaptador compatible con openai-agents-sdk.
- Ejecutar smoke real con Gemini y validar OpenAI por mocks cuando no existan credenciales OpenAI.
- Mantener enfoque autonomy-first: el agente decide secuencia interna de acciones usando tools/MCP bajo limites y guardrails.
- Evitar pre-localizacion heuristica hardcodeada en el orquestador; la localizacion debe emerger del uso autonomo de tools.
- Aceptar no determinismo del flujo interno y validar por resultados por run + estimaciones medias sobre multiples runs.

## Referencias de especificacion activa
- Spec principal: specs/001-mono-agente-entorno/spec.md
- Lista de tasks por subhitos: specs/001-mono-agente-entorno/tasks.md

## Criterios de calidad de especificacion
- Requisitos claros y verificables.
- Trazabilidad entre objetivo, requisito y validacion.
- Priorizacion explicita de decisiones tecnicas iniciales.

## Criterios de aceptacion de fase base
- Reparar al menos 1 bug reproducible en QuixBugs.
- Ejecutar en contenedor efimero por run.
- Generar diff, resultado de tests y logs.
- Registrar metrica minima: exito/fallo, iteraciones, tiempo, tokens, coste estimado.
