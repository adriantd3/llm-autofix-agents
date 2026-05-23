# SPEC-020 — Tareas

## Estado: T2 completado (sin reboot); T3 listo para aplicar

---

### T1 — Medir contexto real en GPU ⏳ (requiere reboot)

Tras el reboot (fix NVML):
1. Arrancar `gemma4:26b` en Ollama.
2. Lanzar un batch mínimo (1 bug) sin `num_ctx`.
3. Consultar `curl localhost:11500/api/ps` y registrar `context_length`.
4. Confirmar si adopta el `context_length` del GGUF (262 144) o 8 192.

Hipótesis: en GPU Ollama usa el `context_length` del GGUF como default, lo que
explicaría por qué los experimentos GPU resolvieron bugs sin `num_ctx` explícito.

---

### T2 — Medir consumo de tokens por run ✅

**Completado** con batch `qwen3.5:9b` (38 runs, 77 agent_executions).

Hallazgos clave (ver spec.md para tabla completa):

- **Primer turno = sistema (~1 627) + tools (~1 510) + user (p50 ~1 185) = ~4 322 tokens**.
  Con `num_ctx=4096` (CPU default) el primer turno ya supera el límite en p50.
- Los `input_tokens` en `agent_executions` son **acumulativos** (suma de todos los
  turnos de la ejecución, no por turno individual).
- Turno final estimado: p50=18 398, p95=34 923, max=44 369.
- `num_ctx=32 768` cubre el 95% de los turnos; `num_ctx=4096` trunca el 100%.

**Conclusión**: 32 768 es el valor mínimo razonable para qwen3.5:9b.
Para gemma4:26b, el límite es VRAM (ver spec.md).

---

### T3 — Actualizar `generate_experiment_batches.py` ✅

```python
MODELS = [
    ("ollama", "qwen3.5:9b",  "qwen3.5-9b",  True, {"think": False, "num_ctx": 32768}),
    ("ollama", "gemma4:26b",  "gemma4-26b",  True, {"num_ctx": 8192}),
    ...
]
```

YAMLs regenerados. Verificado: `extra_body: {num_ctx: 32768}` en qwen3.5-9b y
`extra_body: {num_ctx: 8192}` en gemma4-26b.

---

### T4 — Actualizar VRAM estimates en `scheduler.py` ⬜

Cambiar `DEFAULT_MODEL_VRAM_MIB` para incluir pesos + KV cache:

```python
DEFAULT_MODEL_VRAM_MIB: dict[str, int] = {
    "gemma4:26b": 22_200,  # 18 421 pesos + ~3 800 KV@8K
    "qwen3.5:9b": 10_700,  # 6 754 pesos + ~3 900 KV@32K
}
VRAM_SAFETY_BUFFER_MIB: int = 512  # solo fragmentación, KV ya incluido arriba
```

Actualizar los tests que usan `DEFAULT_MODEL_VRAM_MIB` o `VRAM_SAFETY_BUFFER_MIB`.

---

### T5 — Verificar en GPU (smoke test) ⬜

Tras T3:
1. `uv run python scripts/run_experiment_ollama.py --dry-run` — verificar VRAM.
2. Lanzar 1 bug: confirmar `context_length=8192` en `/api/ps`.
3. Confirmar sin OOM.

---

## Dependencias

- T1, T2: requieren reboot (NVML fix)
- T3: puede hacerse ahora, pero los YAMLs solo se usarán tras confirmar T1
- T4: depende de T1 (para validar estimaciones de KV cache)
- T5: depende de T3 + T4 + reboot
