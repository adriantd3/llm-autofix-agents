# Spec 007: LLM Configuration Refactor

## Objetivo

Eliminar inconsistencias de configuración LLM y aplicar principios SOLID (OCP, DIP) al desacoplamiento de providers.

## Problemas resueltos

1. **Inconsistencia max_turns**: `LLM_MAX_TURNS` como variable de entorno no debería existir cuando ya está definida en el YAML del batch.
2. **Acoplamiento a URLs de providers**: `LLMSettings` tenía un atributo específico `ollama_base_url`; las URLs deben ser estáticas por provider en un mapa centralizado.
3. **Lógica condicional por provider**: `from_env()` contenía múltiples `if provider` que violaban el OCP. Las estrategias por provider ahora están delegadas a una resolución limpia.
4. **Normalización y validación innecesarias**: Funciones `_parse_int`, `_parse_float`, `_parse_bool` repetían lógica que Pydantic puede manejar directamente.

## Cambios implementados

### 1. Mapa estático provider → URL

**Archivo**: `src/llm_autofix_agents/llm/settings.py`

```python
PROVIDER_DEFAULT_URLS = {
    "ollama": "http://localhost:11500/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openai": "https://api.openai.com/v1",
}
```

- Single source of truth para URLs por defecto.
- Constants de backward compatibility preservadas (`DEFAULT_OLLAMA_BASE_URL`, etc.).
- Fácil de extender a nuevos providers sin cambiar la lógica de `from_env()`.

### 2. Simplificación de `from_env()`

- Eliminadas funciones `_parse_provider`, `_parse_int`, `_parse_float`, `_parse_bool`.
- Parsing inline directo con manejo de errores explícito.
- Validación de boolean estricta preservada.
- Resolución de API key y base_url simplificada mediante lookups de maps.

### 3. Eliminación de `LLM_MAX_TURNS` desde entorno

- `max_turns` en `from_env()` siempre retorna `3` (default para configs ad-hoc).
- El batch config YAML proporciona `max_turns` explícitamente en `GlobalSettings.llm.max_turns`.
- Removido de `batch/runner.py` (no se exporta a env del contenedor).
- Removido de `.env.example`.

### 4. Eliminar `ollama_base_url` de batch config

- `batch/config.py`: Removido atributo `ollama_base_url` del modelo `LLMSettings`.
- Las URLs provienen de `PROVIDER_DEFAULT_URLS[provider]` en la instancia `llm/settings.py`.
- Override de URL posible vía `LLM_BASE_URL` si es necesario (para testing o proxies).

### 5. Limpieza en batch runner

- `batch/runner.py`: No exporta `LLM_MAX_TURNS` ni `OLLAMA_BASE_URL` a env del contenedor.
- Solo expone `LLM_PROVIDER` y `LLM_MODEL` (el runtime resuelve la URL internamente).

## Beneficios

- **OCP**: Nuevo provider se añade solo actualizando `PROVIDER_DEFAULT_URLS`.
- **DIP**: `from_env()` no depende de condicionales por provider; usa lookups.
- **SRP**: Cada responsabilidad clara: maps para URLs, validación inline, resolución de defaults.
- **Menos ruido**: Eliminadas 5 funciones helper que solo normalizaban entrada.
- **Separación clara**: Config de ejecución (batch YAML) vs config de provider (env).

## Testing

- Tests actualizados en `tests/test_config.py`:
  - `test_from_env_openai_custom_settings`: Removido `LLM_MAX_TURNS`, validado `max_turns=3`.
  - `test_from_env_invalid_boolean`: Preservada validación estricta de boolean.
  - `test_from_env_base_url_override`: Nuevo test para validar override de URL.

## Cambios por archivo

| Archivo | Cambios |
|---------|---------|
| `src/llm_autofix_agents/llm/settings.py` | Mapa `PROVIDER_DEFAULT_URLS`, simplificación `from_env()`, eliminar parsers, eliminar `ollama_base_url` |
| `src/llm_autofix_agents/batch/config.py` | Eliminar `ollama_base_url` del modelo |
| `src/llm_autofix_agents/batch/runner.py` | No exportar `LLM_MAX_TURNS`/`OLLAMA_BASE_URL` a env |
| `.env.example` | Remover `LLM_MAX_TURNS` |
| `src/llm_autofix_agents/llm/__init__.py` | Agregar `DEFAULT_OPENAI_BASE_URL` a exports |
| `tests/test_config.py` | Actualizar tests para refactoring |

## Validación

- [ ] Tests unitarios en verde: `tests/test_config.py`
- [ ] Lint y typecheck en verde
- [ ] Validación e2e: ejecutar batch con `quixbugs-sample` y verificar que no falte env vars

## Notas para futuro

- Si se agrega un nuevo provider (ej: Claude, Mistral), solo agregar entrada en `PROVIDER_DEFAULT_URLS`.
- Si se requiere cambiar una URL por defecto, editarlo en un solo lugar.
- La validación de API key requerida por provider está centralizada en `from_env()`.
