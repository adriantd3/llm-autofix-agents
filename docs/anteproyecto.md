# ANTEPROYECTO DEL TRABAJO DE FIN DE MÁSTER

## INFORMACIÓN GENERAL

**Alumno/a**
ADRIÁN TORREMOCHA DOBLAS

**Titulación:**
MÁSTER EN INGENIERIA DEL SOFTWARE E INTELIGENCIA ARTIFICIAL

**Título**
ANÁLISIS EXPERIMENTAL DE ORQUESTACIÓN DE AGENTES BASADOS EN LLMS PARA LA REPARACIÓN AUTOMÁTICA DE SOFTWARE

**Título en inglés**
EXPERIMENTAL ANALYSIS OF LLM-BASED AGENT ORCHESTRATION FOR AUTOMATED SOFTWARE REPAIR

**Idioma de la memoria y defensa:**
Castellano X
Inglés ☐

---

## INTRODUCCIÓN

**Contextualización del problema a resolver. Descripción detallada de la motivación de este TFM y el dominio de aplicación.**

El desarrollo de software moderno se apoya cada vez más en procesos automatizados de integración continua (CI), donde cada cambio en el repositorio se valida mediante compilación y ejecución de baterías de tests. En ese escenario, la señal inicial de que algo va mal suele ser muy concreta: un pipeline que falla, una salida de consola, o un conjunto de tests que falla. A partir de esa evidencia, el flujo habitual es iterativo: interpretar el fallo, localizar en qué parte del repositorio se origina, aplicar un cambio y volver a ejecutar los tests para confirmar si el sistema vuelve a un estado estable y funciona según lo esperado.

Este ciclo es relativamente directo en proyectos pequeños, pero se vuelve más costoso cuando el repositorio crece, la base de código está distribuida en múltiples módulos, o el fallo depende de configuraciones, dependencias y condiciones de ejecución que no se reflejan de forma transparente en el log.

A pesar de que disponemos de mucha herramientas para detectar fallos (tests automatizados, linters, pipelines), el paso de tener un log con tests fallando a obtener un cambio en el código que soluciona el problema, sigue siendo un cuello de botella principalmente manual [1], siendo esta la brecha que motiva este TFM.

En la literatura esta idea se relaciona con la reparación automática de software (del inglés, Automated Program Repair, APR), y en particular con los enfoques basados en suites de tests, donde un parche se considera válido si el proyecto compila y los tests pasan [2]. Sin embargo, la experiencia acumulada en APR también muestra ciertas limitaciones:

* El proceso depende de localizar con precisión el origen del fallo y de explorar un espacio de posibles parches que puede ser muy grande.
* Es conocido el riesgo de generar correcciones “plausibles” que pasan los tests disponibles pero no son necesariamente correctas fuera de esos casos (por ejemplo, por sobreajuste a una suite incompleta).

En consecuencia, el problema no es solo generar un cambio, sino diseñar un proceso de autocorrección que sea controlable, verificable y razonablemente fiable [3].

En este contexto, la aparición reciente de modelos de lenguaje de gran tamaño (del inglés, Large Language Models, LLMs) ha reabierto el debate sobre hasta qué punto es posible automatizar la reparación de bugs de manera útil [4]. A diferencia de aproximaciones tradicionales basadas en plantillas, mutaciones o búsqueda, los LLMs pueden proponer modificaciones al código aprovechando patrones aprendidos a gran escala, y pueden hacerlo condicionados por información textual como logs, mensajes de error o descripciones del fallo. Además, recientemente se ha popularizado un paradigma especialmente alineado con el escenario de este trabajo: el de agentes (AgenticAI) que, en lugar de producir un parche en un único paso, operan de forma iterativa de manera similar a un desarrollador.

En este ciclo, el agente analiza el fallo, inspecciona el repositorio, edita archivos, ejecuta comandos y vuelve a lanzar los tests para comprobar el resultado, repitiendo el proceso hasta converger o alcanzar un criterio de parada.

