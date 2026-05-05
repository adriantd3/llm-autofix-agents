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