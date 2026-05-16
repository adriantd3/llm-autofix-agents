Graduado en Ingeniería del Software

Uso de Modelos de Visión y Lenguaje a Gran Escala en la

Desambiguación de Mapas Semánticos Probabilísticos para

Robótica Móvil

```
Use of Large-Scale Vision and Language Models in the
Disambiguation of Probabilistic Semantic Maps for Mobile Robotics
```
```
Realizado por
Adrián Torremocha Doblas
```
```
Tutorizado por
José Raúl Ruiz Sarmiento
Javier González Jiménez
```
```
Departamento
Ingeniería de Sistemas y Automática
```
UNIVERSIDAD DE MÁLAGA

MÁLAGA, junio de 2025


```
ESCUELA TÉCNICA SUPERIOR DE INGENIERÍA INFORMÁTICA
GRADUADO EN INGENIERÍA DEL SOFTWARE
```
**Uso de Modelos de Visión y Lenguaje a Gran Escala en
la Desambiguación de Mapas Semánticos Probabilísticos
para Robótica Móvil**

```
Use of Large-Scale Vision and Language Models in the
Disambiguation of Probabilistic Semantic Maps for
Mobile Robotics
```
```
Realizado por
Adrián Torremocha Doblas
```
```
Tutorizado por
José Raúl Ruiz Sarmiento
Javier González Jiménez
```
```
Departamento
Ingeniería de Sistemas y Automática
```
```
UNIVERSIDAD DE MÁLAGA
MÁLAGA, JUNIO DE 2025
```
```
Fecha defensa: julio de 2025
```

Resumen

Los mapas semánticos son representaciones del entorno de trabajo de un ro-
bot móvil que incluyen información tanto sobre la geometría de los elementos de
la escena como de su semántica, por ejemplo, las categorías de los objetos presen-
tes (silla, televisor, vaso, microondas, etc.). El proceso de construcción de dichos
mapas se ve afectado fundamentalmente por errores en el sensor y el modelo de
categorización empleado, lo que resulta en mapas con objetos categorizados de
manera imprecisa. Habitualmente, esta imprecisión en las categorías se explicita
mediante distribuciones probabilísticas.
Este Trabajo Fin de Grado propone un método para refinar mapas semánticos
probabilísticos mediante la desambiguación de objetos con alta incertidumbre en
su categorización. Para ello se emplea Voxeland, un marco que modela probabi-
lísticamente dicha incertidumbre sobre las categorías de los objetos, interpretadas
como opiniones subjetivas según la Teoría de la Evidencia.
La propuesta identifica las instancias ambiguas mediante el cálculo de la en-
tropía y, para cada una de ellas, selecciona sus categorías más probables y un
conjunto reducido de imágenes representativas. Estas se suministran, junto con
unpromptestructurado, a un Modelo de Visión y Lenguaje a Gran Escala (LVLM),
que devuelve nuevas opiniones sobre la categoría del objeto.
Las respuestas del LVLM se integran de vuelta en el mapa como nuevas evi-
dencias, actualizando las probabilidades de cada categoría. Las pruebas sobre el
conjunto de datos SceneNN muestran mejoras en la clasificación de objetos y una
reducción clara de la incertidumbre, fortaleciendo la fiabilidad de los mapas gene-
rados para su uso en robótica móvil en entornos humanos.

### Palabras clave:Robótica inteligente, Aprendizaje automático, Mé-

todos Bayesianos, Robots móviles autónomos, Construcción de mapas


Abstract

Semantic maps are representations of a mobile robot’s working environment
that include information about both the geometry of scene elements and their
semantics—for example, the categories of present objects (chair, television, glass,
microwave, etc.). The construction of such maps is fundamentally affected by sen-
sor errors and the categorization model used, which results in maps with impre-
cisely categorized objects. Typically, this imprecision in categories is represented
using probabilistic distributions.
This Bachelor’s Thesis proposes a method to refine probabilistic semantic maps
by disambiguating objects with high uncertainty in their categorization. To this
end, it uses Voxeland, a framework that probabilistically models such uncertainty
over object categories, interpreted as subjective opinions according to Evidence
Theory.
The proposed method identifies ambiguous instances by computing entropy,
and for each of them, selects their most probable categories along with a reduced
set of representative images. These are provided, along with a structured prompt,
to a Large Vision-Language Model (LVLM), which returns new opinions about
the object’s category.
The LVLM’s responses are reintegrated into the map as new evidence, upda-
ting the probabilities for each category. Tests conducted on the SceneNN dataset
show improvements in object classification and a clear reduction in uncertainty,
thereby enhancing the reliability of the generated maps for use in mobile robotics
in human environments.

### Keywords:IntelligentRobots,MachineLearning,Bayesianmethods,

Autonomous robotic systems, Map building



## Índice


- 1. Introducción
   - 1.1. Motivación.
   - 1.2. Objetivos
   - 1.3. Estado del arte.
   - 1.4. Estructura del documento.
- 2. Tecnologías utilizadas
   - 2.1. Lenguajes de programación.
      - 2.1.1. C++
      - 2.1.2. Python.
   - 2.2. Gestión y organización
      - 2.2.1. Trello
      - 2.2.2. Notion
   - 2.3. Herramientas de desarrollo
      - 2.3.1. ROS2.
      - 2.3.2. Visual Studio Code
      - 2.3.3. Git y GitHub
   - 2.4. Visual Paradigm
   - 2.5. Hugging Face
   - 2.6. CSAR
- 3. Desarrollo y diseño
   - 3.1. Metodología de trabajo
   - 3.2. Requisitos del sistema.
      - 3.2.1. Requisitos funcionales
      - 3.2.2. Requisitos no funcionales
   - 3.3. Modelado del software
      - 3.3.1. Patrones de diseño
      - 3.3.2. Comunicación entre nodos.
   - 3.4. Pruebas del software
- 4. Descripción del método
   - 4.1. Construcción del mapa semántico con Voxeland
   - 4.2. Identificación de instancias con incertidumbre
   - 4.3. Selección de categorías e imágenes
      - 4.3.1. Selección basada en propiedades visuales.
      - 4.3.2. Selección basada en diversidad temporal
   - 4.4. Desambiguación mediante LVLM
   - 4.5. Integración en Voxeland
- 5. Validación
- 6. Conclusiones y Líneas Futuras
   - 6.1. Conclusiones.
   - 6.2. Líneas Futuras
- Apéndice A. Repositorios de código
- Apéndice B. Manual de instalación
   - B.1. Requisitos Previos
   - B.2. Instalación del Sistema
      - B.2.1. Instalación de Dependencias.
      - B.2.2. Instalación de ROS
      - B.2.3. Clonado de repositorios
   - B.3. Compilación del Sistema
   - B.4. Ejecución del Sistema
      - B.4.1. Inicialización del Entorno
      - B.4.2. Lanzamiento de Voxeland y Voxeland Disambiguation


## 1. Introducción

### 1.1. Motivación.

Los robots móviles desplegados en entornos centrados en humanos son utilizados cada vez
en más ámbitos, entre otros, la asistencia al hogar, la industria, la sanidad o la agricultura (Bac
et al., 2014 ). Un requisito fundamental para su despliegue efectivo en tareas de alto nivel es
que posean capacidades cognitivas avanzadas para interpretar su entorno y razonar sobre él.

Un enfoque comúnmente aplicado para alcanzar dicha comprensión es la construcción de
mapas semánticos (Han et al., 2021 ), es decir, modelos del entorno de trabajo donde, además, de
la habitual reconstrucción geométrica de los elementos que lo componen, también se integra
información semántica sobre los mismos (propiedades, funcionalidades, relaciones, etc). Por
ejemplo, un robot de servicio en un hospital podría utilizar un mapa semántico para gestionar
la distribución de medicamentos y suministros médicos. El mapa contendría información sobre
la ubicación de cada medicamento, sus propiedades (fecha de caducidad, temperatura de al-
macenamiento) y sus relaciones (compatibilidad entre medicamentos, restricciones de acceso).
Gracias a esta información, el robot podría optimizar su entrega, garantizar el cumplimiento
de protocolos de seguridad y emitir alertas en caso de uso incorrecto de un medicamento.

En el proceso de construcción de un mapa semántico entran en juego numerosas fuen-
tes de incertidumbre, como son las que dependen de las técnicas de Visión por Computador
empleadas para percibir el entorno e identificar los elementos (objetos) en él, actualmente ba-
sadas en Aprendizaje Profundo: la falta de garantía de corrección en las categorizaciones de
objetos, la generación de predicciones con alto grado de confianza sobre objetos que están
fuera del conjunto de categorías identificables por el método usado, máscaras incompletas o
sobredimensionadas, etc. (Chaves et al., 2019 ;Matez-Bandera et al., 2024 ).


Así, queda patente que la incertidumbre sobre las detecciones debe ser tratada. Además, da-
do que la percepción del entorno se realiza con una secuencia de imágenes (vídeo), todos estos
problemas se acumulan a lo largo del proceso de construcción del mapa semántico, mermando
la corrección y la fiabilidad del mapa si se ignoran, pudiendo dar lugar a un comportamiento
errático del robot (Matez-Bandera et al., 2022 ). Por tanto, es crucial gestionar explícitamente
la incertidumbre durante la construcción y uso de mapas semánticos.
Este contexto motiva el desarrollo de marcos de trabajo como Voxeland (Matez-Bandera
et al., 2024 ), que construye mapas semánticos probabilísticos capaces de cuantificar explícita-
mente la incertidumbre tanto geométrica como semántica (ver Figura 1 ). Voxeland representa
la información semántica como “opiniones” probabilísticas sobre las categorías de los objetos.
En concreto, este trabajo tiene como propósito reducir la incertidumbre del mapa semán-
tico. Para ello, se propone un método que, dado un mapa semántico de entrada, identifique
las instancias de objetos con alta incertidumbre en su categorización (esto es, con opiniones
contradictorias) basándose en el concepto de entropía, y desambigüe estas, empleando Mode-
los de Visión y Lenguaje a Gran Escala (del inglésLarge Vision Language Models, LVLMs) para
aportar opiniones adicionales que se integran de nuevo en el mapa a partir de una serie de
imágenes y el diseño de lospromtsadecuados. Remarcar que estos procesos son automáticos,
sin necesitar operaciones manuales. Los desarrollos se han realizado en el contexto de Ro-
bot Operating System 2 (ROS 2)Quigley et al.( 2009 ), requiriendo modificaciones en el propio
Voxeland y el desarrollo de componentes adicionales.
Estos desarrollos se han validado empleando escenas del conjunto de datos del estado del
arte ampliamente extendido, SceneNN (Hua et al., 2016 ). Para ello, se han analizado mapas
semánticos construidos por Voxeland a partir de varias escenas de dicho repositorio (en es-
ta memoria se describe la más completa de ellas), identificándose las instancias con mayor
incertidumbre semántica y aplicando el proceso de desambiguación para cada una de ellas,
obteniendo unas categorías finales válidas y con menor incertidumbre.

