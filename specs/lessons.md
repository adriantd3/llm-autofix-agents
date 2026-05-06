# Lecciones y Aprendizajes

## Plantilla de entrada
- Fecha:
- Contexto:
- Anti-patron detectado:
- Que no hay que hacer:
- Por que estuvo mal:
- Alternativa recomendada:
- Regla preventiva para futuras specs:

## Notas iniciales
- Mantener esta bitacora corta y accionable.
- Registrar solo aprendizajes reutilizables.

## Regla de uso (futuras specs)
- Este archivo es para anti-patrones detectados (por ejemplo, over-engineering o decisiones que complican sin aportar valor).
- Registrar aqui solo cosas que identificamos que no hay que repetir.
- No usar este archivo como bitacora general de avance.
- Cada entrada debe dejar explicito: que no hacer, por que estuvo mal y cual es la alternativa simple recomendada.

## 2026-04-11
- Contexto: revision anti over-engineering del runner Docker.
- Riesgo detectado: la opcion `runtime-user` en CLI y su logica asociada aportaba complejidad sin ser requisito de SH1.
- Decision aplicada: eliminar `runtime-user` y conservar solo hardening esencial del contenedor.
- Resultado: menor superficie de configuracion, mismo comportamiento funcional en smoke/test.
- Accion preventiva: introducir opciones nuevas en CLI solo si cubren un requisito activo de la spec.

## 2026-04-12
- Contexto: revision de coherencia entre filosofia autonomy-first y tareas SH3.
- Anti-patron detectado: imponer un pre-flujo determinista (pre-localizacion heuristica) en el orquestador cuando el objetivo es que el agente decida su estrategia con tools/MCP.
- Que no hay que hacer: codificar pasos internos fijos de localizacion/razonamiento antes de llamar al agente.
- Por que estuvo mal: reduce autonomia real, sesga el comportamiento y aleja el sistema del modelo mental tipo coding-agent autonomo.
- Alternativa recomendada: limitar el orquestador a guardrails, limites e instrumentacion; delegar localizacion y secuenciacion al agente via system prompt + tools.
- Regla preventiva para futuras specs: cuando un requisito hable de autonomia, priorizar decisiones de configuracion y toolset sobre heuristicas hardcodeadas de flujo interno.

## 2026-04-12 (runtime contenedizado)
- Contexto: cambio de filosofia hacia runtime completo contenedizado para ejecucion experimental reproducible con multiples runners.
- Anti-patron detectado: depender del host para ejecutar componentes criticos del runtime (orquestador/MCPs) mientras solo se contenediza el sandbox de comandos.
- Que no hay que hacer: mezclar despliegue local host-dependent con expectativas de replicas parametrizables y comparabilidad experimental.
- Por que estuvo mal: reduce reproducibilidad, complica despliegue y dificulta comparar configuraciones entre runners.
- Alternativa recomendada: contenerizar todo el runtime operativo e instanciar runners por Compose con contrato minimo de parametros por contenedor.
- Regla preventiva para futuras specs: cuando el objetivo incluya replicabilidad experimental, cualquier dependencia de ejecucion debe residir dentro de imagenes/servicios versionados.

## 2026-04-16 (baseline Ollama + simplificacion MVP)
- Contexto: disponibilidad de maquina con GPU dedicada y objetivo de primera version funcional con coste cero.
- Anti-patron detectado: mantener baseline de proveedor remoto y limites dinamicos complejos en una fase MVP enfocada a velocidad de validacion.
- Que no hay que hacer: introducir politicas de recursos y configuraciones avanzadas que aumentan friccion antes de validar el flujo funcional end-to-end.
- Por que estuvo mal: eleva complejidad operativa, dificulta debugging y retrasa aprendizaje temprano sin mejorar la hipotesis principal.
- Alternativa recomendada: baseline Ollama por defecto y runner simple con timeout + limites opcionales.
- Regla preventiva para futuras specs: en MVP, toda complejidad adicional debe justificar una mejora medible de validacion o fiabilidad.

