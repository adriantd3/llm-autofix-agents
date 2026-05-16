---
name: tfm-memoria
description: Skill para redactar la memoria del TFM en español y LaTeX (clase LNCS). Usar siempre que el usuario pida escribir, completar, revisar o reestructurar cualquier parte de la memoria: introducción, estado del arte, diseño, implementación, evaluación, conclusiones o cualquier otro apartado. También activar cuando el usuario quiera añadir contenido a memoria/, convertir decisiones técnicas en narrativa académica, o añadir entradas a la bibliografía. Si el usuario menciona "la memoria", "el TFM", "el capítulo de X" o "redacta/escribe/completa", usar este skill.
---

# TFM Memoria — Skill de Redacción

El TFM documenta el diseño, implementación y evaluación de una plataforma APR (Automated Program Repair) basada en LLMs con múltiples arquitecturas multi-agente. La memoria se escribe en español y LaTeX con clase LNCS.

## Referencia de estilo

El archivo `reference/tfg.md` (en el directorio de este skill) contiene el TFG del mismo autor. Es la referencia de estilo más fiable: cuando haya duda sobre el tono, la estructura de un párrafo o cómo introducir un concepto, leerlo y dejarse guiar por lo que hay ahí. No se trata de copiar frases, sino de calibrar el registro y los patrones.

## Antes de escribir

Leer `memoria/README.md` y explorar el directorio `memoria/` para entender qué secciones existen y cuál es el estado actual del documento. Las especificaciones en `specs/`, el estado en `specs/status.md` y los aprendizajes en `specs/lessons.md` son fuente de información técnica del proyecto; consultar los que sean relevantes según lo que se esté redactando. El historial de git también puede aportar contexto sobre la evolución de decisiones.

No fabricar datos, métricas ni decisiones de diseño. Si la información no está en el repositorio, indicarlo explícitamente.

## Qué incluir y qué no

La memoria trata aspectos de **alto nivel**: arquitecturas, tecnologías utilizadas, decisiones de diseño, evaluación experimental y resultados. No se incluye código fuente ni detalles de implementación de bajo nivel. El objetivo es que un lector técnico entienda qué se ha construido, por qué se tomaron las decisiones que se tomaron y qué resultados se obtuvieron.

## LaTeX y estructura del documento

El documento sigue la plantilla LNCS con `subfiles`. Cada sección se coloca en su propio archivo dentro de `memoria/sections/`. Para una sección nueva, usar esta plantilla:

```latex
% !TeX root = ../../main.tex
\documentclass[../../main.tex]{subfiles}

\begin{document}

\section{Título de la sección}

Contenido...

\end{document}
```

Añadir el correspondiente `\subfile{sections/NN-nombre/NN-nombre.tex}` en `main.tex`. Las citas van con `\cite{clave}` y las entradas en `references.bib`. Las figuras se colocan en `memoria/images/` y se referencian con `\ref{fig:nombre}`.

Para compilar: `cd memoria && latexmk -pdf -interaction=nonstopmode main.tex`.

## Guía de estilo

Esta sección es la más importante del skill. El texto debe cumplir con el estilo descrito a continuación. Ante cualquier duda, leer `reference/tfg.md`.

### Tono

Tono de estudiante técnico serio: académico y riguroso, pero que explica bastante, justifica las decisiones y valora las herramientas de forma práctica. No es un paper de investigación ni un manual de usuario; es una memoria universitaria. Al hablar de una tecnología, no se limita a definirla: se comenta para qué sirve y por qué resulta útil o conveniente en el proyecto.

### Registro

Voz predominantemente impersonal: *se ha utilizado*, *se consideró*, *se propone*, *se describe*, *se han realizado*. Con todo, no es una voz completamente neutra. Aparecen valoraciones directas con naturalidad: *brilla también por*, *ha sido determinante*, *resulta especialmente útil*, *hace que la experiencia de trabajo sea muy fluida y agradable*, *ha sido fundamental*, *se ha considerado oportuno*. Esta mezcla entre impersonalidad y valoración es característica del estilo; no suprimirla.

### Patrón de párrafo: definición → utilidad → aplicación

Cuando se introduce una herramienta, tecnología o concepto, seguir esta secuencia:
1. Qué es (definición directa)
2. Para qué sirve o qué aporta (utilidad general)
3. Cómo y por qué se usa en este proyecto concreto (aplicación)

Este patrón debe sentirse natural, no mecánico. Variar la apertura de párrafo para que el texto no resulte monótono.

### Párrafo de introducción de capítulo

Al abrir un capítulo o sección con varias subsecciones, incluir un párrafo que anticipe el contenido con conectores explícitos y referencias cruzadas a las subsecciones. El TFG lo hace sistemáticamente:

> En primer lugar, se especifican [...] (ver Sección 2.1). Posteriormente, se mencionan [...] (ver Sección 2.2). También se hace una descripción general de [...] (ver Sección 2.3). Por último, se mencionan [...]

Este patrón orienta al lector y da coherencia estructural al capítulo. Reproducirlo siempre que el capítulo tenga más de una subsección.

### Justificaciones

Las decisiones no son arbitrarias. El texto transmite que cada elección responde a una necesidad real del proyecto. Conectores causales frecuentes en el TFG: *dado que*, *debido a*, *por ello*, *ya que*, *con el objetivo de*, *esto permite*, *de modo que*, *se consideró que*.

### Conectores estructurales

Guiar el avance del discurso con: *en primer lugar*, *posteriormente*, *también*, *por último*, *en concreto*, *además*, *finalmente*, *sin embargo*, *no obstante*, *asimismo*. Usarlos para marcar transiciones reales, no para rellenar.

### Frases

Las frases tienden a ser largas, con varias aclaraciones en la misma oración: explicación, causa y consecuencia juntas. Esto aporta densidad informativa, pero puede volverse pesado si se abusa. Alternar frases largas con otras más cortas para dar ritmo al texto.

### Léxico del dominio

Términos propios de la disciplina: sistema, proceso, herramienta, desarrollo, flujo de trabajo, requisitos, pruebas, integración, seguimiento, validación, funcionalidad, arquitectura, agente, iteración, benchmark, ejecución, dataset, reparación. Usarlos con naturalidad, sin forzarlos.

### Restricciones

- **No usar** muletillas de IA: *En resumen*, *En conclusión*, *Cabe destacar*, *Es importante mencionar*, *Vale la pena señalar*, *En definitiva*
- **No repetir** la misma fórmula sintáctica en párrafos consecutivos; variar la apertura de oración
- **No repetir** mecánicamente fórmulas como *se ha utilizado*, *permite*, *en el contexto de este proyecto* en exceso; son parte del estilo, pero si se acumulan suenan artificiales
- **No inventar** datos, resultados ni citas que no estén en el repositorio
- **No generalizar** más allá de lo que la documentación del proyecto sustenta
- La guía es orientadora, no un oráculo de estilo: priorizar la coherencia y naturalidad del texto sobre la imitación mecánica