### 1.2. Objetivos

El objetivo de este trabajo es el desarrollo de un método para analizar y reducir automá-
ticamente la incertidumbre semántica en mapas construidos con Voxeland, con el objetivo
de producir representaciones del entorno más confiables. Este objetivo general incluye los
siguientes objetivos específicos:


Figura 1:Representación de los cuatro tipos de mapas generados por Voxeland, extraída del
artículo original (Matez-Bandera et al., 2024 ).

```
Identificación de incertidumbre, mediante técnicas como el cálculo de la entropía
sobre las opiniones semánticas para localizar las áreas o instancias de objetos más am-
biguas en el mapa
```
```
Desambiguación, con el uso de herramientas externas, como Modelos de Lenguaje
y Visión a Gran Escala (LVLMs), para obtener nuevas “opiniones” sobre las instancias
identificadas como inciertas.
```
```
Integraciónde la información obtenida de la desambiguación como nuevas opiniones
ponderadas dentro del marco probabilístico de Voxeland, refinando así el mapa y redu-
ciendo la incertidumbre global.
```
### 1.3. Estado del arte.

En materia de mapas semánticos, existen numerosos artículos que se enfrentan a las difi-
cultades en la compleja creación de este tipo de representaciones (Ruiz-Sarmiento et al., 2017 ;
Kostavelis and Gasteratos, 2015 ). Quizás uno de los trabajos recientes más populares sea el


Figura 2:Descripción visual del flujo de creación de mapas semánticos usandoConceptGraphs.
Imágen extraída del artículo originalGu et al.( 2023 ).

presentado porGu et al.( 2023 ), donde se introduce el concepto deConceptGraphs. UnConcept-
Graphes una representación de una escena mediante un grafo en el cual los nodos representan
los objetos y los arcos representan las relaciones geométricas entre ellos (ver Figura 2 ). Aun-
que destaca por su planteamiento claro y sencillo, en el articulo se obvian las implicaciones de
la incertidumbre en la creación del grafo.

Como se ha mencionado con anterioridad, este trabajo se enmarca en el contexto del marco
de trabajo probabilístico Voxeland, diseñado para construir, de manera incremental, mapas
semánticos que tengan en cuenta las instancias de objetos. El enfoque probabilístico es dual, ya
que se considera tanto para determinar la posición como la categoría semántica de los objetos.
Principalmente, se basa en la Teoría de la Evidencia deJsang( 2018 ), Concretamente, a partir
de una secuencia de imágenes del entorno, es capaz de generar 4 mapas: mapa de las instancias
de objetos, mapa semántico con las categorías de estos objetos y los correspondientes mapas
de incertidumbre (recuérdese la Figura 1 ).
Para la construcción del mapa semántico con Voxeland es necesario el análisis de imágenes
RGB-D, concretamente se recurre a técnicas de Visión por Computador, actualmente basadas
en Aprendizaje Profundo, que permitan la detección y clasificación de los elementos del en-
torno (p.ej.,YOLO (Redmon et al., 2016 ;Wang et al., 2024 ) y Mask R-CNN (He et al., 2017 )) a
partir de dichas imágenes (véase la Figura 3 ). Son el uso de estas técnicas las que fundamentan


```
Figura 3:Ejemplos de identificación y segmentación de objetos usando Mask R-CNN.
```
este trabajo, pues dado que el margen de tiempo operativo es muy reducido, a menudo, las
detecciones pueden ser inexactas (producción de máscaras erróneas o sobredimensionadas) y
las clasificaciones erróneas (categoría incorrecta), provocando incertidumbre en el mapa.
En los últimos años, la construcción de mapas semánticos para robótica móvil ha expe-
rimentado importantes avances debido al desarrollo y la integración de métodos avanzados
de percepción y aprendizaje automático. Entre estas innovaciones destacan los Modelos de
Visión y Lenguaje a Gran Escala (LVLMs), herramientas capaces de procesar e interpretar
conjuntamente información visual y lingüística, proporcionando una mayor capacidad para la
comprensión semántica de los entornos.
Una arquitectura clave que subyace en muchos de estos modelos es eltransformer(Vaswani
et al., 2017 ). Eltransformerdestaca por su mecanismo deautoatención(self-attention), que
permite modelar dependencias a largo plazo sin la limitación de procesamiento secuencial
inherente a redes tradicionales. Este mecanismo evalúa la relevancia de cada elemento de la
entrada (por ejemplo, palabras en texto o regiones en imágenes) en relación con todos los
demás elementos, facilitando así representaciones más contextuales y efectivas.
En el contexto que nos ocupa, entre los LVLMs más destacados se encuentran MiniCP-
Mo2.6 y Qwen2.5VL. MiniCPMo2.6 (Yao et al., 2024 ) es un modelo compacto y eficiente, pen-


sado para entornos con recursos limitados, que ofrece buenos resultados en clasificación de
objetos, reconocimiento de escenas y generación de descripciones a partir de imágenes, lo que
lo hace especialmente útil en tareas de desambiguación. Qwen2.5VL (Bai et al., 2025 ), por su
parte, está orientado a tareas que exigen una alta precisión tanto en visión como en lenguaje.
Gracias a su capacidad para manejar contexto de forma efectiva, resulta especialmente ade-
cuado para aplicaciones en robótica móvil.

### 1.4. Estructura del documento.

```
Este documento esta dividido en 6 secciones, organizadas de la siguiente manera:
```
1. Introducción: esta sección donde se ha introducido el tema de este proyecto, detallando
    las principales motivaciones que lo justifican y especificando los objetivos a cumplir.
    También se ha descrito brevemente el estado del arte en el que se enmarca el proyecto.
2. Tecnologías utilizadas: en esta sección se detallan las principales tecnologías emplea-
    das a lo largo del desarrollo de este Trabajo de Fin de Grado. Las tecnologías están cla-
    sificadas por contexto, incluyendo tanto una descripción de cada una de ella como una
    descripción de la forma en la que han sido empleadas para este trabajo.
3. Desarrollo y diseño: esta sección incluye toda la información relacionada a la aplica-
    ción de las metodologías y buenas prácticas que caracterizan a la Ingeniería del Software.
    Se incluye tanto la gestión y organización del trabajo como el modelado conceptual del
    sistema, los requisitos y las pruebas a las que se ha sometido el software.
4. Descripción del método: esta sección explica de manera detallada el flujo de trabajo
    principal desarrollado en este proyecto. Describe el proceso desde que se recibe el mapa
    semántico de Voxeland, se identifican instancias de objetos inciertas, se desambiguan, y
    se integra el resultado de nuevo en el mapa.
5. Validación: en esta sección se valida el método propuesto mostrando un caso de uso en
    el que se aplica el proceso de desambiguación semántica a una escena de especial interés
    del conjunto de datos del estado del arte SceneNN. Además, se hacen comparativas entre
    diversas configuraciones del sistema. Los resultados expuestos demuestran el correcto
    funcionamiento del flujo de trabajo desarrollado.


6. Conclusiones: en esta sección se hace un breve resumen del trabajo realizado en este
    proyecto, indicando las implicaciones y mejoras que supone. Además, por último, se
    especifican posibles trabajos futuros que complementan a los avances desarrollados en
    este trabajo.



## 2. Tecnologías utilizadas

En esta sección se presentan los distintos recursos tecnológicos empleados durante el de-
sarrollo del proyecto, agrupados según su función dentro del flujo de trabajo.

En primer lugar, se especifican aquellos lenguajes de programación con los que se ha de-
sarrollado todo el código para este TFG, es decir, tanto la implementación del nodo principal
de Voxeland Disambiguation como del resto de herramientas o utilidades que forman parte
del sistema (ver Sección2.1).

Posteriormente, se mencionan todas las herramientas de organización y gestión que han
sido clave para realizar un control y seguimiento eficaz de los desarrollos a lo largo de este
TFG, facilitando la planificación de tareas y el mantenimiento del repositorio (ver Sección2.2).

También se hace una descripción general de todas aquellas herramientas que sustentan
el desarrollo, desde el marco de trabajo empleado para la ejecución de nodos robóticos, hasta
los entornos que han servido como soporte para la programación, prueba y depuración del
sistema (ver Sección2.3).

Por último, se mencionan todas aquellas tecnologías relevantes en distintas áreas del desa-
rrollo, ya sea el ecosistema base en el que se despliega todo el sistema, la herramienta principal
de modelado o la plataforma utilizada para acceder a modelos de lenguaje y visión fundamen-
tales en el proceso de desambiguación.


### 2.1. Lenguajes de programación.

#### 2.1.1. C++

Es el lenguaje de programación que se ha usado para desarrollar el nodo principal de des-
ambiguación. Si bien es un lenguaje de programación muy usado en todo tipo de ámbitos, está
perdiendo popularidad a lo largo de los años debido a la complejidad en su sintaxis y la ges-
tión manual de referencias y punteros. No obstante, es este control sobre la memoria lo que lo
hace ideal para todo tipo de sistemas en los cuales la eficiencia y el rendimiento son requisitos
fundamentales. Dado que el sistema de Voxeland fue implementado en C++, se consideró que
era conveniente realizar la aportación de este trabajo también en este lenguaje.

#### 2.1.2. Python.

Python es uno de los lenguajes de programación mas utilizados en los últimos años. Su
sintaxis sencilla, el tipado dinámico y no declarativo, junto con el gran apoyo de la comunidad,
lo han convertido en una de las opciones por defecto en una amplia variedad de ámbitos,
desde “scripts” sencillos hasta aplicaciones web, visión por computador, inteligencia artificial,
robótica, etc.
Concretamente, para el desarrollo de este proyecto se ha utilizado la versión 3.10, debido a
su estabilidad y a la gran compatibilidad con muchísimas dependencias que necesitaba. Python
brilla también por su excelente gestión de las mismas, permitiendo crear entornos virtuales,
los cuales permiten instalar las dependencias que se necesiten en cada proyecto, evitando así
conflictos entre ellos.

