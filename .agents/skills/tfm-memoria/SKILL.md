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

Tambien se puede explorar el código, para entender mejor y tener siempre la referencia actualizada sobre el funcionamiento del sistema y detalles especificos.
Por supuesto, tambien puedes acceder a results/ para analizar las trazas de ejecución, los resultados de los experimentos y las métricas de evaluación.

La idea es tener un conocimiento global del proyecto, su evolución, sus decisiones técnicas y sus resultados, para poder redactar la memoria con una visión completa y coherente. No se trata de escribir sin más, sino de hacerlo con una comprensión profunda de lo que se ha hecho y por qué.


## El índice es preliminar — razonar la sección antes de escribirla

El índice del documento es un punto de partida, no una obligación. A medida que se escribe puede aparecer que una subsección no tiene suficiente contenido para existir por sí sola, que dos subsecciones tratan la misma idea y conviene fusionarlas, o que algo que no estaba en el índice es necesario para que el argumento funcione. Ajustar la estructura si la escritura lo exige; la coherencia del texto importa más que la fidelidad al índice original.

Antes de escribir cualquier sección o subsección, hacerse estas preguntas en orden:

1. **¿Qué va a saber el lector después de leer esto que no sabía antes?** Si la respuesta es vaga o equivale a «lo mismo que antes con otras palabras», la sección no tiene contenido suficiente todavía.
2. **¿Por qué este apartado existe aquí y no en otro lugar?** Si no hay una respuesta clara, revisar si pertenece a otro capítulo o si directamente sobra.
3. **¿Cuánto hay que profundizar?** Un apartado de contexto histórico necesita menos detalle técnico que uno de diseño o implementación. Calibrar según el nivel del capítulo y lo que el lector necesita para entender lo que viene después.
4. **¿Cómo se puede explicar esto mejor que con párrafos?** Una tabla, un diagrama, una lista numerada de pasos, un ejemplo concreto de un bug del benchmark. Los párrafos no son la única herramienta.

La longitud adecuada de una sección es la que necesita para explicar lo que tiene que explicar, ni más ni menos. Dos párrafos sustanciosos valen más que cinco párrafos vacíos.


## Qué incluir y qué no

La memoria trata aspectos de **alto nivel**: arquitecturas, tecnologías utilizadas, decisiones de diseño, evaluación experimental y resultados. No se incluye código fuente ni detalles de implementación de bajo nivel. El objetivo es que un lector técnico entienda qué se ha construido, por qué se tomaron las decisiones que se tomaron y qué resultados se obtuvieron.

A lo largo del desarrollo se han tomado muchisimas decisiones tecnicas, en general estan documentadas en specs, por lo que podemos analizar toda esa experiencia para incluirlo en la memoria segun convenga. Por supuesto, no todo lo que se hizo es relevante para la memoria. El criterio para decidir qué incluir es: ¿aporta información útil para entender el proyecto, sus desafíos y sus resultados? Si la respuesta es sí, incluirlo con la profundidad adecuada. Si la respuesta es no, omitirlo. Por ejemplo, detalles de configuración de un experimento que no afecten a los resultados o decisiones de diseño que no tengan impacto en el funcionamiento del sistema pueden no ser relevantes para la memoria. En cambio, decisiones que afecten a la arquitectura, a la elección de herramientas, a la metodología de evaluación o a la interpretación de resultados sí son relevantes.

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

### Metadatos obligatorios en main.tex

### LNCS: nunca referenciar subsubsecciones con `\ref{}`

En la clase LNCS, `\subsubsection` se renderiza como cabecera de párrafo inline **sin número visible** en el documento. Como consecuencia, `\ref{}` a un label dentro de un `\subsubsection` resuelve al número de la subsección padre, produciendo referencias rotas (p. ej., *(ver Sección 2.1)*, *(ver Sección 2.1)*, *(ver Sección 2.1)* seguidas dentro de la misma subsección 2.1).

**Regla**: nunca usar `\ref{}` para referenciar subsubsecciones. El patrón «párrafo de introducción de sección» descrito en la guía de estilo aplica solo a `\section` y `\subsection`. Los subapartados de nivel `\subsubsection` se mencionan en la introducción en prosa, sin número de sección.

### TikZ: verificar acentos en nodos

Los nodos TikZ aceptan UTF-8 directamente con `[utf8]{inputenc}`, pero si el texto del nodo contiene tildes o caracteres especiales, verificar siempre que se renderizan correctamente en el PDF compilado. En caso de problema, usar macros LaTeX explícitas: `\'{a}` para á, `\'{e}` para é, `\~{n}` para ñ, etc.

