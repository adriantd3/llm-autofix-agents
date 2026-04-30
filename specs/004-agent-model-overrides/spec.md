# SPEC-004: Configuracion de modelos por agente

## Metadata
- Fecha: 2026-04-30
- Estado: Propuesto
- Owner: adriantd3
- Tipo: configuracion runtime

## Contexto
Actualmente el runtime usa un unico modelo para todos los agentes. Se quiere habilitar la configuracion de un modelo especifico por rol/agent, pero se considera un cambio mayor y queda fuera del alcance inmediato de SPEC-003 (SH2).

## Objetivo
Permitir configurar modelos por agente/rol via RUN_AGENT_MODELS, con fallback a "main" y luego a LLMSettings.model, manteniendo el comportamiento actual cuando no hay overrides.

## Principios y restricciones
- Mantener comportamiento estable cuando no se definen overrides.
- Respetar el enfoque autonomy-first y el contrato actual de salida.
- Mantener compatibilidad con providers actuales (Ollama/OpenAI/Gemini).
- Trazabilidad en observabilidad y fingerprinting por modelo resuelto.

## Alcance confirmado
- Resolver modelos por rol con fallback "main".
- Exponer overrides en metadata runtime y builders de arquitectura.
- Aplicar el modelo resuelto en cada agente del pipeline.
- Actualizar observabilidad para reflejar el modelo efectivo por agente.
- Documentar RUN_AGENT_MODELS y ejemplos en .env.example y docker-compose.yml.
- Cobertura unitaria para el resolver y wiring basico.

## Fuera de alcance
- Multi-provider por agente.
- Politicas dinamicas de cambio de modelo durante una misma ejecucion.
- Ajustes de pricing/costos por rol.

## Criterios de aceptacion
- Si RUN_AGENT_MODELS no se define, el comportamiento es identico al baseline actual.
- Si se define un rol, el modelo de ese agente usa el override.
- Si un rol no esta definido, usa "main" y si falta, LLMSettings.model.
- La telemetria refleja el modelo resuelto por agente.

## Preguntas abiertas
- Convencion final de keys por rol para arquitecturas futuras.
- Si el validator debe forzarse a un modelo mas fuerte por defecto.