El uso de Python ha sido crucial para el desarrollo de herramientas fundamentales que
permitan probar o validar el flujo de trabajo de Voxeland Disambiguation. Los casos de uso
implementados han sido la conversión de escenas de conjuntos de datos a un formato compa-
tible con ROS y el desarrollo de un ligero visualizador de mapas de incertidumbre semántica.
Otro punto fuerte es la enorme cantidad de librerías y marcos de trabajo disponibles, que
cubren prácticamente cualquier necesidad. Además, se integra muy bien con los principales
editores de código y entornos de desarrollo (IDE), como Visual Studio Code o PyCharm, ha-
ciendo que la experiencia de trabajo sea muy fluida y agradable.


Figura 4:Tablero de Trello usado para la gestión de tareas del proyecto. Está dividido en varias
columnas:Backlog, donde se almacenan aquellas tareas de alto nivel que pueden contener
subtareas;To Do, un conjunto reducido de tareas (máximo 5) que están próximas a hacerse;
Doing, con las tareas en las que se esta trabajando en ese momento (máximo 2); y las columnas
Donesemanales, donde se recogen aquellas tareas completadas a lo largo de cada semana.

### 2.2. Gestión y organización

#### 2.2.1. Trello

Trello es una aplicación web diseñada para la gestión ágil de proyectos. Brinda la posi-
bilidad de crear tableros que permitan distribuir el trabajo en columnas y tareas. Es perfecta
para la implantación de diversas metodologías de trabajo, tales comoKanbanoScrum. En el
contexto de este proyecto, ha sido fundamental, pues permite registrar y visualizar de ma-
nera sencilla y estructurada las tareas pendientes de realizar, las que están en progreso y las
finalizadas (ver Figura 4 ).

Su carácter completamente personalizable lo convierte en una herramienta muy versátil
capaz de adaptarse a cualquier tipo de proyecto y casos de uso. Cuenta, además, con opciones
para añadir extensiones y automatizaciones, que simplifican la gestión aún más.


Figura 5:Tabla de Notion creada para registrar las horas de trabajo y el progreso o anotaciones
útiles de cada día. En la parte izquierda de la imágen se muestra una tabla que actua como
calendario, mientras que en la derecha se encuentra uno de los documentos asociados a uno
de los días registrados.

#### 2.2.2. Notion

Notion es una aplicación que está disponible tanto en dispositivos móviles, ordenador per-
sonal y aplicación web. Es bastante popular pues permite organizar información, gestionar
tareas y colaborar en equipo. Combina funcionalidades de aplicaciones de procesadores de
texto (basado en el lenguaje Markdown), bases de datos, listas de tareas, wikis, calendarios,
etc.
Es realmente accesible, pues ofrece una interfaz flexible basada en bloques que permite
crear desde cero todo tipo de páginas. En el contexto de este proyecto, ha sido usado para
mantener un histórico de las horas que se han dedicado cada día al proyecto, agregando des-
cripciones de las tareas realizadas y pendientes, y diversas anotaciones.

### 2.3. Herramientas de desarrollo

#### 2.3.1. ROS2.

ROS 2 (Robot Operating System 2) es un conjunto de herramientas y bibliotecas para el
desarrollo de software robótico. Un sistema de ejecución de ROS (Quigley et al., 2009 ) está


formado por una red de nodos, es decir, procesos que realizan tareas específicas. Los nodos
pueden comunicarse entre sí mediante diversos protocolos de comunicación: tópicos, servicios
y acciones.

A diferencia de ROS 1, ROS 2 fue diseñado desde cero para soportar comunicación dis-
tribuida robusta mediante DDS (Data Distribution Service), mejorando aspectos clave como la
seguridad, la escalabilidad, la comunicación en tiempo real y la compatibilidad con múltiples
sistemas operativos.
ROS 2 Humble Hawksbill, la versión utilizada en este proyecto, fue lanzado en 2022, inclu-
yendo mejoras importantes en rendimiento, herramientas de desarrollo, soporte para múltiples
lenguajes (como C++ y Python), y un ecosistema más consolidado. Esta versión utiliza “colcon”
como sistema de construcción, que permite compilar múltiples paquetes de manera eficiente,
paralela y personalizada. En ROS 2, un paquete es la unidad mínima de software reutilizable:
contiene código fuente, nodos, archivos de configuración, recursos y archivos de metadatos
que describen sus dependencias. Dada la gran cantidad de paquetes que requiere Voxeland
para ser ejecutado, tener la posibilidad de compilar cada uno de manera independiente hace
que se reduzca mucho la fricción a la hora de desarrollar y hacer pruebas sobre el proyecto.

Además ROS2 gestiona las dependencias de paquetes automáticamente, lo que facilita el
mantenimiento y escalado de proyectos complejos.

En cuanto a las herramientas que proporciona ROS2, las más relevantes y utilizadas en el
contexto de este trabajo son:

```
RViz: visualizador de escenas 3D que es capaz de vincularse con cualquier nodo ROS
para representar cualquier escena en 3D.
```
```
RQT Graph: herramienta que permite visualizar grafos representativos de los nodos
y los servicios, tópicos y acciones que usan para interactuar con otros nodos (véase la
Figura 6 ).
```
```
RQT: herramienta sencilla que permite simular la publicación de servicios que consume
cualquier nodo ROS. Esta diseñado para hacer pruebas sencillas sobre los nodos.
```

Figura 6:Ejemplo de la representación gráfica del nodo Voxeland Server junto con los tópicos
y servicios que implementa y consume. Diagrama generado con la herramienta RQT Graph.

#### 2.3.2. Visual Studio Code

Visual Studio Code es un editor de código muy liviano que se ha convertido en la opción
de preferencia para muchos desarrolladores. Al ser de código abierto, la comunidad puede
contribuir activamente creando extensiones que lo hacen adaptable a todo tipo de lenguajes
de programación o casos de uso. Ha sido utilizado en este proyecto para desarrollar todo el
código relacionado con el mismo, programando tanto en C++ como en Python, y la experiencia
ha sido muy cómoda. Las extensiones como el autocompletado con sugerencias de código, la
integración con Git y la conexión remota con SSH hacen que trabajar sea mucho más ágil
que con otros editores. Aunque en la actualidad han surgido muchas alternativas basadas en
Visual Studio Code, tales como Cursor o Windsurf, el editor sigue evolucionando día tras día
para mantenerse como el editor de código más relevante y completo para programar hoy en
día.

#### 2.3.3. Git y GitHub

Git es un sistema de gestión de versiones que permite crear repositorios en los que alma-
cenar el código y mantener un histórico de todos los cambios que experimenta a lo largo del
tiempo. Se utiliza principalmente mediante la línea de comandos (CLI), aunque los principales
editores de código y entornos de desarrollo integran una interfaz de uso sencilla para poder
utilizarlo.


Figura 7:Ejemplo de una Pull Request en GitHub solicitada en el repositorio de MAPIRlab/-
ros_lm.

Esta tecnología es clave para el desarrollo de código colaborativo, pues permite crear rami-
ficaciones del código que pueden ir mezclandose al gusto. Hoy en día, la plataforma principal
para alojar cualquier repositorio de Git es GitHub, la cual brinda acceso a un sinfín de reposi-
torios públicos, con la posibilidad también de crear repositorios privados de manera comple-
tamente gratuita. Por lo tanto, se ha utilizado GitHub principalmente para desarrollar código
nuevo y compartirlo con compañeros y supervisores.
Una de las funcionalidades claves en GitHub es la creaciónPull Requests(ver Figura 7 ),
es decir, solicitudes de revisión para mezclar el código entre ramas, más habitualmente entre
una rama de desarrollo y la principal omain. Esta funcionalidad ha sido utilizada en varias
ocasiones a lo largo del proyecto, siendo clave para mantener a los compañeros al día con el
estado del proyecto.

### 2.4. Visual Paradigm

Visual Paradigm es un programa de escritorio que facilita mucho el trabajo de planificar
y diseñar software, especialmente cuando se necesita plasmar ideas de forma visual. Permite
crear todo tipo de diagramas, como los de flujo, UML, casos de uso o estructuras de base de
datos, lo que ayuda a entender mejor cómo debe funcionar un sistema antes de construirlo.


Figura 8:Representación de la interfaz gráfica de Visual Paradigm para la creación de un dia-
grama de clases.

Es muy útil tanto para desarrolladores como para analistas o equipos que necesitan organizar
sus ideas y comunicarlas con claridad.
También incluye herramientas que acompañan todo el proceso de desarrollo, desde la de-
finición de requisitos hasta la documentación final. Incluso permite colaborar en línea y ges-
tionar proyectos con enfoques ágiles. Se trata de una herramienta clave que se utiliza con
frecuencia a lo largo de la carrera y, consecuentemente, también en este proyecto. Visual Pa-
radigm ha sido esencial para la creación de los diagramas de clase, de secuencia, etc (ver Figura
8 ).

### 2.5. Hugging Face

Se trata de una plataforma diseñada para que cualquier persona interesada en la inteli-
gencia artificial pueda encontrar, usar y compartir modelos de manera sencilla. Es un espacio
colaborativo donde miles de desarrolladores e investigadores publican sus modelos y datos,
permitiendo que cualquier usuario pueda probarlos, ya sea directamente desde la web, con un
pequeño “playground”, o integrándolos manualmente en sus proyectos.


En cuanto al uso de los modelos en el código, Hugging Face consigue que trabajar con mo-
delos de inteligencia artificial sea ciertamente accesible, pues pues trabajan muy activamente
en el desarrollo y mantenimiento de su propia libreríatransformers, la cual permite cargar y
usar cualquier modelo de la plataforma de manera que no se requieran conocimientos excesi-
vamente técnicos.
Hugging Face ha resultado ser muy útil, pues ha permitido encontrar diversos modelos de
inteligencia artificial utilizados en este proyecto, tales como MiniCPM-o2.6 (Yao et al., 2024 ) o
Qwen-2.5-VL (Bai et al., 2025 ).

### 2.6. CSAR