### TikZ: contenedores con etiqueta visible (`fit` + background layer)

Para diagramas con un contenedor que agrupa nodos internos (como un "Runtime Docker"), usar el patrón:

1. Colocar los nodos internos primero (se necesitan para que `fit` calcule el bounding box).
2. Dibujar el contenedor en el background layer con `fit=(nodo1)(nodo2)` e `inner sep=8pt`.
3. Colocar la etiqueta del contenedor como nodo separado con `anchor=south at (container.north)` y `fill=white` para que tape el borde y resulte legible.

```latex
\begin{scope}[on background layer]
  \node[draw=gray!30, fill=gray!5, rounded corners=8pt, dashed, thick,
        fit=(nodo1)(nodo2), inner sep=10pt] (container) {};
\end{scope}
\node[fill=white, inner sep=3pt, font=\scriptsize\sffamily\itshape, text=gray!55,
      anchor=south] at (container.north) {Nombre del contenedor};
```

**TikZ `calc`**: para posicionamiento con aritmética de coordenadas (`$(nodo.south)+(0,-12mm)$`), la librería `calc` ya está en `preamble.tex`. Útil especialmente para fan-out routing (varios nodos destino a posición relativa de un nodo padre). El patrón estándar para flechas es `>=Stealth` en las opciones del `tikzpicture` y `arr/.style={->, thick, gray!65}` para el estilo de flecha.

**Error frecuente**: definir el contenedor como caja vacía (`minimum height`) antes de los nodos internos y luego colocar los nodos dentro. Resulta en solapamiento inevitable porque las posiciones no se coordinan.

### Paleta material-like en diagramas TikZ

Los colores de la paleta material se definen en `preamble.tex` y están disponibles en todas las figuras:
- `coreFill` / `coreStroke` (azul): operaciones, procesos, componentes core.
- `procFill` / `procStroke` (amarillo): pasos de procesamiento y decisiones.
- `greenFill` / `greenStroke` (verde): datos de entrada/salida, observabilidad, resultados.
- `optFill` / `optStroke` (rosa): componentes especiales, optimizaciones.
- `memFill` / `memStroke` (naranja): almacenamiento, base de datos, estado persistente.

Para diseñar figuras nuevas, consultar la skill `tikz-flowchart` (tema material-like por defecto). Los colores ya están en `preamble.tex` sin necesidad de redefinirlos en cada figura.

### Visualización del PDF compilado

Para inspeccionar visualmente el documento, convertir la página a PNG con `pdftoppm` y luego usar `view_image`:

```bash
# Convertir página N (y listar el fichero generado):
cd memoria && pdftoppm -r 150 -png -f N -l N main.pdf /tmp/mem_page && ls /tmp/mem_page*.png
# Luego: view_image /tmp/mem_page-N.png
```

El nombre exacto del fichero generado depende del número total de páginas: para documentos de menos de 100 páginas no hay cero a la izquierda (`-19.png`); para más de 99 páginas sí lo hay (`-019.png`). El `ls` posterior elimina esa ambigüedad. Usar `-r 150` para calidad suficiente sin ficheros excesivamente grandes. Útil para detectar solapamientos en figuras, problemas de fuentes, o verificar el encabezado LNCS.

## Guía de estilo

Esta sección es la más importante del skill. El texto debe cumplir con el estilo descrito a continuación. Ante cualquier duda, leer `reference/tfg.md`, el cual se ha tomado como referencia para crear esta guia de estilos.

### Tono

Tono de estudiante técnico serio: académico y riguroso, pero que explica bastante, justifica las decisiones y valora las herramientas de forma práctica. No es un paper de investigación ni un manual de usuario; es una memoria universitaria. Al hablar de una tecnología, no se limita a definirla: se comenta para qué sirve y por qué resulta útil o conveniente en el proyecto.

### Registro

Voz predominantemente impersonal: *se ha utilizado*, *se consideró*, *se propone*, *se describe*, *se han realizado*. Con todo, no es una voz completamente neutra. Aparecen valoraciones directas con naturalidad: *brilla también por*, *ha sido determinante*, *resulta especialmente útil*, *hace que la experiencia de trabajo sea muy fluida y agradable*, *ha sido fundamental*, *se ha considerado oportuno*. Esta mezcla entre impersonalidad y valoración es característica del estilo; no suprimirla.

