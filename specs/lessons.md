# Lecciones y Aprendizajes

## Plantilla de entrada
- Fecha:
- Contexto:
- Anti-patron detectado:
- Que no hay que hacer:
- Por que estuvo mal:
- Alternativa recomendada:
- Regla preventiva para futuras specs:

## 2026-05-08 (tests con mocks stale tras refactor)
- Contexto: Tras multiples refactors acumulados, la suite tenia 8 fallos clasificados como "pre-existentes".
- Anti-patron detectado: Mocks apuntando a nombre antiguo de funcion (`collect_repo_diff`) cuando el codigo usa ya `collect_repo_diff_for_paths`. Y `_patch_run_test_command` apuntando al modulo fuente (`flow.execution.tests`) en lugar de los namespaces donde `orchestrator.py` y `runner.py` tienen su binding local.
- Que no hay que hacer: Asumir que un mock en el modulo fuente intercept llamadas desde modulos que importaron la funcion con `from module import func` (binding local en import time, no referencia viva).
- Por que estuvo mal: Python `from module import func` crea un binding local al objeto. Parchear `module.func` cambia el dict del modulo fuente pero NO afecta los bindings ya creados en otros modulos. Los tests pasaban por casualidad (real command exitcode=5, no 0 ni 1, mascara el comportamiento esperado).
- Alternativa recomendada: Parchear `"target_module.symbol_name"` donde `target_module` es el modulo que LLAMA a la funcion, no el que la define. Dividir side_effect cuando hay N consumidores (orchestrator baseline vs iteration runner).
- Regla preventiva: Cuando un refactor renombra una funcion o cambia su modulo de origen, buscar todos los mocks en tests y actualizar el target. Verificar con `grep "old_name"` en `tests/`.

## 2026-05-08 (model blocker BugsInPy qwen3.5:9b)
- Contexto: BugsInPy youtube-dl-1 con mono_agent + qwen3.5:9b → partial/max_iterations.
- Anti-patron detectado: Evaluar capacidad del sistema solo en QuixBugs (bugs simples, 1 archivo, fix trivial). BugsInPy tiene bugs mas complejos (logica boolean en utils multifuncion).
- Que no hay que hacer: Concluir que el sistema falla por infra cuando el problema es capacidad del modelo.
- Por que estuvo mal: El modelo identifica el root cause correctamente pero no produce un fix valido tras 3 iteraciones. Con qwen3-coder:30b (planner_executor) el mismo bug se resuelve en 1 iteracion con exito.
- Alternativa recomendada: Para benchmarks complejos (BugsInPy), usar modelos mas potentes o arquitectura planner_executor. qwen3.5:9b es suficiente para QuixBugs.
- Regla preventiva: Cuando un run termina en `partial/max_iterations` con file_changes>0, revisar `live.md` iteracion por iteracion antes de clasificar como infra error.


## 2026-05-11 (BugsInPy Docker: venvs no son portables entre contenedores)
- Contexto: split bugsinpy-runner (prep, Python 3.8) / runner (agente+tests, Python 3.13) → todos los bugs fallaban con `import pipes` o `No module named pytest`.
- Anti-patron detectado: crear el venv del bug en un contenedor y ejecutar los tests en otro.
- Que no hay que hacer: separar prep y ejecucion de tests en contenedores con distinta version de Python en la misma ruta `/usr/local/bin/python3`.
- Por que estuvo mal: los venvs de BugsInPy contienen symlinks absolutos a `/usr/local/bin/python3`. Al ejecutar los tests en `runner` (Python 3.13), los symlinks resuelven al Python equivocado → `pipes`/`imp` no existen en 3.13.
- Alternativa recomendada: prep Y ejecucion de tests en el MISMO contenedor (`bugsinpy-runner`, Python 3.8 sistema). El agente tambien corre ahi, con uv gestionando su propio Python 3.13 en `UV_PYTHON_INSTALL_DIR=/opt/uv-python` (world-readable con `chmod -R a+rX`).
- Regla preventiva: para cualquier dataset con venvs precreados, la ejecucion de tests DEBE ocurrir en el mismo contenedor donde se creo el venv.

## 2026-05-11 (execute_command como shell generico)
- Contexto: trazas de orchestrator multi_agent_v2 muestran execute_command como 2a herramienta mas usada (36 llamadas), con cat/ls/grep/find siendo los comandos mas frecuentes.
- Anti-patron detectado: el orchestrator usa execute_command como shell de propósito general en lugar de las herramientas dedicadas.
- Que no hay que hacer: dar execute_command al orchestrator main si tiene read_file, list_files, search_files.
- Por que estuvo mal: (1) las calls son opacas (un `cat` no aporta estructura), (2) el agente puede hacer `pip install` o modificar el entorno, (3) consume turns sin aportar más info que read_file.
- Alternativa recomendada: eliminar execute_command del perfil `orchestrator_main`. Forzar uso de herramientas dedicadas. Solo el test_runner task-agent necesita execute_command para setups complejos.
- Regla preventiva: un perfil de herramientas para un agente de razonamiento no debe incluir un shell genérico si existen herramientas dedicadas para las mismas operaciones.

