## Cuestiones de main.py
En main.py:app, necesitamos tantos runners? Actualmente hay 4. Además, por que el que realmente hace la ejecucion (run_agent_smoke) se llama smoke?

Luego, En el parseador igual, necesitamos tantos parametros? La imformacion casi que toda viene directamente en el docker compose como variable de entorno. Yo diria que casi que no sirve para el proposito del proyecto, dado que todo se ejecuta usando variables de entorno o configuracion en un docker-compose.

Tambien, en run_agent_smoke, hay varias cosas que no estan bien o no me gustan:
- El modo debug e interactive no parecen funcionar. Si yo ejecuto el make quixbugs-gcd-run el sistema se ejecuta pero no sale nada en la terminal, ni siquiera los prints de debug.
- Si ejecuto el sistema con el make quixbugs-gcd-run el sistema se ejecuta, pues se va escribiendo todo en el archivo de live.md y termina el summary.json, pero la terminal se queda colgada y no puedes hacer nada.
- La forma de imprimir cosas en la terminal con el debug no me parece adecuada, mejor usar un logger idiomatico para este tipo de cosas.
- Seguimos recibiendo un prompt del parseador, pero realmente no se va a recibir un prompt, sino que el propio sistema ejecuta los tests y ya acopla un input ajustado al resultado de los tests, los cuales fallan al inicio. En el futuro quizas lo usamos, pero de momento, todo aquello que no vayamos a usar, se debe eliminar.
- El codigo esta lleno de try-except y cosas que, en general producen bastante ruido visual.
- El metodo de `load_container_instantiation_from_env` no tiene necesidad ninguna de ser un metodo aislado de la clase. Puede definirse como metodo de clase.
- El metodo en general no tiene una responsabilidad definida, hace carga de datos del entorno, prepara el entorno y ejecuta. Esta bien, pero, por ejemplo, hay cosas de la carga que se hacen en metodos dedicados y otras que se externalizan. Debe haber mayor consistencia.
- Los métodos de resolve_X. No hay algo ya definido en pydantic o helpers estandar que eviten tener que implementar esas validaciones?

El sistema siempre se va a ejecutar en un contenedor docker, nunca en la maquina local, eso hay que tenerlo en cuenta para no implementar codigo adaptado a eso cuando realmente no vamos a necesitarlo.