El dominio de aplicación de este TFM es la reparación automática basada en tests en repositorios de software: se parte de un fallo reproducible expresado mediante tests fallidos, y se busca proponer un cambio que haga que el sistema vuelva a pasar las pruebas.

Para validar el sistema, es habitual emplear conjuntos de datos del estado del arte en APR como Defects4J [5] (defectos reales con tests asociados en proyectos Java) y QuixBugs [6] (colección de programas con bugs y sus correspondientes tests). Estos conjuntos permiten analizar el comportamiento del sistema en fallos conocidos, medir tasas de reparación bajo condiciones reproducibles y observar las limitaciones que este presente.

---

## OBJETIVOS

**Descripción detallada de este TFM. Preguntas de investigación a abordar (si procede).**

El objetivo principal de este TFM es estudiar de forma experimental la influencia de la orquestación de agentes y del uso de distintos LLMs en la autocorrección de errores en software, analizando cómo diferentes decisiones de diseño afectan a la eficacia de la reparación automática y a la calidad de los parches generados.

Para poder llevar a cabo este estudio, se diseñará y desarrollará una plataforma experimental de autocorrección apoyada en LLMs y agentes, capaz de partir de señales de fallo (por ejemplo, logs o tests que no pasan) para entender el error, localizar el código relevante e implementar una corrección, verificándola mediante la ejecución de pruebas. Esta plataforma se plantea como un entorno controlado que permita realizar un análisis empírico riguroso.

Este objetivo se concreta en los siguientes objetivos específicos:

* Diseñar las etapas principales del flujo de autocorrección siguiendo principios de herramientas de orquestación tipo workflow (por ejemplo, n8n), definiendo con claridad entradas/salidas de cada etapa y las condiciones de transición entre ellas.
* Diseñar distintas arquitecturas de orquestación de agentes que puedan compararse experimentalmente, incluyendo un enfoque mono-agente y uno o varios enfoques multi-agente, donde cada agente asuma un rol concreto (por ejemplo: análisis del error, propuesta de parche y verificación) [7].
* Seleccionar y preparar el entorno de ejecución necesario para que el sistema pueda operar sobre un proyecto software de forma controlada: leer archivos del repositorio, aplicar cambios de código, ejecutar tests y capturar evidencias del resultado (logs, resultados de compilación/pruebas).
* Definir el diseño experimental, incluyendo la selección de un dataset de bugs reales (por ejemplo, Defects4J, QuixBugs u otro similar), las variables independientes (tipo de orquestación y modelo LLM utilizado) y las variables dependientes (eficacia de autocorrección, calidad del parche, tiempo y coste/consumo), así como el procedimiento de ejecución y análisis de resultados.

A nivel metodológico, el experimento consistirá en ejecutar el sistema sobre un conjunto común de bugs bajo distintas configuraciones experimentales, combinando cada estrategia de orquestación con cada modelo LLM seleccionado. Para cada ejecución se registrarán de forma sistemática los resultados obtenidos (estado final de los tests, número de iteraciones necesarias, tiempo empleado y coste estimado cuando aplique). Posteriormente, se realizará un análisis comparativo entre configuraciones, manteniendo constantes el entorno, el dataset y las condiciones de ejecución, con el objetivo de aislar el efecto de las variables estudiadas.

Con esta plataforma y este diseño experimental se pretende realizar un estudio sistemático que permita responder a las siguientes preguntas de investigación:

* RQ1. ¿Cómo afecta la orquestación (mono-agente vs multi-agente con roles) a la eficacia de autocorrección y a la calidad de los parches generados?
* RQ2. ¿Qué diferencias se observan al usar distintos LLMs (por ejemplo, modelos locales vs propietarios) en términos de eficacia, tiempo y coste/consumo?

---

## ENTREGABLES

**Listado de resultados que generará el TFM (aplicaciones, estudios, manuales, etc.)**

Código y diagramas del/os flujos de trabajo desarrollados.
Memoria del TFM

---

## MÉTODOS Y FASES DE TRABAJO

### METODOLOGÍA

**Descripción de la metodología empleada en el desarrollo del TFM.**