## 2026-05-13 (rate limit reinicia Runner.run() desde cero — pérdida de contexto)
- Fecha: 2026-05-13
- Contexto: minimax-m2.5 obtuvo un 429 a mitad de run (después de 7 tool calls). El retry reiniciaba `Runner.run(agent, user_input, ...)` con el input original, perdiendo todo lo investigado. El agente re-descubrió exactamente los mismos 7 pasos (tools 8-11 = tools 1-4), consumiendo ~280s extra.
- Anti-patron detectado: reiniciar el runner completo en cualquier error retryable, sin preservar lo que el agente ya había explorado.
- Que no hay que hacer: asumir que un retry es gratis. Con modelos lentos (>30s/turn), el overhead de re-descubrimiento puede superar el timeout del contenedor.
- Por que estuvo mal: el agente tiene un presupuesto de turns fijo. Si pierde turns re-explorando por un error de infra (rate limit), ese presupuesto se agota sin avanzar en el fix.
- Alternativa recomendada: `APRRunHooks` acumula search hits, files read y edits de forma live. En el siguiente intento, `provider.py` inyecta ese contexto en `effective_input` con el prefijo `[RECOVERY: ...]`. El agente retoma desde donde se quedó sin re-explorar. `rerun_full_runner=False` en el evento si hay contexto.
- Regla preventiva: toda mejora de resiliencia ante errores transitorios (rate limit, timeout) debe evitar no solo el fallo en sí sino también el coste de re-descubrimiento. El presupuesto de turns es un recurso escaso.

## 2026-05-13 (no overfitting en instrucciones del agente)
- Fecha: 2026-05-13
- Contexto: se evaluó añadir un hint "busca lógica de deduplicación" cuando el test falla con `N != M`. Este hint venía directamente de analizar youtube-dl-2. El handoff lo calificó como SF-3 con prioridad MEDIA-BAJA.
- Anti-patron detectado: añadir hints específicos al prompt del agente basados en un bug concreto. Los agentes deben ser agnósticos al dataset/bug (AGENTS.md regla 6).
- Que no hay que hacer: codificar en el flujo el conocimiento de un bug específico aunque esté "generalizado" superficialmente.
- Por que estuvo mal: si el hint es correcto para youtube-dl-2 pero no para otros bugs con count mismatch, empeora el fix rate general. La capacidad del modelo, no las instrucciones, debe resolver la clasificación del error.
- Alternativa recomendada: si la capacidad del modelo es el cuello de botella, cambiar el modelo; no añadir hints que overfiten. Para count mismatch genérico, el agente competente ya busca dedup/filtering.
- Regla preventiva: antes de añadir cualquier hint al prompt del agente, verificar que aplica a ≥3 bugs distintos del benchmark sin falsos positivos. Si solo aplica al bug que motivó el cambio, descartarlo.

## 2026-05-11 (explore_code task-agent ignorado)
- Contexto: en toda la campaña de 3 bugs x 3 iteraciones, explore_code fue invocado solo 1 vez. El orchestrator leía archivos directamente.
- Anti-patron detectado: instrucciones que dicen "prefer explore_code" pero no obligan a usarlo → el agente siempre toma el camino de menor resistencia (leer directamente).
- Que no hay que hacer: instrucciones opcionales para herramientas que deben ser obligatorias.
- Por que estuvo mal: el punto de la arquitectura task-agent es que el orchestrator no gaste turns leyendo archivos; sin exploración delegada, el patrón colapsa al mono-agente.
- Alternativa recomendada: instruccion MANDATORY: "CALL explore_code FIRST every iteration". Reforzar con regla de turno presupuesto.
- Regla preventiva: si un task-agent es parte del diseño de la arquitectura, las instrucciones deben obligar su uso, no sugerirlo.
- Registrar solo aprendizajes reutilizables.

