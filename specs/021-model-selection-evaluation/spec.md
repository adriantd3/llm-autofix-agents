# SPEC-021 — Evaluación de Modelos Locales para Experimentación Formal

**Estado:** Cerrado
**Fecha:** 2026-05-23
**Objetivo:** Identificar qué modelos de Ollama son viables para experimentación formal de APR y justificar la selección final.

---

## Decisión final

> **Modelos para el experimento formal: `qwen3.5-9b-ctx65k` (baseline open-source), `gemma4-26b-ctx32k` (modelo grande local) y `gpt-5.4-mini` (propietario SOTA). `qwen3-coder:30b` descartado del experimento formal; su resultado (0/4) se documenta como hallazgo del proceso de selección.**

**Modelos seleccionados para el experimento formal:**

| Modelo | VRAM | Tool calling | Score hard | Rol en experimento |
|--------|------|--------------|------------|-------------------|
| `qwen3.5-9b-ctx65k` | 6.6 GB | nativo | **3/4** ✅ | baseline open-source pequeño |
| `gemma4-26b-ctx32k` | 18 GB | workaround | 2/4 | modelo grande local (exploratorio) |
| `gpt-5.4-mini` | API | nativo OpenAI | — | baseline propietario SOTA |

**Por qué gemma4 en lugar de qwen3-coder:**
- `qwen3-coder:30b` obtuvo 0/4 en el benchmark de selección con over-exploración destructiva y test overfitting. Añadirlo al experimento formal (53 bugs × 3 arquitecturas) produciría un dataset de fallos sin nuevo insight — el veredicto es el 0/4 de selección.
- `gemma4-26b-ctx32k` obtiene 2/4 y genera datos reales comparables en todas las arquitecturas. Es el único modelo local de 26B funcional.
- El workaround de tool calling de gemma4 es un confound conocido; se documenta como limitación en la memoria y los resultados de gemma4 se analizan como comparación exploratoria, no como fair comparison directa.

**Hallazgo de selección retenido (no en experimento formal):**
`qwen3-coder:30b` 0/4 — la hipótesis "un modelo RL-entrenado en SWE-Bench superará a un generalista" queda refutada en este entorno: over-exploración (15+ execute_cmds/iteración), test overfitting sistemático → validation_failure. El resultado se presenta en el capítulo de evaluación como contexto del proceso de selección.

---

## Contexto

El sistema de APR requiere que el modelo realice tool calling fiable en bucles de múltiples turnos (hasta 30), leyendo archivos, aplicando parches y ejecutando tests. El entorno de prueba es un RTX 4090 (24 GB VRAM). La selección de modelos busca tres perfiles distintos: un modelo propietario SOTA, un modelo open-source pequeño de uso general y un modelo open-source mayor especializado en código.

La exploración en esta spec cubre únicamente los **modelos de Ollama**. El modelo propietario queda fuera de alcance.

Dataset de prueba de referencia: `bugsinpy-hard-mono.yaml` (4 bugs: tornado-6, ansible-1, ansible-2, scrapy-33).

---

## Hallazgos por modelo

### 1. devstral-ctx45k — `0/4`

- **Tamaño:** 14.3 GB
- **Fallo:** Ejecuta exactamente 1 tool call por iteración y luego genera `finish_reason: stop`. El SDK de OpenAI Agents interpreta el `stop` como fin de turno del agente y cierra el loop sin continuar. Resultado: 0 cambios en todos los runs.
- **Causa raíz:** El modelo Mistral-format devstral detiene la generación de tool calls demasiado pronto en el contexto APR. No es un bug del framework — el modelo genuinamente para.
- **Veredicto:** Inviable. Comportamiento de parada prematura no superable con configuración.

---

### 2. mistral-small32-ctx45k — `0/4`

- **Tamaño:** 15.2 GB
- **Fallo:** `sdk_error` en la primera herramienta útil — llama a `read_file(start_line=0, end_line=40)` omitiendo el argumento obligatorio `path`. El SDK rechaza la llamada.
- **Causa raíz:** El modelo genera llamadas de herramienta con argumentos incompletos. No es un error de schema del framework; el modelo interpreta incorrectamente la firma de las tools.
- **Veredicto:** Inviable. Herramienta mal construida desde el primer turno, sin señal de mejora.

---

### 3. hermes3-8b-ctx45k — `0/4`

