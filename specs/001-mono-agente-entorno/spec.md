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
- Baseline MVP: tools locales del SDK (filesystem + comandos + validacion + helpers de git/parche), sin MCP servers ni websearch en el runtime principal.

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
- C10: Flujo de referencia = analizar fallo -> localizar -> proponer -> aplicar -> validar, sin imponer un orden interno estricto al agente.
- C10b: Enfoque de ejecucion baseline = tool-driven: el agente usa tools APR locales del SDK para explorar, editar y validar; el orquestador no aplica parches desde la salida del modelo y se limita a observar/validar estado del repo y tests.
- C11: Estrategia inicial de localizacion = autonomia del agente via tools APR definidos (filesystem + comandos + git/parche + validacion) y directrices, sin pre-localizador hardcodeado en el orquestador.
- C12: Politica de edicion = hacer los cambios necesarios para resolver el problema (sin limite estricto de archivos).
- C13: No progreso (estandar) = mismos tests fallando en iteraciones consecutivas.
- C14: Al agotar iteraciones = fallo controlado con informe y artefactos.
- C15: Se permite no determinismo en la trayectoria interna del agente; la validacion se centra en resultados y metricas agregadas.

### D) Docker y entorno
- D15: 1 contenedor efimero por run.
- D16: Montaje de codigo con bind mount.
- D17: Red en contenedor con acceso libre a internet para documentacion y necesidades del agente, con auditoria.
- D18: MVP simple sin limites estrictos de CPU/RAM/PIDs por defecto; solo timeout de ejecucion y limites opcionales por configuracion.
- D19: Soporte inicial de lenguaje = Python.
- D20: Dependencias resueltas dentro del contenedor segun gestor/lockfile del proyecto objetivo.
- D21: Runtime completo del sistema contenedizado para invocacion local via Compose con un runner unico parametrizable.

### E) Herramientas baseline
- E21: Set minimo inicial de tools APR locales para baseline (filesystem + shell/comandos + validacion + git/parche helpers).
- E22: Politica de comandos = amplia con auditoria.
- E23: Fallo de tools = reintentos acotados + fallback + log.
- E24: Trazabilidad completa de tool calls.
- E25: Presupuesto de tools por iteracion habilitado.
- E26: No usar MCP servers ni websearch en el baseline MVP; cualquier helper externo queda fuera de este alcance.

### F) Git y parches
- F26: Rama temporal por run.
- F27: Entrega de parche en formato unified diff + resumen.
- F27b: Fuente de verdad del parche = diff real del repositorio tras la ejecucion del agente (execution-driven), no un parche textual aplicado por el orquestador a partir de la salida del modelo.
- F28: Permitir multiples archivos si hace falta para reparar de forma efectiva.
- F29: Limpiar o ignorar artefactos generados por build/test.

### G) Validacion y tests
- G30: Objetivo = pasar test objetivo sin romper la suite relevante.
- G31: Si hay mejora parcial = continuar iterando con memoria de progreso.
- G32: Regresiones = rechazo automatico del parche.
- G33: Timeouts por comando y timeout global de run.
- G34: En v1 no se exige validacion extra de lint/typecheck.

### H) Modelos LLM
- H35: Baseline de ejecucion actual = Ollama (endpoint OpenAI-compatible) para operacion local 100% gratuita.
- H36: Framework inicial = openai-agents-sdk; se mantiene compatibilidad opcional con OpenAI y Gemini.
- H37: Configuracion minima por entorno habilitada en v1 para provider/model y timeout operativo, mas contrato de instanciacion por contenedor (repository, branch, architecture, agent_models, bootstrap_prompt).
- H38: Fallos de API = retry exponencial + backoff + failover opcional.
- H39: Versionado obligatorio por run con `prompt_version` y `agent_config_hash` en resultados persistidos.
- H40: El provider baseline recibe tools locales del SDK y contexto local del run; no debe depender de MCPServer/MCPServerManager.

### I) Observabilidad y datos
- I40: Unidad de analisis = run e iteracion.
- I41: Metricas minimas = exito/fallo, iteraciones, tiempo, tokens, coste estimado.
- I42: Persistencia inicial de resultados = MongoDB Atlas como primario + fallback JSONL local.
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
- L54: Arranque con implementacion simple/monolitica contenedizada, invocada localmente por Compose, sin control plane ni colas en esta fase.
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
- Implementacion esperada: registrar `prompt_version` y `agent_config_hash` por run en almacenamiento persistido.

### OA-002 (Red del contenedor) - Cerrada
- Decision aplicada: acceso libre a internet con auditoria.
- Implementacion esperada: permitir salida de red y registrar trazas de actividad relevante.

### OA-003 (Provider baseline en SH3) - Cerrada
- Decision aplicada: dual provider con adaptador compatible con openai-agents-sdk.
- Implementacion esperada: OpenAI y Gemini bajo la misma abstraccion, con Gemini como ruta de ejecucion real cuando no hay credenciales OpenAI.

### OA-004 (Autonomia de flujo en SH3) - Cerrada
- Decision aplicada: autonomia-first para localizacion y secuenciacion de acciones.
- Implementacion esperada: evitar heuristicas de localizacion codificadas en el orquestador; priorizar directrices y toolset para que el agente decida el flujo.

### OA-005 (Runtime local contenedizado + contrato de instanciacion) - Cerrada
- Decision aplicada: runtime completo en contenedores locales via Compose con un runner base parametrizable.
- Implementacion esperada: definir por contenedor repository, branch, architecture, agent_models y bootstrap_prompt como contrato minimo de instanciacion.

## Criterios de aceptacion de la spec
- Existe implementacion funcional de run mono-agente con maximo de 3 iteraciones.
- El sistema genera diff, resultado de tests y logs por run.
- Se ejecuta en contenedor Docker efimero por run.
- El runtime completo se puede levantar localmente con Docker Compose usando un runner base parametrizable.
- El runner respeta el contrato minimo de instanciacion (repository, branch, architecture, agent_models, bootstrap_prompt).
- Se registran resultados en MongoDB Atlas con fallback JSONL local y trazabilidad de configuracion.
- Se valida al menos 1 caso QuixBugs reproducible como gate MVP y se documenta resultado.
- Se deja plan de expansion para benchmark de 5 casos QuixBugs en fase posterior.
- El sistema no fuerza una trayectoria determinista interna; se evalua por resultados reproducibles a nivel de run y por metricas agregadas entre multiples runs.
- El runtime baseline opera en modo tool-driven con tools locales del SDK y no requiere MCP servers ni websearch para el MVP.