## 2026-05-11 (orchestrator explora en loop y nunca escribe código)
- Contexto: youtube-dl-42 con orchestrator v2 + qwen3.5:9b → 3 iteraciones, 8-15 tool calls por iteración, 0 changed_files. El agente entendía perfectamente el fix (reasoning_summary correcto) pero generaba respuesta de texto en lugar de llamar `replace_in_file`.
- Anti-patron detectado: dar al orchestrator las mismas herramientas de exploración que al explorer task-agent (list_files, search_files, get_workspace_info). El agente elige exploración sobre edición porque tiene más opciones de "seguir investigando" que de "escribir ahora".
- Que no hay que hacer: incluir list_files, search_files, get_workspace_info, git_status_summary, git_diff_summary en APR_ORCHESTRATOR_MAIN_TOOLS.
- Por que estuvo mal: con 9 herramientas de exploración disponibles, qwen3.5:9b entra en un loop exploratorio (pattern matching de su entrenamiento: "responder con texto tras reunir info") en vez de transicionar a "modo acción". Con 12-15 calls de exploración, el modelo "decide" que tiene suficiente contexto y genera texto resumen sin llamar a replace_in_file.
- Alternativa recomendada: perfile mínimo: `APR_ORCHESTRATOR_MAIN_TOOLS = [read_file, replace_in_file, replace_lines, write_file]`. Exploración delegada EXCLUSIVAMENTE a explore_code task-agent. read_file solo para recuperar exactos old_string para replace_in_file (máx 1 call por iteración).
- Regla preventiva: el perfil de herramientas del orchestrator debe hacer que "escribir código" sea la acción más fácil disponible, no explorar más. Si hay 8 herramientas de lectura y 3 de escritura, el agente leerá 8 veces antes de escribir.

## 2026-05-11 (output_schema y ModelBehaviorError en orchestrator con qwen3.5:9b)
- Contexto: orchestrator v2 con qwen3.5:9b, `output_schema=AgentOutputSchema(AgentFixIterationRecord)` → `ModelBehaviorError` en todas las iteraciones. El modelo nunca llamaba `replace_in_file` ni `final_output`.
- Anti-patron detectado: dar `output_schema` estructurado (JSON) a un orchestrator que usa qwen3.5:9b. El SDK inyecta un tool `final_output` que el modelo debe llamar para terminar. qwen3.5:9b no llama correctamente a `final_output` → `ModelBehaviorError`.
- Que no hay que hacer: usar `output_schema=AgentOutputSchema(...)` en agentes locales con modelos pequeños (qwen3.5:9b, 9B params). El `final_output` tool crea ambigüedad: ¿llamo replace_in_file y luego final_output? ¿O solo final_output? El modelo elige solo final_output (incorrectamente) o no llama ninguno.
- Por que estuvo mal: la regla `output_schema=None REQUIRED on all agents to prevent final_output tool injection` ya estaba documentada para explorer y test_runner pero NO se aplicó al orchestrator.
- Alternativa recomendada: `output_schema=None` en todos los agentes locales, incluido el orchestrator. El provider code ya maneja texto plano vía `isinstance(output, str)`. El pipeline evalúa changed_files independientemente del output del modelo.
- Regla preventiva: toda llamada a `build_agent()` para un agente local (qwen, llama, etc.) debe incluir `output_schema=None`. Verificar en code review que el orchestrator también lo tiene.

## 2026-05-11 (sub-agente LLM para run_tests bloqueante con Ollama single-slot)
- Contexto: `run_tests` como sub-agente LLM fallaba con "An error occurred" en la primera llamada (4.885s) y en llamadas concurrentes (28.340s) cuando el orchestrator invocaba el sub-agent justo después de llamar a replace_in_file.
- Anti-patron detectado: usar un sub-agente LLM para ejecutar tests cuando el modelo local tiene un único slot de inferencia. El orchestrator termina de generar su respuesta y llama al test runner sub-agent, que intenta acceder al mismo modelo → colisión/timeout.
- Que no hay que hacer: `test_runner_agent.as_tool(tool_name="run_tests")` con modelo local single-slot.
- Por que estuvo mal: un sub-agente LLM necesita 2 llamadas LLM (1 para decidir qué herramienta llamar + 1 para resumir el resultado). Con Ollama single-slot, la segunda llamada LLM del sub-agent entra en cola detrás del orchestrator → "An error occurred" o timeout silencioso.
- Alternativa recomendada: `run_test_target` como herramienta directa en el perfil del orchestrator. Devuelve stdout/stderr directamente, el orchestrator lo lee sin necesidad de LLM intermediario. La summarización la hace el orchestrator con su propio LLM call.
- Regla preventiva: con modelos locales (single-slot), cada herramienta que llama a un sub-agente LLM puede fallar cuando el modelo ya está ocupado. Preferir herramientas directas (sin LLM) siempre que sea posible.

## 2026-05-12 (doom loop: replace_in_file con exact match falla silenciosamente)
- Contexto: trazas de youtube-dl-42 con mono_agent + qwen3.5:9b. El agente retría `replace_in_file` con el mismo `old_hash` varias veces consecutivas y cada vez recibía `old_text_not_found`. No convergía nunca.
- Anti-patron detectado: exact string match rígido en `replace_in_file` cuando el modelo puede producir `old` con espacios trailing diferentes, saltos de línea distintos (CRLF vs LF) o indentación que no coincide exactamente.
- Que no hay que hacer: retornar `old_text_not_found` sin intentar normalizaciones básicas que absorban imprecisiones del LLM.
- Por que estuvo mal: el modelo produce `old` razonablemente correcto pero con diferencias menores de whitespace; con exact match cada reintento falla identicamente → doom loop que quema todos los turnos.
- Alternativa recomendada: fallback progresivo antes de reportar not-found: (1) exact → (2) CRLF-normalize ambos lados → (3) strip trailing whitespace por línea. Reportar `fuzzy_matched: true` para trazabilidad. Excluir `replace_all=True` del fuzzy path (ambiguo con múltiples matches).
- Regla preventiva: la interfaz de herramientas debe absorber imprecisiones del LLM, no exigir perfección. Cada fallo que el agente no puede superar con información disponible es un doom loop potencial.