- **Tamaño:** 4.7 GB
- **Fallo:** Genera 1 tool call por iteración en contextos complejos. En `run_test_target` produce `tool_error`. Incapaz de encadenar lecturas y ediciones.
- **Causa raíz:** Modelo de 8B con capacidad de multi-step tool use insuficiente para el contexto de APR (traceback + ficheros + historial de iteraciones).
- **Veredicto:** Inviable por tamaño y capacidad de razonamiento, no por incompatibilidad técnica.

---

### 4. llama3.1-8b-ctx45k — `0/4`

- **Tamaño:** 4.9 GB
- **Fallo:** `finish_reason: stop, tool_calls=0`. El modelo describe en texto las acciones que "realizaría" pero nunca emite una llamada de herramienta real.
- **Causa raíz:** Llama 3.1 8B no activa el tool calling en formato Ollama para este tipo de prompts. Genera texto libre en lugar de JSON de herramienta.
- **Veredicto:** Inviable. El modelo no llama tools en absoluto.

---

### 5. deepseek-r1:14b, phi4-14b-ctx45k, gemma3:12b

- **Fallo:** Sin soporte de tool calling en Ollama para estos modelos en el setup actual. Solo generan texto/pensamiento/visión.
- **Veredicto:** Inviables sin implementar un workaround específico de renderer/parser. No explorados en detalle.

---

### 6. gemma4-26b-ctx45k (think=off) — `0/4`

- **Tamaño:** 17 GB
- **Fallo:** Produce `<channel|><thought>` en el output visible con think=off. El output del modelo se corrompe con fragmentos de tokens de thinking expuestos en el texto.
- **Veredicto:** Inviable con esta configuración de contexto.

---

### 7. gemma4-26b-ctx45k (think=on) — `0/4`

- **Tamaño:** 17 GB
- **Fallo:** En el caso ansible-2, la tool `replace_in_file` generó un bloque de 167 líneas para reemplazar 4 líneas. El resultado fue código Python con error de sintaxis (exit_code=4). La generación larga y garbled es característica del contexto 45k con think=on en este modelo.
- **Veredicto:** Inviable con ctx45k.

---

### 8. gemma4-26b-ctx32k (think=on) — `2/4` ✅

- **Tamaño:** 17 GB
- **Resultado:** Único modelo local no-Qwen que produjo fixes correctos. Fijó ansible-2 y scrapy-33.
- **Mecanismo:** Tool calling vía renderer/parser personalizado (no nativo). El modelo genera los tool calls correctamente en contextos cortos (ctx32k).
- **Patrones de comportamiento observados:**
  - `reasoning_summary: "Model returned empty text output"` en ~80% de iteraciones — todo el razonamiento queda en thinking tokens internos, sin texto visible.
  - Alucinaciones recuperables: scrapy-33 iter 2 buscó `failure_to_exc_info` cuatro veces con la misma query (función inventada, no existe en scrapy). 24 tool calls sin cambios.
  - Error de sintaxis en iter 1 de ansible-2 (exit_code=4), recuperado en iter 3.
  - `replace_in_file` con `old_text_not_found` en iter 3 scrapy-33 (texto alucinado), recuperado en siguiente tool call.

---

## Por qué gemma4:26b NO es una buena opción para experimentación formal

### 1. Tool calling vía workaround no comparable

gemma4 no soporta tool calling nativo en Ollama. El sistema usa un renderer/parser personalizado que formatea las herramientas en el prompt y parsea las respuestas. Esto introduce un confound: al comparar gemma4 con qwen3.5:9b (tool calling nativo), no se está midiendo solo la capacidad del modelo sino también el efecto del mecanismo de tool calling. Los resultados no son comparables de forma limpia.

### 2. Razonamiento completamente opaco

El campo `reasoning_summary` reporta "Model returned empty text output" en la mayoría de iteraciones. Con `think=on`, el modelo realiza toda la inferencia en tokens de pensamiento que no son capturados por el framework. Para un TFM que necesita analizar y comparar el comportamiento de los agentes, esta opacidad hace inviable el análisis cualitativo. No se puede saber por qué el modelo tomó una decisión.

### 3. Alta varianza y alucinaciones frecuentes

El modelo alucina de forma sistemática en detalles concretos (funciones que no existen, fragmentos de texto que no están en los ficheros, código con errores de sintaxis) y necesita varias iteraciones para recuperarse. Los éxitos ocurren *a pesar* de las alucinaciones, no porque el modelo sea fiable. Esto eleva la varianza de los resultados: el mismo bug podría pasar o no dependiendo de si la alucinación se produce en la iteración decisiva.

