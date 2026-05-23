# SPEC-020 — Context Length & VRAM Budget

## Problema

El experimento usa `AsyncOpenAI → Ollama /v1/chat/completions` sin especificar
`num_ctx`. Ollama asigna su default cuando no se pide nada explícito:
- **CPU**: `num_ctx=4096` (confirmado con `GET /api/ps context_length`).
- **GPU**: probablemente el `context_length` del GGUF (262 144 para ambos modelos),
  lo que explicaría por qué los experimentos en GPU resuelven bugs incluso sin
  `num_ctx` explícito.

El código **no pasa `num_ctx`** en `extra_body`. Los YAMLs de experimento tampoco
lo incluyen.

## Diagnóstico empírico (T2 — batch qwen3.5:9b, 38 runs, 77 agent_executions)

### Breakdown del primer turno

| Componente | Tokens estimados |
|---|---|
| System prompt (`MONO_AGENT_APR_INSTRUCTIONS`) | ~1 627 |
| Tool schemas (12 tools, profile `full`) | ~1 510 |
| User message (`facade_input`, p50) | ~1 185 |
| **TOTAL primer turno (p50)** | **~4 322** |

→ **Con `num_ctx=4096`, el primer turno ya supera el límite en el p50** (+226 tokens).
  Con `facade_input` en p95 (2 126 tokens), el exceso es de ~1 167 tokens.

### Tokens acumulados por `agent_execution` (= suma de todos los turnos)

| Métrica | Valor |
|---|---|
| AVG | 355 606 |
| p50 | 368 215 |
| p95 | 598 851 |
| MAX | 740 542 |

Este valor es **acumulativo** (el SDK suma los `usage.input_tokens` de cada llamada LLM
individual). Con `max_turns=30`, cada turno k envía todo el historial hasta k.

### Tamaño máximo estimado del turno final (turno más largo = más contexto)

| Métrica | Valor |
|---|---|
| AVG | ~20 366 |
| p50 | ~18 398 |
| p75 | ~24 869 |
| p95 | ~34 923 |
| MAX | ~44 369 |

→ `num_ctx=32 768` cubre el **95%** de los turnos individuales con qwen3.5:9b.

### Impacto del default actual

- `num_ctx=4096` (CPU default): **100% de agent_executions truncadas** desde el
  primer turno.
- `num_ctx=32 768`: solo 5% (4/77) de executions verían truncación en el último turno.

## Implicaciones VRAM

El KV cache se reserva en GPU al inicio de la sesión y escala linealmente con
`num_ctx`. Ignorar esto en el planificador puede causar OOM.

| Modelo              | Pesos (MiB) | KV cache @8K (med.) | KV cache @32K (med.) | Total @32K    |
|---------------------|-------------|---------------------|----------------------|---------------|
| gemma4:26b (GQA)    | ~18 771     | ~170                | ~682                 | 19 453 MiB ✓  |
| qwen3.5:9b          |  ~6 754     | ~963 (Q4)           | ~3 946 (Q4)          | ~10 700 MiB ✓ |

> **Nota:** Las estimaciones originales del KV de gemma4:26b eran ~20x mayores
> de lo real. gemma4 usa GQA con muy pocos KV heads, lo que reduce drásticamente
> el KV cache. La afirmación anterior de que `num_ctx=32768` causaría OOM era
> incorrecta — medido en RTX 4090 a 32 768 ocupa 19 453 MiB (5 111 MiB libre).

Para qwen3.5:9b, `num_ctx=65536` usa ~10 700 MiB (Q4 KV) → margen amplio.

> **Nota sobre `num_ctx` vía `/v1/`:** El endpoint OpenAI-compatible de Ollama
> ignora el `num_ctx` pasado en el body del request. El context length se fija
> en el momento de carga del modelo. La solución es usar modelos Modelfile-derivados
> con `PARAMETER num_ctx N` baked in. Pasar `num_ctx` en `extra_body` no tiene efecto.

## Valores confirmados (medidos en RTX 4090)

| Modelo derivado        | num_ctx | VRAM medida | Buffer libre | Cobertura |
|------------------------|---------|-------------|--------------|---|
| `gemma4-26b-ctx32k`    | 32 768  | 19 453 MiB  | 5 111 MiB    | p95 turnos |
| `qwen3.5-9b-ctx65k`    | 65 536  | ~10 700 MiB | ~13 800 MiB  | 100% turnos |

## Cambios aplicados

1. **Modelfiles creados** (Ollama, RTX 4090):
   - `ollama create qwen3.5-9b-ctx65k` — `FROM qwen3.5:9b` + `PARAMETER num_ctx 65536`
   - `ollama create gemma4-26b-ctx32k` — `FROM gemma4:26b` + `PARAMETER num_ctx 32768`

2. **`scripts/generate_experiment_batches.py`** — MODELS actualizado para usar los
   modelos Modelfile-derivados; `num_ctx` eliminado de `extra_body` (baked in).

3. **YAMLs de experimento** — regenerar con el script tras cualquier cambio de selección.

## Pendiente

- **T4** — actualizar `DEFAULT_MODEL_VRAM_MIB` en `scheduler.py` con los valores
  medidos reales (19 453 MiB para gemma4-26b-ctx32k, ~10 700 MiB para qwen3.5-9b-ctx65k).
