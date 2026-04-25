## Contexto

En el baseline del proyecto definimos explicitamente el uso de servidores MCP para la gestion del filesystem, shell y websearch.
No obstante, nuestro objetivo actual era conseguir ejecutar una primera ejecucion de autofix sobre una rama del repositorio de quixbugs. Aspecto que no hemos conseguido dado el 
estado tan fragil en el que se encuentra el proyecto actualmente.

Vamos a comenzar refactorizando y simplificando todas las partes del proyecto que suponen problemas y que en general, estan siendo over-engineered.
Tenemos que priorizar tener un MVP funcional con una arquitectura mono-agente, pero que posteriormente nos permita extender facilmente a una arquitecura multiagente (handoff y orquestrator)

Para tener una comprension sobre el openai-agents-sdk y su funcionamiento, he creado varias carpetas:
- openai-examples: modulo oficial de ejemplos de codigo de distintos casos de uso usando openai-agents-sdk
- demo: carpeta de prueba en el que he incluido: 
* toolkit suficiente para el APR, 
* ejemplo de prueba de dockerfile y archivo de test creando un contenedor y accediendo a ollama en la maquina local.
* notebook demo de los 3 enfoques objetivo a implementar: monoagente, multiagente handoff y multiagente coordinator.

## Objetivo

Un error que hemos cometido ha sido el uso de MCPs que estaban complicando el despliegue en el contedor docker. Por lo que vamos a hacer lo siguiente:

- Eliminar el websearch de la spec y del proyecto en general. Para el APR por ahora no vamos a usar WebSearch simplemente filsystem y comandos. Elimina todo lo asociado a ello
- Reemplazar el uso de los mcps servers por tools. Analiza el apr_toolkit de la carpeta de demmo, comprendelas bien y cómo usarlas -> Crea un módulo de tools en el directorio de nuestro proyecto -> copialas, pegalas y haz las adaptaciones que hagan falta en el proyecto. Ten en cuenta que es un modulo que se ha creado de cero para adaptarse a este proyecto
- Añade los tests del modulo de apr a nuestro proyecto, prueba que funcionen bien y haz las correcciones pertinentes.

## Restricciones

- No asumas aspectos del framework de openai-agents-sdk sin investigar. Ten en cuenta siempre la ultima version (0.14+). tambien puedes buscar referencias en la carpeta de openai-examples