### 4. Sensibilidad al tamaño de contexto no documentada

ctx45k → 0/4 (garbled output o parada prematura). ctx32k → 2/4. La diferencia de rendimiento entre dos configuraciones del mismo modelo base es drástica y no está documentada por el proveedor. En experimentación formal esto es un factor de confusión que dificulta reproducir resultados en otro entorno.

### 5. Throughput y ocupación VRAM

17 GB VRAM → 1 run simultáneo en RTX 4090. Con el patrón de 3 iteraciones × 7-28 tool calls × latencia de thinking, un batch de 50 bugs puede tardar varias horas. Esto hace que la experimentación completa sea costosa en tiempo y dificulta repeticiones estadísticamente significativas.

---

## Selección de modelos recomendada

| Rol | Modelo | VRAM | Hard benchmark | Justificación |
|-----|--------|------|----------------|---------------|
| Propietario | GPT-4o-mini o Claude Haiku | API | — | SOTA baseline, tool calling fiable, bajo coste por token |
| Open-source baseline | `qwen3.5:9b` | 6.6 GB | — (pendiente) | Tool calling nativo, bottom line confirmado, permisivo para comparación |
| Open-source large | `qwen3:8b` | 5.2 GB | 1/4 | Mejor score open-source confirmado en hard benchmark |

> **Nota**: No existe candidato code-especializado viable. qwen3-coder:30b (0/4) y gemma4:26b-ctx32k (2/4 pero con workaround y razonamiento opaco) son las únicas alternativas evaluadas. qwen3:8b se incluye como referencia pero tampoco es viable para experimentación formal (fallo en bugs complejos).

La combinación qwen3.5:9b + qwen3-coder:30b permite una narrativa de investigación clara: ¿aporta más la especialización en código o el tamaño del modelo para tareas de reparación automática de software?

### Por qué qwen3-coder:30b es el candidato code-especializado óptimo

**Arquitectura MoE** (qwen3moe): 30.5B total, 3.3B activos por token. VRAM 19 GB (Q4_K_M) + ~3 GB KV cache 32K = ~22 GB → cabe en RTX 4090 con margen.

**Entrenamiento orientado a APR**: 7.5T tokens (70% código), scaling context nativo 256K. Post-training con Long-Horizon RL en SWE-Bench Verified: entrenado a "planear, usar herramientas, recibir feedback y tomar decisiones" en bucles multi-turno — exactamente el patrón del sistema APR. SOTA entre open-source en SWE-Bench sin test-time scaling.

**Tool calling nativo**: arquitectura qwen3moe detectada automáticamente por Ollama, `tools` capability listada, mismo stack que qwen3.5:9b. No requiere renderer/parser custom.

**Velocidad de inferencia**: al activar solo 3.3B de 30.5B parámetros, el cómputo por token es equivalente a un modelo de 3-4B → throughput alto pese al tamaño en disco.

---

## Fixes de framework aplicados durante la exploración

Durante las pruebas con gemma4 se identificaron y corrigieron dos bugs reales del framework:

1. **`workspace/manager.py` — `restore_test_files()`**: método nuevo que revierte únicamente los ficheros de test modificados por el agente, preservando los cambios en ficheros fuente.
2. **`iteration/decision_enactor.py` — revert selectivo**: cuando la validación es `test_file_modified` y la decisión es `retry`, se llama a `restore_test_files()` en lugar de `restore_all_changes()`. Antes de este fix, si el agente aplicaba un fix correcto en source y además tocaba un fichero de test, el fix se descartaba completamente.

Estos fixes son lógicamente correctos aunque no fueron el factor determinante en los runs exitosos de gemma4-ctx32k (el modelo no llegó a modificar ficheros de test en esos runs).

---

## Fase 2 — Exploración modelos ≤5 GB con tool calling nativo (2026-05-23)

**Objetivo:** Encontrar el mejor modelo de código que quepa en ~4-5 GB VRAM con tool calling nativo fiable.

### Hallazgos sobre RENDERER/PARSER en Ollama 0.24.0

El soporte de tool calling nativo (campo `tool_calls` en la respuesta, no texto en `content`) depende del par RENDERER/PARSER en el Modelfile. Los renderers disponibles en la instalación son solo `qwen3.5` y `gemma4`.