### Patrón de párrafo: definición → utilidad → aplicación

Cuando se introduce una herramienta, tecnología o concepto, seguir esta secuencia:
1. Qué es (definición directa)
2. Para qué sirve o qué aporta (utilidad general)
3. Cómo y por qué se usa en este proyecto concreto (aplicación)

Este patrón debe sentirse natural, no mecánico. Variar la apertura de párrafo para que el texto no resulte monótono. Este patron tampoco es una restriccion cerrada: siempre se puede evaluar su conveniencia según el caso concreto. En algunos casos, la utilidad y la aplicación pueden ir juntas, o la aplicación puede ser tan evidente que no requiera explicación adicional. El objetivo es que el texto fluya de forma natural, pero sin perder claridad ni profundidad.

### Párrafo de introducción de capítulo

Al abrir un capítulo o sección con varias subsecciones, incluir un párrafo que anticipe el contenido con conectores explícitos y referencias cruzadas a las subsecciones. El TFG lo hace sistemáticamente:

> En primer lugar, se especifican [...] (ver Sección 2.1). Posteriormente, se mencionan [...] (ver Sección 2.2). También se hace una descripción general de [...] (ver Sección 2.3). Por último, se mencionan [...]

Este patrón orienta al lector y da coherencia estructural al capítulo. Reproducirlo siempre que el capítulo tenga más de una subsección.

### Justificaciones

Las decisiones no son arbitrarias. El texto transmite que cada elección responde a una necesidad real del proyecto. Conectores causales frecuentes en el TFG: *dado que*, *debido a*, *por ello*, *ya que*, *con el objetivo de*, *esto permite*, *de modo que*, *se consideró que*.

### Conectores estructurales

Guiar el avance del discurso con: *en primer lugar*, *posteriormente*, *también*, *por último*, *en concreto*, *además*, *finalmente*, *sin embargo*, *no obstante*, *asimismo*, *en cambio*, *por otro lado*, *de este modo*, *no obstante*. Usarlos para marcar transiciones reales, no para rellenar.

Los conectores no son solo para abrir párrafos o subsecciones. También son imprescindibles dentro de los párrafos para que las frases no queden como una lista de hechos yuxtapuestos. Un párrafo donde cada frase empieza con sujeto sin conector previo suena a enumeración mecánica. La prueba: si se puede reordenar las frases sin que el significado cambie, faltan conectores. La idea es que el texto fluya de manera natural, que se note que lo ha escrito un humano.

Ejemplo problemático (IA):
> Un agente autónomo no dispone de ningún mapa del repositorio. Para localizar el código tiene que explorar. Esta exploración tiene un coste directo en tokens.

Ejemplo corregido:
> Un agente autónomo no dispone de ningún mapa del repositorio, por lo que para localizar el código relevante tiene que explorar activamente: leer ficheros, seguir importaciones, buscar las funciones del traceback. Esta exploración tiene un coste directo en tokens de contexto y, además, existe una tensión real entre dos extremos: explorar demasiado desperdicia contexto, mientras que hacerlo demasiado poco puede llevar a proponer un fix sin entender el contrato completo de la función.

### Rayas como separadores — PROHIBIDO

En español las rayas (`---`) no se usan como separadores de listas inline dentro del texto. Son un anglicismo tipográfico que queda muy forzado. En su lugar, usar comas o restructurar la frase. En vez de `---X, Y y Z---` escribir `X, Y y Z` directamente.

### Punto coma

En español, el uso del punto coma es muy limitado y suele indicar un registro anglófono o generado automáticamente. Evitarlo completamente. En su lugar, usar puntos para separar oraciones completas, o comas con conectores para marcar relaciones lógicas. El uso de ";" delata a menudo el uso de IA, cosa que no queremos que se note.

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

3. **Longitud de los párrafos**: cada párrafo debe tener la longitud que requiera su contenido, sin forzar la homogeneidad. La clave es no crear una tendencia clara a un patrón fijo de párrafos de longitud similar. Naturalmente, habra párrafos más largos y otros más cortos, según lo que se esté explicando. El objetivo es que el texto fluya de manera natural, como si lo hubiera escrito un humano, no como un algoritmo con una plantilla rígida.

### Frases

Las frases tienden a ser largas, con varias aclaraciones en la misma oración: explicación, causa y consecuencia juntas. Esto aporta densidad informativa, pero puede volverse pesado si se abusa. Alternar frases largas con otras más cortas para dar ritmo al texto.