CSAR (Ambrosio et al., 2024 ) se trata de un servicio micro-nube desarrollado en el gru-
po MAPIR que, bajo el paradigma del Edge Computing, proporciona los recursos necesarios
para el desarrollo de software orientado a la robótica. Es un sistema distribuido que permi-
te la creación y gestión de contenedores Linux que actúan como máquinas virtuales ligeras.
Esto permite a cada usuario del sistema desarrollar sus soluciones particulares en un entorno
completamente personalizable. Concretamente, en CSAR la tecnología para la gestión de con-
tenedores es LXD de Canonical. No obstante, también soporta Docker y Podman.
Una de las ventajas de usar contenedores, a diferencia usar maquinas virtuales directas,
es que estos tienen acceso directo al kernel del sistema y, por lo tanto, también a los recursos
físicos del servidor.
Se ha desarrollado todo el proyecto usando un contenedor creado a partir de una imagen
con Ubuntu 22.04 LTS como sistema operativo, CUDA 12.2 y la distribución de ROS2 Hum-
ble LTS. Cabe destacar que el acceso a los contenedores se realiza mediante el protocolo de
comunicación SSH (ver Figura 9 ).
CSAR y, por tanto, todos los contenedores se ejecutan en un servidor gestionado por el
grupo MAPIR. Se trata del ordenadorUltra Edge, equipado con algunos de los componentes
más potentes del mercado en la actualidad. Las principales especificaciones del sistema son las
siguientes:

```
Procesador AMD Ryzen Threadripper PRO 7975WX de 32 núcleos a 4.0GHz
512GB de memoria RAM DDR5 4800MHz
```

```
Configuración de triple NVIDIA RTX6000 ADA GPUs, cada una con 48GB de memoria
GDDR6.
6TBs de almacenamiento SSD con un WD_Black con velocidades de lectura de hasta
7300MB/s y 6300MB/s de escritura.
18TB de almacenamiento HDD.
```
Figura 9:Ventana de bienvenida al acceder a uno de los contenedores de CSAR a través de la
línea de comandos. Accesible mediante el protocolo SSH.


## 3. Desarrollo y diseño

En esta sección se describen las decisiones tomadas durante el proceso de implementación
de Voxeland Disambiguation, así como los criterios seguidos para el diseño del sistema, des-
de una perspectiva tanto metodológica como técnica. El objetivo es proporcionar una visión
clara de los fundamentos que han guiado el desarrollo del sistema y sentar las bases para la
comprensión detallada del método, que se aborda en el capítulo siguiente.
Se expone el enfoque ágil e iterativo adoptado, basado en la metodología Kanban, y apoya-
do en herramientas como Trello y Notion para la planificación y seguimiento de los avances
en el software desarrollado (ver Sección3.1). También se detallan los requisitos que han guia-
do el desarrollo, tanto funcionales (identificación de instancias ambiguas o la integración con
Voxeland mediante ROS2) como no funcionales (la eficiencia, modularidad y escalabilidad del
sistema) (ver Sección3.2).
Asimismo, se analiza el modelado del software, incluyendo tanto los patrones de diseño
empleados, como los mecanismos de comunicación entre nodos que permiten la integración
con el sistema de Voxeland (ver Sección3.3). Finalmente, se presentan las pruebas a las que se
ha sometido el software, especificando las buenas prácticas implementadas (ver Sección3.4).
Todo ello proporciona un marco coherente y fundamentado sobre el que se sustenta el
sistema propuesto, garantizando su funcionalidad, robustez y capacidad de extensión.

### 3.1. Metodología de trabajo

Como en cualquier proyecto de software, cumplir con una buena metodología y organiza-
ción del trabajo es clave para llevar a cabo todas las tareas del proyecto de la manera más efec-
tiva y cumpliendo con los plazos establecidos. Además, mantener un seguimiento del trabajo
es importante para tener un histórico de todas las etapas del proyecto, cuando se empezaron, y
cuanto tardaron en hacerse. Toda esta información es de vital importancia de cara a optimizar


nuestro tiempo e identificar aquellas áreas que requieran más o menos tiempo.
Dado que se trata de un proyecto personal, se consideró que la mejor metodología a aplicar
es Kanban, es decir, una simple manera de distribuir el trabajo en un grupo reducido de tareas
dispuestas de manera visual que permita una rápida y sencilla organización de las mismas.
Kanban es además una metodología muy flexible, pues no te exige dividir el trabajo ensprints
que debes cumplir, a diferencia de otras como Scrum. Ya que el desarrollo de este TFG se
produjo de manera paralela a las prácticas curriculares de empresa, el hecho de no exigirse
unos plazos límites tan estrictos e inamovibles permitió desarrollar el proyecto a un buen
ritmo y sin presiones innecesarias.
Para aplicar Kanban, se ha hecho uso de un tablero de Trello, por la gratuidad y el buen
diseño de su interfaz (recuérdese Figura 4 ). Dado que esta plataforma está diseñada para dis-
tribuir las tareas en muy poco texto, se consideró que, para mantener un histórico completo de
los avances, dudas y cuestiones que surgían a lo largo del proyecto, se necesitaba otra herra-
mienta que permitiese escribir libremente. Para esto, se optó por usar Notion, una plataforma
que permite crear todo tipo de documentos completamente personalizables.
Es este caso, se consideró oportuno crear una página con una tabla (recuérdese la Figura
5 ) en el que las filas representan cada día en el que se ha trabajado en el proyecto y varias
columnas: una columna con enlace a documentos en los que escribir todo lo que considerase
necesario sobre ese día, y otras columnas en las que hacer un registro de las horas dedicadas
al proyecto.
El uso de Trello y Notion en conjunto permitieron estar al tanto de los avances del proyecto
y recordar todas las tareas comenzadas y pendientes sin importar el tiempo que pasase.

### 3.2. Requisitos del sistema.

La Ingeniería de Requisitos es una fase fundamental en todo proyecto de desarrollo soft-
ware, ya que permite establecer de forma clara y estructurada lo que se espera del sistema
antes de proceder con su implementación. Definir correctamente los requisitos ayuda a redu-
cir ambigüedades, anticipar posibles conflictos y asegurar que el resultado final satisfaga las
necesidades reales del problema planteado. En el contexto de este TFG, los requisitos son es-
pecialmente importantes, dado que el sistema propuesto debe integrarse con una arquitectura
ya existente.


#### 3.2.1. Requisitos funcionales

```
RF1. Configuración de parámetros: el sistema debe soportar una serie de configura-
ciones que definen el flujo de trabajo, tales como: los archivos de entrada, el clasificador
de apariciones, el LVLM utilizado, el número de iteraciones de desambiguación, etc. Di-
chas configuraciones deben ser establecidas mediante un archivolaunchde ROS2.
RF2. Identificación de incertidumbre semántica: el sistema debe detectar automá-
ticamente las instancias del mapa semántico que presentan alta entropía en su distribu-
ción de categorías, utilizando para ello la información proporcionada por Voxeland en
formato JSON.
RF3. Selección de observaciones relevantes: para cada instancia ambigua, el sistema
debe seleccionar las categorías más probables y extraer un subconjunto representativo
de imágenes en las que ha sido clasificada en dichas categorías.
RF4. Desambiguación mediante LVLM: el sistema debe generar unpromptestruc-
turado con las imágenes e instrucciones necesarias y consultar un modelo de visión y
lenguaje a gran escala (LVLM) para obtener una categoría “definitiva”.
RF5.ReintegracióndelaopinióndelLVLM: la salida del LVLM debe ser interpretada
como una nueva opinión subjetiva e integrada en el marco probabilístico de Voxeland,
actualizando los parámetros de concentración correspondientes.
RF6.Exportaciónderesultados: el resultado de la desambiguación debe ser exportado
en formato JSON compatible con Voxeland, permitiendo su reintegración automática en
el mapa.
```
#### 3.2.2. Requisitos no funcionales

```
RNF1. Rendimiento: el sistema debe procesar cada instancia con alta incertidumbre
en un tiempo razonable, permitiendo su ejecución en escenarios reales o conjuntos de
datos de gran tamaño como SceneNN.
RNF2. Modularidad: el sistema debe estar organizado en módulos independientes y
reutilizables, como identificador de incertidumbre, selector de apariciones, generador
```

```
deprompt, y actualizador de evidencias.
RNF3. Integración en ROS 2: toda la funcionalidad debe estar encapsulada en nodos
de ROS 2, siguiendo buenas prácticas de desarrollo distribuido y comunicación mediante
servicios o tópicos.
RNF4. Compatibilidad con Voxeland: se debe asegurar la compatibilidad comple-
ta con la representación de datos y estructuras del marco de trabajo de Voxeland, sin
necesidad de modificar su núcleo.
RNF5. Usabilidad y trazabilidad: el sistema debe facilitar el seguimiento y depura-
ción del proceso de desambiguación, proporcionando salidas intermedias, métricas y
registros de los pasos realizados.
RNF6. Portabilidad: el código debe ejecutarse correctamente en entornos Linux, ya
sea en aquellos basados en contenedores (CSAR) o en ordenadores personales.
```
### 3.3. Modelado del software

Una de las características que diferencian a la Ingeniería del Software de otras disciplinas
similares es la forma de proceder tan sistemática a la hora de diseñar y desarrollar software.
En este caso, realizar diagramas del código a implementar es un aspecto clave, ya que sirve
tanto para forzarnos a diseñar el sistema más robusto y completo posible desde el comienzo,
como de documentación para cualquier persona que quiera aprender sobre el proyecto. En el
caso particular de este proyecto, se ha realizado un diagrama de clases del sistema de Voxe-
land Disambiguation Node, la principal aportación de este TFG, y también un diagrama de
componentes y diagramas de secuencia que ilustran el flujo general del sistema, incluyendo
las interacciones entre los nodos que conforman Voxeland.

#### 3.3.1. Patrones de diseño

Los patrones de diseño constituyen a una serie de soluciones probadas a todo tipo de casos
en el diseño e implementación del software. La aplicación de patrones de diseño hacen que el
sistema a desarrollar sea más entendible y, sobre todo, escalable. El uso de patrones de diseño
están muy alineados con el cumplimiento de los principios SOLID, por tanto, se han tenido