| Renderer | Modelos compatibles |
|----------|---------------------|
| `qwen3.5` | qwen3.5:9b, qwen3:8b y familia Qwen3 |
| `gemma4` | gemma4:26b y familia Gemma4 |

### 9. qwen2.5-coder:7b — `inviable` (tool calling no nativo)

- **Tamaño:** 4.7 GB — encaja perfectamente en el rango objetivo
- **Template:** tiene plantilla interna con `<tool_call>` XML pero el modelo pone la llamada en `content` como texto
- **Test:** `finish_reason: stop`, `tool_calls: None`, content = JSON de la tool call como string
- **Intentos de RENDERER:** `qwen2.5` → error ("unknown renderer"), `qwen3` → error, `qwen3.5` → genera XML en content (malformado, no funcional)
- **Causa raíz:** qwen2.5-coder es arquitectura distinta a qwen3.5. Sin renderer nativo, el SDK no puede procesar sus respuestas como tool calls estructurados.
- **Veredicto:** Inviable. Sin workaround de parser custom, no puede integrarse con el OpenAI Agents SDK.

### 10. qwen3:8b (think=false) — evaluación en curso

- **Tamaño:** 5.2 GB — ligeramente por encima del límite de 5 GB pero justificable
- **Tool calling:** ✅ Nativo — `finish_reason: tool_calls`, `tool_calls: [...]` estructurado
- **Config:** Modelfile `qwen3-8b-ctx32k` con `num_ctx 32768`, `think=false` para menor latencia
- **Smoke test:** Llamada simple `read_file` → tool call correcto con argumentos bien formados

#### Análisis tornado-6 (batch `20260523T060958Z`)

**Iteración 1 (9 tool calls, 175s):**
- search_files → read_file → 1× replace_in_file (ok) → run_test (exit_code=2) → 4× replace_in_file adicionales sobre el mismo `old_hash` → run_test (exit_code=2)
- Patrón de bug: El modelo usa `replace_all=False` con el mismo `old_hash` en múltiples llamadas consecutivas. Cada reemplazo exitoso añade contenido porque el texto insertado todavía contiene el patrón original. Resultado: archivo crece de 9747 → 10251 bytes (5 inserciones del mismo bloque → código repetido × 5 veces).
- Error resultante: `IndentationError: expected an indented block` en línea 48 (código garbled).
- La iteración termina con "Model returned text output instead of structured output".
- El modelo reporta en su `reasoning_summary`: "All tests passed" → **alucinación de éxito** cuando el test_exit_code real era 1.

**Iteración 2 (30 turns, 0 cambios reales):**
- El framework no revirtió el archivo correctamente tras iter 1 (el archivo quedó en estado garbled, 294 líneas, hash `741acfeff94b98f3`, en lugar del original 104 líneas, hash `c0f5d88e20054e5c`).
- El modelo entra en bucle: intenta `replace_in_file` con `old_hash=c0f5d88e20054e5c` (el hash de la memoria del original) → falla. Lee el archivo y descubre el hash real → intenta reemplazar con `old_hash=new_hash=741acfeff94b98f3` (no-op). Repite 30 veces.
- Resultado: MaxTurnsExceeded con 0 ficheros modificados efectivamente.
- Notas: las llamadas "exitosas" en iter 2 son todas no-ops (old_hash = new_hash → el archivo no cambia).

**Iteración 3 (en progreso):**
- Mismo patrón de iter 2. El modelo está atascado en el estado garbled del archivo y no puede salir del bucle de hashes.

**Causas raíz del fallo de qwen3:8b en tornado-6:**
1. **Bug de replace loop (iter 1):** `replace_all=False` + mismo `old_hash` → inserción repetida del mismo bloque. El modelo no reconoce que el patrón buscado sigue presente tras cada reemplazo.
2. **Alucinación de éxito (iter 1):** El modelo reporta "tests passed" cuando exit_code=2. El framework ve señales contradictorias (model=done, test=fail) y posiblemente no revierte el archivo.
3. **Confusión de estado de archivo (iters 2-3):** En las iteraciones siguientes, el modelo trabaja con el hash del archivo original (de su memoria) en lugar del hash real del archivo corrupto, resultando en 100% de errores `old_text_not_found`.

#### Resultado final qwen3:8b en bugsinpy-hard-mono (`batch-bugsinpy-hard-mono-20260523T060958Z`)