## 2026-04-16 (compose runner unico)
- Contexto: decision de reducir al minimo el runtime de inicio.
- Anti-patron detectado: introducir multiples servicios runner en Compose antes de tener un flujo base estable.
- Que no hay que hacer: escalar horizontalmente la orquestacion local antes de validar una ruta unica end-to-end.
- Por que estuvo mal: aumenta complejidad operativa y ruido de debugging sin aportar capacidad esencial en fase inicial.
- Alternativa recomendada: usar un runner unico parametrizable y crecer a multiples runners cuando existan necesidades experimentales concretas.
- Regla preventiva para futuras specs: primero estabilizar una instancia funcional, luego replicar configuraciones.

## 2026-04-16 (gate MVP vs expansion)
- Contexto: priorizacion de tareas para cerrar primer bugfix funcional con Compose + Ollama.
- Anti-patron detectado: mezclar en el gate del MVP objetivos de validacion minima con benchmark amplio de evaluacion.
- Que no hay que hacer: exigir en el mismo hito inicial tanto la prueba de valor minima (1 caso) como la comparativa extensa (5 casos).
- Por que estuvo mal: diluye foco, retrasa feedback temprano y complica depuracion del flujo base.
- Alternativa recomendada: fijar gate MVP con 1 caso reproducible y mover benchmark de 5 casos a fase de expansion.
- Regla preventiva para futuras specs: separar explicitamente criterios de cierre MVP de objetivos de escalado experimental.

## 2026-04-18 Makefile mínimo
- Contexto: archivo Makefile para la ejecucion de comandos regulares
- Anti-patron detectado: El archivo esta creciendo con comandos que no son puramente imprescindibles.
- Que no hay que hacer: añadir comandos al archivo que no son muy importantes
- Por que estuvo mal: sobrecomplica el archivo y añade comandos que en general no aportan tanto
- Alternativa recomendada: Analizar siempre si un comando es muy importante y realmente ayuda meterlo en el makefile. Si no, simplemente ejectar de manera normal
- Regla preventiva para futuras specs: No introducir comandos si no son imprescindibles

## 2026-04-18 (tests de lifecycle Git)
- Contexto: implementacion de rama temporal por run en SH4.
- Anti-patron detectado: ejecutar tests de orquestador sobre el repo real sin aislar operaciones Git.
- Que no hay que hacer: dejar que tests unitarios creen/cambien ramas en el workspace de desarrollo.
- Por que estuvo mal: introduce efectos colaterales, ensucia ramas locales y puede ocultar fallos reales por estado mutable del repo.
- Alternativa recomendada: en tests de flujo, mockear deteccion de repo Git por defecto; para validar operaciones reales, usar repos temporales dedicados.
- Regla preventiva para futuras specs: cualquier test que toque Git debe ejecutarse en sandbox temporal o con mocks estrictos de comandos de rama.

## 2026-04-18 (spec/tasks no absolutas)
- Contexto: revisiones de alcance donde la vision del usuario no siempre coincide con tasks heredadas.
- Anti-patron detectado: asumir specs y tasks como verdad absoluta y ejecutarlas de forma ciega.
- Que no hay que hacer: implementar por inercia sin cuestionar si el subhito sigue alineado con objetivo, filosofia y direccion actual del proyecto.
- Por que estuvo mal: en desarrollo incremental, decisiones antiguas pueden quedar desalineadas o ser incompatibles con el estado real del sistema y la vision vigente.
- Alternativa recomendada: antes de analizar o implementar, validar explicitamente: (1) alineacion de spec con objetivo/filosofia, (2) utilidad real de tasks para el proposito, (3) posibles incompatibilidades tecnicas o de direccion.
- Regla preventiva para futuras specs: no iniciar implementacion sin una mini-validacion estrategica previa y, si hay dudas de vision general, preguntar al usuario antes de ejecutar.

