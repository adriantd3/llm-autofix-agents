# SPEC-001: Mono-agente + Entorno de Ejecucion v1

## Metadata
- Fecha: 2026-04-11
- Estado: En curso
- Owner: adriantd3
- Spec activa para desarrollo inicial

## Objetivo de la spec
- Construir una base mono-agente simple para APR, con ejecucion aislada y reproducible.
- Ser capaz de arreglar al menos 1 bug reproducible en QuixBugs.
- Dejar preparada la base para crecer a multi-agente en fases posteriores.

## Alcance confirmado
- Arquitectura mono-agente (multi-agente fuera de alcance en esta fase).
- Entorno de ejecucion con Docker por run.
- Integracion inicial de QuixBugs como dataset de arranque.
- Registro de resultados experimentales y trazabilidad por run.

## Registro completo de decisiones (A1-M61)

### A) Vision y exito
- A1: Priorizar capacidad real de reparacion efectiva, no solo infraestructura.
- A2: Exito minimo = arreglar 1 bug reproducible de QuixBugs, con duda abierta sobre estrategia para incorporar mas datasets/repos.
- A3: Prioridad tecnica = base robusta y extensible.
- A4: Fuera de alcance inicial = arquitectura multi-agente.

### B) MVP mono-agente
- B5: Input libre tipo prompt, capaz de incluir contexto de test fail (rama, traza, etc.).
- B6: Output minimo = diff + resultado de tests + logs de ejecucion.
- B7: Operacion autonoma con limites estrictos.
- B8: Maximo de 3 iteraciones por run.
- B9: Dataset inicial = QuixBugs; se agregaran mas en el futuro.

### C) Flujo interno
- C10: Pipeline base = analizar fallo -> localizar -> proponer -> aplicar -> validar.
- C11: Estrategia inicial de localizacion = heuristica guiada por stacktrace/tests.
- C12: Politica de edicion = hacer los cambios necesarios para resolver el problema (sin limite estricto de archivos).
- C13: No progreso (estandar) = mismos tests fallando en iteraciones consecutivas.
- C14: Al agotar iteraciones = fallo controlado con informe y artefactos.

### D) Docker y entorno
- D15: 1 contenedor efimero por run.
- D16: Montaje de codigo con bind mount.
- D17: Red en contenedor con acceso libre a internet para documentacion y necesidades del agente, con auditoria.
- D18: Limites de recursos dinamicos por proyecto.
- D19: Soporte inicial de lenguaje = Python.
- D20: Dependencias resueltas dentro del contenedor segun gestor/lockfile del proyecto objetivo.

### E) Herramientas y MCPs
- E21: Set minimo inicial de tools (filesystem + comandos + diff/test).
- E22: Politica de comandos = amplia con auditoria.
- E23: Fallo de tools = reintentos acotados + fallback + log.
- E24: Trazabilidad completa de tool calls.
- E25: Presupuesto de tools por iteracion habilitado.

### F) Git y parches
- F26: Rama temporal por run.
- F27: Entrega de parche en formato unified diff + resumen.
- F28: Permitir multiples archivos si hace falta para reparar de forma efectiva.
- F29: Limpiar o ignorar artefactos generados por build/test.

### G) Validacion y tests
- G30: Objetivo = pasar test objetivo sin romper la suite relevante.
- G31: Si hay mejora parcial = continuar iterando con memoria de progreso.
- G32: Regresiones = rechazo automatico del parche.
- G33: Timeouts por comando y timeout global de run.
- G34: En v1 no se exige validacion extra de lint/typecheck.

### H) Modelos LLM
- H35: Un unico modelo estable como baseline.
- H36: Framework inicial = openai-agents-sdk; se podra cambiar/mejorar mas adelante.
- H37: Parametrizacion no configurable en v1; abrir configuracion en fases posteriores (ej. temperatura, max_tokens).
- H38: Fallos de API = retry exponencial + backoff + failover opcional.
- H39: Versionado obligatorio por run con `prompt_version` y `agent_config_hash` en resultados JSONL.

### I) Observabilidad y datos
- I40: Unidad de analisis = run e iteracion.
- I41: Metricas minimas = exito/fallo, iteraciones, tiempo, tokens, coste estimado.
- I42: Persistencia inicial de resultados = JSONL.
- I43: Logging = INFO por defecto y DEBUG activable.
- I44: Trazabilidad config -> resultado con identificador reproducible.

### J) Seguridad
- J45: Aislamiento minimo = contenedor + privilegios minimos.
- J46: Secretos via variables de entorno enmascaradas.
- J47: Internet permitido con auditoria.
- J48: Auditoria minima = comandos ejecutados y cambios de archivos.

### K) Diseno experimental
- K49: Dataset inicial = QuixBugs.
- K50: Muestra inicial = 5 casos.
- K51: Variables de control fijas = entorno, prompt/version, limites, modelo, seed.
- K52: Casos no reproducibles = excluir con justificacion trazable.
- K53: Comparacion = tasa de exito + coste + tiempo.

### L) Arquitectura y roadmap
- L54: Arranque con implementacion simple/monolitica, refactor posterior.
- L55: Contratos a estabilizar primero = input bug, contexto repo, resultado run, metrica run.
- L56: Base lista para escalar cuando haya baseline reproducible + metricas + logs + 1 benchmark inicial.
- L57: Orden de construccion = entorno Docker -> runner -> agente -> metricas.

### M) SDD y documentacion
- M58: Actualizacion de status por hito cerrado.
- M59: Requisitos redactados como items verificables con criterios de aceptacion.
- M60: Lessons solo accionables y reutilizables.
- M61: Cambios de alcance siempre explicitos en requirements con justificacion.

## Decisiones cerradas tras confirmacion

### OA-001 (H39) - Cerrada
- Decision aplicada: OA-001.A.
- Implementacion esperada: registrar `prompt_version` y `agent_config_hash` por run en JSONL.

### OA-002 (Red del contenedor) - Cerrada
- Decision aplicada: acceso libre a internet con auditoria.
- Implementacion esperada: permitir salida de red y registrar trazas de actividad relevante.

## Criterios de aceptacion de la spec
- Existe implementacion funcional de run mono-agente con maximo de 3 iteraciones.
- El sistema genera diff, resultado de tests y logs por run.
- Se ejecuta en contenedor Docker efimero por run.
- Se registra JSONL con metricas minimas y trazabilidad de configuracion.
- Se completa benchmark inicial de 5 casos QuixBugs y se documenta resultado.
