# **Requisitos del sistema de autocorrección de errores basado en LLMs**

## **1. Introducción**

El presente documento define los requisitos funcionales y no funcionales de un sistema orientado a la **autocorrección de errores en software** mediante el uso de modelos de lenguaje de gran tamaño (LLMs) y arquitecturas basadas en agentes.

El objetivo del sistema no es únicamente proporcionar una solución funcional, sino también servir como **plataforma experimental** que permita analizar el impacto de distintas decisiones de diseño, especialmente en lo relativo a la orquestación de agentes y el uso de diferentes modelos.

---

## **2. Objetivo del sistema**

El sistema debe ser capaz de recibir como entrada un error en un proyecto software (por ejemplo, un fallo de test o un reporte de bug) y ejecutar un proceso automatizado que incluya, al menos, las siguientes etapas:

1. Comprensión del error.
2. Localización de las partes relevantes del código.
3. Propuesta de una posible solución.
4. Aplicación de cambios sobre el código fuente.
5. Verificación mediante ejecución de tests.

Adicionalmente, el sistema podrá incluir funcionalidades como la creación de ramas o la preparación de cambios integrables en el repositorio.

---

## **3. Requisitos funcionales**

### **3.1. Procesamiento de errores**

El sistema deberá:

* Aceptar como entrada distintos tipos de errores (logs, stack traces, tests fallidos).
* Analizar el contexto del error para extraer información relevante.
* Generar una representación interna del problema a resolver.

---

### **3.2. Interacción con el repositorio**

El sistema deberá:

* Acceder a un repositorio de código fuente de forma aislada.
* Leer, modificar y escribir archivos.
* Gestionar cambios mediante operaciones básicas de control de versiones.

---

### **3.3. Ejecución de código y tests**

El sistema deberá:

* Ejecutar comandos en un entorno controlado.
* Lanzar suites de tests asociadas al repositorio.
* Capturar y procesar los resultados de ejecución.

---

### **3.4. Generación y aplicación de soluciones**

El sistema deberá:

* Proponer modificaciones sobre el código basadas en el análisis previo.
* Aplicar dichas modificaciones de forma incremental.
* Permitir múltiples intentos de corrección [POR DEFINIR: número máximo de iteraciones].

---

### **3.5. Arquitecturas de agentes**

El sistema deberá soportar, al menos, las siguientes configuraciones:

* **Arquitectura mono-agente**: un único agente responsable de todo el proceso.
* **Arquitectura multi-agente secuencial**: varios agentes especializados que se transfieren el control (handoff).
* **Arquitectura multi-agente con coordinador**: un agente principal que delega tareas en otros agentes.

Estas configuraciones deberán poder ejecutarse sobre la misma base experimental para permitir su comparación.

---

### **3.6. Uso de modelos de lenguaje**

El sistema deberá:

* Permitir el uso de distintos LLMs.
* Ser compatible tanto con modelos propietarios como con modelos ejecutados en local.
* Facilitar la sustitución del modelo sin modificar la lógica principal del sistema.

---

### **3.7. Ejecución en entorno aislado mediante Docker**

El sistema deberá:

* Ejecutar cada proceso de autocorrección dentro de un contenedor gestionado mediante Docker.
* Desplegar dinámicamente entornos de ejecución que incluyan el repositorio objetivo y sus dependencias.
* Permitir la ejecución de comandos, tests y modificaciones de código dentro de dicho entorno.

El uso de Docker deberá garantizar que:

* El sistema pueda interactuar libremente con el sistema de archivos del repositorio.
* Se puedan ejecutar herramientas de desarrollo (compiladores, intérpretes, gestores de dependencias, etc.).
* El entorno sea independiente del sistema anfitrión.

---

## **4. Requisitos no funcionales**

### **4.1. Reproducibilidad**

El sistema deberá:

* Ejecutarse en entornos controlados y consistentes mediante Docker.
* Garantizar que los experimentos puedan repetirse bajo las mismas condiciones.
* Permitir la reconstrucción del entorno de ejecución a partir de configuraciones definidas (por ejemplo, mediante imágenes de Docker).

---

### **4.2. Observabilidad y métricas**

El sistema deberá recoger, como mínimo, las siguientes métricas:

* Número de iteraciones necesarias para la corrección.
* Uso de tokens por parte de los LLMs.
* Tiempo de ejecución.
* Número y tipo de herramientas utilizadas.
* Resultado final (éxito o fallo de la corrección).

Estas métricas serán utilizadas para la evaluación experimental.

---

### **4.3. Configurabilidad**

El sistema deberá permitir la configuración de:

* Prompts del sistema y comportamiento de los agentes.
* Conjunto de herramientas disponibles.
* Parámetros de ejecución (límites de iteración, tiempo, etc.).
* Selección de modelos.
* Configuración del entorno de ejecución (dependencias, comandos, imágenes de Docker, etc.).

---

### **4.4. Extensibilidad**

El sistema deberá diseñarse de forma modular, permitiendo:

* Añadir nuevas herramientas.
* Incorporar nuevas arquitecturas de agentes.
* Integrar nuevos conjuntos de datos o repositorios.
* Adaptar el sistema a distintos lenguajes y entornos de ejecución.

---

### **4.5. Seguridad y aislamiento**

El sistema deberá:

* Ejecutar todas las acciones sobre el código en entornos aislados mediante Docker.
* Evitar efectos colaterales sobre el sistema anfitrión.
* Limitar el acceso a recursos externos cuando sea necesario.

---

## **5. Requisitos experimentales**

Dado el carácter investigador del proyecto, el sistema deberá:

* Permitir la ejecución de experimentos comparativos entre distintas arquitecturas de agentes.
* Facilitar la evaluación de diferentes modelos de lenguaje.
* Soportar el uso de datasets de referencia [POR DEFINIR: Defects4J, QuixBugs u otros].
* Garantizar la trazabilidad entre configuraciones y resultados.

---

## **6. Consideraciones abiertas**

Existen aspectos que deberán definirse en fases posteriores del proyecto:

* [POR DEFINIR] Estrategia concreta de evaluación y métricas derivadas.
* [POR DEFINIR] Selección definitiva de datasets.
* [POR DEFINIR] Nivel de generalización a repositorios arbitrarios.
* [POR DEFINIR] Número máximo de iteraciones por intento de corrección.

---

## **7. Conclusión**

Este conjunto de requisitos define un sistema orientado tanto a la **reparación automática de software** como a la **evaluación experimental de arquitecturas basadas en agentes y LLMs**.

El uso de Docker como tecnología de contenedorización resulta clave para garantizar la reproducibilidad, seguridad y validez de los experimentos, permitiendo ejecutar procesos de autocorrección de forma controlada y comparable.