### Los dos puntos (`:`) — no usarlos como muleta estructural

El `:` tiene tres usos legítimos en prosa española: introducir una lista real, definir un término directamente, y preceder una cita textual. Fuera de esos casos, es señal de que se está evitando escribir la frase completa.

El abuso más frecuente es el patrón `etiqueta: descripción brevísima` encadenado varias veces seguidas:

> *En primer lugar, reproducibilidad: misma base en cada intento. En segundo lugar, limpieza: los cambios de un run no contaminan el siguiente. Y, además, portabilidad: un lote puede reproducirse en otro host.*

Esto es una lista disfrazada de prosa. La forma correcta es elegir: convertirlo en una lista `\begin{itemize}` real y desarrollar cada punto, o reescribirlo como prosa que explique por qué cada cosa importa, no solo nombrarla. *Reproducibilidad: misma base en cada intento* no explica nada; *la reproducibilidad está garantizada porque cada run parte del mismo estado inicial del contenedor* sí lo hace.

**Prueba rápida:** si lo que va después del `:` puede decirse con sujeto, verbo y predicado completos, hay que escribirlo así.

Cuando la construcción `X: Y` encubre dos frases completas, la reescritura es partir en dos con un conector que exprese la relación real:

| Original (patrón a evitar) | Reescritura preferida |
|---|---|
| `Su principal limitación es la rigidez: si un agente posterior descubre...` | `La transición es unidireccional, siendo este el motivo de su principal limitación. Si un agente posterior descubre...` |
| `subagentes que actúan como funciones: puede llamarlos cuando lo necesite` | `subagentes que actúan como si fueran funciones. Esto quiere decir que el coordinador puede llamarlos cuando lo necesite` |
| `no tiene estado entre llamadas: no recuerda nada` | `no tiene estado entre llamadas. No recuerda nada...` |
| `en cada momento concreto: qué parte del historial conservar, qué señales...` | `en cada momento concreto, lo que en la práctica significa decidir qué parte del historial conservar, qué señales...` |

Conectores útiles para unir o separar: *siendo este el motivo de*, *Esto quiere decir que*, *Esto se debe a que*, *lo que en la práctica significa*, *en concreto*. Si la segunda frase ya es autoexplicativa, no hace falta conector explícito.

Nota adicional: junto al `:`, vigilar también el uso de `en vez de` frente a `en lugar de` — el primero es más directo y natural en este registro.

### Párrafos vacíos — test de contenido real

Antes de dar por bueno un párrafo, hacerse esta pregunta: **¿qué sabe el lector después de leerlo que no sabía antes?** Si la respuesta es «lo mismo que antes, con otras palabras», el párrafo está vacío.

Los síntomas más frecuentes:

- **El párrafo circular:** repite con distintas palabras lo que acaba de decirse. «Esta separación no es un detalle de ingeniería, sino una decisión metodológica. Si cada variación exigiera modificar la lógica base, sería difícil distinguir si una mejora viene del diseño del agente...» — las dos frases dicen lo mismo.
- **El párrafo etiqueta:** nombra ideas sin explicarlas. «La iteración es la unidad de trabajo real del sistema. Cada vuelta combina propuesta, evidencia y decisión.» El lector asiente porque suena razonable, pero no aprende nada concreto.
- **El párrafo de transición hinchado:** «Una vez conocidos los fundamentos X, se puede entender cómo han confluido en Y.» Es aceptable como primera frase de un párrafo de verdad, pero no puede ser el párrafo entero.

El contenido que suele faltar: una cifra, un ejemplo concreto, una consecuencia real, la razón por la que algo fue difícil, o la alternativa que se descartó. Si no se tiene ninguno de esos, la sección probablemente no está lista para escribirse todavía.

### Voz defensiva — no escribir para el evaluador

Hay un patrón que aparece cuando el autor justifica sus decisiones ante el evaluador en lugar de explicárselas al lector. Se reconoce por frases como:

- *«Esta separación no es un detalle de ingeniería, sino una decisión metodológica.»*
- *«La figura se conserva porque aclara mejor que la prosa...»*
- *«Por eso no basta con describirlo en bloques amplios...»*
- *«Se decidió no tomar ese camino, dado que...»* (cuando la justificación aparece antes de haber explicado siquiera que era una opción)