muy en cuenta en el diseño de la solución propuesta en este TFG. Todos ellos están aplicados
en el diagrama de clases conceptual de la Figura 10.
Dado que el propósito del nodo es ejecutar un procedimiento secuencial y sistemático, las
partes principales del código se estructuran aplicando el patrón de diseño“Pipeline”. Este
patrón organiza el flujo en una lista ordenada de manejadores (o etapas) independientes, cada
uno responsable de una acción muy concreta y coherente con el principio de responsabilidad
única. El nodo principal instancia dichas etapas, define su orden de ejecución y las invoca
secuencialmente, deteniendo el proceso si alguna experimenta cualquier excepción. A dife-
rencia del patrón“Chain of Responsibility”, donde cada manejador se encarga de ejecutar
el siguiente, en el patrón“Pipeline”la secuencia está completamente centralizada en el nodo
principal, lo que permite un mayor control del flujo sin sacrificar la modularidad ni la claridad
de cada fase.
Para implementarlo, se crea la interfazPipelineStepque define el métodoexecute(),
el cual constituye la principal acción de cada manejador. Posteriormente, se crea una cla-
se abstracta para incorporar cualquier lógica común a todos los manejadores concretos, en
este caso, la clase abstracta esAbstractPipelineStep. Por último, cada manejador concre-
to hereda de la clase abstracta, redefiniendo el métodoexecute()e implementando aque-
llos métodos propios de cada paso del pipeline. Por ejemplo:JsonDeserializationStep,
UncertainInstanceIdentificationStep, etc.


Figura 10:

Diagrama de clases del nodo ROS2 Voxeland Disambiguation. Se recomienda su visualización empleando un Zoom del 200 %.


Uno de los pasos del pipeline consiste en hacer una selección de imágenes de una lista. Da-
do que dicha selección se puede realizar de diversas formas, se consideró que la mejor forma
de implementarlo es mediante el patrónStrategy, el cual permite cambiar algoritmos en tiem-
po de ejecución fácilmente y dinámicamente. Este enfoque está alineado con los principios de
abierto/cerrado, de segregación de interfaces y de inversión de dependencias. En este caso,
la interfaz esAppearancesClassifierla cual define el métodoclassify_appearances().
Esta función debe ser implementada por todas la estrategias que cumplen con la interfaz, por
ejemplo:RandomClassifierySplitClassifier.
Para crear instancias de dichas estrategias de forma parametrizable, se ha implementado
unFactoryque es capaz de crear cada clasificador en función de un string identificador, se
trata de la claseAppearancesClassifierFactory. De esta forma, se delega la responsabilidad
de la creación de cada estrategia a otra clase.
Por último, ya que todos los manejadores trabajan sobre los mismos datos, en vez de propa-
gar dicha información a lo largo del flujo de trabajo, se considera oportuno crear un contexto
global del sistema mediante el uso del patrónSingleton. Este patrón permite garantizar la
existencia de una única instancia de una clase, en este caso, delDisambiguationContext, el
cual contiene referencias del mapa semántico y de aquellas instancias con incertidumbre.

#### 3.3.2. Comunicación entre nodos.

Para orquestar un sistema de ROS2 formado por varios nodos, éstos necesitan comunicarse
para transmitir información u órdenes. Para ello, se definen una serie de protocolos de comu-
nicación:tópicos, que se asemejan al patrón de diseñoObserver, en el que hay un elemento
suscriptor y otro publicador;servicios, los cuales cumplen con el esquema típico de cliente-
servidor; y lasacciones, una mezcla entre los otros protocolos, en la que el cliente realiza una
acción sobre el servidor y éste publica periódicamente el estado de la misma. La información
transmitida en cada comunicación es definida en una interfaz que ambos nodos partícipes de
la comunicación deben implementar.
Dado que el nodo deVoxeland Disambiguationdepende directamente de la información
transmitida a lo largo de diferentes componentes del sistema, una buena forma de ilustrar de
manera estructural y sencilla los nodos que componen el sistema completo y las comunicacio-
nes entre ellos es mediante un diagrama de componentes.


Figura 11:Diagrama de componentes del sistema de Voxeland. Las interfaces de color verde
se refieren a los tópicos, mientras que las naranjas a los servicios.

En la Figura 11 se muestran los 6 nodos del sistema que componen Voxeland en este TFG,
especificando las interfaces mediante las que se comunican los nodos y el tipo de comunica-
ción. Cada nodo cumple con una funcionalidad muy concreta:

```
Scene Rosbag: Constituye la fuente de imágenes que da inicio al sistema. Contiene la
información RGB, de profundidad y parámetros de calibración de la cámara. Actúa como
una base de datos que reproduce la secuencia de imágenes de la escena.
Robot Perception: Nodo que se encarga de recibir las imágenes RGB-D y solicitar la
información semántica de las mismas a otro nodo. Finalmente integra toda esta infor-
mación en una nube de puntos que envía a Voxeland Server.
Detectron2: Nodo que implementa una interfaz para solicitar la identificación, clasifi-
cación y segmentación de objetos de una imagen. Destaca por tener unos tiempos de
respuesta muy bajos pese a todo el proceso que aplica sobre cada imagen.
Voxeland Server: Componente principal del sistema. Recibe la información geométrica
y semántica de la nube de puntos local asociada a cada imagen y aplica un proceso que
integra de manera incremental los mapas locales con el mapa global.
Voxeland Disambiguation: Principal aportación de este TFG, se encarga de obtener
la información semántica del mapa y aplicar un proceso de desambiguación mediante
un LVLM cargado en el nodo ROS LM
```

```
ROSLM: Nodo especializado en cargar y usar distintos modelos de inteligencia artificial.
Se adapta a cualquier modelo, ya sea un Modelo de Lenguaje a Gran Escala (del ingés,
LLM) o un LVLM.
```
Otro tipo de diagramas muy apropiado para comprender el funcionamiento interno del
sistema es el diagrama de secuencia. Este tipo de diagrama permite realizar una descripción a
alto nivel de ciertos flujos del sistema. En el caso de Voxeland, en la Figura 12 se ilustra todo
el procedimiento principal que se aplica en el sistema, desde el momento en el que se provee
una imagen hasta que se integra en el mapa semántico. Este proceso se repite a lo largo de
todas las imágenes de la escena, construyendo poco a poco, de manera incremental, el mapa
semántico.

En el caso de Voxeland Disambiguation, se ha realizado también un diagrama de secuen-
cia que describe de forma simplificada el flujo de trabajo implementado. En la Figura 13 se
detalla todo el proceso, comenzando por la obtención del archivo JSON que contiene toda la
información semántica del mapa, pasando por la identificación de instancias y la selección
de imágenes, la desambiguación mediante un LVLM y concluyendo con la reintegración con
Voxeland Server.

Figura 12:Diagrama de secuencia del proceso de construcción de un mapa semántico con
Voxeland. Se recomienda su visualización con un zoom del 200 %.


Figura 13:Diagrama de secuencia del proceso de desambiguación de un mapa semántico de
Voxeland. Se recomienda su visualización con un zoom del 200 %.

### 3.4. Pruebas del software

Las pruebas unitarias son una parte fundamental del desarrollo de software, ya que per-
miten verificar que cada componente individual de un programa funcione correctamente de
forma aislada. Su importancia radica en que facilitan la detección de errores, mejorando la
calidad del código y reduciendo el costo de tiempo que implica el mantenimiento a lo largo
del desarrollo del software. Si bien no garantizan que el sistema no contiene errores, propor-
cionan la garantía de saber que los flujos principales del sistema funcionan según lo esperado,
brindando confianza y tranquilidad al realizar modificaciones en el código.
Dado el diseño del sistema propuesto, el cual está basado en una secuencia de manejadores
que realizan las acciones del sistema, se han decidido hacer pruebas unitarias sobre dichos ma-


nejadores, especialmente aquellos que implementan lógica propensa a excepciones, y aquellas
clases auxiliares de las que dependen.
En total se ha implementado una batería de más de 40 pruebas unitarias, tanto de “caja ne-
gra”, para comprobar los resultados o salidas de los métodos, como de “caja blanca”, estudiando
la cobertura para contemplar todas las ramificaciones del código. Se trata de una buena canti-
dad de tests que validan que el flujo principal del sistema funciona según lo esperado. Además,
los tests han sido implementados siguiendo buenas prácticas, como por ejemplo, seguir una
nomenclatura consistente y apropiada a los tests, por ejemplo:

```
test_(nombre_método)_(caso)_(resultado_esperado)
```
Otra buena práctica aplicada es cumplir con el patrón AAA (Arrange, Act, Assert) para estruc-
turar correctamente cada test y que el flujo de los mismos sea entendible de un sólo vistazo.
Un test que ejemplifica lo anteriormente mencionado se muestra en el Listing 1.


1 #include <gtest/gtest.h>
2
3 TEST(JsonSemanticMapTest , test_add_instance_new_instance_updates_map)
{
4 //Arrange
5 JsonSemanticMap map;
6 auto instance = std:: make_shared <JsonSemanticObject >();
7 instance ->InstanceID = "test_id";
8
9 //Act
10 map.add_instance(instance);
11
12 //Assert
13 std:: shared_ptr <JsonSemanticObject > expected_instance = map.
get_instance("test_id");
14 EXPECT_NE(expected_instance , nullptr);
15 ASSERT_EQ(expected_instance ->InstanceID , "test_id");
16 }

```
Listing 1: Prueba unitaria que valida que el método de añadir una instancia semántica al mapa
funciona según lo esperado.
```

## 4. Descripción del método

El flujo de trabajo del método propuesto puede observarse en la Figura 14. El punto de par-
tida es la obtención de la información relacionada con la semántica proporcionada por Voxe-
land (ver columna derecha de la Figura 1 ). Esto incluye la información relativa a las instancias
de objetos detectadas (distribución de probabilidad sobre las categorías de objeto y número
total de observaciones), así como una lista por objeto de asociaciones categoría-imagen. Esta
lista asocia a cada categoría el conjunto de imágenes en las que el objeto aparece y ha sido
clasificado en dicha categoría (ver Sección4.1).
Gracias a la información de las distribuciones de probabilidad, es posible cuantificar la
incertidumbre semántica. Esto se realiza mediante el cálculo de la entropía y el establecimiento
de un umbral (ver Sección4.2). Una vez identificadas las instancias con mayor incertidumbre,
se realiza una selección de categorías e imágenes relevantes para cada una de ellas (Sección4.3).
Posteriormente, se procede con la desambiguación de las mismas instancias. Para ello, se
emplea un Modelo de Lenguaje y Visión a Gran Escala (LVLM) junto con las imágenes anterio-
res, de tal manera que sea capaz de especificar claramente cuál de las categorías previamente
seleccionadas es la correcta (ver Sección4.4). Finalmente, este resultado se integra de vuelta
en Voxeland en forma de nuevas “opiniones subjetivas”, aportando una mayor certidumbre al
mapa (ver Sección4.5).