## 2026-05-13 (orchestrator explore_code bloqueante por SDK default max_turns=10)
- Contexto: run `batch-bugsinpy-orchestrator-local-20260513T161137Z` con youtube-dl-2. 3 iteraciones × 20 tool calls cada una, 0 changed_files. El agente leía sin escribir nunca.
- Anti-patron detectado: `Agent.as_tool()` usa `max_turns=None` por defecto, lo que resuelve en el default interno del SDK (10 turnos). Con qwen3.5:9b el explorer sub-agent consume sus 10 turnos leyendo y falla con `Max turns (10) exceeded`. El orchestrator pierde su herramienta principal de exploración y degrada a escaneo secuencial con `read_file`.
- Que no hay que hacer: llamar `explorer_agent.as_tool(...)` sin pasar `max_turns` explícito cuando el sub-agente necesita explorar ficheros grandes.
- Por que estuvo mal: el SDK default no está alineado con el propósito del explorer (puede necesitar 10-20 reads para un fichero grande). Al fallar, el orchestrator queda sin `search_files` (excluido de orchestrator_main para evitar loops exploratorios) y no puede localizar métodos en ficheros de 2600+ líneas.
- Alternativa recomendada: (1) `as_tool(max_turns=20)` explícito para el explorer, (2) añadir `search_files` de vuelta a orchestrator_main como fallback — un `search_files("def _parse_mpd_formats")` localiza el método en 1 call en lugar de 20 reads secuenciales.
- Regla preventiva: todo `Agent.as_tool()` debe incluir `max_turns` explícito adecuado al propósito del sub-agente. El default del SDK es arbitrario y puede ser demasiado bajo para tareas de lectura de código.

## 2026-05-13 (search_files es bloqueante en orchestrator_main para bugs en ficheros grandes)
- Contexto: orchestrator_main tenía `search_files` excluido para evitar loops exploratorios (lessons 2026-05-11). Con explore_code fallando y sin search_files, el agente no podía localizar `_parse_mpd_formats` en common.py (2624 líneas) → escaneo secuencial de 20 chunks de 50 líneas.
- Anti-patron detectado: eliminar search_files del orchestrator_main sin mecanismo de fallback cuando explore_code falla.
- Que no hay que hacer: asumir que explore_code siempre estará disponible y es suficiente para localizar símbolos en ficheros grandes.
- Por que estuvo mal: search_files(pattern, glob) localiza una función en 1 call; sin ella el agente necesita entre 20-50 read_file calls para escanear un fichero de 2600 líneas, agotando los turnos sin escribir nada.
- Alternativa recomendada: mantener search_files en orchestrator_main como herramienta de localización rápida. search_files es acción-orientada (devuelve file+line para usar directamente con replace_in_file) — no promueve exploración indefinida como list_files o get_workspace_info.
- Regla preventiva: distinguir entre "herramientas de browsing" (list_files, get_workspace_info → excluir del orchestrator) y "herramientas de lookup puntual" (search_files → incluir). Solo las primeras promueven loops de procrastinación.

## 2026-05-13 (instrucción de turno budget en prompt ignorada si el SDK permite más turnos)
- Contexto: orchestrator instructions decían "Maximum 5 tool calls per iteration. Stop at turn 5 regardless." pero SDK max_turns=20. qwen3.5:9b ignoró la instrucción y usó los 20 turnos.
- Anti-patron detectado: poner límites de turnos en el prompt cuando el SDK tiene un límite diferente (mayor). El modelo optimiza hacia el límite real (SDK), no el instruccional.
- Que no hay que hacer: mantener instrucciones de conteo de turnos en el prompt si no están reforzadas por el SDK.
- Por que estuvo mal: crea una incoherencia: el prompt dice "para en 5" pero el SDK deja seguir hasta 20. El modelo interpreta el límite del SDK como el real.
- Alternativa recomendada: eliminar las instrucciones de conteo de turnos del prompt. Ajustar max_turns en la config del batch si se quiere controlar el presupuesto real.
- Regla preventiva: el único límite de turnos efectivo es el que impone el SDK. Las instrucciones de conteo en el prompt son ruido si no coinciden con el max_turns de la config.

