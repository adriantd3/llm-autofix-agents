# Execution 001 - MCP to Tools Refactor

Date: 2026-04-23
Status: In progress

Total steps: 13
Implemented steps: 0/13
Current step: 13

## Step list

1. [x] Realinear specs activas para eliminar websearch y baseline MCP.
2. [x] Actualizar status/lessons con el cambio de direccion y anti-patron.
3. [x] Crear modulo tools APR en src con perfil full adaptado desde demo.
4. [x] Exponer tools y perfiles en paquete tools y migrar gateway de toolset.
5. [x] Refactorizar provider para eliminar MCPServer/MCPServerManager y usar solo tools.
6. [x] Refactorizar contrato de salida del provider a modo puramente tool-driven.
7. [x] Refactorizar agent_flow para inyectar tools/contexto y quitar acoplamiento MCP.
8. [x] Ajustar validaciones y logs del flow al nuevo modo tool-driven.
9. [x] Portar tests de apr_toolkit demo al repo principal.
10. [x] Sustituir tests de toolset MCP por tests de tools/perfiles.
11. [x] Actualizar tests de provider y agent_flow para modo sin MCP.
12. [x] Actualizar README eliminando documentacion MCP/websearch del baseline.
13. [ ] Ejecutar validacion de tests y registrar resultado final.

## Progress log

- 2026-04-23: Inicializacion de plan de ejecucion y trazabilidad step-by-step.
- 2026-04-23: Primer slice tool-driven aplicado: spec realineada, toolkit APR local creado, provider sin MCP y loop baseline desacoplado de servidores MCP.
- 2026-04-23: Tests de toolkit/provider/flow adaptados al nuevo contrato tool-driven y validados en verde.
- 2026-04-23: README del runtime principal limpiado de MCP/websearch.
