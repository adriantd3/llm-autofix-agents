# Alcance Confirmado

## Contexto
- El proyecto es una plataforma experimental de APR con LLMs para comparar arquitecturas de agentes y modelos.

## Alcance base actual
- Politica de dependencias: cualquier alta o actualizacion de dependencia del proyecto debe realizarse con `uv add`.
- Arrancar por una arquitectura mono-agente simple y extensible.
- Definir entorno de ejecucion aislado y reproducible con Docker.
- Registrar decisiones y estado en la carpeta specs.
- Integrar QuixBugs como dataset inicial para baseline.
- Operar en modo autonomo con limites (max 3 iteraciones por run).
- Registrar resultados experimentales con trazabilidad (MongoDB Atlas primario + fallback JSONL local).
- Permitir acceso libre a internet en run con auditoria.
- Versionar por run la configuracion de prompt/agente en resultados.
- Usar Ollama como baseline por defecto en SH3 para ejecucion local gratuita sobre endpoint OpenAI-compatible.
- Mantener OpenAI y Gemini como providers opcionales compatibles con el mismo adaptador.
- Mantener enfoque autonomy-first: el agente decide secuencia interna de acciones usando tools locales del runtime bajo limites y guardrails.
- Adoptar enfoque tool-driven en SH3: el agente usa tools APR locales del SDK para explorar, editar, validar y registrar cambios; el orquestador no aplica parches desde la salida textual del modelo.
- Priorizar MVP simple: sin limites de CPU/RAM/PIDs por defecto en el Docker runner; aplicar solo timeout y dejar limites opcionales.
- Evitar pre-localizacion heuristica hardcodeada en el orquestador; la localizacion debe emerger del uso autonomo de tools.
- En SH3-T02B priorizar tools APR locales (filesystem + comandos + validacion + git/parche helpers) sobre dependencias externas adicionales en fase MVP.
- Eliminar web-search del baseline del APR en fase MVP; mantener foco en filesystem, comandos de ejecucion/validacion y helpers de git/parche.
- Ejecutar runtime completo del sistema en contenedores locales (Compose), no solo el sandbox de ejecucion por run.
- Definir por contenedor un contrato minimo de instanciacion con: repository, branch, architecture, agent_models y bootstrap_prompt.
- Permitir invocacion local simple (CLI/Compose) con un runner base parametrizable; ampliar a multiples runners en fases posteriores.
- Mantener fuera de alcance en esta fase: colas, workers distribuidos y control plane.
- Usar MongoDB Atlas como almacenamiento primario de resultados con fallback JSONL local en caso de fallo temporal.
- Aceptar no determinismo del flujo interno y validar por resultados por run + estimaciones medias sobre multiples runs.
- No introducir MCP servers en el baseline MVP: la capa operativa debe ser local y tool-driven.

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

## Criterios de aceptacion MVP (secuencia minima)
- Runtime completo invocable por Compose con runner unico funcional.
- Flujo autonomo con maximo 3 iteraciones por run.
- Aplicacion de cambios multiarchivo por el agente y validacion de tests en el repo objetivo.
- Generacion de parche final (unified diff) desde el estado real del repositorio al finalizar el run.
- Rechazo automatico de regresiones antes de aceptar resultado.
- Tools APR locales de filesystem y comandos habilitadas durante el run (baseline).

## Expansion posterior al MVP
- Ampliar benchmark de QuixBugs a 5 casos reproducibles para comparativas agregadas.