Un texto bien escrito no necesita convencer al lector de que las decisiones fueron acertadas. Las explica con suficiente claridad como para que la justificación sea obvia. Si hace falta defender explícitamente por qué algo «se mantiene» o por qué «no basta» con otra solución, normalmente es señal de que el texto anterior no ha explicado bien el problema que esa decisión resuelve. La solución no es añadir la defensa, sino revisar si el problema está planteado con claridad antes de presentar la solución.

### Párrafos de navegación — no narrar lo que el lector está a punto de ver

Un párrafo como «Primero, la Tabla X resume la organización por grupos. A continuación se explican una a una con el problema que resuelven y el riesgo que mitigan» no aporta nada: el lector ya va a ver la tabla, y sabe que después vendrán las explicaciones. Estos párrafos deben eliminarse o reemplazarse por contenido real.

Lo mismo aplica al párrafo que sigue a una figura. No describir lo que la figura muestra —eso ya lo hace la figura sola—: añadir la consecuencia, el punto no evidente, o la conclusión que el diagrama no puede expresar por sí mismo.

El párrafo que precede a una tabla tampoco debe narrar su contenido. Debe responder a alguna de estas preguntas: ¿por qué existe esta tabla?, ¿qué decisión de diseño comunica?, ¿qué debe observar el lector en ella?

### Vocabulario técnico inventado — usar la expresión directa

El texto del TFM tiende a crear términos internos que suenan técnicos pero no tienen carga semántica real fuera del documento. Algunos ejemplos que han aparecido en las secciones ya escritas:

- *microciclo* → «una iteración», «cada vuelta del bucle»
- *higiene de contexto* → «evitar que el contexto acumule ruido», «mantener la información útil»
- *cartografiar el repositorio* → «explorar el repositorio», «identificar la estructura de ficheros»
- *relación señal-ruido de iteración* → «calidad de la información entre iteraciones»
- *comprobaciones fuertes* → «validaciones», «checks de integridad»
- *firmas de propuesta* → «resumen del cambio propuesto», «huella del parche»

El problema no es que estos términos sean incorrectos en abstracto; es que obligan al lector a aprender un vocabulario privado del autor sin que eso aporte comprensión extra. Cuando un término inventado se puede sustituir por una expresión directa sin perder precisión, siempre se prefiere la expresión directa.

Regla práctica: si el término no aparece en ningún trabajo del estado del arte ni en documentación estándar del dominio, no es vocabulario del dominio sino vocabulario del autor. En ese caso, o bien se define explícitamente cuando aparece por primera vez (si aporta brevedad real a lo largo del texto), o bien se sustituye por la expresión directa.

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
- **No usar el punto y coma (`;`)**: es un signo infrecuente en prosa académica española y delata un registro anglófono o generado automáticamente. Cuando se sienta la tentación de usarlo, reestructurar la frase: separar en dos oraciones con punto, unir con una coma y un conector (`y`, `pero`, `aunque`, `mientras que`, `por lo que`, `de modo que`), o reformular completamente. En vez de `A; B` escribir `A, mientras que B` o `A. Por ello, B`, según la relación lógica entre las ideas.
- **No usar `:` como muleta estructural**: ver la regla «Los dos puntos — no usarlos como muleta estructural». Si lo que va después del colon puede decirse con una frase completa, escribirlo así.
- **No escribir párrafos vacíos**: aplicar el test de contenido real antes de dar por bueno cualquier párrafo. Si el lector no aprende nada nuevo al leerlo, reescribirlo o eliminarlo.
- **No usar la voz defensiva**: no escribir frases que justifiquen decisiones ante el evaluador. Si la motivación de una decisión no queda clara desde el contexto, revisar la explicación del problema que la precede, no añadir la defensa explícita.
- **No narrar lo que viene**: los párrafos que dicen «primero la tabla X muestra Y, a continuación se explica Z» deben eliminarse o reemplazarse por contenido real. El párrafo después de una figura no describe lo que ya muestra la figura.
- **No inventar vocabulario técnico interno sin definirlo**: términos como *microciclo*, *higiene de contexto*, *firmas de propuesta* o *relación señal-ruido de iteración* o bien se definen cuando aparecen por primera vez, o bien se sustituyen por expresiones más directas.
- **No citar en inglés texto propio del sistema** (instrucciones del agente, cadenas de prompt): si se quiere recoger un principio de diseño, redactarlo en español integrado en la prosa, no como cita en bloque sin atribución.
- La guía es orientadora, no un oráculo de estilo: priorizar la coherencia y naturalidad del texto sobre la imitación mecánica