## 2026-04-18 (observabilidad resiliente)
- Contexto: implementacion de SH5 con MongoDB Atlas y fallback local.
- Anti-patron detectado: acoplar la finalizacion del run a una unica via de persistencia externa o a dependencias no siempre instaladas en todos los entornos.
- Que no hay que hacer: fallar el run completo por indisponibilidad puntual de MongoDB o por ausencia de utilidades de testing no criticas (`pytest` en entornos minimos).
- Por que estuvo mal: rompe reproducibilidad operativa y degrada la capacidad de recoger evidencia experimental en escenarios reales.
- Alternativa recomendada: persistencia best-effort con fallback JSONL local obligatorio y validacion por `unittest` cuando `pytest` no esta disponible.
- Regla preventiva para futuras specs: toda capacidad experimental critica debe tener ruta degradada no bloqueante y estrategia de validacion portable.

## 2026-04-23 (MCP innecesario en MVP)
- Contexto: reorientacion del baseline hacia tools locales del SDK para el MVP.
- Anti-patron detectado: depender de MCP servers para capacidades que ya pueden resolverse con tools locales del runtime.
- Que no hay que hacer: mantener MCP/websearch en el camino critico del baseline cuando el objetivo inmediato es validar el loop tool-driven.
- Por que estuvo mal: añade superficie de despliegue, mas puntos de fallo y ruido conceptual en una fase donde la prioridad es ejecutar y validar cambios locales.
- Alternativa recomendada: exponer un toolkit APR local con perfiles claros y dejar MCP fuera del MVP.
- Regla preventiva para futuras specs: si una capability ya existe en el SDK de tools o puede implementarse localmente, preferirla antes que introducir un servidor adicional.

## 2026-04-26 (errores transitorios del proveedor)
- Contexto: ejecuciones QuixBugs intermitentemente abortadas por 500 del backend del modelo durante el parsing de tool calls.
- Anti-patron detectado: tratar un fallo transitorio del provider como error terminal del run.
- Que no hay que hacer: convertir un 500 puntual o un timeout de red en `infra_failure` definitivo sin reintento.
- Por que estuvo mal: los runs se cortan aunque el backend se recupere en el siguiente intento, degradando la tasa de exito sin aportar senal util.
- Alternativa recomendada: retry exponencial con backoff y clasificacion explicita de errores transitorios antes de propagar fallo terminal.
- Regla preventiva para futuras specs: si el fallo es del proveedor y es razonablemente recuperable, preferir retry acotado antes que abortar el run.

## 2026-05-01 (modelos locales y structured output en handoff)
- Contexto: modelos locales Ollama (qwen2.5-coder:14b, qwen3.5:9b) no siguen handoffs de forma consistente en la arquitectura multi-agente.
- Anti-patron detectado: asumir que modelos locales seguiran instrucciones de handoff (output_schema=None para intermediarios, output_type estricto para validator) sin validacion previa.
- Que no hay que hacer: desplegar arquitectura handoff con modelos locales sin verificar capacidad de seguir structured output y handoffs.
- Por que estuvo mal: el triage agent usa tools pero no entrega al localizer; el validator debe producir AgentFixIterationRecord pero modelos locales generan texto libre.
- Alternativa recomendada: (1) usar modelos con mejor seguimiento de instrucciones para handoff (GPT-4, Claude, Gemini), (2) simplificar prompts o usar output_schema mas permisivo como fallback, (3) documentar compatibilidad de modelos por arquitectura.
- Regla preventiva para futuras specs: validar modelo por arquitectura antes de asumir que handoff funciona; ofrecer fallback a mono_agent cuando el modelo no soporta structured output.

