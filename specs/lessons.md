# Lecciones y Aprendizajes

## Plantilla de entrada
- Fecha:
- Contexto:
- Anti-patron detectado:
- Que no hay que hacer:
- Por que estuvo mal:
- Alternativa recomendada:
- Regla preventiva para futuras specs:

## Notas iniciales
- Mantener esta bitacora corta y accionable.
- Registrar solo aprendizajes reutilizables.

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