## 2026-05-13 (análisis e2e post-root-fixes: qué funcionó y qué sigue bloqueando)
- Contexto: run `batch-bugsinpy-mono-youtube-dl-42-20260513T154840Z` mono_agent + qwen3.5:9b con los 4 root-fixes implementados. Resultado: `partial` (3 iteraciones). Baseline previo (sin fixes): también `partial`. Duración: 434s vs 629s (más rápido, sin doom loops).
- **Qué funcionó correctamente:**
  1. No hay doom loops: cero reintentos de `replace_in_file` con el mismo `old_hash`. El agente avanzó.
  2. `_target_looks_like_command` funcionó: `run_test_target` recibió `target=""` en todos los calls, sin double-command.
  3. El test context extractor encontró funciones de clase (el failing test function block fue incluido en el prompt).
  4. El write_file guard disparó en el segundo intento (correct behavior given the file was already corrupted).
  5. La firma del test cambió de `2c1878772297` (ImportError puro) a `83c1ac0f2f2c` en todas las iteraciones posteriores — el agente resolvió parcialmente el ImportError.
- **Qué sigue bloqueando:**
  1. **write_file guard threshold 1/3 demasiado permisivo**: el agente escribió 19339 bytes (600 líneas) a un fichero de 37858 bytes (1163 líneas) — 51% truncación, no bloqueada. Módulo corrupto permanentemente para esas iteraciones. Corregido a 2/3.
  2. **Model over-engineering (capability limitation)**: los 3 `replace_in_file` exitosos antes del write_file no añadieron el alias de una línea (`fix_xml_ampersands = fix_xml_all_ampersand`). En su lugar modificaron funciones del módulo (~45KB de diff). Después de cada cambio, el test seguía en exit=1 — el agente continuó modificando en lugar de diagnosticar el estado intermedio.
  3. **sdk_error Invalid JSON en run_test_target (it3)**: el modelo generó JSON inválido para el tool call. Reintentó automáticamente con éxito, sin impacto real.
- **Conclusión**: los root-fixes son efectivos (eliminan el doom loop, la truncación catastrófica y el double-command). El bloqueante final es el modelo: qwen3.5:9b no puede identificar el fix mínimo de 1 línea para un ImportError de alias en un módulo de 1163 líneas. Con el guard 2/3, la iteración 1 hubiera terminado con el módulo intacto aunque incorrecto, y las iteraciones 2-3 tendrían un estado de partida correcto.
- Anti-patron detectado: evaluar "¿funciona el root-fix?" solo con una run. El resultado sigue siendo `partial`, pero el análisis de la traza muestra que el problema ya no es el doom loop o la destrucción del entorno — es la capacidad del modelo.
- Regla preventiva: al validar root-fixes de herramientas, analizar la traza completa (¿cambió el comportamiento?, ¿el agente evitó el anti-patrón?) en lugar de solo el resultado final (success/partial/failed). Un partial con traza limpia es mejor que un partial con doom loops.

## 2026-05-13 (write_file guard threshold 1/3 demasiado permisivo — evidencia e2e)
- Contexto: run e2e post-fix `youtube-dl-42` mono_agent. El agente escribió 19339 bytes (≈600 líneas) en utils.py que tenía 37858 bytes (1163 líneas). 600 > 1163//3=387 → guard NO disparó. El módulo quedó truncado al 51%.
- Anti-patron detectado: threshold de 1/3 insuficiente para truncaciones moderadas (50%). El 1/3 original solo bloqueaba stubs muy pequeños (< 33%).
- Que no hay que hacer: asumir que 1/3 cubre todos los casos destructivos. Un write de 50% ya destruye la mitad del módulo.
- Por que estuvo mal: el agente hizo 3 `replace_in_file` correctos (que añadieron el alias), luego intentó "mejorar" la implementación con `write_file`. Con 1/3 threshold, esa escritura pasó. Con el módulo truncado, los subsiguientes `replace_in_file` fallaron con `old_text_not_found` y el run no se recuperó.
- Alternativa recomendada: threshold 2/3 — bloquea cualquier write que reduzca el archivo en más de ~33%. Evidencia: con 2/3, la escritura de 600 líneas a un fichero de 1163 (51% < 66%) habría sido bloqueada.
- Regla preventiva: cuando se tune un guardrail, validar con un e2e real, no solo con el caso extremo (stub vs fichero grande). Los casos intermedios (50-60% truncación) son igualmente destructivos.