## 2026-05-01 (instrucciones de handoff vs mecanismo del SDK)
- Contexto: arquitectura handoff fallaba porque el modelo retornaba texto en lugar de llamar herramientas de handoff.
- Anti-patron detectado: escribir prompts que ensenan al modelo a producir texto con secciones "HANDOFF:" cuando el SDK espera que llame una funcion `transfer_to_<agent>`.
- Que no hay que hacer: incluir formatos de output de texto (SUMMARY/SIGNALS/HANDOFF) para agentes que deben usar handoff tools del SDK.
- Por que estuvo mal: el modelo sigue las instrucciones literales y escribe texto; el SDK interpreta ese texto como `final_output` y nunca se ejecuta el handoff.
- Alternativa recomendada: (1) usar `agents.extensions.handoff_prompt.RECOMMENDED_PROMPT_PREFIX` para ensenar al modelo el mecanismo de handoff del SDK, (2) eliminar formatos de output de texto para agentes intermediarios, (3) instruir explicitamente "llama la herramienta transfer_to_X" en lugar de "escribe HANDOFF:".
- Regla preventiva para futuras specs: cuando se use handoff del SDK, nunca mezclar instrucciones de formato de texto con expectativas de llamada a tool; usar el prompt prefix oficial del SDK.

## 2026-05-01 (resiliencia ante limites de turnos)
- Contexto: modelos locales excedian `max_turns` sin producir output final, causando fallo total del run aunque hubieran aplicado cambios utiles.
- Anti-patron detectado: tratar `MaxTurnsExceeded` como error terminal sin evaluar el trabajo realizado durante el run.
- Que no hay que hacer: dejar que una excepcion de turnos aborte el run cuando el agente ya ha modificado archivos y los tests pasan.
- Por que estuvo mal: desecha trabajo util y reduce la tasa de exito por un artefacto del mecanismo de control (limite de turnos) en lugar de un fallo real.
- Alternativa recomendada: capturar `MaxTurnsExceeded` en el provider, retornar un fallback record con `status="done"` (para que el stop policy evalue tests/diff), y dejar que la iteracion continue o finalice segun la evidencia observable.
- Regla preventiva para futuras specs: toda excepcion del SDK que pueda ocurrir tras trabajo util debe convertirse en fallback record, no en error terminal.

## 2026-05-01 (ModelBehaviorError como fallo de capacidad, no transitorio)
- Contexto: modelos locales no producen structured output para AgentFixIterationRecord; el provider reintentaba 5 veces re-ejecutando todo el pipeline handoff.
- Anti-patron detectado: clasificar ModelBehaviorError como error retryable y re-ejecutar el pipeline completo desde triage.
- Que no hay que hacer: reintentar ModelBehaviorError con re-ejecucion completa del pipeline multi-agente.
- Por que estuvo mal: cada reintento re-ejecuta triage→localizer→patcher→validator, quemando 60-90s por intento; el modelo local no va a producir structured output de repente.
- Alternativa recomendada: tratar ModelBehaviorError como fallo de capacidad (no transitorio), retornar fallback record con status="done" y dejar que el stop policy evalue cambios reales.
- Regla preventiva para futuras specs: distinguir errores de capacidad del modelo de errores transitorios de infraestructura; solo reintentar los segundos.

## 2026-05-01 (config separada de secrets)
- Contexto: .env mezclaba API keys, provider config y run-specific config (RUN_REPOSITORY, RUN_TEST_COMMAND, RUNNER_A/B/C) en un solo archivo.
- Anti-patron detectado: almacenar configuracion de ejecucion experimental junto con secrets en .env.
- Que no hay que hacer: usar .env para parametros que cambian por experimento (bug, arquitectura, modelo).
- Por que estuvo mal: .env no es versionable, no soporta multiples configuraciones simultaneas y mezcla concerns diferentes.
- Alternativa recomendada: .env solo para secrets y provider defaults; batch YAML para configuracion experimental (arquitectura, modelo, bugs, prompts).
- Regla preventiva para futuras specs: separar secrets de configuracion experimental; usar formatos declarativos versionables para lo segundo.