| Bug | Status | Iters | Tokens | Tiempo | Patrón de fallo |
|-----|--------|-------|--------|--------|-----------------|
| tornado-6 | ❌ failed | 3 | 633K | 1351s | replace_all=False loop → garbled → hash confusion |
| ansible-1 | ❌ failed | 3 | — | 449s | replace_all=False garble en iter 3 (328→1045 líneas) |
| ansible-2 | ✅ success | 1 | 31K | 138s | 4 tool calls: search→read→replace→test (happy path) |
| scrapy-33 | ❌ failed | 3 | — | 449s | execute_command before changes, wrong paths, wrong logic |

**Score: 1/4**

**Conclusión**: qwen3:8b solo funciona en bugs simples de una sola edición directa. En bugs que requieren razonamiento multi-paso, falla con patrones distintos: replace loop garbler (tornado-6, ansible-1) o lógica incorrecta sin garble (scrapy-33). No es viable para experimentación APR formal.


---

### Conclusión Fase 2: modelos ≤5 GB — investigación cerrada

**No existe candidato viable de código especializado en el rango ≤5 GB con tool calling nativo en Ollama 0.24.0.**

Análisis exhaustivo del espacio:

| Modelo | Tamaño | Tool calling | Especialización | Veredicto |
|--------|--------|--------------|-----------------|-----------|
| `qwen2.5-coder:7b` | 4.7 GB | ❌ texto, no nativo | código | Inviable: renderer incompatible |
| `qwen3:8b` | 5.2 GB | ✅ nativo | generalista | Inviable: replace loop + hash confusion en APR |
| `qwen3:4b` | 2.5 GB | ✅ nativo | generalista | No evaluado: demasiado pequeño, probable inviable |
| `phi4-mini:3.8b` | 2.5 GB | ✅ nativo (Ollama page) | razonamiento/math | Descartado: NO code-specialized; no aporta vs qwen3.5:9b para APR |
| `deepseek-coder-v2:16b` | 8.9 GB | ❌ no tools tag | código MoE | Inviable: sin tool calling nativo en Ollama |
| `starcoder2:7b` | 4.3 GB | ❌ no tools tag | código | Inviable: sin tool calling |
| Community `hhao/qwen2.5-coder-tools` | 4.7 GB | ⚠️ workaround | código | Inviable: mismo problema de renderer que qwen2.5-coder:7b nativo |

**Causa estructural**: En Ollama 0.24.0 sólo los modelos de arquitectura `qwen3` y `gemma4` tienen tool calling nativo o renderer disponible. La familia `qwen2.5-coder` y `deepseek-coder` no tienen renderer compatible. phi4-mini tiene tools pero no es code-specialized. Modelos code-especializados en ≤5 GB con tool calling nativo no existen en este ecosistema.

**Bottom line confirmado**: `qwen3.5:9b` (6.6 GB) es el modelo más pequeño viable para APR con tool calling nativo. No es código especializado pero funciona como baseline sólido.

---

### 11. qwen3-coder:30b — `0/4` ❌

- **Tamaño:** 18 GB disco, ~22 GB VRAM (Q4_K_M + KV cache 32K)
- **Arquitectura:** MoE qwen3moe — 30.5B parámetros totales, 3.3B activos por token
- **Tool calling:** ✅ Nativo — misma arquitectura que qwen3.5:9b
- **Config:** `qwen3-coder-30b-ctx32k` — `num_ctx 32768`, sin extra_body
- **Batch:** `batch-bugsinpy-hard-mono-20260523T073042Z`

#### Resultados por bug

| Bug | Status | Stop reason | Iters | Tokens | Tiempo |
|-----|--------|-------------|-------|--------|--------|
| tornado-6 | ❌ failed | max_iterations | 3 | 1.14M | 265s |
| ansible-1 | ❌ failed | validation_failure | 2 | 769K | 152s |
| ansible-2 | ❌ failed | validation_failure | 3 | 1.31M | 243s |
| scrapy-33 | ❌ failed | validation_failure | 1 | 389K | 103s |

**Score: 0/4** (peor que qwen3:8b con 1/4)

#### Análisis por bug

**tornado-6**: El modelo aplicó un patch semánticamente razonable en iter 1 (`del IOLoop._ioloop_for_asyncio[self.asyncio_loop]` con try/except KeyError). Iter 2 sin cambios de fichero (patch vacío). No hubo garbling ni hash loops como en qwen3:8b — la exploración fue limpia pero insuficiente.

