# Tasks — SPEC-021

## Estado: Cerrado

## Tareas completadas

- [x] Probar devstral-ctx45k en bugsinpy-hard-mono → 0/4, fallo: 1 tool call + stop
- [x] Probar mistral-small32-ctx45k → 0/4, fallo: argumento `path` faltante en read_file
- [x] Probar hermes3-8b-ctx45k → 0/4, fallo: 1 tool call por iteración
- [x] Probar llama3.1-8b-ctx45k → 0/4, fallo: no emite tool calls
- [x] Probar gemma4-26b-ctx45k think=off → 0/4, fallo: tokens de thinking expuestos
- [x] Probar gemma4-26b-ctx45k think=on → 0/4, fallo: replace garbled 167 líneas
- [x] Probar gemma4-26b-ctx32k think=on → 2/4 ✅ (ansible-2, scrapy-33)
- [x] Analizar trazas de éxito y fracaso (gemma4-ctx32k batch 8 y 9)
- [x] Documentar hallazgos por modelo
- [x] Justificar descarte de gemma4 para experimentación formal
- [x] Proponer selección final de modelos

## Pendiente

_(ninguno — spec cerrada)_