### 4.1. Construcción del mapa semántico con Voxeland

El proceso de construcción del mapa semántico mediante Voxeland representa el punto de
partida del método propuesto en este trabajo. Consiste en generar, de manera incremental, una
representación detallada del entorno combinando información geométrica y semántica. Voxe-


Figura 14:Descripción visual del flujo de trabajo del proceso de desambiguación semántica
aplicado a la escena 61 de SceneNN. Cada uno de los recuadros del mapa semántico de Voxeland
se corresponden a un objeto de la escena. Por último, el texto resaltado en color amarillo
representa el nuevo parámetro de confianza de la categoría resultante por parte del LVLM.
Este incremento se calcula a partir de la confianza del LVLM en dicha categoría.


land toma como entrada una secuencia de imágenes RGB-D en la que muestra el escenario a
mapear, y las procesa mediante una red neuronal especializada en identificación, clasificación
y segmentación de objetos, en este caso Detectron2 (Wu et al., 2019 ). Este procedimiento pro-
duce inicialmente predicciones sobre las instancias presentes en cada imagen, indicando tanto
la categoría a la que pertenecen, un valor de confianza de dichas predicciones y el recuadro
aproximando en el que se encuentra el objeto.
Una vez obtenidas las predicciones semánticas, Voxeland las proyecta al espacio tridimen-
sional utilizando la información de profundidad, generando así opiniones subjetivas tanto a
nivel geométrico como semántico. Estas opiniones se acumulan a lo largo del tiempo utili-
zando un enfoque probabilístico basado en laTeoría de la Evidencia. Gracias a este método, es
posible cuantificar la incertidumbre:

```
Incertidumbre geométrica: se da cuando no se conoce a qué instancia del mapa per-
tenece un voxel. Surge cuando múltiples instancias incrementan su confianza posicional
en los mismos vóxeles, es decir, coinciden en algunos puntos del espacio.
Incertidumbre semántica: se produce cuando no se tiene la certeza de a qué categoría
semántica pertenece una instancia. Puede ser provocado debido a que un objeto ha sido
clasificado en un gran número de categorías o si presenta varias con un alto valor de
confianza.
```
Finalmente, una vez se ha analizado la escena completa y se ha integrado toda la informa-
ción, tanto geométrica como semántica, Voxeland permite exportar el mapa semántico resul-
tante en un formato JSON estructurado, constituyendo la información de entrada al flujo de
trabajo propuesto. Un ejemplo de un fragmento de mapa semántico representado en formato
JSON:

{
"obj0": {༞༞༞},
"obj15": {
"bbox": {༞༞༞},
"n_observations": 103,
"results": {
"bed": 38.433941751718521,
"couch": 50.72217634320259,
"chair": 12.25138512451,


༟༞༢
},
appearances: {
"bed": [123,125,245, ༟༞༢ ],
"couch": [301,302,315, ༟༞༢ ],
"chair": [87, 88, 96, ༟༞༢ ],
༟༞༢
}
},
༟༞༢
}

Cada entrada del objeto principal corresponde a una instancia detectada en el entorno (por
ejemplo,“obj15”), incluyendo información relevante para su análisis semántico. En particular,
se almacena el número total de observaciones recibidas (n_observations), una distribución de
resultados que asocia a cada categoría semántica su valor de confianza acumulado (results), y
una lista de identificadores de imagen en las que la instancia ha sido clasificada como perte-
neciente a dicha categoría (appearances).

### 4.2. Identificación de instancias con incertidumbre

Una vez generado el mapa semántico con Voxeland, el siguiente paso consiste en identi-
ficar aquellas instancias cuya clasificación semántica no es lo suficientemente clara, es decir,
que presentan un alto grado de incertidumbre. Para ello, se analiza los parámetros de concen-
tración sobre las categorías asignadas a cada objeto, dicha información viene dada por la lista
de“results”en el JSON anteriormente mostrado.
Concretamente, se emplea la entropía de Shannon como métrica para cuantificar esta in-
certidumbre, ya que refleja de manera intuitiva cómo de dispersas están las predicciones sobre
las posibles categorías. Cuanto más alta es la entropía, más incierta es la clasificación de la
instancia, pues indica que las opiniones sobre su categoría están divididas.
En el marco de Voxeland, esta entropía se calcula a partir del vector de parámetros de
concentraciónβk, correspondiente a la distribución de Dirichlet sobre las categorías para la
instanciak. La expresión empleada es la siguiente:

```
H(Ck) =ψ
```
##### (∑

```
l
```
```
βkl
```
##### )

##### −∑^1

```
lβkl
```
##### ∑

```
l
```
```
βklψ(βkl) (1)
```

dondeψ(·)es la función digamma, yβklrepresenta la evidencia acumulada a favor de la
categoríal.
Finalmente, para decidir qué instancias requieren un análisis más profundo, se establece un
umbral empírico de 0 , 7 nats. La unidadnatsse corresponde con una medida de información
utilizada principalmente en contextos que involucran logaritmos naturales. Aquellas instan-
cias cuya entropía supere este valor son consideradas altamente ambiguas y serán objeto del
posterior proceso de desambiguación mediante un LVLM.

### 4.3. Selección de categorías e imágenes

Dado que la secuencia de una escena esta formada por miles de imágenes, es necesario
hacer una selección, tanto de imágenes como de categorías, pues proporcionarle tanta infor-
mación al LVLM sería un proceso inviable e ineficiente. Concretamente, se escogen para cada
instancia una serie de imágenes de cada categoría seleccionada.
En cuanto a la selección de categorías, el objetivo es escoger, para cada instancia, aquellas
con un mayor parámetro de concentración, es decir, aquellas con un mayor valor de confianza
acumulado a lo largo del proceso de construcción del mapa, proporcionado por la lista de
“results”previamente especificada.
Cada instancia del mapa semántico almacena un listado de apariciones por categoría, es
decir, un conjunto de imágenes en las que esa instancia ha sido clasificada como perteneciente
a dicha categoría. Se corresponde a la lista de“appearances”mostrada en el JSON anterior. A
partir de esta base, se aplica un proceso de selección de imágenes de entre las miles que suele
presentar cada objeto, para ello, se proponen diversas estrategias, cada una con un enfoque,
tal y como se describe en las siguientes secciones.

#### 4.3.1. Selección basada en propiedades visuales.

El primer enfoque consiste en analizar las imágenes disponibles para cada categoría candi-
data y seleccionar aquellas que presenten las mejores condiciones visuales. Esto puede incluir,
por ejemplo:

```
Imágenes con buena iluminación.
Imágenes que presenten poco ruido.
```

Imágenes donde el objeto no está parcialmente oculto por otros elementos.
Esta estrategia tiene la ventaja de ofrecer al LVLM imágenes nítidas y claras, maximizando
las posibilidades de una clasificación correcta. No obstante, su principal inconveniente radica
en la dificultad para implementar este sistema y el gran coste computacional que conlleva.
Este enfoque requiere un análisis individualizado de un elevado número de imágenes por cada
instancia, resultando ser computacionalmente intratable.

#### 4.3.2. Selección basada en diversidad temporal

Una alternativa más eficiente y viable es seleccionar imágenes en función de la diversidad
temporal. Este método asegura la obtención de distintos puntos de vista del objeto, mejorando
el contexto visual disponible para el modelo. Esta alternativa destaca por eliminar la necesidad
de analizar el contenido de cada imagen, simplificando el proceso. Dentro de esta categoría se
contemplan varias opciones de clasificación:

```
Selección aleatoria: escoger un número fijo de imágenes al azar dentro del conjunto de
apariciones de cada categoría. Aunque muy sencillo y rápido, no garantiza la diversidad
visual ni la calidad óptima.
Selección por tramos temporales: se divide el conjunto completo de apariciones en
intervalos temporales, seleccionando la imagen asociada a los límites de cada tramo.
Esta técnica proporciona diversidad visual y distintos ángulos de observación del objeto,
permitiendo al LVLM captar mejor su estructura tridimensional.
Selección por área de la caja contenedora (del inglésbounding box): permite apro-
vechar la información del tamaño del área ocupada por el objeto en cada imagen. Se
priorizan aquellas imágenes donde el objeto aparece con mayor tamaño, incrementando
la probabilidad de que el objeto sea claramente visible y centrado. Sin embargo, al se-
leccionar pocas imágenes de entre un conjunto de gran tamaño, es altamente probable
que se obtengan puntos de vista casi idénticos del objeto.
Seleccióncombinada(recomendada): combina la división temporal con el criterio del
área delbounding box. Se dividen las imágenes en subconjuntos de tamaño fijo y, dentro
de cada subconjunto, se escoge aquella con elbounding boxmás grande. Esta estrategia
```

```
asegura tanto la diversidad como la calidad visual óptima del objeto. En definitiva, se
obtienen los beneficios de ambos clasificadores.
```
Todos estos enfoques brillan por su sencillez, tanto a nivel computacional como en diseño
e implementación. Por lo tanto, se han convertido en el método preferido para la selección de
imágenes.

### 4.4. Desambiguación mediante LVLM

Una vez seleccionadas las categorías más probables e imágenes representativas para cada
instancia identificada como ambigua, se lleva a cabo la fase de desambiguación propiamente
dicha. Este proceso se basa en el uso de Modelos de Visión y Lenguaje a Gran Escala (LVLM),
modelos avanzados capaces de analizar imágenes y comprender instrucciones en lenguaje na-
tural para clasificar objetos con precisión.
La interacción con el LVLM se realiza mediante un mensaje estructurado, conocido como
prompt, que contiene la información necesaria para la clasificación del objeto. Esteprompt
debe ser claro, breve y conciso para evitar confusiones y sobrecargas de información, algo
esencial para que el modelo produzca resultados precisos. Concretamente, elpromptsigue
una estructura que incluye tres componentes clave:Contexto,ObjetivoyRestricciones. El con-
texto proporciona información sobre las imágenes, el objetivo define claramente la tarea que
el modelo debe realizar, y las restricciones especifican cómo debe formularse la respuesta.
Un ejemplo concreto del formato delpromptutilizado es el siguiente:
Prompt proporcionado al LVLM.
You are an expert object classifier. I will provide you with several images that contain an
object seen from different perspectives. The object belongs to one of the following categories:
[bed, chair, couch]
Your task is to analyze the object and its surrounding environment across all images to
determine the correct category.
Your response must include only one of the previously specified categories and follow this
exact format:“The category is <category>”