**ansible-1**: Bug real: `for api in apis:` falla cuando `apis` es un `GalaxyAPI` en lugar de lista. Fix correcto: añadir `if not isinstance(apis, (list, tuple)): apis = [apis]`. El modelo identificó correctamente la línea y aplicó el fix en iter 1 (tools 012→014, 1 hash error recuperado). Pero el test siguió fallando (exit_code=1): el error pasó de TypeError a un error de autenticación HTTP (la API hace llamadas reales en el contexto del test mock). En iter 2, el modelo intentó modificar el test file (`test_collection.py`) → `test_file_modification_forbidden`, pero procedió a hacer cambios en el test de todas formas → `validation_failure` con exit_code=4 (syntax error en test).

**ansible-2**: Bug real: `__gt__` en `_Alpha` y `_Numeric` produce recursión infinita. Fix correcto: `if self == other: return False` en `__gt__` de ambas clases (qwen3:8b lo hizo en 4 tool calls). qwen3-coder:30b tomó 30 tool calls en iter 1 ejecutando 15 execute_commands de análisis antes de hacer cualquier edición, luego modificó `__lt__` (método incorrecto) y usó `is` en vez de `==`. Test resultante: exit_code=1. En iter 3 intentó modificar test files → `validation_failure`.

**scrapy-33**: 6 execute_commands antes de cualquier edición. `run_test_target` antes de cambios → `no_changes_yet` (tool 007). Path incorrecto `scrapy/scrapy/__init__.py` → file_not_found (tool 008). 24 herramientas de exploración adicionales. Al final del iter modificó 5 archivos distintos → `validation_failure` (cambios masivos no dirigidos).

#### Patrones de fallo sistemáticos

1. **Over-análisis pre-edición**: 6-15 execute_commands antes de la primera edición → quema el presupuesto de 30 turnos sin avanzar hacia el fix. En ansible-2, solo 1 de los 30 turnos del iter 1 no fue execute_command o read_file.

2. **Test overfitting**: En 3 de 4 bugs intentó modificar ficheros de test → `validation_failure`. El stop_reason es `validation_failure` (no `max_iterations`) en 3 casos — el framework paró antes.

3. **Fix en método incorrecto**: ansible-2 necesitaba `__gt__`, el modelo modificó `__lt__`. Análisis profundo pero conclusión equivocada.

4. **Token inefficiency**: 389K–1.31M tokens por bug vs 30K para ansible-2 con qwen3:8b. La exploración exhaustiva y los scripts de verificación Python (que pasaban aunque el test real fallaba) inflan el consumo sin mejorar la calidad.

#### Comportamiento positivo observado (insuficiente)

- Uso de `git_diff_summary`, `git_status_summary`, `get_workspace_info` — herramientas de estado que qwen3:8b nunca usó
- Recuperación de hash error (ansible-1: 1 error en tool 012, correcto en tool 014)
- Scripts Python de verificación independiente del runner del framework
- Sin hash confusion loops ni garbling de archivos — no cayó en los patrones degenerados de qwen3:8b

#### Por qué el entrenamiento SWE-Bench no se traduce en APR local

El entrenamiento Long-Horizon RL en SWE-Bench produce comportamiento "profesional" (exploración profunda, verificación, uso de herramientas de estado) que es contraproducente dentro del límite de 30 turnos por iteración. En SWE-Bench los agentes tienen presupuesto de turnos más alto y repositorios más grandes donde la exploración profunda es necesaria. En BugsInPy, los bugs son locales y la exploración es overhead puro.

Además, el modelo desarrolló una tendencia al test overfitting (observada en SWE-Bench como un problema conocido): cuando no puede hacer pasar el test modificando el código fuente, intenta modificar el test. El framework lo detecta y activa `validation_failure` — correcto, pero el run se pierde.

**Hipótesis rechazada**: qwen3-coder:30b NO supera a qwen3:8b en APR sobre BugsInPy. Su entrenamiento SWE-Bench no generaliza a este benchmark con el setup actual (30 turnos, bugs simples y localizados).



---

### 12. qwen3.5:9b (base ctx) — `2/4` ✅

- **Tamaño:** 6.6 GB
- **Modelo:** `qwen3.5:9b` (contexto por defecto, ~8K)
- **Tool calling:** ✅ Nativo
- **Batch:** `batch-bugsinpy-hard-mono-20260523T081218Z`
- **Nota:** Se usó el modelo base (no el modelfile ctx65k) — los resultados representan la configuración de contexto mínima.

