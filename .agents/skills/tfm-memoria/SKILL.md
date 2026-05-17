---
name: tfm-memoria
description: Skill para redactar la memoria del TFM en español y LaTeX (clase LNCS). Usar siempre que el usuario pida escribir, completar, revisar o reestructurar cualquier parte de la memoria: introducción, estado del arte, diseño, implementación, evaluación, conclusiones o cualquier otro apartado. También activar cuando el usuario quiera añadir contenido a memoria/, convertir decisiones técnicas en narrativa académica, o añadir entradas a la bibliografía. Si el usuario menciona "la memoria", "el TFM", "el capítulo de X" o "redacta/escribe/completa", usar este skill.
---

# TFM Memoria — Skill de Redacción

El TFM documenta el diseño, implementación y evaluación de una plataforma APR (Automated Program Repair) basada en LLMs con múltiples arquitecturas multi-agente. La memoria se escribe en español y LaTeX con clase LNCS.

## Referencia de estilo

El archivo `reference/tfg.md` (en el directorio de este skill) contiene el TFG del mismo autor. Es la referencia de estilo más fiable: cuando haya duda sobre el tono, la estructura de un párrafo o cómo introducir un concepto, leerlo y dejarse guiar por lo que hay ahí. No se trata de copiar frases, sino de calibrar el registro y los patrones.

El archivo `reference/tfm-compañero.md` contiene la memoria de un compañero del mismo máster. Sirve de referencia complementaria de granularidad: indica qué nivel de detalle se espera al explicar conceptos técnicos en una memoria de máster (cómo funcionan los transformers, qué hace concretamente una API, qué implica un benchmark...). Usarlo para calibrar cuánto profundizar, no para copiar su estilo ni su vocabulario.

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

Guiar el avance del discurso con: *en primer lugar*, *posteriormente*, *también*, *por último*, *en concreto*, *además*, *finalmente*, *sin embargo*, *no obstante*, *asimismo*, *en cambio*, *por otro lado*, *de este modo*, *no obstante*. Usarlos para marcar transiciones reales, no para rellenar.

Los conectores no son solo para abrir párrafos o subsecciones. También son imprescindibles dentro de los párrafos para que las frases no queden como una lista de hechos yuxtapuestos. Un párrafo donde cada frase empieza con sujeto sin conector previo suena a enumeración mecánica. La prueba: si se puede reordenar las frases sin que el significado cambie, faltan conectores.

Ejemplo problemático (IA):
> Un agente autónomo no dispone de ningún mapa del repositorio. Para localizar el código tiene que explorar. Esta exploración tiene un coste directo en tokens.

Ejemplo corregido:
> Un agente autónomo no dispone de ningún mapa del repositorio, por lo que para localizar el código relevante tiene que explorar activamente: leer ficheros, seguir importaciones, buscar las funciones del traceback. Esta exploración tiene un coste directo en tokens de contexto y, además, existe una tensión real entre dos extremos: explorar demasiado desperdicia contexto; explorar demasiado poco puede llevar a proponer un fix sin entender el contrato completo de la función.

### Rayas como separadores — PROHIBIDO

En español las rayas (`---`) no se usan como separadores de listas inline dentro del texto. Son un anglicismo tipográfico que queda muy forzado. En su lugar, usar comas o restructurar la frase. En vez de `---X, Y y Z---` escribir `X, Y y Z` directamente.

### Citas con `\cite{}` — no repetir autores manualmente

No escribir `Autor et al.~\cite{clave}` salvo que sea imprescindible nombrar a los autores por alguna razón narrativa concreta. Lo habitual es nombrar el sistema o el trabajo y poner la cita al final: `GenProg~\cite{legoues2012genprog}`, `En~\cite{prenner2022codex} se evaluó...`, o `el trabajo de~\cite{xia2023chatrepair} demostró...`. No duplicar la información que ya está en el número de la cita.

### Ritmo y naturalidad — evitar el tono IA

El texto no debe ser telegráfico ni avanzar a máxima velocidad de un concepto al siguiente. Antes de presentar un trabajo o una herramienta, conviene situar al lector: por qué surge, qué problema resuelve, en qué contexto aparece. Evitar:
- Frases que empiezan directamente con la definición del concepto sin contexto previo.
- Párrafos de dos o tres frases que equivalen a un titular, sin desarrollo.
- Vocabulario excesivamente formal o técnico-clínico que delata un registro de experto o de IA: *sintomatología*, *cualitativamente superior*, *de naturaleza metodológica*, *implicaciones directas*, *resulta fundamental destacar*, *convergencia de líneas de investigación*. Usar el equivalente más sencillo: *los efectos del error*, *mejor que*, *algo metodológico*, *afecta directamente a*.
- Construir cada párrafo con la misma estructura mecánica.

El registro es el de un estudiante técnico serio: formal pero no pretencioso, capaz de explicar algo complejo con palabras directas.

### Granularidad en conceptos nuevos