## 2026-05-02 (nunca ejecutar el agente sobre el repo de desarrollo)
- Contexto: validacion e2e del refactor de adapters donde se ejecuto `autofix run` con `RUN_REPOSITORY=$(pwd)` sobre el repo del proyecto.
- Anti-patron detectado: ejecutar el flujo del agente directamente en el repositorio de desarrollo del usuario.
- Que no hay que hacer: invocar `autofix run` o `run_agent_baseline` con un path que apunte al repo de trabajo local del usuario.
- Por que estuvo mal: el flujo crea ramas temporales (`autofix/...`), modifica archivos y deja el repo en un estado no deseado; ademas, el run debe vivir dentro del contenedor Docker, no en el host.
- Alternativa recomendada: para validar e2e, usar dry-run (`--dry-run`) o ejecutar dentro de un contenedor Docker con un repo clonado en un workspace temporal aislado (`benchmark-workspaces/` o `/tmp`).
- Regla preventiva para futuras specs: nunca ejecutar agentes APR sobre el repo de desarrollo del usuario; siempre usar workspaces aislados o contenedores.

## 2026-05-02 (sandbox Docker: un contenedor por bug)
- Contexto: aclaracion del modelo de ejecucion tras el refactor de adapters.
- Anti-patron detectado: asumir que el agente puede ejecutarse en el host o compartir estado entre bugs.
- Que no hay que hacer: (1) ejecutar `autofix run` directamente en el host, (2) reutilizar un contenedor para multiples bugs, (3) hacer que el agente modifique el filesystem del host.
- Por que estuvo mal: el host solo orquesta; todo trabajo del agente (git branches, edits, tests) debe estar encapsulado en un contenedor efimero que muere tras cada bug. Reutilizar contenedores o ejecutar en host rompe aislamiento y deja artefactos.
- Alternativa recomendada: `BatchRunner` en host prepara workspace → lanza `docker compose run --rm` por bug → monta `./benchmark-workspaces:/benchmark-workspaces` → `RUN_REPOSITORY=/benchmark-workspaces/<batch>/<case>` → container ejecuta y muere.
- Regla preventiva para futuras specs: el agente APR siempre corre dentro de un contenedor Docker efimero; el host nunca ejecuta logica del agente ni toca repos objetivo.

## 2026-05-02 (prompt engineering para modelos debiles)
- Contexto: modelo local qwen3.5:9b ignora sistemáticamente instrucciones sobre no modificar tests y hacer tool calls redundantes; desperdicia 40-60% de turns en llamadas redundantes.
- Anti-patron detectado: instrucciones suaves ("Do not make redundant tool calls") sin consecuencias explícitas ni ejemplos concretos de lo que NO hacer.
- Que no hay que hacer: dejar las restricciones críticas enterradas en secciones secundarias del prompt o formularlas como sugerencias sin consecuencias.
- Por que estuvo mal: modelos débiles no siguen instrucciones implícitas; necesitan consecuencias explícitas ("your iteration will be REJECTED"), posición prominente (ABSOLUTE RULES), y anti-patrones concretos.
- Alternativa recomendada: (1) elevar restricciones críticas a ABSOLUTE RULES con consecuencias explícitas, (2) añadir TURN BUDGET AWARENESS para crear urgencia, (3) enumerar ANTI-PATTERNS concretos, (4) hacer restricciones no terminales (retryable) con feedback explícito inyectado en el prompt de la siguiente iteración.
- Regla preventiva para futuras specs: para modelos débiles, las instrucciones de sistema deben combinar (a) reglas absolutas con consecuencias, (b) ejemplos negativos concretos, (c) feedback de errores previos en el prompt de continuación, y (d) noción de presupuesto limitado.