#### Resultados por bug

| Bug | Status | Stop reason | Iters | Tokens | Tiempo | Archivos modificados |
|-----|--------|-------------|-------|--------|--------|---------------------|
| tornado-6 | ❌ failed | max_iterations | 3 | 1.42M | 1312s | 1 |
| ansible-1 | ❌ failed | max_iterations | 3 | 1.76M | 683s | 1 |
| ansible-2 | ✅ success | completed | 2 | 645K | 236s | 2 |
| scrapy-33 | ✅ success | completed | 2 | 824K | 297s | 1 |

**Score: 2/4** (mejor que qwen3-coder:30b con 0/4 y que qwen3:8b con 1/4)

#### Análisis por bug

**tornado-6 y ansible-1 (fallos):** El modelo agota los 30 turnos en cada iteración sin conseguir hacer pasar el test. No cae en test overfitting (solo modifica 1 archivo en cada caso). El patrón sugiere que el modelo encuentra el lugar del bug pero no llega a la solución correcta — posiblemente por falta de contexto (8K) en razonamiento multi-paso sobre ficheros largos.

**ansible-2 (éxito, iter 2):** 2 iteraciones, 2 archivos modificados, 645K tokens, 236s. El modelo converge en iter 2 con un fix limpio. Comportamiento similar al observado con qwen3:8b (que lo resolvió en iter 1), pero necesita una iteración extra.

**scrapy-33 (éxito, iter 2):** 2 iteraciones, 1 archivo modificado, 824K tokens, 297s. Fix correcto, solo 1 archivo modificado — no hay test overfitting ni cambios masivos (vs 5 archivos modificados por qwen3-coder:30b).

#### Diferencias clave vs qwen3-coder:30b

| Aspecto | qwen3-coder:30b | qwen3.5:9b (base) |
|---------|----------------|-------------------|
| Score | 0/4 | **2/4** |
| Test overfitting | 3/4 bugs | 0/4 bugs |
| Stop reason predominante | validation_failure | max_iterations |
| Archivos modificados (scrapy-33) | 5 | 1 |
| Token efficiency (ansible-2) | 1.31M (fallido) | 645K (éxito) |

El modelo pequeño generalista supera al modelo grande code-especializado en este setup. La diferencia no es de calidad del fix sino de disciplina en el uso de herramientas: qwen3.5:9b no intenta modificar tests, no hace over-exploración, y cuando falla es porque se queda sin turnos, no porque tome decisiones destructivas.

---

### 13. qwen3.5-9b-ctx65k — `3/4` ✅

- **Tamaño:** 6.6 GB
- **Modelo:** `qwen3.5-9b-ctx65k` (Modelfile con `num_ctx 65536`)
- **Tool calling:** ✅ Nativo
- **Batch:** `batch-bugsinpy-hard-mono-20260523T091648Z`
- **Config:** `timeout_seconds: 1500`, `iteration_timeout_seconds: 600` (timeouts de experimento real)

#### Resultados por bug

| Bug | Status | Stop reason | Iters | Tokens | Tiempo | Archivos modificados |
|-----|--------|-------------|-------|--------|--------|---------------------|
| tornado-6 | ❌ failed | max_iterations | 3 | 1.25M | 588s | 1 |
| ansible-1 | ✅ success | completed | 2 | 999K | 290s | 1 |
| ansible-2 | ✅ success | completed | 1 | 193K | 73s | 1 |
| scrapy-33 | ✅ success | completed | 1 | 328K | 123s | 1 |

**Score: 3/4** — mejora directa sobre base ctx (2/4)

#### Impacto del contexto extendido

| Bug | Base ctx ~8K | ctx65K | Mejora |
|-----|--------------|--------|--------|
| tornado-6 | ❌ 3 iters / 1312s / 1.42M tok | ❌ 3 iters / 588s / 1.25M tok | Sigue fallando, pero 2.2× más rápido |
| ansible-1 | ❌ 3 iters / 683s / 1.76M tok | ✅ 2 iters / 290s / 999K tok | **FAIL → SUCCESS** |
| ansible-2 | ✅ 2 iters / 236s / 645K tok | ✅ 1 iter / 73s / 193K tok | 3.2× más rápido, 3.3× menos tokens |
| scrapy-33 | ✅ 2 iters / 297s / 824K tok | ✅ 1 iter / 123s / 328K tok | 2.4× más rápido, 2.5× menos tokens |

