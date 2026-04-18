# TASKS SPEC-001: Mono-agente + Entorno de Ejecucion v1

## Estado global
- Spec: SPEC-001
- Subhito activo: SH3
- Estado: En curso

## SH1 - Entorno Docker base y runner (Completado)
### Objetivo
Disponer de ejecucion aislada por run con limites y captura de evidencias.

### Tasks
- [x] SH1-T01 Definir imagen base Docker y estrategia de build.
- [x] SH1-T02 Implementar runner de contenedor efimero por run.
- [x] SH1-T03 Implementar bind mount del repo objetivo.
- [x] SH1-T04 Implementar acceso libre a internet con auditoria en contenedor.
- [x] SH1-T05 Implementar limites de recursos dinamicos por proyecto.
- [x] SH1-T06 Ejecutar comando de prueba dentro de contenedor y capturar salida.

### Done cuando
- Runner Docker ejecuta un comando reproducible y retorna logs con timeout aplicado.

## SH2 - Contratos de entrada/salida y run model (Completado)
### Objetivo
Fijar contratos minimos para input libre y salida trazable.

### Tasks
- [x] SH2-T01 Definir esquema de input libre (prompt + metadatos opcionales).
- [x] SH2-T02 Definir esquema de output (diff, tests, logs, estado final).
- [x] SH2-T03 Definir IDs de run/iteracion reproducibles.
- [x] SH2-T04 Definir modelo de errores y motivo de parada.

### Done cuando
- Existen contratos documentados y validados en una ejecucion de humo.

## SH3 - Flujo mono-agente baseline (En curso)
### Objetivo
Habilitar ejecucion autonoma del agente bajo limites de run y validacion de resultados.

### Tasks
- [x] SH3-T01 Integrar openai-agents-sdk en version baseline.
- [x] SH3-T02 Definir localizacion autonoma via tools/MCP y directrices de system prompt (sin pre-localizacion hardcodeada en el orquestador).
- [x] SH3-T02B Habilitar MCPs definidos para localizacion autonoma efectiva (filesystem + web-search).
- [x] SH3-T02B1 Integrar MCP shell opcional para ejecucion de comandos del agente (parametrizable por entorno).
- [x] SH3-T02B2 Rebaselinar MCPs por defecto a filesystem + shell.
- [x] SH3-T02B3 Incluir web-search en baseline por defecto junto a filesystem y shell.
- [x] SH3-T02C Definir contrato minimo de instanciacion por contenedor (repository, branch, architecture, agent_models, bootstrap_prompt).
- [x] SH3-T02D1 Contenerizar runtime completo minimo del sistema para invocacion local via Docker Compose (runner unico funcional).
- [ ] SH3-T02D2 Endurecer runtime Compose del runner unico (parametrizacion y robustez operativa no bloqueante para primer bugfix).
- [ ] SH3-T03 Implementar ciclo de iteracion (max 3) con criterio de no progreso.
- [x] SH3-T03A Implementar esqueleto de ciclo iterativo (max 3) con razones de parada `max_iterations` y `no_progress` por señal textual.
- [x] SH3-T03B Reforzar no-progreso con senales objetivas (firma de tests + cambios de archivos) manteniendo loop interno del SDK.
- [ ] SH3-T04 Consolidar salida de parche multiarchivo basada en estado real del repo (execution-driven) y empaquetado de artefactos.
- [x] SH3-T04A Migrar de aplicacion de parche desde salida textual del modelo a enfoque execution-driven (agente aplica cambios via MCP; orquestador observa diff/tests).
- [ ] SH3-T05 Implementar rechazo automatico de regresiones.

### Done cuando
- El flujo autonomo se ejecuta end-to-end sobre un caso controlado sin imponer pasos internos fijos al agente.

### Secuencia MVP (ruta critica)
- SH3-T02D1 -> SH3-T03 -> SH3-T04 -> SH3-T05.
- SH3-T02D2 queda diferida mientras no bloquee la validacion de 1 bugfix reproducible.

## SH4 - Git y artefactos de parche (Pendiente)
### Objetivo
Asegurar gestion de cambios por run y artefactos comparables.

### Tasks
- [ ] SH4-T01 Crear rama temporal por run.
- [ ] SH4-T02 Exportar unified diff + resumen.
- [ ] SH4-T03 Limpiar/ignorar artefactos de build/test.
- [ ] SH4-T04 Registrar trazabilidad de cambios por archivo.

### Done cuando
- Cada run deja diff limpio y auditable.

## SH5 - Observabilidad y datos experimentales (Pendiente)
### Objetivo
Guardar metrica y trazabilidad para analisis posterior.

### Tasks
- [ ] SH5-T01 Definir esquema de resultados para MongoDB Atlas con fallback JSONL local.
- [ ] SH5-T02 Registrar metrica minima (exito, iteraciones, tiempo, tokens, coste).
- [ ] SH5-T03 Implementar logging INFO/DEBUG.
- [ ] SH5-T04 Registrar trazabilidad de tool calls.
- [x] SH5-T05 Cerrar OA-001 (versionado de prompt/config).

### Done cuando
- Se puede reconstruir una ejecucion desde datos guardados.

## SH6 - Benchmark QuixBugs inicial (Pendiente)
### Objetivo
Validar baseline con un caso reproducible inicial y ampliar a 5 casos en fase posterior.

### Tasks
- [ ] SH6-T00 Seleccionar 1 caso QuixBugs reproducible como gate MVP.
- [ ] SH6-T01 Ejecutar 1 run controlado end-to-end sobre el caso MVP.
- [ ] SH6-T02 Registrar resultado y, si falla, documentar causa raiz en lessons.
- [ ] SH6-T03 Seleccionar 5 casos QuixBugs reproducibles para la fase de expansion.
- [ ] SH6-T04 Ejecutar runs con configuracion controlada en 5 casos.
- [ ] SH6-T05 Excluir casos no reproducibles con justificacion.
- [ ] SH6-T06 Generar comparativa tasa exito/coste/tiempo.

### Done cuando
- Existe evidencia trazable de 1 caso MVP y un plan ejecutable para ampliar a 5 casos.

## Dependencias entre subhitos
- SH1 -> SH2 -> SH3 -> SH4 -> SH5 -> SH6