## 2026-05-02 (validación retryable vs terminal)
- Contexto: `test_file_modified` era terminal (FAILED/VALIDATION_FAILURE) sin oportunidad de reintento; el agente perdía toda la corrida por un error corregible.
- Anti-patron detectado: tratar toda violación de validación como error terminal sin distinguir entre errores corregibles (modificar tests) y errores estructurales (diff integrity, regression).
- Que no hay que hacer: terminar el run por una violación de política que se puede corregir revirtiendo cambios y dando feedback al agente.
- Por que estuvo mal: el agente hace un intento completo, pierde los cambios de código fuente válidos, y no recibe feedback explícito sobre qué hizo mal.
- Alternativa recomendada: clasificar validaciones en retryable (test_file_modified, con rollback + feedback) y terminal (diff_integrity, regression). Para las retryable: restaurar workspace, inyectar feedback explícito en el prompt de la siguiente iteración, y permitir un reintento.
- Regla preventiva para futuras specs: distinguir siempre entre violaciones corregibles (retryable) y errores estructurales (terminal); las corregibles deben incluir rollback y feedback, no solo rechazo.

## 2026-05-05 (estrategias de provider vs condicionales)
- Contexto: refactor de configuración LLM para eliminar `LLM_MAX_TURNS` como env var y desacoplar URLs de providers.
- Anti-patron detectado: múltiples `if provider is X` en `from_env()` + atributo específico `ollama_base_url` en `LLMSettings` + funciones parsers helper para cada tipo de campo.
- Que no hay que hacer: duplicar la misma lógica "si provider A, usa configuración X; si provider B, usa configuración Y" en muchas partes; mantener URLs provider-specific como atributos en la clase.
- Por que estuvo mal: viola OCP (abrir/cerrado), dificulta agregar providers nuevos, y esparce configuración provider-specific en lugares incoherentes.
- Alternativa recomendada: (1) crear un map estático `PROVIDER_DEFAULT_URLS = {"ollama": ..., "openai": ..., "gemini": ...}`, (2) usar lookups simples en `from_env()` en lugar de condicionales, (3) delegar configuración específica al map y resolver valores de forma centralizada.
- Beneficio aplicado: OCP logrado (agregar provider solo requiere agregar entrada al map), DIP mejorado (no dependencias de provider-specific logic), SRP reforzado (cada part tiene una responsabilidad clara).
- Regla preventiva para futuras specs: cuando detectes múltiples `if variant` en lógica compartida, prefiere un map + lookup o estrategia sobre condicionales; esta es una señal de que la configuración debería estar centralizada.

## 2026-05-06 (proteger el repo de desarrollo de operaciones destructivas)
- Contexto: `make test` ejecutaba `unittest` y en validaciones retryable el flujo llamaba a `restore_all_changes()` (git checkout + git clean -fd) sobre `cfg.repo_root`, que por defecto apuntaba al workspace local del desarrollador.
- Anti-patron detectado: permitir que código de producción ejecute operaciones destructivas de Git en el repositorio de desarrollo sin guardrail.
- Que no hay que hacer: (1) dejar que `repo_root` por defecto sea `Path(".")` en tests o ejecuciones locales, (2) no proteger `restore_all_changes` contra ejecución en el proyecto actual, (3) confiar únicamente en mocks para evitar daños colaterales en tests.
- Por que estuvo mal: un solo test que llegue al flujo real puede borrar el working directory del desarrollador (archivos no commiteados, cambios en progreso, etc.), con pérdida de trabajo irreversible.
- Alternativa recomendada: (1) **Guardrail de producción**: en `restore_all_changes`, detectar si el target es el repo del proyecto (via `__file__` del paquete) y bloquear con `RuntimeError` salvo override explícito (`AUTOFIX_ALLOW_RESTORE=1`), (2) **Aislamiento en tests**: usar `tempfile.mkdtemp()` como `repo_root` por defecto en helpers de test, (3) **Mock defensivo**: mockear `restore_all_changes` en `setUp` de cualquier test de integración que use `WorkspaceManager` real.
- Regla preventiva para futuras specs: cualquier operación destrutiva sobre filesystem/Git debe tener (a) guardrail que bloquee el proyecto de desarrollo, (b) aislamiento por defecto en tests, y (c) mocks defensivos en la capa de integración.