El contexto extendido tiene impacto doble: en calidad (ansible-1 fail→success) y en eficiencia (todos los bugs resueltos en menos iteraciones y menos tokens). Con ctx65K el agente puede mantener el historial completo de la iteración anterior en ventana, evitando re-exploración innecesaria.

**Por qué tornado-6 sigue fallando**: es un bug de race condition en asyncio de Tornado que requiere entender la interacción entre el event loop y los callbacks de plataforma. El modelo localiza la zona problemática pero no llega a la corrección semántica correcta. No es un problema de contexto sino de razonamiento sobre concurrencia — un bug que probablemente requiere un modelo más capaz (propietario) o la arquitectura orquestador.

### Resumen comparativo de modelos evaluados en bugsinpy-hard-mono

| Modelo | Tamaño | Hard benchmark | Stop patterns | Veredicto |
|--------|--------|----------------|---------------|-----------|
| devstral-ctx45k | 14.3 GB | 0/4 | finish_reason: stop prematuro | Inviable |
| mistral-small32 | 15.2 GB | 0/4 | tool args incompletos | Inviable |
| hermes3-8b | 4.7 GB | 0/4 | 1 tool/iter | Inviable |
| llama3.1-8b | 4.9 GB | 0/4 | no emite tool calls | Inviable |
| gemma4-26b ctx45k | 17 GB | 0/4 | garbled output | Inviable |
| gemma4-26b ctx32k | 17 GB | 2/4 | test overfitting, alucinaciones | Viable pero con limitaciones |
| qwen2.5-coder:7b | 4.7 GB | — | renderer incompatible | Inviable técnico |
| qwen3:8b (ctx32k) | 5.2 GB | 1/4 | replace loop garble, hash confusion | Viable solo bugs simples |
| qwen3.5:9b (base ctx ~8K) | 6.6 GB | **2/4** ✅ | max_iterations en bugs complejos | **Viable — baseline formal** || **qwen3.5-9b-ctx65k** | **6.6 GB** | **3/4** ✅ | max_iterations solo tornado-6 | **Modelo final para TFM** || **qwen3-coder:30b** | **18 GB** | **0/4** | **over-análisis, test overfitting** | **Hipótesis rechazada** |

### Hallazgo principal

**`qwen3.5-9b-ctx65k` score: 3/4 en hard benchmark.** El contexto extendido es determinante: base ctx da 2/4, ctx65k da 3/4. La mejora no es marginal — ansible-1 pasa de fail a success, y los bugs que ya pasaban lo hacen en la mitad de tiempo y tokens.

**El modelo code-especializado rinde peor**: qwen3-coder:30b (0/4) < qwen3:8b (1/4) < qwen3.5:9b-base (2/4) < **qwen3.5-9b-ctx65k (3/4)**. La especialización SWE-Bench es contraproducente en BugsInPy con presupuesto de 30 turnos.

**Único bug sin resolver: tornado-6** — race condition asyncio, genuinamente difícil. No es un problema de contexto sino de razonamiento sobre concurrencia.

### Recomendación para experimentación formal (TFM)

1. **Modelo open-source principal**: `qwen3.5-9b-ctx65k` — **3/4 confirmado en hard benchmark**, tool calling nativo, comportamiento estable y analizable, sin test overfitting. ✅ Listo para experimentación formal.

2. **Baseline propietario**: GPT-4o-mini o Claude Haiku (API) — herramienta de comparación SOTA.

3. **No se incluye modelo code-especializado en el experimento formal**: qwen3-coder:30b (0/4) es peor que el generalista en este setup. La comparación qwen3.5-9b-ctx65k vs qwen3-coder:30b es el hallazgo de selección, no el experimento principal.

### Insight de investigación relevante

El fracaso de qwen3-coder:30b introduce una pregunta de investigación con valor para el TFM: ¿Por qué modelos entrenados en SWE-Bench (repositorios grandes, presupuesto alto de turnos) rinden peor en benchmarks de reparación localizada como BugsInPy? La hipótesis es la inadecuación entre la granularidad de la exploración aprendida y el espacio de búsqueda real del bug. Esta asimetría es observable en las trazas: el modelo usa 15+ herramientas exploratorias antes de la primera edición, un patrón óptimo para SWE-Bench pero destructivo en entornos con límite de 30 turnos y bugs unicausales.
