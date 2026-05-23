# SPEC-021 — Evaluación de Modelos Locales para Experimentación Formal

**Estado:** Cerrado (fase exploratoria concluida)
**Fecha:** 2026-05-23
**Objetivo:** Identificar qué modelos de Ollama son viables para experimentación formal de APR y justificar la selección final.

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

| Rol | Modelo | Justificación |
|-----|--------|---------------|
| Propietario | GPT-4o-mini o Claude Haiku | SOTA baseline, tool calling fiable, bajo coste por token, bien documentado en literatura APR |
| Open-source pequeño | `qwen3.5:9b` | Tool calling nativo, 6.6 GB VRAM, permisivo para comparación |
| Open-source grande/especializado | `qwen3-coder:30b` | Code-specialized (relevante para APR), mismo stack tool calling que qwen3.5:9b, 18 GB, comparación limpia |

La combinación qwen3.5:9b + qwen3-coder:30b permite una narrativa de investigación clara: ¿aporta más la especialización en código o el tamaño del modelo para tareas de reparación automática de software?

---

## Fixes de framework aplicados durante la exploración

Durante las pruebas con gemma4 se identificaron y corrigieron dos bugs reales del framework:

1. **`workspace/manager.py` — `restore_test_files()`**: método nuevo que revierte únicamente los ficheros de test modificados por el agente, preservando los cambios en ficheros fuente.
2. **`iteration/decision_enactor.py` — revert selectivo**: cuando la validación es `test_file_modified` y la decisión es `retry`, se llama a `restore_test_files()` en lugar de `restore_all_changes()`. Antes de este fix, si el agente aplicaba un fix correcto en source y además tocaba un fichero de test, el fix se descartaba completamente.

Estos fixes son lógicamente correctos aunque no fueron el factor determinante en los runs exitosos de gemma4-ctx32k (el modelo no llegó a modificar ficheros de test en esos runs).
