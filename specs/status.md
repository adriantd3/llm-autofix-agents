# Estado

## Hecho
- Estructura base del proyecto disponible (uv, Makefile, lint, typecheck, entrypoint).
- Skill de elicitacion actualizado para exigir opciones recomendadas en cada pregunta.
- Registro completo de decisiones en SPEC-001.
- Lista de tasks por subhitos creada para SPEC-001.
- Convencion de carpetas por spec adoptada: specs/<NNN-slug>/{spec.md,tasks.md}.
- H39 cerrado con OA-001.A (versionado por run).
- Politica de red definida: internet libre con auditoria.
- SH1 completado: imagen base Docker, runner efimero, bind mount, limites dinamicos y smoke test con logs/timeout.
- SH2 completado: contratos Pydantic v2 para input/output, IDs reproducibles y modelo de errores con smoke de validacion.
- Validacion reforzada: pruebas unitarias base y pipeline local de comprobaciones para formato, tests y smokes Docker.
- SH3-T01 completado: integracion baseline de openai-agents-sdk con adaptador OpenAI/Gemini compatible OpenAI API y comando `agent-smoke`.
- Cobertura de SH3-T01 agregada: tests de configuracion LLM, adaptador provider y flujo baseline con manejo de errores.
- SH3-T02 realineado: localizacion autonomy-first definida via tools/MCP y directrices, sin pre-localizacion hardcodeada en el orquestador.
- Ajuste de implementacion aplicado: se retiro la pre-localizacion heuristica del flujo baseline para respetar autonomia del agente.
- SH3-T02B completado: integracion MCP stdio autonomy-first habilitada con servidores definidos de filesystem y web-search, inyectados al baseline via openai-agents-sdk.
- Inicio implementacion SH3 activo: MCP shell opcional integrado en toolset baseline con pruebas unitarias y documentacion de entorno.
- Rebaseline MCP aplicado: filesystem + shell pasan a ser default del baseline; web-search queda como MCP opt-in por entorno.
- Ajuste de baseline MCP aplicado: filesystem + shell + web-search pasan a ser el baseline por defecto.
- SH3-T03 avance inicial: ciclo iterativo (max 3) implementado con parada por `max_iterations` y `no_progress` en modo esqueleto.
- SH3-T03 avance objetivo: no-progress reforzado con firma de resultados de test y deteccion de cambios de archivos por iteracion.
- SH3-T04 avance inicial: extraccion/aplicacion de unified diff multiarchivo y captura de diff del repositorio por iteracion.
- Refactor de mantenibilidad: `agent_flow` simplificado como orquestador y utilidades extraidas a modulo de soporte para mejorar SRP/legibilidad.
- Provider LLM reforzado con salida estructurada (`output_type`) para homogenizar contrato de salida del agente y mantener interfaz externa estable.
- Contrato APR endurecido: salida del agente migrada a propuesta tipada (`patch_unified_diff`, `rationale`, `confidence`, `changed_files`, `notes`) y eliminada extraccion de parches desde texto libre.
- Pivot de ejecucion aplicado: flujo baseline pasa a execution-driven (el agente aplica cambios via MCP dentro del repo; el orquestador observa diff/tests y no aplica parches desde la salida del modelo).
- Alineacion SDD aplicada: spec/tasks/requirements actualizados para dejar explicito el enfoque execution-driven como direccion oficial del MVP.
- SH3-T05 completado: baseline de tests pre-iteracion y rechazo automatico de regresiones (baseline exit_code=0 y post-run exit_code!=0) con corte `validation_failure`, `status=failed` y evidencia en logs.
- SH3-T04 completado: consolidacion multiarchivo execution-driven desde estado real del repo, validacion bloqueante de coherencia `proposal.changed_files` vs cambios observados y empaquetado de artefactos por iteracion en `results/`.
- SH3-T02D2 avance inicial: hardening de Compose y runner con `.env` opcional, defaults de entorno robustos, validaciones tempranas de `DockerRunner`/`ContainerRunRequest` y cobertura unitaria dedicada.
- SH3-T02D2 completado: runtime Compose endurecido con validaciones de entrada y manejo robusto de errores en `docker-smoke` para evitar fallos operativos no controlados.
- SH3 completado: baseline mono-agente operativo con iteracion (max 3), no-progreso objetivo, consolidacion execution-driven, empaquetado de artefactos y rechazo de regresiones.
- Rebaseline iniciado: runtime completo en contenedores locales via Compose como base operativa previa a SH3-T03.
- Rebaseline MVP aplicado: Ollama definido como provider por defecto para ejecucion local gratuita y compatibilidad opcional OpenAI/Gemini preservada.
- Refactor estructural aplicado: separacion en submodulos `llm/` y `runtime/` con wrappers de compatibilidad para imports existentes.
- Simplificacion runner MVP aplicada: se eliminan limites dinamicos por defecto (CPU/RAM/PIDs) y se mantiene timeout operativo con limites opcionales.
- Simplificacion infra aplicada: comando `docker run` reducido a flags minimas, Docker Compose reducido a un unico servicio `runner`, y consolidacion en un solo Dockerfile (`runtime.Dockerfile`).
- SH3-T02D1 completado: contrato RUN_* validable en runtime con comando `runtime-contract-smoke` y smoke Compose asociado (`compose-contract-smoke`).

## En curso
- Spec activa: specs/001-mono-agente-entorno/spec.md
- Tasks activas: specs/001-mono-agente-entorno/tasks.md
- Subhito activo: SH4 - Git y artefactos de parche.
- Task activa: SH4-T01 Crear rama temporal por run.

## Siguiente
- Implementar SH4-T01/T02/T03/T04 (git y artefactos de parche).
- Ejecutar SH6-T00/T01/T02 para validar 1 caso QuixBugs reproducible como gate MVP.