Es importante destacar que el diseño y estructura delpromptjuegan un papel fundamen-
tal en la calidad de las respuestas del modelo. A menudo, errores o falta de claridad en esta
etapa pueden llevar a resultados incorrectos o ambiguos. Por lo tanto, elpromptha sido cui-
dadosamente refinado, siguiendo las mejores prácticas y recomendaciones actuales para la
estructuración de mensajes dirigidos a modelos generativos (Moncada-Ramirez et al., 2025 ).
Siguiendo el enfoque de la Teoría de la Evidencia empleado en Voxeland, dado que el “co-
nocimiento” se obtiene a partir de “experiencias”, este proceso de desambiguación mediante
un LVLM no se aplica solamente una vez por instancia, sino que se repite en varias ocasiones,
acumulando los distintos resultados a lo largo de las iteraciones. Este enfoque iterativo per-
mite acumular evidencia, reduciendo progresivamente la incertidumbre sobre la categoría del
objeto, y asegurando así una mayor precisión y fiabilidad en la clasificación final.

### 4.5. Integración en Voxeland

Una vez que el LVLM ha proporcionado respuestas sobre las categorías más probables para
cada objeto ambiguo, es fundamental que esta información se incorpore correctamente en el
sistema de Voxeland para actualizar y refinar el mapa semántico construido inicialmente. Este
proceso asegura que el robot cuente con una representación del entorno más precisa y fiable.
La información obtenida del LVLM se interpreta como nuevas “opiniones subjetivas”. Estas
opiniones son pesadas acordemente considerando 3 factores, 2 de ellos dependientes de la
función sigmoide. Siendoxla variable de interés,μel punto medio de la sigmoide yβel
parámetro que controla la pendiente, la función sigmoide se define de la siguiente manera:

```
sigm(x;μ, β) =1 +exp(−^1 β(x−μ)) (2)
```
Además, seaC el conjunto de categorías del objeto,Niterel número de iteraciones del
proceso de desambiguación,rcel conteo devuelto por el LVLM para la categoríac, yRcel
parámetro de concentración de la categoríac; entonces, los factores de peso que determinan
el incremento se definen de la siguiente manera:

```
Factor dependiente del número de categorías existentes en la distribución
Scat=sigm(|C|; 5, 0 ,6) (3)
```

```
Factor dependiente del total de observaciones del objeto
```
```
Sobs=sigm(Nobs; 75, 0 ,08) (4)
```
```
Factor de confianza en la respuesta del LVLM
```
```
Sconf,c=Nriterc (5)
```
Todos los valores que configuran la sigmoide han sido establecidos empíricamente. Consi-
derando que la entropía está fuertemente determinada por estos factores, es crucial actualizar
los parámetros de confianza de cada categoría en función del factor total resultanteFc. De esta
forma, podemos calcularlo sumando todos los factores previos (ver Ecuación 6 ) y, finalmente,
actualizar el valor de cada categoría (ver Ecuación 7 ):

```
Fc=Scat+Sobs+Sconf,c 0 ≤Fc≤ 3 (6)
```
Rc←Rc+Fc·rc (7)
Además, el enfoque iterativo que se aplica en la desambiguación semántica, no solo con-
tribuye a incrementar la certeza sobre la categoría más adecuada, sino que también permite
obtener información adicional y valiosa acerca del estado de la clasificación del objeto. Con-
cretamente, el análisis de las respuestas del modelo puede revelar las siguientes situaciones:

1. Si el modelo responde consistentemente con una frecuencia cercana al 100 %, esto indica
    que existe una alta confianza en la categoría determinada.
2. Si el modelo no muestra una clara preferencia por ninguna categoría específica, esto
    puede indicar diferentes escenarios:
       a)El objeto puede no pertenecer a ninguna de las categorías contempladas origi-
          nalmente, es decir, podría ser un objeto fuera del conjunto de entrenamiento del
          modelo.
       b)La ambigüedad entre las categorías contempladas es significativa, por lo que el
          objeto podría clasificarse en más de una categoría.


```
c) Existe incertidumbre geométrica que provoca la fusión de varios objetos distintos
en una sola instancia. Por ejemplo, un ordenador colocado sobre una mesa podría
ser detectado como un único objeto fusionado.
```
Finalmente, tras realizar estas actualizaciones, toda la información semántica actualizada
se serializa en formato JSON, manteniendo la misma estructura original utilizada por Voxeland.
Este formato facilita que Voxeland identifique las instancias actualizadas y aplique los cambios
a la información semántica del entorno.


## 5. Validación

Para validar la propuesta presentada en este trabajo, se han realizado una serie de pruebas
con escenas del popular conjunto de datos SceneNN (Hua et al., 2016 ). En esta sección se
discuten los resultados obtenidos en una de ellas, comparando el rendimiento de los distintos
LVLMs y clasificadores de imágenes. En concreto, se trata de la escena 206 (véase la Figura
15 ), una escena categorizada como “Study space” la cual muestra una habitación amplia llena
de sillas y mesas para estudiar y un pequeño sofá en una esquina para descansar.

Figura 15:Representación de la nube de puntos de la escena 206 del conjunto de datos de
SceneNN.

Antes de comenzar con el método propuesto, se debe proceder con la construcción y ex-
portación del mapa semántico mediante Voxeland, el cual serializa la información del mapa


en formato JSON:

{
"obj1": {༞༞༞},
"obj159": {
"bbox": {༞༞༞},
"n_observations": 149,
"results": {
"cell phone": 0.5676894187927246,
"chair": 50.86360323429108,
"dining table": 52.24861344695091,
"suitcase": 20.8092296719551086
},
"appearances": {
"cell phone": [156,157༩༞༢,3405,3406],
"chair": [120,122༩༞༞༢,2453,2455],
"dining table": [124,130༩༞༞༢,2512,2516],
"suitcase": [230,235༩༞༞༢,2419,2420]
}
},
༟༞༢
}

Una vez obtenido el archivo JSON, el nodo encargado de la desambiguación semántica
analiza la información de las instancias de objetos para identificar aquellas con un mayor
grado de incertidumbre. Para ello se calcula la entropía de la lista de “results” de cada objeto
(Sección4.2).
Aplicando este proceso al ejemplo anterior, se determina que el “obj159” (véase el JSON
anterior) se corresponde con uno de los objetos con una alta entropía, concretamente con un
valor de 1 , 0668 nats. Si analizamos su lista de “results”, la cual representa los parámetros de
concentración para cada categoría en la que ha sido clasificado dicho objeto, vemos que, a
pesar de poseer un número reducido de categorías, la confianza correspondiente a varias de
ellas son similares entre sí, justificando así la incertidumbre en la identificación.
A continuación, se seleccionan las imágenes a partir de la lista de “appearances” de las 3
categorías con mayor concentración. En este caso,dining table,chairysuitcaseson las más
probables de representar la categoría correcta del objeto. Siguiendo el procedimiento expuesto
en la Sección4.3, se seleccionan, para cada una de las 3 categorías, varias imágenes espaciadas
en el tiempo, con el fin de obtener distintos puntos de vista del objeto. Si bien se obtiene
la imagen completa, sólo almacenaremos el recuadro aproximado en el que se encuentra el


objeto, pues no es conveniente sobrecargar al LVLM con información que no es relevante.
Con las imágenes del objeto y elpromptque incluye las categorías y las instrucciones,
podemos hacer uso del nodo LVLM para que decida, finalmente, cuál es la categoría correcta
del objeto (véase en la sección4.4). Las respuestas generadas por el LVLM son de la siguiente
forma:

The category is dining table.

La respuesta del LVLM se considera válida, pues cumple con las instrucciones que hemos
indicado (la respuesta debe incluir sólo una de las 3 categorías que hemos mencionado) y
el formato es el esperado (The category is ...). Además de ser válida, es correcta, pues según
el valor de referencia (del inglés,ground truth) la categoría es “dining table”. Con el fin de
obtener una respuesta lo más definitiva posible, se aplica este proceso de decisión a lo largo
de 100 iteraciones, empleando el mismo prompt y las mismas imágenes. Por último, por cada
resultado válido devuelto por el nodo LVLM, se actualiza el parámetro de concentración de la
categoría devuelta (en este último caso “dining table”), incrementando su valor (sección4.5).

```
Objeto Categorías Random Split Bbox CombinadoMiniCPM Random Split Bbox CombinadoQwen
couch 63 66 81 100 100 100 100 100
1 dining table 37 33 19 0 0 0 0 0
backpack 0 0 0 0 0 0 0 0
chair 0 0 0 0 0 0 0 0
159 dining table 100 100 100 100 100 100 100 100
suitcase 0 0 0 0 0 0 0 0
chair 100 100 100 100 100 100 100 100
49 suitcase 0 0 0 0 0 0 0 0
handbag 0 0 0 0 0 0 0 0
chair 100 100 100 100 100 100 100 100
78 dining table 0 0 0 0 0 0 0 0
mouse 0 0 0 0 0 0 0 0
```
Cuadro 1:Comparativa de los resultados de desambiguación aplicando todas las combinacio-
nes de clasificadores de imágenes y LVLMs implementados. Pruebas realizadas sobre el mapa
semántico de Voxeland de la escena 206 del conjunto de datos SceneNN. Las categorías desta-
cadas se corresponden a la correcta según elground-truth.


Este procedimiento que se ha aplicado sobre el “obj159” se ha repetido para todos aquellos
objetos de la escena que también presenten un alto grado de incertidumbre. Concretamente,
en el Cuadro 1 se pueden ver las ocurrencias de cada categoría en las respuestas del LVLM a
lo largo de 100 iteraciones, comparando el funcionamiento de cada clasificador de imágenes y
los 2 modelos utilizados. En dicha tabla se puede ver que los resultados son generalmente muy
positivos, siendo el clasificador combinado el que mejor resultados proporciona. En cuanto a
los LVLM, se puede ver que la confianza que brinda el modelo de Qwen es superior a MiniCPM,
ya que es un modelo más grande y, por supuesto, computacionalmente costoso. No obstante,
los resultados del modelo MiniCPM junto con el clasificador combinados son similares a los
de Qwen.

