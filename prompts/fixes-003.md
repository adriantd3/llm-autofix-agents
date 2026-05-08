# Cuestiones a arreglar o mejorar

## Tests

Los tests presentan varios problemas que me gustaría solventar:

- Hay claramente 2 estructuras: 
    una lista de tests sin organizacion ninguna entre archivos, estan todos ahi.
    estructura de carpetas que replica la organizacion del source. Aquí se ve una clara intencion de establecer una convencion de tests, pero no se mantiene. La forma correcta sería esta, pues es el estandar.
- Los tests utilizan la libreria builtin the python para tests: unittest. Me gustaría actualizar a pytest y asi poder hacer uso de los decoradores y mecanismos
propios como los fixtures, los conftests, pruebas parametrizadas, etc.
- Todos los archivos principales deberian tener tests
- Los tests deberian cumplir con buenas convenciones como utilizar conftest para fixtures comunes, tests parametrizados para evitar redundancias, estructura AAA y nomenclatura acorde con test_<funcion>_<caso>_<return>.

## Configuracion del modelo

- Hay una inconsistencia con los max_turns de los modelos. Este parametro depende en gran medida de la arquitectura a ejecutar, por lo tanto, debe ir indicado en el yaml del batch concreto, tal y como esta ahora. No obstante, tambien viene definida una variable de entorno de LLM_MAX_TURNS, lo cual no deberia existir, puesto que viene definido en el yaml.
* El modelo de `LLMSettings` presenta varios problemas:
    * Actualmente esta acoplado a la URL de ollama, pues tiene un atributo concreto de ello. Entiendo que es debido a que hay que especificar la URL. No obstante, debido a que la URL de los providers es algo estatico, en vez de tener que pasarlo como variable de entorno o configuración, se puede definir un map de provider -> client url. De esta forma, podemos crear un strategy por provider para devolver el cliente concreto en cada caso. Por lo tanto, la variable de entorno de URL de los clientes no es necesaria.
    * El aplicar strategies simples por cliente es algo que quiero que se tenga en cuenta en el from_env porque actualmente hay acoplamiento de ollama y muchos if (provider), lo cual rompe con el principio de (OCP - Open Closed principle).
    * A lo largo del repositorio hay mucha normalizacion y validacion de inputs. Podemos delegar eso en el propio pydantic y asi quitar mucho ruido relacionado con eso. Por ejemplo, creo que los parse_X son quizas innecesarios.


## Ejecucion
Ya que hemos migrado toda la ejecucion a batch config, toda el flujo, logica, variables de entorno, configuracion, relacionado con la propia ejecucion tradicional de un run concreto debe eliminarse.
Por ejemplo, en main.py el _run_run y los metodos/declaraciones auxiliares que sólo se utilicen ahi podrian eliminarse.
Es decir, debe hacerse una exploracion de todo el flujo para analizar que es necesario y qué no.

Tambien convendría analizar qué se podria mejorar para eliminar o mejorar aquellas adaptaciones que tuvieran que hacerse para "permitir" el batch, pues antes era todo con variables de entorno y ejecucion única.

En definitiva, hacer el flujo entendible


## Memoria entre iteraciones

Actualmente el prompt input del modelo en la primera iteración es una descripcion a alto nivel de lo que debe hacer y una traza del error de los tests (ligeramente comprimida).

Esto para la primera iteracion esta bien, pero actualmente la informacion que recibe el agente en futuras iteraciones es insuficiente.
Sólo recibe el summary de la iteracion (si es que el agente llega a rellenar la nota, puesto que si sale por max turns esto no se incluye) y una descrpcion generica pidiendo que continue. Ejemplo:

```
Previous attempt summary:
status: done
reasoning_summary: Agent exceeded maximum turns; assuming completion based on tool usage
confidence: 0.500
changed_files: (unspecified)

Continue improving the repair strategy and validate with available tools.
Initial failing test context: exit_code=1, timed_out=False, signature=05a68538b0dae10d.
```

Esto es insuficiente, puesto que el agente, parte de un contexto limpio y no sabe que ha hecho hasta ahora, gastando turns en llamadas a tools para comprender qué es lo que ha hecho en la iteracion anterior. Esto provoca que el funcionamiento del agente se degrade a lo largo de las itearaciones y que no sea capaz de solucionar el problema.

## Objetivo

Diseñar una solucion facil de implementar que contribuya enormemente a que el contexto del agente en siguientes iteraciones es realmente valido.
De manera resumida, se debe construir la información mínima de:

- qué está fallando
- qué se sabe del bug
- qué se ha inspeccionado
- qué se ha intentado
- qué cambios se hicieron
- qué resultado tuvieron
- qué restricciones siguen vigentes
- qué debe hacer ahora el agente

En definitiva, el contexto que necesita el agente para continuar, manteniendo las restricciones que imponemos al agente de manera inicial.


## TOKENS

Mirar por que results/batch-quixbugs-mono-local-sample-20260506T212449Z solo la de gcd tiene informacion de tokens