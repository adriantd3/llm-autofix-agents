# SPEC-002 - Simplificacion de Arquitectura y Preparacion Multi-Agente

## Contexto
El flujo actual prioriza SRP, pero la lectura del flujo principal es costosa por la cantidad de capas y clases. Esto frena la comprension y dificulta extender el sistema hacia arquitecturas multi-agente o variantes futuras. En esta spec no se implementara multi-agente: solo se prepara una interfaz externa simple para configurar agentes y tools sin acoplarse a un caso concreto.

## Problema
- El flujo principal esta fragmentado en demasiadas piezas pequeñas.
- La abstraccion supera el beneficio de legibilidad para el tamano actual del sistema.
- La arquitectura es modular pero no facilita cambios rapidos en el flujo.
- La seleccion de arquitectura no esta conectada al contrato runtime.

## Objetivos
- Reducir capas con abstraccion innecesaria sin romper SRP.
- Mejorar la lectura del flujo principal en 1-2 archivos clave.
- Mantener una interfaz simple y directa para crear agentes, asignar tools y configurar el flujo.
- Evitar acoplar la arquitectura a un patron multi-agente concreto.
- Mantener observabilidad, validacion y contratos de salida sin regresiones.

## No objetivos
- Redisenar el runtime de Docker o la capa de tools.
- Cambiar el contrato publico de salida del run.
- Introducir nuevas dependencias.
- Reescribir observabilidad o el modelo de errores.

## Principios de diseno
- SRP con sentido practico: menos clases cuando la colaboracion no aporta claridad real.
- Flujo narrativo: el camino feliz debe ser legible de principio a fin.
- Interfaz externa simple: la configuracion de agentes y tools debe ser directa.
- Extension segura: futuras variantes multi-agente deben encajar sin reescribir el flujo.
- Cambios minimos: conservar contratos existentes cuando sea posible.

## Alcance de cambios
1. Fusionar colaboraciones de iteracion que solo agregan indirecta (context builder, recorder, outcome handler).
2. Simplificar el contexto de iteracion para reducir ruido.
3. Aplanar el flujo de orquestacion para que el ciclo principal se lea con menos saltos.
4. Introducir una capa de configuracion de agente/tools desacoplada de una arquitectura concreta.
5. Centralizar la ejecucion de agente para que futuras variantes la reutilicen sin duplicar lifecycle.

## Casos objetivo
- Mono-agente baseline con configuracion abstracta de agente y tools.
- Soporte futuro para variantes multiagente no definidas (sin implementarlas ahora).

## Criterios de aceptacion
- El flujo principal se puede leer en menos de 2 saltos entre archivos.
- La configuracion de agente/tools se define en una interfaz simple y directa.
- El flujo no queda acoplado a un patron multi-agente concreto.
- Tests existentes del flujo siguen pasando o se actualizan con cambios minimos.

## Riesgos
- Cambios a objetos de estado pueden romper tests actuales.
- Riesgo de sobre-simplificar y perder puntos de extension.
- Riesgo de crear una interfaz generica poco clara si no se delimita bien.

## Preguntas abiertas
- Que nivel minimo de configuracion de agente/tools necesitamos en el MVP.
- Donde viviria la futura seleccion de variantes sin contaminar el flujo base.