## 2026-05-12 (write_file destruye módulo existente)
- Contexto: trazas de youtube-dl-42. El agente usó `write_file` para "hacer un cambio" en `youtube_dl/utils.py` (37KB, ~1600 líneas) escribiendo un stub de 1756 bytes. El entorno quedó roto permanentemente para esa iteración (pérdida del `bugsinpy_compile_flag`).
- Anti-patron detectado: `write_file` sin guardrail que detecte truncación masiva de un fichero existente.
- Que no hay que hacer: permitir que `write_file` sobreescriba un fichero grande con contenido mucho más corto sin error explícito.
- Por que estuvo mal: `write_file` está pensado para crear ficheros nuevos o reemplazarlos completamente; los modelos lo confunden con "hacer un edit pequeño". Una vez destruido el fichero, el entorno no se recupera en esa iteración (el venv y compile_flag están basados en el fichero correcto).
- Alternativa recomendada: guard en `write_file`: si el fichero existe con >50 líneas y el nuevo contenido tiene menos de 1/3 líneas → retornar `write_file_would_truncate` con mensaje explícito que dirija al agente a `replace_in_file` o `replace_lines`.
- Regla preventiva: añadir guardrails a nivel de tool para los "errores de categoría" más comunes del modelo. Los modelos pequeños (9B) cometen sistemáticamente estos errores, y el coste de un guardrail es O(1) mientras que el coste de no tenerlo es perder toda la iteración.

## 2026-05-12 (double-command en run_test_target)
- Contexto: trazas de youtube-dl-42. El agente pasaba el comando completo tanto en `runner` como en `target`, produciendo `. env/bin/activate && bash bugsinpy_run_test.sh . env/bin/activate && bash bugsinpy_run_test.sh` → error de shell.
- Anti-patron detectado: interfaz de `run_test_target` sin validación del argumento `target`, permitiendo que el agente pase un comando completo donde se espera solo un nombre de fichero o clase de test.
- Que no hay que hacer: concatenar `runner` y `target` sin verificar que `target` es realmente un selector de test (nombre de módulo/clase/función) y no un comando de shell completo.
- Por que estuvo mal: el agente confunde el propósito de ambos parámetros, especialmente con comandos complejos que tienen múltiples partes. Las instrucciones de prompt no son suficientes para evitar el error consistentemente en modelos pequeños.
- Alternativa recomendada: `_target_looks_like_command()` que detecta metacaracteres de shell (`&&`, `||`, `;`, `|`, `$(`, ` -`, etc.) y descarta `target` si se activa. Registrar el `safe_target` en el resultado para trazabilidad.
- Regla preventiva: el tool debe ser defensivo ante el patrón de error más probable de ese modelo, especialmente para errores que producen fallos silenciosos (el shell interpreta el doble comando de forma inesperada sin error claro).

## 2026-05-12 (extracción de función de test: métodos de clase ignorados)
- Contexto: `_find_test_function_using` usaba `r'^def (test_\w+)\('` con `re.MULTILINE`. En youtube-dl, los tests están dentro de `class TestUtil(unittest.TestCase):` con indentación `    def test_xml_ampersands(self):`. El agente nunca recibía el cuerpo del test correcto en el prompt.
- Anti-patron detectado: regex `^def` que solo captura funciones de nivel 0, ignorando métodos de clase.
- Que no hay que hacer: anclar el regex a `^` (inicio de línea) cuando se buscan funciones de test que pueden estar dentro de `unittest.TestCase`.
- Por que estuvo mal: el 90% de los tests en proyectos reales (BugsInPy especialmente) usan `unittest.TestCase` con métodos indentados. El contexto de test que el agente recibe estaba vacío, forzándolo a buscar las aserciones manualmente (burns turns).
- Alternativa recomendada: eliminar el anchor `^` → `r'def (test_\w+)\('`. El body extraction con `source.find("\ndef ", ...)` puede incluir métodos hermanos, pero eso es aceptable para el check `symbol in func_body`.
- Regla preventiva: al escribir regex para buscar patrones de código, verificar con casos reales del dataset objetivo antes de asumir que el patrón cubre todos los casos. BugsInPy usa `unittest.TestCase` casi universalmente.

## 2026-05-13 (salida de test con SyntaxWarning distrae al modelo del error real)
- Contexto: todos los runs de youtube-dl-2 incluían `youtube_dl/extractor/pandatv.py:39: SyntaxWarning: "is not" with a literal.` antes del FAIL. Con qwen3.5:9b, el agente gastó 6 de sus 20 turnos buscando `pandatv.py` cuando el bug estaba en `common.py:_parse_mpd_formats`.
- Anti-patron detectado: pasar SyntaxWarning, DeprecationWarning, ResourceWarning etc. al modelo como parte del compact_test_output sin filtrar. El modelo las interpreta como errores relacionados con el bug.
- Que no hay que hacer: asumir que el modelo ignorará los warnings porque el test failure está más abajo en la salida.
- Por que estuvo mal: los warnings tienen el mismo formato que un error (`file:line: Category: message`). Un modelo de 9B no tiene suficiente razonamiento para distinguir "warning irrelevante" de "stacktrace del bug" si ambos están en el mismo bloque de texto.
- Alternativa recomendada: filtrar líneas que coincidan con `<file>:<line>: <XxxWarning>:` (y su línea de snippet indentada siguiente) en `compact_test_output` antes de pasarlas al agente. El agente siempre puede leer el archivo si quiere ver el warning.
- Regla preventiva: cualquier línea de salida de test que no sea parte del fallo real (warnings, deprecations, informational output) debe filtrarse antes de incluirla en el prompt.