```
Objeto Entropía inicial Ground-truth Predicción inicial Resultado Confianza Entropía resultante
1 1.9716 mixto couch couch 100 1.6673
159 1.0668 dining table dining table dining table 100 0.6374
49 0.9227 chair chair chair 100 0.2209
78 1.3572 chair chair chair 100 0.1839
```
Cuadro 2:Resultados de desambiguación de las instancias ambiguas identificadas en un ma-
pa semántico de Voxeland sobre la escena 206 del conjunto de datos SceneNN, utilizando el
clasificador combinado y el modelo Qwen.Ground-truthhace referencia a la categoría real de
cada objeto.Predicción inicialse refiere a la categoría con mayor confianza previo a desambi-
guación.ResultadoyConfianzahacen referencia al resultado mayoritario en las respuestas del
LVLM y el porcentaje de ocurrencias, respectivamente.

Si analizamos la corrección en las clasificaciones por parte de los modelos (ver Cuadro 2 )
se puede observar que, de nuevo, son correctas y además con una alta confianza. No obstante,
como se puede ver en el “obj1”, el resultado obtenido no se corresponde con la verdad de
referencia, siendo ésta “mixto”. Esto se debe a que el “obj1” no es realmente un objeto, sino 2
objetos (“couch” y “dining table”) que se han fusionado a causa de la incertidumbre geométrica
del mapa. Dicho objeto se corresponde con aquel representado en la esquina superior derecha
de los mapas de incertidumbre semántica mostrados en la Figura 16.
Se trata de un caso previsto en el diseño del flujo de trabajo (véase la Sección4.5), en el que
la incertidumbre geométrica es tan elevada que su entropía inicial alcanza un valor cercano a


Figura 16:Mapas de incertidumbre semántica realizados sobre la escena 206 del conjunto de
datos SceneNN representado mediante mapas de calor. De izquierda a derecha, el antes y el
después de aplicar el proceso de desambiguación semántica

2, lo que impide su desambiguación semántica.
Por último, la reducción de entropía en las instancias ambiguas es realmente significativa,
en torno al45%. Esto provoca que, si cuantificamos de nuevo la incertidumbre semántica del
mapa después de aplicar el proceso de desambiguación, ésta se reduzca notablemente (recuér-
dese la Figura 16 ). Aquellos objetos que no presentaban incertidumbre se mantienen intactos,
mientras que aquellos más dudosos se desambiguan, resultando en un mapa semántico más
confiable para la operativa del robot.



## 6. Conclusiones y Líneas Futuras

### 6.1. Conclusiones.

En este trabajo se ha propuesto un método para el refinamiento de mapas semánticos cons-
truidos por robots móviles, con el objetivo de incrementar la certidumbre sobre las categorías
semánticas asociadas a los objetos detectados. Este método complementa al marco de trabajo
probabilístico Voxeland, aprovechando su capacidad para representar la incertidumbre semán-
tica como distribuciones de probabilidad sobre las posibles categorías de cada instancia.

El sistema desarrollado se basa en la identificación sistemática de aquellas instancias del
mapa que presentan una elevada entropía en su distribución categórica, y que, por tanto, re-
quieren una desambiguación adicional. Para ello, se han empleado Modelos de Lenguaje y
Visión a Gran Escala (LVLMs), los cuales proporcionan opiniones más precisas a partir de
múltiples vistas del objeto.

La validación del método se ha llevado a cabo sobre escenas del conjunto de datos SceneNN,
ampliamente utilizado en este ámbito, mostrando una mejora significativa en la certidumbre
de las categorías finales. El enfoque propuesto demuestra además una alta generalización,
ya que puede ser aplicado a cualquier mapa semántico que proporcione información en un
formato compatible con Voxeland, independientemente del origen de las escenas (datos reales
o simulados).

Asimismo, se ha comprobado que el sistema es compatible con una amplia variedad de
LVLMs modernos, incluyendo modelos abiertos comoQwenyMiniCPM, lo cual refuerza su
versatilidad.

```
El sistema resultante, totalmente funcional y encapsulado como nodo ROS 2, aporta una
```

solución robusta y flexible al problema de la ambigüedad semántica en mapas probabilísti-
cos, permitiendo una mejora sustancial en la representación del entorno que maneja el robot
durante su operativa.

### 6.2. Líneas Futuras

Voxeland es un marco de trabajo que, si bien demuestra buenos resultados generalizados,
presenta aún retos por resolver, especialmente aquellos relacionados con el tratamiento de
la incertidumbre geométrica que tanto afecta a la robustez de los mapas semánticos. Por lo
tanto, de manera análoga a este trabajo, se propone el desarrollo de métodos de reducción de
la incertidumbre geométrica.
No obstante, dada la mejora de los mapas semánticos presentada en este trabajo, en el
futuro, se estudia la posibilidad de aprovechar la semántica proporcionada por los mapas para
que el robot móvil sea capaz de razonar sobre ellos e inferir la información necesaria para
completar sus tareas de manera efectiva.


Referencias

Ambrosio, G., Matez-Bandera, J.L., Ruiz-Sarmiento, J., González-Jiménez, J., 2024. Entorno
basado en contenedores linux para el desarrollo de aplicaciones robóticas. Jornadas de Au-
tomática doi:10.17979/ja-cea.2024.45.10943.

Bac, C.W., van Henten, E.J., Hemming, J., Edan, Y., 2014. Harvesting robots
for high-value crops: State-of-the-art review and challenges ahead. Jour-
nal of Field Robotics 31, 888–911. URL: https://onlinelibrary.wiley.
com/doi/abs/10.1002/rob.21525, doi:https://doi.org/10.1002/rob.21525,
arXiv:https://onlinelibrary.wiley.com/doi/pdf/10.1002/rob.21525.

Bai, S., Chen, K., Liu, X., Wang, J., Ge, W., Song, S., Dang, K., Wang, P., Wang, S., Tang, J.,
Zhong, H., Zhu, Y., Yang, M., Li, Z., Wan, J., Wang, P., Ding, W., Fu, Z., Xu, Y., Ye, J., Zhang,
X., Xie, T., Cheng, Z., Zhang, H., Yang, Z., Xu, H., Lin, J., 2025. Qwen2.5-vl technical report.
arXiv preprint arXiv:2502.13923.

Chaves, D., Ruiz-Sarmiento, J.R., Petkov, N., Gonzalez-Jimenez, J., 2019. Integration of cnn
into a robotic architecture to build semantic maps of indoor environments, in: Advances in
Computational Intelligence: 15th International Work-Conference on Artificial Neural Net-
works, IWANN 2019, Gran Canaria, Spain, June 12-14, 2019, Proceedings, Part II 15, Springer.
pp. 313–324.

Gu, Q., Kuwajerwala, A., Morin, S., Jatavallabhula, K.M., Sen, B., Agarwal, A., Rivera, C., Paul,
W., Ellis, K., Chellappa, R., Gan, C., de Melo, C.M., Tenenbaum, J.B., Torralba, A., Shkurti,
F., Paull, L., 2023. Conceptgraphs: Open-vocabulary 3d scene graphs for perception and
planning. URL:https://arxiv.org/abs/2309.16650,arXiv:2309.16650.

Han, X., Li, S., Wang, X., Zhou, W., 2021. Semantic mapping for mobile robots in indoor
scenes: A survey. Information 12. URL:https://www.mdpi.com/2078-2489/12/2/92,
doi:10.3390/info12020092.

He, K., Gkioxari, G., Dollár, P., Girshick, R., 2017. Mask r-cnn, in: Proceedings of the IEEE
international conference on computer vision, pp. 2961–2969.


Hua, B.S., Pham, Q.H., Nguyen, D.T., Tran, M.K., Yu, L.F., Yeung, S.K., 2016. Scenenn: A sce-
ne meshes dataset with annotations, in: 2016 fourth international conference on 3D vision
(3DV), Ieee. pp. 92–101.

Jsang, A., 2018. Subjective Logic: A formalism for reasoning under uncertainty. Springer
Publishing Company, Incorporated.

Kostavelis, I., Gasteratos, A., 2015. Semantic mapping for mobile robotics tasks: A survey.
Robotics and Autonomous Systems 66, 86–103.

Matez-Bandera, J.L., Fernandez-Chaves, D., Ruiz-Sarmiento, J.R., Monroy, J., Petkov, N.,
Gonzalez-Jimenez, J., 2022. Ltc-mapping, enhancing long-term consistency of object-
oriented semantic maps in robotics. Sensors 22, 5308.

Matez-Bandera, J.L., Ojeda, P., Monroy, J., Gonzalez-Jimenez, J., Ruiz-Sarmiento, J.R., 2024.
Voxeland: Probabilistic instance-aware semantic mapping with evidence-based uncertainty
quantification. URL:https://arxiv.org/abs/2411.08727,arXiv:2411.08727.

Moncada-Ramirez, J., Matez-Bandera, J.L., Gonzalez-Jimenez, J., Ruiz-Sarmiento, J.R., 2025.
Agentic workflows for improving large language model reasoning in robotic object-centered
planning. Robotics 14, 24.

Quigley, M., Conley, K., Gerkey, B., Faust, J., Foote, T., Leibs, J., Wheeler, R., Ng, A.Y., et al., 2009.
Ros: an open-source robot operating system, in: ICRA workshop on open source software,
Kobe. p. 5.

Redmon, J., Divvala, S., Girshick, R., Farhadi, A., 2016. You only look once: Unified, real-time
object detection, in: Proceedings of the IEEE conference on computer vision and pattern
recognition, pp. 779–788.

Ruiz-Sarmiento, J.R., Galindo, C., Gonzalez-Jimenez, J., 2017. Building multiversal semantic
maps for mobile robot operation. Knowledge-Based Systems 119, 257–272.

Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A.N., Kaiser, Ł., Polosukhin,
I., 2017. Attention is all you need. Advances in neural information processing systems 30.


Wang, A., Chen, H., Liu, L., Chen, K., Lin, Z., Han, J., Ding, G., 2024. Yolov10: Real‑time
end‑to‑end object detection. arXiv preprint arXiv:2405.14458 NMS‑free, estado‑del‑arte en
eficiencia y precisión.

Wu, Y., Kirillov, A., Massa, F., Lo, W.Y., Girshick, R., 2019. Detectron2.https://github.com/
facebookresearch/detectron2.

Yao, Y., Yu, T., Zhang, A., Wang, C., Cui, J., Zhu, H., Cai, T., Li, H., Zhao, W., He, Z., et al., 2024.
Minicpm-v: A gpt-4v level mllm on your phone. arXiv preprint arXiv:2408.01800.