El trabajo combinará el desarrollo de una plataforma experimental con un estudio empírico en el ámbito de la Ingeniería del Software.

En la parte de implementación se seguirá un enfoque iterativo e incremental, con el objetivo de construir progresivamente la infraestructura necesaria para ejecutar los experimentos. Al tratarse de un trabajo individual, la organización del desarrollo se apoyará en una metodología agil tipo Kanban, utilizando herramientas de planificación y control de versiones que permitan mantener trazabilidad de los cambios.

Desde el punto de vista investigador, se aplicará una metodología propia de estudios empíricos:

1. Formulación de hipótesis relacionadas con la influencia de la orquestación y del modelo LLM.
2. Definición formal de variables independientes y dependientes.
3. Diseño de un protocolo experimental reproducible.
4. Ejecución sistemática de experimentos bajo distintas configuraciones.
5. Análisis comparativo de resultados, incluyendo análisis estadístico básico.
6. Discusión de amenazas a la validez.

El experimento consistirá en ejecutar el sistema sobre un conjunto común de bugs bajo distintas combinaciones de orquestación y modelo LLM, manteniendo constantes el entorno y las condiciones de ejecución. Para cada ejecución se registrarán de forma sistemática los resultados obtenidos.

---

### FASES DE TRABAJO

1. **Estudio del estado del arte:**
   Revisión de trabajos sobre reparación automática de software y uso de LLMs, con especial atención a estudios empíricos y enfoques basados en agentes.

2. **Diseño de la plataforma experimental:**
   Definición del workflow extremo a extremo que servirá como base para la experimentación.

3. **Implementación de la infraestructura experimental:**
   Desarrollo de los componentes necesarios para ejecutar el flujo y registrar resultados.

4. **Análisis experimental:**
   Ejecución sistemática sobre el dataset seleccionado, comparación entre configuraciones y análisis de resultados.

5. **Documentacion y redacción de la memoria:**
   Elaboración de la memoria final.

---

## ENTORNO TECNOLÓGICO

### TECNOLOGÍAS EMPLEADAS

Python
Java
Javascript
LLMs propietarios y/o abiertos (por ejemplo, a través de HuggingFace)
Ollama

### RECURSOS SOFTWARE Y HARDWARE

Ordenador personal
Visual Studio Code
Trello
GitHub

### CONJUNTOS DE DATOS (DATASETS)

QuixBugs - MIT License
Defects4J - MIT License

---

## REFERENCIAS

[1] Wang, B., Deng, M., Chen, M., Lin, Y., Zhou, J., & Zhang, J. M. (2026). Assessing the effectiveness of recent closed-source large language models in fault localization and automated program repair. Automated Software Engineering, 33(1), 1-42.

[2] Dikici, S., & Bilgin, T. T. (2025). Advancements in automated program repair: a comprehensive review. Knowledge and Information Systems, 67(6), 4737-4783.

[3] Zhang, C., Wang, H., Xu, C., Liu, J., Liu, K., & Liu, Z. (2026). Can test cases generated by large language models facilitate automated program repair?. Empirical Software Engineering, 31(3), 68.

[4] Zubair, F., Al-Hitmi, M., & Catal, C. (2025). The use of large language models for program repair. Computer Standards & Interfaces, 93, 103951.

[5] Just, R., Jalali, D., & Ernst, M. D. (2014). Defects4J: A database of existing faults to enable controlled testing studies for Java programs.

[6] Lin, Derrick & Koppel, James & Chen, Angela & Solar-Lezama, Armando. (2017). QuixBugs: a multi-lingual program repair benchmark set based on the quixey challenge. 55-56. 10.1145/3135932.3135941.

[7] Santana Jr, E. G., Benjamin, G., Araujo, M., Santos, H., Freitas, D., Almeida, E., Neto, P. A. da M. S., Li, J., Chun, J., & Ahmed, I. (2025). Which Prompting Technique Should I Use? An Empirical Investigation of Prompting Techniques for Software Engineering Tasks. arXiv preprint arXiv:2506.05614.