## 2026-05-13 (search_files como herramienta de búsqueda de ficheros en lugar de búsqueda de contenido)
- Contexto: todos los runs de youtube-dl-2. El agente llamó `search_files("float_duration", glob="**/*.mpd")` 6-12 veces esperando encontrar el fichero `float_duration.mpd` por su nombre. `search_files` busca CONTENIDO (grep), no nombres de fichero.
- Anti-patron detectado: usar `search_files` para descubrir si existe un fichero por nombre, cuando la herramienta es un grep de contenido.
- Que no hay que hacer: excluir `list_files` del perfil del orchestrator_main asumiendo que `search_files` puede sustituirla para descubrimiento de ficheros en directorio.
- Por que estuvo mal: `list_files("test/testdata/mpd/")` habría respondido en 1 call; sin ella el agente gastó 6-12 turns con `search_files` en el directorio correcto, obteniendo 0 resultados porque buscaba el texto "float_duration" dentro de los .mpd, no el fichero con ese nombre.
- Alternativa recomendada: mantener `list_files` en `APR_ORCHESTRATOR_MAIN_TOOLS` para lookups de directorio concretos. Distinguir en el comentario del profile: `list_files` = descubrimiento de ficheros, `search_files` = búsqueda de contenido/símbolos. Excluir solo `get_workspace_info` (dump completo = procrastinación) y `execute_command` (shell genérico).
- Regla preventiva: el conjunto mínimo de herramientas del orchestrator debe cubrir los 3 modos de localización de código: (1) buscar símbolo por nombre → `search_files`, (2) listar ficheros en directorio → `list_files`, (3) leer sección específica → `read_file`. Si falta alguno, el agente improvisa con los que tiene, gastando 5-10x más turnos.

## 2026-05-13 (notas de MaxTurnsExceeded truncadas al campo `notes` con límite 8 líneas)
- Contexto: `_format_notes_block` tenía `max_lines=8`. Las notas de `MaxTurnsExceeded` incluyen "Search hits", "Files read" y "Last agent reasoning" — típicamente 12-20 líneas. Las líneas más importantes (`Files read: youtube_dl/extractor/common.py:1753-2100`) quedaban fuera del límite y el agente en la siguiente iteración re-descubría lo mismo desde cero.
- Anti-patron detectado: truncar las notas de contexto de investigación a 8 líneas cuando ese contexto es la única continuidad entre iteraciones.
- Que no hay que hacer: cap conservador de 8 líneas en `_format_notes_block` cuando las notas son el principal mecanismo de handoff entre iteraciones que terminan en MaxTurnsExceeded.
- Por que estuvo mal: si el agente en iteración N encontró `common.py:1753` con `_parse_mpd_formats` pero ese dato queda en la línea 9+ de las notas, la iteración N+1 empieza como si fuera iteración 1, re-buscando el mismo símbolo.
- Alternativa recomendada: aumentar `max_lines` a 20. Las notas son texto breve (bullets), 20 líneas son <500 chars — irrelevante vs el contexto completo del prompt. Paralelamente, `_extract_research_context` debe filtrar paths de ficheros de test/ de "Search hits" para que las líneas valiosas (source files) no queden desplazadas.
- Regla preventiva: el límite de notas debe ser suficiente para contener el contexto completo de una investigación interrumpida. Si el contexto tiene estructura fija (header + N bullets + Files read + Last reasoning), el límite debe ser mayor que N_max_bullets + 4 líneas de overhead.

## 2026-05-13 (iteración siguiente no fuerza edición cuando la previa terminó sin cambios)
- Contexto: 3 iteraciones consecutivas con 0 changed_files. El prompt de continuación decía "Continue improving the repair strategy" — idéntico tanto si el agente había aplicado un fix como si no había hecho ningún cambio. El agente volvía a explorar sin sentido de urgencia.
- Anti-patron detectado: prompt de continuación genérico que no diferencia entre "el fix falló, ajusta" (changes > 0) y "no hiciste nada, empieza ya" (changes = 0).
- Que no hay que hacer: el mismo texto de tarea para iteraciones con y sin cambios previos.
- Por que estuvo mal: el modelo interpreta "continue improving" como "puedo seguir explorando". Sin señal explícita de que la exploración ya no es aceptable, continúa el mismo patrón. La advertencia `⚠ WARNING: No source files were modified` ya estaba en el snapshot pero el task text la contradecía implícitamente.
- Alternativa recomendada: detectar `⚠ WARNING: No source files were modified` en el snapshot de la iteración anterior y sustituir el task text por: "You MUST apply a code change this iteration — reading more files without editing is not acceptable. Use the notes above to apply your best hypothesis with replace_in_file, then validate."
- Regla preventiva: el texto de tarea de cada iteración debe ser condicional al resultado de la iteración anterior. Al menos distinguir: (a) no hubo cambios → exigir edición, (b) hubo cambios pero tests siguen fallando → guiar hacia iteración de fix.

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

