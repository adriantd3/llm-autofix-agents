# Tasks - Spec 007: LLM Configuration Refactor

## Implementación completada

- [x] Crear mapa estático `PROVIDER_DEFAULT_URLS` en `settings.py`
- [x] Simplificar `LLMSettings.from_env()` removiendo funciones `_parse_*`
- [x] Eliminar `LLM_MAX_TURNS` de `from_env()` (siempre retorna default 3)
- [x] Remover `LLM_MAX_TURNS` de `batch/runner.py`
- [x] Remover `LLM_MAX_TURNS` de `.env.example`
- [x] Eliminar `ollama_base_url` de `batch/config.py`
- [x] Remover `OLLAMA_BASE_URL` de exportación en `batch/runner.py`
- [x] Actualizar `__init__.py` para exportar `DEFAULT_OPENAI_BASE_URL`
- [x] Actualizar tests en `test_config.py`
- [x] Agregar test para override de `LLM_BASE_URL`
- [x] Crear spec 007 con documentación

## Validación pendiente

- [ ] Ejecutar tests unitarios: `python -m unittest tests.test_config`
- [ ] Ejecutar lint: `make lint`
- [ ] Ejecutar typecheck: `make typecheck`
- [ ] Ejecutar e2e batch sample: verificar que batch execution no falle por env vars
