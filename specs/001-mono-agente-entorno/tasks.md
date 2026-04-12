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
Implementar pipeline analizar->localizar->proponer->aplicar->validar.

### Tasks
- [ ] SH3-T01 Integrar openai-agents-sdk en version baseline.
- [ ] SH3-T02 Implementar localizacion heuristica por stacktrace/tests.
- [ ] SH3-T03 Implementar ciclo de iteracion (max 3) con criterio de no progreso.
- [ ] SH3-T04 Implementar aplicacion de parches multiarchivo.
- [ ] SH3-T05 Implementar rechazo automatico de regresiones.

### Done cuando
- El flujo completo se ejecuta end-to-end sobre un caso controlado.

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
- [ ] SH5-T01 Definir esquema JSONL de resultados.
- [ ] SH5-T02 Registrar metrica minima (exito, iteraciones, tiempo, tokens, coste).
- [ ] SH5-T03 Implementar logging INFO/DEBUG.
- [ ] SH5-T04 Registrar trazabilidad de tool calls.
- [x] SH5-T05 Cerrar OA-001 (versionado de prompt/config).

### Done cuando
- Se puede reconstruir una ejecucion desde datos guardados.

## SH6 - Benchmark QuixBugs inicial (Pendiente)
### Objetivo
Ejecutar baseline sobre 5 casos reproducibles.

### Tasks
- [ ] SH6-T01 Seleccionar 5 casos QuixBugs reproducibles.
- [ ] SH6-T02 Ejecutar runs con configuracion controlada.
- [ ] SH6-T03 Excluir casos no reproducibles con justificacion.
- [ ] SH6-T04 Generar comparativa tasa exito/coste/tiempo.

### Done cuando
- Existe reporte de benchmark inicial con resultados trazables.

## Dependencias entre subhitos
- SH1 -> SH2 -> SH3 -> SH4 -> SH5 -> SH6