## 2026-05-07 (output_schema como escape hatch para modelos locales)
- Contexto: planner-executor con qwen3-coder:30b hacia 0 tool calls en todas las iteraciones; el modelo inmediatamente llamaba al tool `final_output` (inyectado por AgentOutputSchema del SDK) en vez de tools de investigación/edición.
- Anti-patron detectado: usar `output_type=AgentOutputSchema(...)` con modelos locales que priorizan el path de menor resistencia (producir structured output inmediatamente sin investigar).
- Que no hay que hacer: dar a modelos locales la opción `final_output` como tool cuando se espera que primero usen tools para investigar/editar.
- Por que estuvo mal: el modelo trataba `final_output` como la acción por defecto, produciendo reasoning_summary en JSON sin nunca llamar read_file, search_files, replace_in_file, etc.
- Alternativa recomendada: para modelos locales, usar `output_schema=None` en `build_agent()` — el modelo solo puede producir texto o llamar tools; el provider ya parsea texto libre a `AgentFixIterationRecord` como fallback.
- Resultado: de 0 tool calls → 45 tool calls (20 planner + 25 executor) con output_schema=None.
- Regla preventiva para futuras specs: evaluar si `output_type` del SDK actúa como "escape hatch" para cada modelo; con modelos locales, preferir no restringir output format para forzar tool engagement.

## 2026-05-07 (handoff del SDK inoperante con modelos locales post-transfer)
- Contexto: en planner-executor con handoff SDK, tras la transferencia planner→executor, el agente receptor (executor) producía JSON/text output sin llamar tools; `tool_choice="required"` no resolvía el problema vía Ollama.
- Anti-patron detectado: usar handoffs del SDK (transfer_to_*) con modelos locales (Ollama) que no mantienen coherencia de tool-use post-handoff.
- Que no hay que hacer: depender del mecanismo de handoff del SDK para transferir control entre agentes cuando el modelo local no sigue el contrato post-handoff.
- Por que estuvo mal: tras el handoff, el SDK asigna control al executor pero éste produce output inmediato sin tools; incluso con `ModelSettings(tool_choice="required")` el modelo local no obedece.
- Alternativa recomendada: **iteration-based phasing** — usar el mecanismo de iteraciones del sistema para alternar agentes (iteration 1=planner, iteration 2+=executor); cada agente arranca fresh con su propio prompt y tools, sin dependencia del handoff SDK.
- Resultado: executor pasa de 0 tool calls (con handoff) a 25 tool calls (con iteration-based phasing).
- Regla preventiva para futuras specs: para modelos locales, NO usar handoffs SDK; preferir phasing por iteración donde cada agente tiene un ciclo completo de ejecución independiente.

## 2026-05-07 (limitación de razonamiento del modelo: bool(v) vs v is not False)
- Contexto: bug youtube-dl-1 requiere `lambda v: v is not None and v is not False` en UNARY_OPERATORS; el modelo intenta `bool(v)` repetidamente.
- Anti-patron detectado: asumir que un modelo local (qwen3-coder:30b) puede razonar sobre la diferencia semántica entre `bool(v)` y `v is not False` incluso con instrucciones explícitas.
- Que no hay que hacer: esperar que el modelo siga una instrucción literal que dice "consider `v is not None and v is not False`" cuando su inferencia semántica no distingue ambas expresiones.
- Por que estuvo mal: 77 tool calls en handoff y 45 en planner-executor; el modelo encuentra el archivo correcto, la función correcta, pero aplica `bool(v)` que rompe assertions de x=0 y title=''.
- Impacto: este es un **bloqueante de modelo** — no un problema de arquitectura. La mejora de instrucciones y la mejora arquitectónica son correctas pero insuficientes para este modelo en este bug.
- Alternativa recomendada: (1) escalar a un modelo con mejor razonamiento (GPT-4, Claude, Gemini), (2) para modelos locales más grandes (70B+), re-evaluar capacidad de razonamiento semántico, (3) considerar few-shot examples en el prompt con el patrón correcto.
- Regla preventiva para futuras specs: al evaluar éxito de arquitecturas, separar siempre "la arquitectura funciona" de "el modelo puede resolver el bug"; usar benchmarks con distintos niveles de dificultad de razonamiento.
- Regla preventiva para futuras specs: cualquier operación destrutiva sobre filesystem/Git debe tener (a) guardrail que bloquee el proyecto de desarrollo, (b) aislamiento por defecto en tests, y (c) mocks defensivos en la capa de integración.