Cuando se introduce un concepto técnico que el lector puede no conocer, explicarlo con el detalle suficiente para que sea comprensible sin ser un experto previo. Esto no significa un tutorial exhaustivo: basta con cubrir el mecanismo esencial, lo que hace concretamente y por qué importa en el contexto del trabajo. Como referencia de nivel, consultar `reference/tfm-compañero.md`: ahí se puede ver qué profundidad se espera al hablar de transformers, de la API de chat, de benchmarks o de métricas de evaluación.

En la práctica: si un concepto tiene un mecanismo interno relevante para entender el resto del capítulo (por ejemplo, cómo funciona la atención, qué es un turno en la API, qué mide exactamente una métrica), dedicarle un párrafo propio con explicación directa. Si el concepto solo se menciona de paso, una frase con definición integrada es suficiente. No todo requiere el mismo nivel; calibrar según la centralidad del concepto en el argumento.

### Anglicismos — primera aparición obligatoria

Cada vez que se usa un término técnico en inglés por primera vez en el documento, definirlo con el patrón `(del inglés, \textit{X})` o `(del inglés, \textit{X}, o Y en español)`. El TFG lo hace sistemáticamente: *"del inglés Large Vision Language Models"*, *"del inglés bounding box"*, *"del inglés ground truth"*. A partir de la primera definición, usar el término con libertad.

Terminos que típicamente requieren este tratamiento en este TFM (si aparecen por primera vez en la sección que se redacta): *traceback*, *unified diff*, *guardrails*, *toolset*, *feedback*, *caller*, *benchmark*, *run* (como sustantivo), *test suite*, *token*, *pipeline*, *harness*, *handoff*, *prompt*. No redefinir términos que ya se hayan introducido en capítulos anteriores.

Si el término inglés es ya habitual en español técnico y no tiene equivalente claro (p. ej., *log*, *script*), no es necesario el paréntesis, pero aun así usarlo en cursiva la primera vez.

### Variedad estructural — listas, ejemplos y ritmo

No todo debe ser secuencias de párrafos de longitud similar. La homogeneidad delata un texto generado automáticamente. Tres herramientas para romperla:

1. **Listas** (`\begin{itemize}` o `\begin{enumerate}`): usar cuando el contenido ES inherentemente una lista, es decir, cuando hay pasos secuenciales, opciones alternativas o componentes enumerables. No usar para contenido con causalidad o progresión argumentativa, que se expresa mejor en prosa. El TFG usa listas para describir los nodos de un sistema, los tipos de incertidumbre, los componentes de un mensaje. No las usa para argumentar o justificar.

2. **Ejemplos concretos**: cuando se introduce un mecanismo abstracto (un ciclo, un riesgo, un patrón de fallo), un ejemplo concreto lo hace tangible. Puede ser una referencia a un bug específico del benchmark, una situación hipotética breve, o una descripción de qué le ocurrió al agente en un caso real. El TFG hace esto sistemáticamente al validar: describe el JSON del objeto, el resultado del LVLM, el valor de entropía. Adaptar la granularidad al nivel del capítulo: en descripción del problema basta con un par de frases; en validación el detalle es mayor.

3. **Párrafos cortos intercalados**: un párrafo de una o dos frases, después de uno largo, da aire al texto y enfatiza lo que contiene. No abusar, pero no evitar.

### Frases

Las frases tienden a ser largas, con varias aclaraciones en la misma oración: explicación, causa y consecuencia juntas. Esto aporta densidad informativa, pero puede volverse pesado si se abusa. Alternar frases largas con otras más cortas para dar ritmo al texto.

### Léxico del dominio

Términos propios de la disciplina: sistema, proceso, herramienta, desarrollo, flujo de trabajo, requisitos, pruebas, integración, seguimiento, validación, funcionalidad, arquitectura, agente, iteración, benchmark, ejecución, dataset, reparación. Usarlos con naturalidad, sin forzarlos.

### Restricciones

- **No usar** muletillas de IA: *En resumen*, *En conclusión*, *Cabe destacar*, *Es importante mencionar*, *Vale la pena señalar*, *En definitiva*
- **No repetir** la misma fórmula sintáctica en párrafos consecutivos; variar la apertura de oración
- **No repetir** mecánicamente fórmulas como *se ha utilizado*, *permite*, *en el contexto de este proyecto* en exceso; son parte del estilo, pero si se acumulan suenan artificiales
- **No escribir párrafos que sean listas disfrazadas de prosa**: si cuatro frases consecutivas empiezan por "La primera...", "La segunda...", "La tercera...", "La cuarta...", o todas tienen la misma longitud y la misma estructura sintáctica, el texto suena a IA. En ese caso, o bien usar una lista real (`\begin{enumerate}`) y luego continuar con prosa, o bien reescribir con conectores que hagan explícita la relación entre las ideas.
- **No dejar anglicismos técnicos sin definir en primera aparición**: ver la regla «Anglicismos — primera aparición obligatoria» más arriba.
- **No inventar** datos, resultados ni citas que no estén en el repositorio
- **No generalizar** más allá de lo que la documentación del proyecto sustenta
- La guía es orientadora, no un oráculo de estilo: priorizar la coherencia y naturalidad del texto sobre la imitación mecánica
