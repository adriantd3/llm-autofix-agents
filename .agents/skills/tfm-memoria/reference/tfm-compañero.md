# TRABAJO FIN DE MASTER ́

#### ESCUELA TECNICA SUPERIOR DE INGENIER ́ ́IA INFORMATICA. ́

#### MASTER UNIVERSITARIO EN INGENIER ́ ́IA DEL SOFTWARE E INTELIGENCIA ARTIFICIAL

#### PREDICCION AUTOM ́ ATICA DEL RESULTADO DE INTEGRACI ́ ON CONTINUA EN EL DESARROLLO DE ́

#### SOFTWARE MODERNO

#### AUTOMATIC PREDICTION OF CONTINUOUS INTEGRATION OUTCOME IN MODERN SOFTWARE

#### DEVELOPMENT

```
Realizado por
Joaqu ́ın Alejandro Espa ̃na S ́anchez
```
```
Tutorizado por
Gabriel Jes ́us Luque Polo
Francisco Javier Servant Cort ́es
```
```
Escuela T ́ecnica Superior de Ingenier ́ıa Informatica ́
—
Universidad de M ́alaga,
M ́alaga, Septiembre de 2024
```

## ́Indice general

- 1. Introducci ́on
- 2. Antecedentes y trabajos relacionados
   - 2.1. Antecedentes
      - 2.1.1. El ciclo de vida de la Integraci ́on Continua.
      - 2.1.2. Caracter ́ısticas de lasbuilds.
      - 2.1.3. El costo de la Integraci ́on Continua.
   - 2.2. Trabajos relacionados
- 3. Objetivos y preguntas de investigaci ́on
- 4. Descripci ́on del problema
- 5. Detalles de la propuesta
   - 5.1. Construcci ́on del modelo
      - 5.1.1. Hiperpar ́ametros.
   - 5.2. Evaluaci ́on del modelo
      - 5.2.1. Validaci ́on Cruzada.
      - 5.2.2. Umbral de decisi ́on.
   - 5.3. Featuresempleadas
      - 5.3.1. C ́aculo defeaturesdurante la predicci ́on.
   - 5.4. Interfaz gr ́afica
   - 5.5. Detalles t ́ecnicos de la implementaci ́on
      - 5.5.1. Tecnolog ́ıas empleadas.
      - 5.5.2.GitHubREST API.
      - 5.5.3. Procesamiento debuilds.
- 6. Experimentaci ́on
   - 6.1. Dise ̃no experimental
      - 6.1.1. T ́ecnicas a comparar.
      - 6.1.2. Descripci ́on deldataset.
      - 6.1.3. Procedimiento para el entrenamiento, prueba y validaci ́on cruzada
      - 6.1.4. M ́etricas de evaluaci ́on
   - 6.2. Resultados
      - 6.2.1. Escenario 1 - Proyectos dif ́ıciles.
      - 6.2.2. Escenario 2 - Proyectos normales.
- 7. Amenazas a la validez
   - 7.1. Validez de constructo
   - 7.2. Validez interna
   - 7.3. Validez externa
- 8. Conclusiones y trabajos futuros


Resumen –En el contexto del desarrollo desoftwaremoderno, la Integraci ́on Continua (CI) es una pr ́actica
ampliamente adoptada que busca automatizar el proceso de integraci ́on de cambios de c ́odigo en un proyecto.
A pesar de ofrecer numerosas ventajas, implementarla conlleva una serie de costos significativos que deben ser
abordados para garantizar la eficiencia a largo plazo. La fase de Integraci ́on Continua puede resultar costosa
tanto en t ́erminos de recursos computacionales como econ ́omicos, llevando a grandes empresas como Google
y Mozilla a invertir millones de d ́olares en sus sistemas de CI [12]. Han surgido numerosos enfoques para
reducir el costo asociado a la carga computacional evitando ejecutar construcciones que se espera que sean
exitosas [9]. Sin embargo, estos enfoques no son precisos, llegando a hacer predicciones err ́oneas que omiten
ejecutar construcciones que realmente fallan. Adem ́as de los costos asociados con la carga computacional y
econ ́omica de la CI, otro problema al que se enfrentan los equipos de desarrollo desoftwarees el tiempo que
deben esperar para obtenerfeedbackdel resultado del proceso de CI [10]. Este tiempo de espera en ocasiones
puede ser significativo y puede afectar negativamente a la productividad y eficiencia del equipo, as ́ı como a la
capacidad de respuesta ante problemas y ajustes r ́apidos en el desarrollo. As ́ı, en este trabajo nuestro objetivo
es reducir el costo computacional en CI, al mismo tiempo que maximizamos la observaci ́on de construcciones
fallidas. Para ello, se ha realizado un estudio sobre las t ́ecnicas existentes [9,11,17,2,5,3], y se ha propuesto
una implementaci ́on, JAES24, que busca contribuir a las mismas. Este nuevo enfoque ampl ́ıa el estado del
arte de t ́ecnicas existentes que hacen uso deMachine Learningpara la predicci ́on de construcciones fallidas,
mejorando sus resultados y ofreciendo un punto diferenciador, una interfaz gr ́afica. Dicha interfaz permite
interactuar de forma sencilla con el sistema, abstrayendo la complejidad de los algoritmos de predicci ́on
y ofreciendo una forma intuitiva y sencilla de realizar predicciones basadas en un repositorio concreto.
Posteriormente, se han realizado una serie de experimentos para verificar y validar la efectividad de JAES
en comparaci ́on con otras t ́ecnicas existentes. Finalmente, se desarrollan unas conclusiones sobre lo resultados
obtenidos y se proponen posibles l ́ıneas de trabajo futuro.

Palabras clave: Integraci ́on Continua, Predicci ́on de Builds, Aprendizaje Autom ́atico, Ahorro de Costos,
Caracter ́ısticas de Builds

Abstract –In the context of modern software development, Continuous Integration (CI) is a widely adopted
practice that aims to automate the process of integrating code changes in a project. Despite offering nume-
rous advantages, implementing CI involves significant costs that need to be addressed to ensure long-term
efficiency. The Continuous Integration phase can be costly in terms of computational and economic resources,
leading large companies like Google and Mozilla to invest millions of dollars in their CI systems [12]. Several
approaches have emerged to reduce the cost associated with computational load by avoiding running builds
that are expected to be successful [9]. However, these approaches are not accurate, often making erroneous
predictions that skip running builds that actually fail. In addition to the costs associated with computational
and economic load of CI, another problem faced by software development teams is the time they have to
wait to get feedback on the CI process outcome [10]. This waiting time can sometimes be significant and can
negatively impact team productivity and efficiency, as well as the ability to respond to issues and make quick
adjustments in development. Therefore, the objective of this work is to reduce the computational cost in CI
while maximizing the observation of failed builds. To achieve this, a study has been conducted on existing
techniques [9,11,17,2,5,3], and an implementation, JAES24, has been proposed to contribute to them. This
new approach extends the state of the art of existing techniques that useMachine Learningfor predicting
build failures, improving their results and offering a distinguishing feature, a graphical interface. This inter-
face allows for easy interaction with the system, abstracting the complexity of the prediction algorithms and
providing an intuitive and simple way to make predictions based on a specific repository. Subsequently, a
series of experiments have been conducted to verify and validate the effectiveness of JAES24 in comparison
with other existing techniques. Finally, conclusions are drawn from the results obtained, and possible future
research directions are proposed.

Keywords: Continuous Integration, Build Prediction, Machine Learning, Cost Saving, Build Features


## 1. Introducci ́on

La Integraci ́on Continua (Continuous Integration, CI) es una pr ́actica de desarrollo desoftwareque busca
automatizar el proceso de fusi ́on de cambios de c ́odigo en un proyecto, donde cada integraci ́on es verificada
mediante la ejecuci ́on autom ́atica de pruebas. Este proceso busca la detecci ́on temprana de errores y me-
jorar la calidad del software, permitiendo una integraci ́on m ́as frecuente y r ́apida del trabajo de todos los
desarrolladores. Las buenas pr ́acticas de CI [3] permiten una r ́apida detecci ́on de errores y su resoluci ́on,
unfeedbackr ́apido, la reducci ́on de errores que provienen de tareas manuales, unas tasas decommitsypull
requestsm ́as altas, una calidad delsoftwaremayor, reconocer errores en producci ́on temprano antes del des-
pliegue, etc. Numerosos son sus ́ambitos de aplicaci ́on:softwareempresarial, desarrollo de aplicaciones web,
proyectos de c ́odigo abierto, aplicaciones m ́oviles, etc. Todo ello, haciendo uso de las distintas herramientas
que existen en el mercado [16], comoGitHub Actions,Jenkins,Travis CI,CircleCI,Azure DevOps, entre otras.

Para contextualizar el problema que nos ocupa, vamos a describir algunos t ́erminos relevantes para el
entendimiento del mismo. A lo largo del trabajo, nos referiremos comobuildal proceso autom ́atico mediante
el cual el c ́odigo fuente se compila, se ejecutan las pruebas, y se genera un artefactosoftware, ya sea un
ejecutable, un contenedor, un paquete, etc., que est ́a listo para ser desplegado o usado en producci ́on. Cada
buildes lanzada por lo que se denomina com ́unmentetrigger, que puede ser un:

Commit: representa una “instant ́anea” del estado del proyecto en un momento espec ́ıfico, guardando
las modificaciones que se han hecho a los archivos desde el ́ultimocommit. Cada vez que el desarrollador
realiza uncommit, se dispara una nuevabuild.
Pull request: unpull requesto solicitud de incorporaci ́on de cambios es una solicitud formal para fusio-
nar cambios propuestos en una rama de desarrollo a otra rama, que generalmente es la rama principal.
Este tipo de solicitud permite la revisi ́on de los cambios realizados, su discusi ́on, y aprobaci ́on del c ́odigo
por parte de otros desarrolladores antes de integrarlo con la rama principal. En este caso, al crear o
actualizar unpull request, se lanza unabuildpara verificar que el c ́odigo cumple con los est ́andares de
calidad.
Schedule: se pueden programarbuildspara que se ejecuten en un intervalo de tiempo regular, indepen-
dendientemente de si hubo o no cambios en el c ́odigo.
Existen numerosos sistemas de CI en la actualidad,GitHub Actions,Jenkins,Travis CI,CircleCI,Azure
DevOps, entre otros, sin embargo, en este trabajo nos centraremos enGitHub Actions.GitHub Actionses el
sistema de CI m ́as utilizado en la actualidad, y al cual muchos otros sistemas migraron debido a sus carac-
ter ́ısticas, especialmenteTravis CI. En 2020,Travis CIdecidi ́o imponer numerosas restricciones a su plan
gratuito para proyectossoftwarede c ́odigo abierto [16], siendo este uno de los principales motivos para su mi-
graci ́on haciaGitHub Actions. Adem ́as, existen otras razones para esta migraci ́on, como puede ser utilizar una
herramienta de CI m ́as confiable, mejor integraci ́on con solucionesself-hosted, mejor soporte para m ́ultiples
plataformas, la reducci ́on de la cantidad de uso compartido de la herramienta, tener m ́as funcionalidades, etc.

El ciclo de vida de la Integraci ́on Continua, a pesar de ofrecer numerosas ventajas, conlleva grandes costos
asociados debido a los recursos computacionales [6] necesarios para ejecutar las construcciones, com ́unmen-
te denominadasbuilds. A lo largo de este trabajo, nos referiremos como costo computacional al hecho de
ejecutar unabuild, es decir, el proceso de construir elsoftwarey ejecutar todas las pruebas cuando la CI
es lanzada. Este costo asociado se acent ́ua en empresas de gran tama ̃no, donde el n ́umero debuildsque se
ejecutan diariamente es muy elevado [4,15]. Ahorrar en dicho costo computacional se convierte por tanto en
un objetivo clave para las mismas. Optimizando la cantidad debuildsque se ejecutan, podemos lograr una
reducci ́on significativa de este costo, ya que se habr ́an consumido menor cantidad de recursos. Adem ́as, hay
que sumarle el tiempo de espera que los desarrolladores deben soportar cuando el tiempo de ejecuci ́on de la
buildes elevado, pudiendo ralentizar el tiempo de respuesta ante problemas y ajustes r ́apidos en el desarrollo.

En los ́ultimos a ̃nos, han surgido numerosos enfoques centrados en reducir el costo computacional asociado
a la ejecuci ́on de CI [12,9,11,17,2,5]. La idea principal de estos enfoques es reducir el n ́umero debuildsque se


ejecutan, prediciendo el resultado antes de su ejecuci ́on y, por lo tanto, ahorr ́andose ese costo computacional.
Lasbuildspredichas como construcciones exitosas (build pass) no se ejecutan, mientras que las predichas
como construcciones fallidas (build failure) s ́ı se ejecutan. De esta forma, se mantiene el valor conceptual
de la CI, que es la detecci ́on temprana de errores, pero reduciendo el costo computacional asociado en el
proceso. Este estudio toma como punto de partida el algoritmo deMachine Learning SmartBuildSkip[9]. La
idea principal es realizar una contribuci ́on a este algoritmo, realizando un estudio de lasfeaturesque se usan
para la predicci ́on, y a ̃nadiendo nuevasfeaturesm ́as significativas que puedan mejorar estudios existentes.
Adem ́as, se ha creado una aplicaci ́on web sencilla con la que el usuario puede interactuar de forma directa
a trav ́es de una interfaz gr ́afica, abstrayendo la complejidad de los algoritmos de predicci ́on y ofreciendo
una forma intuitiva y sencilla de realizar predicciones basadas en un repositorio concreto. Por lo tanto, este
estudio se enmarca en el desarrollo desoftwaremoderno, espec ́ıficamente en el ́ambito de la Integraci ́on
Continua y la predicci ́on autom ́atica del resultado de dicha integraci ́on.

Desde nuestra perspectiva, tenemos la intuici ́on de que el momento en el que se realiza la contribuci ́on, as ́ı
como los tipos de cambios introducidos en la base de c ́odigo, podr ́ıan ser factores clave en la predicci ́on del
resultado de la integraci ́on. Consideramos que la utilizaci ́on decaracter ́ısticas que capturen eltiming
exacto de la contribuci ́on, junto con otras quedesglosen detalladamente los tipos de cambiosrealiza-
dos, podr ́ıa llevarnos a obtener mejores resultados en la predicci ́on debuildsfallidas. Tenemos la hip ́otesis de
que el momento en el que se lanza la CI puede ser decisivo en la predicci ́on del resultado. Por ejemplo, pueden
producirse mayor cantidad de fallos los lunes, cuando los desarrolladores regresan despu ́es del fin de semana
y no est ́an concentrados. Tambi ́en, puede que durante picos de actividad justo antes de un lanzamiento o
durante periodos de alta presi ́on, como el d ́ıa de una entrega o en los ́ultimos d ́ıas de unsprint, se produz-
can m ́as fallos. Estas suposiciones, no son arbitrarias, sino que existen estudios que indican que los viernes
tienden a ser el d ́ıa con mayor frecuencia de fallos, posiblemente debido a la prisa de los desarrolladores por
completar las tareas antes del fin de semana o por la fatiga acumulada durante la semana laboral [20]. En
nuestro estudio, hemos encontrado evidencia que respalda esta hip ́otesis.

La memoria queda organizada de la siguiente forma: en primer lugar, se realiza un estudio del estado del
arte que sit ́ua los antecedentes previos a la Integraci ́on Continua y la predicci ́on autom ́atica de resultados
debuilds. Posteriormente, se establecen los objetivos y preguntas de investigaci ́on que pretende este estudio
responder. A continuaci ́on, se describe en detalle el problema a resolver, los principales obst ́aculos que
se plantean y sus posibles soluciones. Acto seguido, se desarrolla con detalle nuestro enfoque al problema,
describiendo las tecnolog ́ıas usadas y el desarrollo de la soluci ́on. Despu ́es se presentan las pruebas y resultados
obtenidos, comparando la soluci ́on con otras existentes, a modo de validar y verificar la aportaci ́on de nuestra
soluci ́on. Seguidamente, se comentan las amenazas a la validez, una parte esencial en cualquier trabajo de
investigaci ́on. Este apartado nos permite identificar y discutir posibles limitaciones que podr ́ıan afectar a
la validez de los resultados y a las conclusiones. Por ́ultimo, se dan unas conclusiones sobre los resultados
obtenidos y se proponen posibles l ́ıneas de trabajo futuro.

## 2. Antecedentes y trabajos relacionados

En esta secci ́on se comentan los principales conceptos necesarios para entender el resto del documento,
as ́ı mismo como un repaso a las t ́ecnicas que existen en la literatura para abordar el problema tratado en
este trabajo.

### 2.1. Antecedentes

Este trabajo se centra en la implementaci ́on, evaluaci ́on y mejora del algoritmo de predicci ́on de CI
propuesto en [9]. Para comprender mejor el contexto en el que se desarrolla, primero vamos a presentar
algunos de los conceptos b ́asicos de CI y del problema que nos ocupa. En primer lugar, se describir ́a el ciclo


de vida de CI, junto a las dos casu ́ısticas que pueden darse en el proceso de integraci ́on. En segundo lugar,
hablaremos sobre la extracci ́on de caracter ́ısticas, un aspecto fundamental para algoritmos de predicci ́on.
Por ́ultimo, se hablar ́a del consumo de recursos computacionales que supone la implementaci ́on de CI, de
ah ́ı la principal motivaci ́on de este trabajo, la reducci ́on de dichos costes.

2.1.1. El ciclo de vida de la Integraci ́on Continua.La Integraci ́on Continua es un proceso iterativo
en el cual varios contribuidores hacen cambios sobre un mismo c ́odigo base a ̃nadiendo nuevas funcionalidades,
para luego integrarlas a la misma linea temporal de desarrollo, de forma controlada y automatizada. Cada
integraci ́on se realiza a trav ́es de la compilaci ́on, construcci ́on y ejecuci ́on de pruebas automatizadas sobre
el c ́odigo fuente [6]. Aunque pueda parecerlo, la Integraci ́on Continua no es un proceso trivial, en [4] se
describen las buenas pr ́acticas de CI que deben seguirse para garantizar la calidad delsoftware, algunas de
las cuales han sido fuertemente adoptadas en el sector, como por ejemplo:

```
1.Punto de c ́odigo fuente ́unico: para faclitar la integraci ́on de cualquier desarrollador a un proyecto,
es fundamental que este pueda obtener el c ́odigo fuente actualizado del proyecto. La mejor pr ́actica es
utilizar un sistema de control de versiones como fuente ́unica del c ́odigo. Todos los archivos necesarios
para la construcci ́on del sistema, incluidosscriptsde instalaci ́on, archivos de configuraci ́on, etc., deben
estar en el repositorio.
2.Automatizaci ́on debuilds: para proyectos peque ̃nos, construir la aplicaci ́on puede ser tan sencillo co-
mo ejecutar un ́unico comando. Sin embargo, para proyectos m ́as complejos o con dependencias externas,
la construcci ́on puede ser un proceso complicado. El uso descriptsde construcci ́on automatizados es
esencial para manejar estos procesos, llegando a analizar qu ́e partes del c ́odigo necesitan ser recompiladas,
y gestionando dependencias para evitar recompilar innecesariamente.
3.Desarrollo de pruebas unitarias o de validaci ́on interna: compilar el c ́odigo no es suficiente para
asegurar que funciona correctamente, por lo que se implementan pruebas automatizadas. Normalmente,
estas se dividen en pruebas unitarias, que prueban partes espec ́ıficas del c ́odigo; y pruebas de aceptaci ́on,
que prueban el sistema completo. Aunque este proceso no puede garantizar la ausencia total de errores,
ofrece un mecanismo efectivo de mejorar la calidad delsoftwaremediante la detecci ́on y correcci ́on
continua de fallos.
```
Sin embargo, en el mundo real, la forma de aplicar cada una de estas t ́ecnicas y la prioridad con la
que se aplica puede estar fuertemente influenciada por la cultura empresarial donde se desarrolle. En [3], se
realiza un caso de estudio con tres empresas donde se percibe que la adopci ́on de las pr ́acticas de CI no es
homog ́enea. Por ejemplo, con respecto a tener un ́unico punto de c ́odigo fuente, algunas prefieren minimizar
los conflictos de fusi ́on (merge conflicts) que el beneficio poco claro de usar un ́unico repositorio. Por otro
lado, en cuanto a las pruebas unitarias, existen diferencias debido a limitaciones en las herramientas (poco
factibles para realizar pruebas de interfaz de usuario), a las percepciones pr ́acticas (el trabajo necesario para
las pruebas de integraci ́on supera los beneficios percibidos) y al contexto del proyecto (pruebas centradas en
datos requieren comunicaci ́on con servicios externos).

Ejemplo pr ́actico: Un desarrollador hace uncommit(una instant ́anea de los cambios realizados) y
mediante una acci ́on depush, lo env ́ıa al repositorio central. El servidor de CI [16] (Jenkins, Travis CI, GitHub
Actions, etc.) detecta autom ́aticamente este nuevocommity desencadena elpipelinede CI. El servidor extrae
el nuevo c ́odigo del repositorio y comienza a construir la aplicaci ́on, lo que denominados la fase de construcci ́on
obuild. Esta parte puede incluir la compilaci ́on del c ́odigo fuente, la instalaci ́on de dependencias, etc. Una
vez que la aplicaci ́on est ́a construida, se ejecutan una serie de pruebas automatizadas (Self-Testing code)
[6]. Dichas pruebas pueden ser pruebas unitarias, pruebas de integraci ́on, pruebas funcionales o pruebas de
interfaz de usuario. Dependiendo del resultado de las fases anteriores, podemos encontrarnos dos casos:

```
Labuild ha sido exitosa: todas las pruebas han pasado con ́exito. En este caso, el servidor de CI
puede desplegar la aplicaci ́on en un entorno de pruebas o producci ́on.
```

```
Labuildha fallado: alguna de las pruebas ha fallado. En este caso, el servidor de CI suele notificar a
los desarrolladores y detiene el despliegue de la aplicaci ́on.
```
2.1.2. Caracter ́ısticas de lasbuilds. Al ejecutarse unabuild, se pueden extraer de ella una serie de
caracter ́ısticas con las que algoritmos de predicci ́on pueden predecir el resultado de la integraci ́on. Tener un
conjunto defeaturesbien seleccionadas y significativas mejorar ́a la precisi ́on de los modelos. La mayor ́ıa de
estudios utilizan catacter ́ıticas extra ́ıdas directamente de la base de datos de TravisTorrent [2], sin embargo,
estas caracter ́ısticas no son las mejores para predecirbuildsque fallan, es decir,builds failures. Algunos
enfoques [2,5] hacen uso de caracter ́ısticas basadas en labuildactual, labuildanterior y el hist ́orico ligado
a todas las ejecuciones debuildsanteriores. El primer estudio en utilizar t ́ecnicas deMachine Learningpara
predecir el resultado de CI fue realizado por Hassan et al. [5]. En su estudio, utiliz ́o caracter ́ısticas basadas
en labuildactual y la anterior, para labuildanterior us ́o:

```
prevblcluster: el cluster de labuildanterior.
prevtrstatus: el estado de labuildanterior.
prevghsrcchurn: el n ́umero de l ́ıneas de c ́odigo fuente cambiadas en labuildanterior.
prevghtestchurn: el n ́umero de l ́ıneas de c ́odigo de test cambiadas en labuildanterior.
```
```
Para la instancia debuildactual, se usaron caracter ́ısticas como:
```
```
ghteamsize: el tama ̃no del equipo.
cmtbuildfilechangecount: n ́umero de cambios en el archivo de script de construcci ́on.
ghotherfiles: n ́umero de archivos no relacionados con el c ́odigo fuente.
ghsrcchurn: n ́umero de l ́ıneas de c ́odigo fuente cambiadas.
ghsrcfiles: n ́umero de archivos de c ́odigo fuente.
ghfilesmodified: n ́umero de archivos modificados.
ghfilesdeleted: n ́umero de archivos eliminados.
ghdocfiles: n ́umero de archivos de documentaci ́on.
cmtmethodbodychangecount: n ́umero de cambios en el cuerpo del m ́etodo.
cmtmethodchangecount: n ́umero de cambios en la cabecera del m ́etodo.
cmtimportchangecount: n ́umero de cambios en losimports.
cmtfieldchangecount: n ́umero de cambios en los atributos de clase.
dayofweek: d ́ıa de la semana del primercommitde labuild.
cmtclasschangecount: n ́umero de clases cambiadas.
ghfilesadded: n ́umero de archivos a ̃nadidos.
ghtestchurn: n ́umero de l ́ıneas de c ́odigo de test cambiadas.
```
En [2] se reutilizaron gran cantidad de estas features mencionadas a ̃nadiendo las relacionadas con el
hist ́orico de ejecuciones debuilds: tanto por ciento de compilaciones fallidas, incremento delfailratio en la
́ultimabuildcon respecto al ratio de la pen ́ultima, porcentaje debuildsexitosas desde la ́ultimabuildfallida,
etc. Como vemos, se utilizan un gran n ́umero defeaturespara la predicci ́on, sin embargo, el objetivo no es
la reducci ́on de los costos de CI ni la importancia de cada una de ellas en relaci ́on con losbuild failures. El
hecho de que se utilicen tantasfeaturesrelacionadas con labuildanterior, hace que predecir unabuildcomo
fallida est ́e fuertemente relacionado con el resultado de labuildanterior, que deber ́ıa ser fallida. Esto hace
que exista una limitaci ́on para la detecci ́on de los primerosbuild failures[9], ya que estos dependen mucho
del resultado de labuildanterior y, por definici ́on, estar ́an siempre precedidos por unabuildexitosa.

Losbuild failurespueden categorizarse en una serie de tipos. Se ha identificado un total de 14 categor ́ıas
de build failures, clasificadas seg ́un el tipo de error que las origina [15]. En el estudio se demostr ́o que m ́as
del 80 % de los errores se produc ́ıan en la fase de ejecuci ́on de pruebas otests. En el estudio se pretende
identificar las causas que originan losbuild failures, para lo que se usan 16 m ́etricas de la literatura y se
descubre lo siguiente:


```
Se respalda la hip ́otesis de que losbuild failurespueden aumentar con la complejidad de los cambios.
Cambios objetivamente insignificantes pueden romper labuild.
Hay poca evidencia de que la fecha y hora de un cambio tenga un aspecto negativo o positivo en los
resultados.
Los autores quecommiteanmenos frecuentemente tienden a causar menosbuild failures.
Normalmente, lasbuildslanzadas a trav ́es depull requestsfallan con mayor frecuencia que las lanzadas
por cambios directamente subidos a trav ́es depusha la rama principal.
No existe evidencia que demuestre que trabajar en paralelo a unpull requestafecte al resultado de la
build.
La mayor ́ıa de los errores se producen consecutivamente. Las fases m ́as inestables de compilaci ́on generan
fallos en la CI.
```
Todos estos resultados se obtuvieron a trav ́es de un estudio emp ́ırico con 14 proyectos de c ́odigo abierto
basados en Java que usan Travis CI. Por ́ultimo, en [8] se realiza un estudio a gran escala con 3.6 millones
debuildsen el que se demuestra que factores como la cantidad de cambios en el c ́odigo fuente, el n ́umero
decommits, el n ́umero de archivos modificados o la herramienta de integraci ́on usada tienen una relaci ́on
estad ́ısticamente significativa con las compilaciones fallidas.

2.1.3. El costo de la Integraci ́on Continua.La implementaci ́on de la Integraci ́on Continua, a pesar de
ofrecer numerosas ventajas, tambi ́en supone un coste computacional y econ ́omico. Adem ́as del costo compu-
tacional que supone ejecutar la CI, debemos sumarle el costo del tiempo no productivo de los desarrolladores
si estos no saben como proceder sin saber el resultado de la integraci ́on. Hilton et al. [6] estudiaron los bene-
ficios y costes de aplicar CI en proyectos de c ́odigo abierto. En su estudio, observaron que entre los proyectos
open-sourceque no usaban CI, el principal motivo no era el costo t ́ecnico, si no que los desarrolladores no
estaban familiarizados con CI. Otra de las razones de no usar CI era la falta detestsautom ́aticos, un aspecto
fundamental en CI. Adem ́as, calcularon el costo de mantenimiento de la CI, para lo que midieron el n ́umero
de cambios en los archivos de configuraci ́on. Observaron que el n ́umero medio de modificaciones en archivos
de configuraci ́on se elevaba a 12, siendo frecuente que se realizaran cambios en la configuraci ́on de CI. Una de
las principales razones para estos cambios en archivos de configuraci ́on era la presencia de versiones obsoletas
en las dependencias. Por ́ultimo, observaron un hecho curioso con respecto al tiempo de ejecuci ́on medio de
lasbuilds: lasbuildsexitosas son, en promedio, m ́as r ́apidas que aquellas que fallan. Intuitivamente, podr ́ıa
esperarse lo contrario, ya que un error deber ́ıa de interrumpir el proceso antes, aunque se necesita una mayor
investigaci ́on para averiguar estas razones.

Klotins et al. [13] realizaron un trabajo con m ́ultiples casos de estudio en el que encontraron que la
aplicaci ́on de CI mejoraba notablemente los procesos de desarrollo internos en las empresas, sin embargo,
se destaca la necesidad de evaluar las consecuencias de aplicar este tipo de desarrollo desde una perspectiva
del cliente. El hecho de actualizar a los clientes a entregas continuas es un obst ́aculo importante ya que
pueden existir acuerdos previos, y renegociar dichos acuerdos conlleva el riesgo de perder clientes y causar
inestabilidad en la empresa. En el estudio se ha observado la necesidad de adoptar pr ́acticas de CI para
mejorar los procesos de desarrollosoftwareen las empresas, sin embargo, estas se enfrentan a desaf ́ıos
comunes en su implementaci ́on:

```
1.Beneficios internos vs. externos: se reconocen los beneficios internos de aplicar CI, como la agilizaci ́on
de los procesos y la liberaci ́on de recursos. Sin embargo, extender estos beneficios a los clientes y la
adaptaci ́on de los modelos de negocio existentes representan un obst ́aculo mayor.
2.Cultura organizacional: la implementaci ́on de CI requiere cambios significativos en los procesos y en
la cultura organizacional. Esto requiere compromiso por parte de los equipos de desarrollo y directivos.
3.Clientes: convencer a los clientes para aceptar entregas m ́as frecuentes y compartir m ́as datos es fun-
damental para sacar partido a las ventajas de CI. Sin embargo, los clientes pueden ofrecer resistencia al
cambio y esto puede poner en peligro las relaciones con los mismos.
```

En [7] se presenta un estudio en el que se pregunt ́o a trabajadores de la empresaAtlassiansobre sus
percepciones sobre los fallos de CI. Entre los trabajadores, una gran mayor ́ıa (46 %) consideraba como muy
o extremadamente dif ́ıcil resolver los fallos de CI, una minor ́ıa (13 %) consideraba que no era dif ́ıcil resol-
verlos, y el resto calific ́o la complejidad como moderada. Adem ́as, comentaban que los fallos de CI pod ́ıan
afectar tanto al flujo de trabajo individual como a la empresa. Los trabajadores notaban que estos fallos
pod ́ıan aumentar el tiempo de trabajo e incluso interrumpir el flujo de desarrollo. Otro impacto posible es
la reducci ́on de la productividad, ya que alguien tiene que dedicar tiempo a investigar por qu ́e fall ́o labuild
y solucionarlo. Este tipo de problemas puede ocasionar que las revisiones o las correcciones r ́apidas tarden
m ́as tiempo de lo esperado, poniendo en peligro el tiempo de lanzamiento (release). Adem ́as, se menciona
que factores t ́ecnicos como humanos desempe ̃nan un papel fundamental en la adopci ́on de CI.

### 2.2. Trabajos relacionados

Existen numerosos estudios que buscan reducir el costo asociado a la Integraci ́on Continua mediante la
creaci ́on depredictors[5,17,9,19,2,18,11,12,14]. Hassan et al. [5] estudiaron un total de 402 proyectos Java
con informaci ́on de 256,055builds, procedentes de la base de datos de TravisTorrent. En su estudio se utili-
zan caracter ́ısticas extra ́ıdas directamente de la base de datos de TravisTorrent y otras propias, relacionando
featurespropias de labuild actualy la anterior. En su propuesta, primero se realiza una selecci ́on defeatu-
resbasada en la evaluaci ́on de la importancia de las mismas mediante elInformation Gain (IG). Con ello
seleccionan las m ́as discriminativas del conjunto defeatures(Secci ́on 2.1.2). Posteriormente, construyen un
clasificador que usarandom forestpara clasificar lasbuildsen exitosas y fallidas. Este estudio fue el primer
enfoque en utilizar t ́ecnicas deMachine Learningpara predecir el resultado de la CI, sin embargo, no estaba
centrado en reducir los costos asociados a la misma ni a losbuild failures, los casos positivos que m ́as inter ́es
tienen.

En [17] se propone una soluci ́on novedosa que usa Programaci ́on Gen ́etica Multi-Objetivo, sin utilizar
t ́ecnicas de aprendizaje autom ́atico. Su enfoque consiste en recopilarbuildsexitosas y fallidas de un pro-
yecto, obtener informaci ́on deTravisTorrentque contiene informaci ́on sobrebuildsdeTravis CIy, a partir
de ah ́ı, se toman esos datos como entrada para generar un conjunto de reglas predictivas que anticipen el
resultado de la compilaci ́on de CI con la mayor precisi ́on posible. Finalmente, entra en juego el algoritmo de
programaci ́on gen ́etica multiobjetivo, el cual va generando un conjunto de soluciones, cada una de ellas con
su conjunto de reglas de predicci ́on, por ejemplo, una combinaci ́on de umbrales asignados a cada m ́etrica.
Dicha combinaci ́on de m ́etricas-umbrales est ́a conectada a operadores l ́ogicos. Todas las muestras generadas
en la soluci ́on son evaluadas usando dos objetivos: maximizar la tasa de verdaderos positivos y, minimizar
la tasa de falsos positivos. En cada iteraci ́on se van cambiando los operadores, generando nuevas soluciones,
hasta llegar a una condici ́on de parada y devolviendo la soluci ́on ́optima. En el estudio encontraron que
caracter ́ısticas como el tama ̃no del equipo, la informaci ́on de la ́ultimabuildo el tipo de archivos cambiados,
pueden indicar el potencial fallo de unabuild. A pesar de obtener buenos resultados, solo se centran en 10
proyectos de lenguajes Java y Ruby, haciendo poco generalizables sus resultados. Adem ́as, el ratio defailures
que presentan estos proyectos es relativamente elevado, lo que puede ocasionar que el algoritmo no sea tan
efectivo en proyectos con ratios defailuresbajos.

La piedra angular de nuestro estudio se basa en el trabajo deServant et al.[9]. En este estudio, se
propone un algoritmo que utiliza t ́ecnicas deMachine Learningpara la predicci ́on de CI, con el objetivo de
reducir los costos asociados a la misma. Su teor ́ıa parte de dos hip ́otesis principales:

```
H 1 : la mayor ́ıa de lasbuildsdevuelven un resultado exitoso. Por lo general, lasbuildsexitosas son m ́as
numerosas que las fallidas. Es decir, siempre habr ́a mayor ratio debuildsque pasan la CI quebuildsque
fallan.
H 2 : muchasbuildsfallidas en CI ocurren consecutivamente despu ́es de otrabuildfallida.
```

Teniendo en cuenta estas dos hip ́otesis encontramos que, si la primera es cierta, al saltarse todas aquellas
buildsque se predigan como exitosas, se reducir ́a el coste considerablemente. En caso de que la segunda sea
cierta, entonces si se predice que lasbuildssubsecuentes a unabuildfallida tambi ́en fallar ́an, se predecir ́an
correctamente una buena parte de lasbuildsfallidas. En el estudio se introduce por primera vez el t ́ermino
defirst failures, que hace referencia a las primerasbuildsque fallan en una subsecuencia debuilds failures.
En enfoques anteriores, existe una limitaci ́on para la predicci ́on de estas primerasbuildsque fallan, ya que
dependen fuertemente del resultado de labuildanterior, haciendo que sean complicadas de predecir.

En el algoritmo, se utilizanfeaturesque son propias de labuildy sirven para predecirbuild failuresen
un mismo proyecto y, por otro lado, se usanproject features, que sirven para realizar lo que se denomina
cross-project predictions. Con respecto a lasbuild features, estas son propias de labuilden cuesti ́on y servir ́an
para realizar predicciones sobre el mismo repositorio que estemos analizando. En el estudio, se mencionan
algunas m ́as, pero finalmente se seleccionan las siguientes:

```
SC: el n ́umero de l ́ıneas de c ́odigo fuente cambiadas desde la ́ultimabuild.
FC: el n ́umero de archivos modificados desde la ́ultimabuild.
TC: el n ́umero de lineas detestscambiadas desde la ́ultimabuild.
NC: el n ́umero decommitsdesde la ́ultimabuild.
```
En cuanto a lasproject features, estas son ́utiles cuando queremos predecir el resultado de la CI en un
proyecto que tiene un n ́umero escaso debuilds, bien porque sea reciente, no se hayan ejecutado en su duraci ́on
gran n ́umero debuilds, etc. Este ́ultimo problema es lo que suele denominarse en sistemas de informaci ́on
como el “arranque en fr ́ıo” (cold start), cuando no se puede extraer informaci ́on ́util para los usuarios debido
a que todav ́ıa no se ha reunido suficiente informaci ́on. Para ello, se usan modelos generados a partir de otros
proyectos entrenados con estasfeatures. En el estudio, se mencionan algunasproject features, pero finalmente
se seleccionan las siguientes:

```
TD: el n ́umero medio de l ́ıneas en los casos de prueba por cada 1000 l ́ıneas ejecutables de c ́odigo de
producci ́on.
PS: el n ́umero medio de l ́ıneas de c ́odigo fuente de producci ́on ejecutale en el repositorio a lo largo de la
historia de uso de CI en el proyecto.
PA: la duraci ́on entre la primera y la ́ultimabuilddel proyecto
```
A continuaci ́on, se explica de forma gr ́afica el funcionamiento de su algoritmo, llamado SmartBuildSkip:

```
Figura 1.L ́ınea temporal de SmartBuildSkip [9].
```
Cada c ́ırculo recoge el resultado real de labuild. Losfirst failuresest ́an sombreados en gris. El s ́ımbolo de
diamante indica que el predictor ha realizado una predicci ́on. Lasbuildsque se han saltado est ́an indicadas
con c ́ırculos discontinuos. Cuando unabuildse predice comopass, el algoritmo acumula los cambios de la
buildcon la siguiente, lo que se indica mediante una flecha entre los c ́ırculos. Cuando se predice unfirst
failure,SmartBuildSkippredice directamente comofaillabuildsiguiente. As ́ı, hasta que se encuentra un
pass, lo que vuelve a reiniciar el algoritmo a la primera fase de predicci ́on.

Se ha elegido este estudio [9] como base para nuestro trabajo porque es el primero que usa ́unicamente
featuresque presentan una correlaci ́on significativa con lasbuild failures. Adem ́as, con nuestro trabajo pre-
tendemos indagar en la calidad de estasfeaturesy en mejorar los resultados obtenidos en el estudio original,


bien mediante la adici ́on de nuevasfeatureso mediante la mejora del algoritmo de predicci ́on.

Continuando con el orden cronol ́ogico del estado del arte, Saidani et al. [19] propone un predictor que
utiliza Redes Neuronales Recurrentes (RNN) basadas en Memoria a Largo Plazo (LSTM). Su estudio se
realiza como es habitual con diez proyectos de c ́odigo abierto que usan el sistema de CI deTravis CI, su-
mando un total de 91330builds. Estos revelan que este tipo de t ́ecnicas ofrecen mejores resultados que las
deMachine Learning, obteniendo mejor rendimiento en t ́erminos de AUC,F1-Scoreyaccuracycuando se
trata de validaci ́on entre proyectos. En [2] se propone una nueva soluci ́on en la que se usa un predictor que
es dependiente del hist ́orico debuildspasadas para poder hacer sus predicciones. En este estudio existen
m ́etodos de selecci ́on defeaturesque selecionan determinadasfeaturesen funci ́on del tipo de proyecto que
se est ́e evaluando. En otro art ́ıculo, Ouni et al. [18] propone una soluci ́on de l ́ınea de comandos donde se
consigue mejorar el estado del arte en t ́erminos deF1-Score. Sin embargo, en el estudio, solo se tiene en
cuenta el estudio [5] comentado anteriormente, obviando todas las implementaciones posteriores y teniendo
una clara amenaza a la validez del mismo. Adem ́as, dada la arquitectura presentada, podemos apreciar que
para la extracci ́on defeatures, se utiliza un parseador de HTML conJsoupySelenium, lo cu ́al hace poco
duradero el enfoque, ya que est ́a fuertemente acoplado a la estructura HTML deGitHuby sus cambios.

Jin et al. [11] propone un nuevo predictor,PreciseBuildSkip, que mejora el ahorro de costo y la observaci ́on
debuildsfallidas, llegando a obtener valores derecallrealmente buenos. En su implementaci ́on, incluyen dos
variantes: la segura, que salva el 5.5 % de lasbuildsy por lo general captura todas las construcciones fallidas,
y una versi ́on que mejora el ahorro de costos, salvando un 35 % de lasbuildsmientras captura un 81 % de
las observaciones debuildsfallidas. Finalmente, Jin et al. [12] propone una soluci ́on que emplea t ́ecnicas de
selecci ́on debuildsy dos t ́ecnicas de selecci ́on de tests. Esta soluci ́on ejecuta seis t ́ecnicas existentes y luego
usa los resultados comofeaturespara un clasificadorRandom forest. Entre sus resultados, se observa que:

```
Se consigui ́o un mayor ahorro de costos con la mayor seguridad en comparaci ́on con t ́ecnicas anteriores.
Tener un componente de selecci ́on detestsadem ́as de un componente de selecci ́on de compilaci ́on aumenta
los ahorros de costos.
Tener enfoques de selecci ́on detestspara predecir los resultados aumenta tanto la capacidad de ahorro
de costos como la capacidad de observaci ́on debuild failures.
El algoritmo de bosque aleatorio es el que ofrece mejor rendimiento en la predicci ́on.
Lafeaturesque recoge los fallos consecutivos fue la m ́as efectiva para este enfoque.
```
Por otro lado, no existen proyectos documentados que usen t ́ecnicas de predicci ́on de CI para el ahorro
de costos, por lo que es complicado evaluar el impacto econ ́omico real que estas pueden causar. Liu et al.
[14] utiliza simulaci ́on de procesossoftwarey experimentos basados en simulaci ́on para evaluar el impacto
de estospredictorsde CI en un entorno m ́as realista. Entre sus descubrimientos, vieron que existe poca
diferencia entre lospredictorsdel esado del arte y las estrategias aleatorias en t ́erminos de ahorro de tiempo.
Sin embargo, en casos donde el ratio debuildsfallidas es mayor, la estrategia aleatoria tendr ́ıa un impacto
negativo. Adem ́as, en proyectos donde la proporci ́on defailureses muy peque ̃na, el uso de CI predictiva no
es mucho mejor que saltarbuildsde forma aleatoria. A pesar de esto, se demuestra que el uso de t ́ecnicas de
predictive CIpuede ayudar a ahorrar el costo de tiempo para ejecutar CI, as ́ı como el tiempo promedio de
espera antes de ejecutar la CI.

## 3. Objetivos y preguntas de investigaci ́on

En un estudio de car ́acter exploratorio como el que se propone, definir unos objetivos y preguntas de
investigaci ́on se convierte en una tarea fundamental para la correcta orientaci ́on del trabajo. En este sentido,
los objetivos nos permiten establecer una serie de metas a alcanzar, mientras que, las preguntas de investi-
gaci ́on nos ayudan a centrar el estudio en aspectos concretos que queremos responder. Los objetivos de la
investigaci ́on son los siguientes:


```
OB-1: implementar un algoritmo de aprendizaje autom ́atico que genere un modelo predictivo (unpre-
dictor) basado en un conjunto de caracter ́ısticasfeaturesextra ́ıdas de lasbuilds.
```
```
OB-2: utilizar la API de GitHub para obtener datos relevantes sobre lasbuilds, como su hist ́orico, ca-
racter ́ısticas asociadas, resultados anteriores de la integraci ́on continua.
```
```
OB-3: desarrollar e implementar diferentes algoritmos de predicci ́on con la selecci ́on de diferentes ca-
racter ́ısticas con el objetivo de proporcionar m ́ultiples opciones a la hora de predecir el resultado de la
integraci ́on continua.
```
```
OB-4: implementar una interfaz gr ́afica que sirva como punto de entrada de datos para el algoritmo de
predicci ́on y que permita visualizar los resultados obtenidos.
```
Antes de introducir las preguntas de investigaci ́on, es importante definir el significado de algunos t ́erminos
clave para evaluar el desempe ̃no de los modelos de predicci ́on y la eficacia con la que cumplen su funci ́on.
Cuando un algoritmo realiza una predicci ́on, podemos encontrarnos con cuatro casos:

```
True Positive(TP): el modelo predice que labuildfallar ́a y, efectivamente, falla.
```
```
True Negative(TN): el modelo predice que labuildpasar ́a y, efectivamente, pasa.
```
```
False Positive(FP): el modelo predice que labuildfallar ́a, pero en realidad pasa.
```
```
False Negative(FN): el modelo predice que labuildpasar ́a, pero en realidad falla.
```
```
TP FN
```
```
FP TN
```
```
La build falla
```
```
La build pasa
```
## Valores reales

## Valores predichos

```
0
```
```
0
```
```
1
```
```
1
```
```
La build falla
```
```
La build pasa
```
```
0 ≡failure
1 ≡pass
```
```
Figura 2.Matriz de confusi ́on.
```
```
Con estos conceptos en mente, podemos definir las siguientes m ́etricas de evaluaci ́on:
```
```
Accuracy: mide la proporci ́on de predicciones correctas realizadas por el modelo. Se calcula como la suma
de los verdaderos positivos y verdaderos negativos dividida entre el total de predicciones realizadas.
```
#### ACC=

#### TP+TN

#### TP+TN+FP+FN

#### (1)


```
Precision: mide la proporci ́on de predicciones positivas correctas realizadas por el modelo. Se calcula
como la suma de los verdaderos positivos dividida entre la suma de los verdaderos positivos y falsos
positivos.
P=
```
#### TP

#### TP+FP

#### (2)

```
Recall: mide la proporci ́on de instancias positivas que el modelo predice correctamente. Se calcula como
la suma de los verdaderos positivos dividida entre la suma de los verdaderos positivos y falsos negativos.
```
#### R=

#### TP

#### TP+FN

#### (3)

```
F1-score: es la media arm ́onica deprecisionyrecall.
```
#### F1 = 2×

#### P×R

#### P+R

#### (4)

Las preguntas de investigaci ́on delimitan el alcance del estudio y ayudan a enfocar el trabajo en aspectos
espec ́ıficos del tema a investigar, evitando que nos desviemos hacia otras ́areas no relevantes. Ayudan a
clarificar qu ́e se quiere lograr con la investigaci ́on y gu ́ıan en el proceso metodol ́ogico, es decir, dependiendo de
las preguntas de investigaci ́on, podremos determinar si necesitamos una metodolog ́ıa cuantitativa, cualitativa
o mixta. Adem ́as, estas tienen una funci ́on estructutural, ya que las secciones y cap ́ıtulos siempre ir ́an
orientados a responder estas preguntas. A continuaci ́on se detallan las preguntas de investigaci ́on junto a las
m ́etricas usadas para su evaluaci ́on:

```
PI-1: ¿Qu ́e algoritmo de predicci ́on produce los mejores resultados en la predicci ́on autom ́atica del re-
sultado de la integraci ́on continua?
```
```
M ́etrica:accuracy,precision,recallyF1-scoredel modelo.
```
```
PI-2: ¿Qu ́e caracter ́ısticas de lasbuildsson m ́as significativas en la predicci ́on?
```
```
M ́etrica: importancia de cadafeaturea trav ́es de la interpretaci ́on de los coeficientes del modelo.
```
Finalmente, queda mencionar que en un modelo entrenado con una serie defeatures, los coeficientes
del modelo representan la relaci ́on cuantitativa entre cadafeaturey la variable objetivo, en este caso, la
predicci ́on del resultado de labuild. Por tanto, los coeficientes indican c ́omo se espera que cambie el valor de
la predicci ́on cuando la correspondientefeaturecambia, manteniendo constante el resto de caracter ́ısticas.

## 4. Descripci ́on del problema

La Integraci ́on Continua (CI) es una pr ́actica esencial en el desarrollo desoftwaremoderno, que busca
automatizar la fusi ́on de cambios de c ́odigo mediante la ejecuci ́on de pruebas autom ́aticas. Esta pr ́actica
permite detectar errores de forma temprana y mejorar la calidad delsoftware, facilitando una integraci ́on
m ́as frecuente y r ́apida del trabajo de los desarrolladores. Aunque la CI ofrece numerosas ventajas, su im-
plementaci ́on conlleva significativos costos computacionales asociados, especialmente en empresas de gran
tama ̃no donde se ejecutan un elevado n ́umero debuildsdiariamente. Estos costos no solo incluyen el costo
de recursos de c ́omputo para ejecutar lasbuilds, sino tmabi ́en el tiempo de espera al que se pueden enfrentar
los desarrolladores durante el proceso de integraci ́on.

El objetivo principal de este trabajo es abordar el problema de la optimizaci ́on de costos computacionales
en CI mediante la predicci ́on autom ́atica del resultado de lasbuilds. Se utilizar ́an algoritmos deMachine
Learningpara predecir si unabuildconcreta pasar ́a o fallar ́a antes de ser ejecutada. En especial, nos centra-
remos en predecir lasbuildsque fallan, ya que son las m ́as valiosas para los desarrolladores y de las cuales


depende la puesta en producci ́on o no delsoftware. Este enfoque permite mantener la detecci ́on temprana
de errores, que es el objetivo fundamental de CI, mientras se reduce el consumo de recursos computacionales.

Por lo tanto, este estudio se centra en desarrollar un modelo predictivo que permita optimizar el proceso
de Integraci ́on Continua. Se pretende:

```
Implementar un algoritmo de aprendizaje autom ́atico que permita predecir los resultados de lasbuilds
bas ́andose en un conjunto de caracter ́ısticas. Se probar ́an varios algoritmos para determinar cu ́al es el
que mejor resultados ofrece en nuestro problema.
```
```
Analizar y seleccionar las caracter ́ısticas m ́as significativas que influyen en la predicci ́on. Para lo cual,
se realizar ́a un estudio de lasfeaturespresentadas en otros estudios y se a ̃nadir ́an otras que puedan ser
relevantes para nuestro problema.
```
```
Evaluar la importancia que cadafeaturetiene sobre el modelo de predicci ́on, lo que permitir ́a a los desa-
rrolladores identificar qu ́e aspectos de lasbuildsson m ́as significativos en la predicci ́on de su resultado.
```
## 5. Detalles de la propuesta

En este apartado, se dar ́a una visi ́on global del contenido y funcionamiento de nuestra propuesta. Se
realizar ́a una descripci ́on completa de nuestro enfoque, desde los conceptos de IA empleados hasta las he-
rramientas y tecnolog ́ıas empleadas para su resoluci ́on. En primer lugar, se detalla c ́omo se ha realizado la
generaci ́on de los modelos, los tipos utilizados y sus caracter ́ısticas, as ́ı como cualquier concepto relacionado.
Posteriormente, se describen las t ́ecnicas empleadas para evaluar el rendimiento de los modelos. Continua-
remos con la explicaci ́on en detalle de lasfeaturesempleadas, qu ́e representan y c ́omo se ha realizado su
c ́alculo. Finalmente, procederemos a explicar detalles t ́ecnicos de la implementaci ́on, como las tecnolog ́ıas y
recursos empleados, el procedimiento de extracci ́on de datos, el entorno de ejecuci ́on, etc. En los siguientes
apartados se describe con detalle cada uno de estos puntos.

### 5.1. Construcci ́on del modelo

El Aprendizaje Autom ́atico (Machine Learning, ML) es un campo de la Inteligencia Artificial que se
centra en desarrollar algoritmos y modelos que sean capaces de aprender y mejorar su desempe ̃no en tareas
espec ́ıficas a partir de datos, sin la necesidad de ser expl ́ıcitamente programadas. Los sistemas de ML iden-
tifican patrones en los datos y utilizan estos patrones para hacer predicciones o tomar decisiones sobre los
datos. Podemos encontrarnos con dos tipos de aprendizaje autom ́atico:

```
Supervisado: en este tipo de aprendizaje el modelo es entrenado utilizando un conjunto de datos
etiquetados. En este contexto “etiquetado” significa que cada instancia en el conjunto de datos viene con
una entrada (conjunto de caracter ́ısticas) y una salida conocida (etiqueta o valor objetivo). En nuestro
problema, la entrada ser ́ıa el conjunto de caracter ́ısticas (features) que vamos a usar y, la salida, el
resultado de la integraci ́on continua (exitosa o fallida).
No supervisado: en este tipo de aprendizaje el modelo es entrenado utilizando un conjunto de datos
que no tiene etiquetas ni salidas predefinidas. A diferencia del supervisado, en el que se indica al modelo
lo que debe predecir, en el no supervisado el modelo explora los datos en busca de patrones, estructuras,
o relaciones ocultas.
```
Teniendo esto en cuenta, nos encontramos claramente ante un problema de aprendizaje supervisado, ya
que tenemos las caracter ́ısticas propias de cadabuild, que ser ́ıa el conjunto de entrada que proporcionamos
al modelo y, por otro lado, los resultados de las ejecuciones, que conformar ́ıan las etiquetas o valores objetivo
de nuestro problema.


Para poder responder a la pregunta de investigaci ́onPI-1, debemos explorar los distintos algoritmos de
Aprendizaje Autom ́atico que existen y ver cu ́al de ellos ofrece mejores resultados en el problema que nos
ocupa. En nuestro caso, nos encontramos con un claro problema de clasificaci ́on binaria en el ́ambito del
aprendizaje autom ́atico supervisado. En este contexto, tenemos dos clases posibles:

```
1.Clase positiva(fallo de labuild): predicci ́on de que labuildfallar ́a.
```
```
2.Clase negativa( ́exito de labuild): predicci ́on de que labuildtendr ́a ́exito.
```
Por lo tanto, dado que nos encontramos con este tipo de problema, se ha decidido utilizar seis algoritmos
de clasificaci ́on supervisada, entre los que nos encontramos:

```
1.Arboles de Decisi ́on ( ́ Decision Trees, DT). Dividen el conjunto de datos en subconjuntos m ́as
peque ̃nos y m ́as simples, bas ́andose en ciertas caracter ́ısticas o condiciones, que est ́an representadas en
un gr ́afico similar a un ́arbol. Cada nodo interno del ́arbol representa una caracter ́ıstica (o atributo), y
cada rama representa el resultado de la partici ́on de los datos en funci ́on de esa caracter ́ıstica. Las hojas
del ́arbol contienen las etiquetas o valores objetivo.
```
```
2.Bosques Aleatorios (Random Forest, RF). Es un algoritmo de aprendizaje supervisado que crea
un conjunto de ́arboles de decisi ́on durante el entrenamiento y realiza la predicci ́on promediando las
predicciones de cada ́arbol individual. Es una t ́ecnica de ensamblaje que combina m ́ultiples modelos de
aprendizaje para mejorar la precisi ́on y la estabilidad del modelo.
```
```
3.Regresi ́on Log ́ıstica (Logistic Regression, LR). Es un algoritmo de clasificaci ́on que se utiliza para
predecir la probabilidad de que una variable dependiente pertenezca a una categor ́ıa particular. Aunque
se llama regresi ́on, en realidad es un algoritmo de clasificaci ́on binaria.
```
```
4.M ́aquinas de Vectores de Soporte (Support Vector Machines, SVM). Es un algoritmo de cla-
sificaci ́on que busca encontrar el hiperplano que mejor divide un conjunto de datos en dos clases. El
hiperplano es la l ́ınea que maximiza el margen entre las dos clases. Si los datos no son linealmente se-
parables, se puede utilizar un truco matem ́atico llamadokernel trickpara transformar los datos en un
espacio de mayor dimensi ́on donde s ́ı sean separables.
```
```
5.Vecinos m ́as Cercanos (K-Nearest Neighbors, KNN). Es un algoritmo de clasificaci ́on que se basa
en la idea de que los puntos de datos que son similares deben pertenecer a la misma clase. Para predecir
la clase de un nuevo punto de datos, el algoritmo busca loskpuntos de datos m ́as cercanos en el conjunto
de entrenamiento y asigna la clase m ́as com ́un entre esos vecinos.
```
```
6.Redes Neuronales (Neural Networks, NN). Son un conjunto de algoritmos de aprendizaje au-
tom ́atico que intentan imitar el funcionamiento del cerebro humano. Consiste en una red de nodos
interconectados, llamados neuronas, que se organizan en capas. Est ́a formada por una capa de entrada,
una o varias capas ocultas y una capa de salida. Cada nodo est ́a conectado a los dem ́as y tiene su propia
ponderaci ́on y umbral asociados. Concretamente, se ha utilizado un Perceptr ́on Multicapa, que es un
tipo de red neuronal utilizado para tareas de clasificaci ́on. Cada neurona en un MLP se conecta a las de
la capa anterior con pesos y aplica una funci ́on de activaci ́on a su suma ponderada.
```
Para realizar la predicci ́on, no ́unicamente se le proporciona al modelo el conjunto de caracter ́ısticas de
labuildy se predice, si no que se sigue un procedimiento m ́as complejo y que simula el funcionamiento de
SmartBuildSkip [9]. Para comprenderlo, veamos el siguiente pseudoc ́odigo:


Algorithm 1SmartBuildSkip con nuestra implementaci ́on
1:Input:List of builds
2:Output:Predictions of builds outcomes
3: infailuresequence←False .Inicializar estado de secuencia de fallos
4:foreach build in buildsdo
5: ifinfailuresequencethen
6: Prediction←Fail .Predicci ́on autom ́atica de fallo
7: ifbuild passesthen .Comprobar resultado
8: infailuresequence←False .Error en la predicci ́on, vuelve a predecir con ML
9: end if
10: else
11: Prediction←Machine Learning Prediction .Predicci ́on usando ML
12: ifPrediction = Passthen
13: Accumulate changes with next build .Se salta la build, acumulando cambios
14: else
15: ifbuild failsthen .Comprobar resultado
16: infailuresequence←True .Entra en predicci ́on autom ́atica de fallo
17: end if
18: end if
19: end if
20:end for

Como podemos observar, este algoritmo se divide en dos partes: una en la que predice autom ́aticamente
que labuildfallar ́a y otra en la que se realiza la predicci ́on mediante el uso de un modelo de aprendizaje
autom ́atico. Esta forma de proceder es debida a las dos hip ́otesis que comentamos en la Secci ́on 2.2, que
muchasbuildsfallan consecutivamente despu ́es de que otra haya fallado y que lasbuildsexitosas siempre
son m ́as numerosas que las fallidas. Esto hace que nuestro algoritmo pueda saltarse mayor n ́umero debuilds
a la vez que captura una mayor cantidad debuild failures. Consecuentemente, debido a la no ejecuci ́on de
estasbuilds, se estar ́a logrando una optimizaci ́on de recursos computacionales.

5.1.1. Hiperpar ́ametros. Cuando se define un algoritmo de clasificaci ́on, es importante seleccionar y
ajustar con cuidado los hiperpar ́ametros, ya que estos controlan aspectos clave del proceso de entrenamiento
y pueden determinar la capacidad del modelo para generalizar a nuevos datos. Para la definici ́on de nuestros
algoritmos de clasificaci ́on, se ha utilizado la bibliotecascikit-learn, una popular biblioteca dePythonpara
Machine Learningy an ́alisis de datos. Por lo general, se han definido todos los algoritmos con los par ́ametros
por defecto de la bibliotecascikit-learn, con las siguientes particularidades:

```
En un conjunto de datos que contienebuilds, donde el n ́umero debuildsexitosas es mucho mayor que el
debuildsfallidas, estamos ante un problema de desequilibrio de clases. En este contexto, asignar distintos
pesos a las clases es una estrategia ́util para entrenar un modelo que sea m ́as sensible en la detecci ́on de
builds failures, a pesar de ser poco numerosas. Para ello, se ha definido un peso de 20:1 a favor de las
build failuresenArbol de Decisi ́on, Bosque Aleatorio, Regresi ́on Log ́ıstica y M ́aquinas de Vectores de ́
Soporte.
```
```
En Regresi ́on Log ́ıstica, se establece el n ́umero m ́aximo de iteraciones que el algoritmo de optimizaci ́on
realizar ́a antes de detenerse. En este caso se utiliza el valor 15000 para asegurar que el algoritmo tenga
suficiente tiempo para converger.
```
```
En el algoritmo de M ́aquinas de Vectores de Soporte, hemos a ̃nadido el hiperpar ́ametro que habilita el
c ́alculo de probabilidades de pertenencia a cada clase. Cuando el par ́ametroprobabilityest ́a habilitado,
el modelo ajusta de manera interna un modelo de probabilidad, permitiendo que las salidas del modelo
```

```
sean las etiquetas de clase y sus probabilidades.
```
```
Para el Perceptr ́on Multicapa (redes neuronales), se ha a ̃nadido, al igual que en Regresi ́on Log ́ıstica, un
par ́ametro que indica el n ́umero m ́aximo de iteraciones para entrenar la red neuronal. En este caso, se
ha a ̃nadido con un valor de 15000.
```
Adem ́as de los par ́ametros antes mencionados, todos ellos tienen definida la semilla de reproducibilidad,
que garantiza que los resultados sean reproducibles.

### 5.2. Evaluaci ́on del modelo

La evaluaci ́on de los modelos de clasificaci ́on tiene como objetivo medir y analizar el rendimiento de los
modelos en la tarea de clasificaci ́on. Esta evaluaci ́on permite identificar con qu ́e precisi ́on el modelo puede
predecir o clasificar nuevas instancias no vistas anteriormente, es decir, bas ́andose en un conjunto de datos de
prueba. Para realizar la evaluaci ́on de los modelos en nuestro problema, hemos seguido los siguientes pasos:

```
1.Divisi ́on del conjunto de datos: se divide el conjunto de datos, en este casofeaturesde cadabuild,
en dos partes: el conjunto de entrenamiento y el conjunto de prueba. El conjunto de entrenamiento se
utiliza para entrenar el modelo, mientras que el conjunto de prueba se usa para evaluar su rendimiento.
Dada la naturaleza de nuestro problema, no podemos hacer esta divisi ́on de manera aleatoria, ya que
lasbuildsest ́an relacionadas temporalmente entre s ́ı, por lo que no ser ́ıa realista realizar una predicci ́on
sobre una instancia antigua bas ́andonos enbuildsque se hayan ejecutado recientemente. Por lo tanto,
en nuestro caso se ha dividido el conjunto de datos igualmente en dos partes, pero siendo el conjunto de
entrenamiento m ́as antiguo en su conjunto que el conjunto de prueba, que es m ́as reciente. Por ejemplo,
si se dividen los datos de entrenamiento y test en un 80 % y 20 % respectivamente, el conjunto de entre-
namiento contendr ́a el 80 % de lasbuildsm ́as antiguas, mientras que el de prueba contendr ́a el 20 % de
buildsm ́as reciente.
```
```
2.Predicci ́on: una vez entrenado el modelo con el conjunto de entrenamiento, se realizan predicciones
sobre el conjunto de prueba. Gracias a estas predicciones, podremos verificar si nuestros modelos se
comportan bien frente a instancias nuevas o no vistas con anterioridad.
```
```
3.M ́etricas de evaluaci ́on: una vez realizadas las predicciones, hemos definido las m ́etricas de evaluaci ́on,
que nos ayudar ́an a determinar el rendimiento de nuestros modelos. Las m ́etricas que hemos usado son:
accuracy,precision,recall,F1-score,confusion matrixy ROCcurve. Todas ellas han sido descritas en la
Secci ́on 3, exceptuando el ́area bajo la curva ROC (Area Under the Curve, AUC), que mide la capacidad
de un modelo para distinguir entre clases positivas y negativas. Cuanto mayor sea el valor de AUC, mejor
ser ́a el desempe ̃no del modelo en la clasificaci ́on, ya que esta indica una mayor capacidad para separar
correctamente las clases.
```
5.2.1. Validaci ́on Cruzada. La validaci ́on cruzada (cross-validation) es una t ́ecnica utilizada para la
evaluaci ́on y selecci ́on de modelos, midiendo su rendimiento y capacidad de generalizaci ́on. Su objetivo prin-
cipal es evitar el sobreajuste (overfitting), que ocurre cuando un modelo aprende demasiado de los datos de
entrenamiento y es incapaz de generalizar a nuevos datos. Esta consiste en dividir el conjunto de datos enk
subconjuntos (folds), entrenar el modelo enk−1 subconjuntos y evaluarlo en el subconjunto restante. Este
proceso se repitekveces, de forma que cada subconjunto se utiliza una vez como conjunto de prueba. Al final,
se promedian los resultados de laskiteraciones para obtener una estimaci ́on m ́as precisa del rendimiento del
modelo.

En nuestro caso particular, hemos tenido que hacer una ligera variaci ́on de esta t ́ecnica. En nuestro pro-
blema, la divisi ́on del conjunto de datos enksubconjuntos no puede realizarse de manera aleatoria, ya que no
tendr ́ıa sentido realizar predicciones para instancias m ́as antiguas utilizando para el entrenamiento instancias


m ́as recientes. Es decir, en nuestro problema existe una dependencia temporal y, por tanto, la secuencia y
el orden de los datos son cr ́ıticos para la validez de las predicciones. Los resultados y caracter ́ısticas de las
buildsest ́an influenciados por lasbuildsanteriores. Esto se debe a que cadabuildpuede depender de cambios
de c ́odigo, configuraciones y otros factores que se acumulen o evolucionen con el tiempo. Por lo tanto, si se
permite que lasbuildsm ́as antiguas predigan utilizando informaci ́on debuildsm ́as recientes, se introducir ́ıa
un sesgo temporal que no reflejar ́ıa el comportamiento real del sistema. Adem ́as de esto, usar datos debuilds
futuras para predecirbuildsantiguas no solamente introduce un sesgo, si no que tambi ́en puede dar una falsa
impresi ́on de precisi ́on del modelo, llevando a resultados artificialmente inflados de precisi ́on durante esta
fase de evaluaci ́on.

En nuestra implementaci ́on dividimos el conjunto en 11 partes de forma secuencial, de modo que el pri-
mer subconjunto contenga lasbuildsm ́as antiguas y el ́ultimo lasbuildsm ́as recientes. El subconjunto de
foldsse recorre y en cada iteraci ́on, se entrena con la acumulaci ́on de subconjuntos anteriores, y se eval ́ua
con el siguiente subconjunto, dejando el resto de subconjuntos sin utilizar. Siempre que se tengankfoldsse
realizar ́ank−1 iteraciones, ya que en la ́ultima iteraci ́on se utilizar ́a el ́ultimo subconjunto como conjunto de
prueba. Finalmente, dado que se habr ́an obtenido 10 resultados de las m ́etricas de evaluaci ́on, se promedian
para obtener una estimaci ́on m ́as precisa del rendimiento del modelo.

A continuaci ́on, se presenta de forma gr ́afica el funcionamiento de nuestro algoritmo dek-fold cross-
validation:

```
Fold 1
```
```
Unused folds Training data Test data
```
```
Fold 2 Fold 3 Fold 4 Fold 11
```
```
Fold 1 Fold 2 Fold 3 Fold 4 Fold 11
```
```
Fold 1 Fold 2 Fold 3 Fold 4 Fold 11
```
```
Fold 1 Fold 2 Fold 3 Fold 4 Fold 11
```
```
Split 1
```
```
Split 10
```
```
Split 3
```
```
Split 2
```
```
Figura 3.Funcionamiento de la t ́ecnicak-fold cross-validation.
```
5.2.2. Umbral de decisi ́on.La evaluaci ́on de los modelos a distintos grados de sensibilidad es especial-
mente relevante cuando se consideran problemas de clasificaci ́on con clases desbalanceadas o cuando el costo
de los errores var ́ıa entre clases. En el problema que nos ocupa, se dan ambas condiciones: por lo general, el
n ́umero debuildsexitosas es muy superior al debuildsfallidas y, el costo de predecir un falso negativo no es
el mismo que el de predecir un falso positivo. Al ajustar la sensibilidad del modelo, se balancean las tasas
de verdaderos positivos (recall) y falsos positivos, lo que permite optimizar el rendimiento del modelo para
diferentes contextos y necesidades. El hecho de variar el umbral de decisi ́on permite al desarrollador decidir
hasta qu ́e punto est ́a dispuesto a obtener falsos positivos en las predicciones. Por ejemplo, si se asigna un
umbral de decisi ́on bajo, se aumentar ́an las tasas de verdaderos positivos, pero tambi ́en aumentar ́a el n ́umero
de falsos positivos, es decir, el algoritmo predecir ́a un mayor n ́umero de veces que labuildfalla, haciendo
al desarrollador ejecutarbuildsque realmente no fallaban. Por otro lado, si se asigna un umbral de decisi ́on
m ́as conservador, se reducir ́an los falsos positivos, pero tambi ́en con el riesgo de predecir algunabuildcomo


exitosa cuando realmente no lo es, teniendo el caso del falso negativo.

Muchos algoritmos de aprendizaje autom ́atico pueden predecir una probabilidad de pertenencia a una
clase. Esto es ́util porque proporciona una medida de la certeza o incertidumbre de una predicci ́on y ofrece
m ́as detalles que solo predecir la etiqueta de la clase. En nuestro problema, es necesario convertir estas pro-
babilidades en el valor de una clase. Esta conversi ́on se basa en un par ́ametro llamado “umbral de decisi ́on”.
El valor por defecto de este umbral es 0,5 para probabilidades normalizadas en el intervalo [0,1]. Por ejemplo,
dadas las etiquetas de nuestro problema: 0 (labuildfalla) y 1 (labuildpasa), si la probabilidad de que una
buildfalle es igual o mayor a 0,5, se predecir ́a que labuildes exitosa, mientras que si es menor a 0,5, se
predecir ́a que labuildfalla.

En nuestra implementaci ́on, hemos analizado el rendimiento de todos los modelos y sus variantes para
diferentes valores del umbral de decisi ́on dentro del rango [0,1]. Para ello, hemos calculado las m ́etricas de
evaluaci ́on en cada valor del umbral, lo que nos ha permitido identificar cu ́al de los algoritmos de clasificaci ́on
ofrece el mejor rendimiento. Como resultado de este an ́alisis, hemos determinado que el modelo basado en
́arboles de decisi ́ones el que obtiene los mejores resultados en t ́erminos deprecisionyrecall. Por lo tanto,
este ser ́a el algoritmo de clasificaci ́on predeterminado que utilizar ́a JAES24.

### 5.3. Featuresempleadas

Lasfeatureso caracter ́ısticas son las propiedades o atributos que se utilizan como entrada para entrenar
un modelo. Son elementos fundamentales que permiten al modelo aprender patrones y tomar decisiones
basadas en los datos. Lasfeaturesrecogen informaci ́on relevante de los datos, en este caso de lasbuilds. La
calidad y relevancia de las mismas afecta al rendimiento del modelo, por lo que escoger las adecuadas es
fundamental. Al hacer la selecci ́on de lasfeatures, hay que tener en cuenta lo siguiente:

```
Elegirfeaturesque sean relevantes y representativas del problema es importante para que el modelo sea
preciso y eficiente. Adem ́as, ayuda a reducir la dimensionalidad del problema, lo que puede mejorar la
eficiencia computacional y la interpretabilidad del modelo.
```
```
Seleccionar gran cantidad defeaturespuede llevar a un sobreajuste del modelo, donde el modelo aprende
de patrones de datos ruidosos o irrelevantes. Esto puede llevar a un rendimiento bajo y a modelos menos
generalizables
```
A continuaci ́on, se presentan las features estudiadas en nuestro problema.


```
Tabla 1.Build features.
```
```
Clasificaci ́on Feature Descripci ́on breve
Consideradas y
utilizadas en
SmartBuildSkipy
JAES
```
```
Number Commits(NC) El n ́umero decommits desde la ́ultima build.
```
```
Files Changed(FC)
```
```
El n ́umero de archivos modificados desde la
́ultimabuild, incluyendo archivos a ̃nadidos,
modificados y eliminados.
```
```
Source Lines Changed(LC)
```
```
El n ́umero de l ́ıneas de c ́odigo modificadas desde
la ́ultimabuild, incluyendo l ́ıneas a ̃nadidas y
eliminadas.
```
```
Test Lines Changed(LT)
```
```
El n ́umero de l ́ıneas de c ́odigo detest
modificadas desde la ́ultimabuild, incluyendo
l ́ıneas a ̃nadidas y eliminadas.
Consideradas en
SmartBuildSkip,
pero no utilizadas
```
```
Performance Short(PS)
La proporci ́on debuildsexitosas en las ́ultimas
cincobuilds.
Performance Long(PL)
La proporci ́on debuildsexitosas de todas las
buildsprevias.
Failure Distance(FD)
El n ́umero debuildsexitosas desde la ́ultima
buildfallida.
Consideradas en
SmartBuildSkipy
utilizadas en
JAES
```
```
Time Frequency(TF)
El intervalo de tiempo en horas desde la ́ultima
build.
Week Day(WD)
El d ́ıa de la semana en el que se ha ejecutado la
build.
Day Hour(DH) La hora del d ́ıa en la que se ha ejecutado labuild.
```
```
Nuevas consideradas
en este estudio, pero
no utilizadas
```
```
Files Added(FA) El n ́umero de archivos a ̃nadidos desde la ́ultima
build.
Files Modified(FM) El n ́umero de archivos modificados desde la
́ultimabuild.
Files Removed(FR) El n ́umero de archivos modificados desde la
́ultimabuild.
Unit Tests(UT) Si se han escrito pruebas unitarias desde la
́ultimabuild.
Commit Delay(CD) El tiempo transcurrido en horas entrecommits
de una mismabuild.
Nuevas consideradas
y utilizadas en este
estudio
```
```
Source Lines Removed(LR)El n ́umero de l ́ıneas de c ́odigo eliminadas desde
la ́ultimabuild.
Source Lines Added(LA)
El n ́umero de l ́ıneas de c ́odigo a ̃nadidas desde la
́ultimabuild.
```
Como vemos en la Tabla 1, lasfeaturesque se encuentran en la primera clasificaci ́on, son aquellas que
han sido consideradas enSmartBuildSkip[9] y que han sido utilizadas tanto en ́el, como en nuestro enfoque,
JAES24. Lasfeaturesque se encuentran en la segunda clasificaci ́on, fueron consideradas enSmartBuildSkip,
pero finalmente no fueron utilizadas. Continuando con la clasificaci ́on, las features que se encuentran en la
tercera divisi ́on, fueron consideradas porSmartBuildSkippor primera vez, pero solo utilizadas en JAES24.
Finalmente, en las dos ́ultimas clasificaciones, se presentanfeaturesnuevas consideradas en este estudio,
teniendo que ́unicamente fueron utilizadas las de la ́ultima clasificaci ́on.

Para el c ́alculo de lasfeaturesmencionadas en la Tabla 1, debemos tener en cuenta los siguientes aspectos:

```
Informaci ́on para el entrenamiento: cuando obtenemos las caracter ́ısticas de lasbuildsdirectamente
desde el repositorio de c ́odigo fuente, tenemos acceso a la informaci ́on completa de cada una de ellas. El
c ́alculo de lasfeatureses sencillo y directo, ya que podemos acceder a la informaci ́on de cadabuildque
se ha ejecutado y extraer las caracter ́ısticas necesarias.
```

```
C ́alculo de Features durante la predicci ́on: debemos recordar que, en el enfoque que planteamos,
a veces no se ejecutan todas lasbuildsque se han programado. Por lo tanto, no siempre se tiene acceso
a la informaci ́on real (Ground Truth) de haber ejecutado lasbuilds.Featurescomo elperformance short,
elperformance longo elfailure distancedeben ser calculadas de forma diferente para poder simular un
comportamiento pr ́actico real.
```
```
Normalizaci ́on: es importante normalizar lasfeaturesantes de entrenar el modelo. La normalizaci ́on es
un proceso que ajusta los valores de lasfeaturespara que tengan una escala com ́un. Esto es importante
porque muchos algoritmos de aprendizaje autom ́atico son sensibles a la escala de lasfeaturesy pueden
dar resultados incorrectos si lasfeaturestienen escalas muy diferentes. En nuestra implementaci ́on, hemos
utilizado dos m ́etodos de normalizaci ́on:
```
1. Normalizaci ́onMin-Max: como comentamos, es una t ́ecnica de escalado de datos que transforma los
    valores de un conjunto de datos dentro de un rango espec ́ıfico, normalmente en el intervalo [0,1],
    como en nuestro caso. La f ́ormula para la normalizaci ́onMin-Maxes la siguiente:

```
Ni=
```
```
Xi−Xmin
Xmax−Xmin
```
#### (5)

2. Normalizaci ́onZ-scoreo estandarizaci ́on: esta t ́ecnica transforma los valores de un conjunto de datos
    a una distribuci ́on con media 0 y desviaci ́on est ́andar 1. Para ello, se resta a cada valor la media de
    los datos y se divide entre la desviaci ́on est ́andar. La f ́ormula para la normalizaci ́onZ-scorees la
    siguiente:

```
Ni=
```
```
Xi−μ
σ
```
#### (6)

```
En nuestro caso, hemos utilizado un tipo de normalizaci ́on u otro en funci ́on del modelo de clasificaci ́on
que estemos utilizando. Por ejemplo, hemos usado normalizaci ́onMin-Maxparakvecinos m ́as cercanos
y para redes neuronales, y normalizaci ́onZ-scorepara regresi ́on log ́ıstica y m ́aquinas de vectores de
soporte. Adem ́as, queda a ̃nadir que no se ha utilizado normalizaci ́on en ́arboles de decisi ́on ni en bosques
aleatorios, ya que estos modelos crean reglas basadas en comparaciones entre valores de las caracter ́ısticas
y no en sus magnitudes, lo que hace que la escala de las caracter ́ısticas no afecte a su rendimiento.
```
En el proceso de selecci ́on defeaturespara nuestro modelo de clasificaci ́on, se ha realizado un an ́alisis
exhaustivo de las variables disponibles, con el objetivo de optimizar el rendimiento, reducir la complejidad y
mejorar la generalizaci ́on del modelo. Tras evaluar diversas combinaciones defeaturesy analizar su impacto
en las m ́etricas de evaluaci ́on, se ha seleccionado el subconjunto defeaturesTF,NC,FC,LC,LA,LR,
LT,WDyDH. Las razones para su selecci ́on son:

```
1.Mejora del rendimiento del modelo: el subconjunto defeatureselegido demostr ́o una clara mejora
en el rendimiento del modelo. Las m ́etricas de evaluaci ́on mejoraron en t ́erminos deprecisionyrecall.
```
```
2.Reducci ́on de la complejidad: la selecci ́on de este subconjunto reduce la complejidad del problema,
lo que nos permite simplificar tanto el entrenamiento del modelo como su interpretaci ́on. Adem ́as, la
utilizaci ́on de un n ́umero excesivo defeaturesresultaba en la adici ́on de ruido al problema.
```
```
3.Relevancia de lasfeatures: lasfeaturesseleccionadas no solo ofrecen mejores resultados desde el punto
de vista cuantitativo, sino que tienen sentido desde nuestra perspectiva pr ́actica. La captura del momento
en el que se realiza la contribuci ́on, junto al desgranado de los cambios realizados, tienen relevancia en
la predicci ́on.
```

5.3.1. C ́aculo defeaturesdurante la predicci ́on.Para comprender bien este punto, vamos a diferen-
ciar dos conceptos fundamentales: labuildpropuestay labuildejecutada. Labuildpropuesta es aquella
que se desea predecir, independientemente de lo que prediga el algoritmo de predicci ́on, y que por lo tanto
todav ́ıa no ha sido ejecutada. Labuildejecutada es aquella que previamente era unabuildpropuesta (a pre-
decir) y que ha sido ejecutada porque el algoritmo predijo que fallar ́ıa. Teniendo claros estos dos conceptos,
pasemos a la explicaci ́on del c ́alculo de lasfeaturesmencionadas anteriormente:

```
Performance Short(PS): para calcular este porcentaje debuildsexitosas en las ́ultimas cincobuilds,
cuando el algoritmo predice que labuildpropuesta pasar ́a, se salta la ejecuci ́on de labuildy se asume
que el algoritmo ha acertado. Cuando el algoritmo predice que labuildpropuesta fallar ́a, labuildse
ejecutar ́a y, podremos ver el resultado real de la CI, considerando dicho valor.
```
```
Performance Long(PL): al igual que en el caso anterior, se calcula el porcentaje debuildsexitosas
de todas lasbuildspropuestas hasta el momento. Si el algoritmo predice que labuildpropuesta pasar ́a,
se asume que ha acertado y si predice que fallar ́a, se ejecuta labuildy se considera el resultado real.
```
```
Failure Distance(FD): se calcular ́a como el n ́umero debuildsexitosas desde la ́ultimabuildfallida.
Si el algoritmo predice que labuildpropuesta pasar ́a, se asume que ha acertado y si predice que fallar ́a,
se ejecuta labuildy se considera el resultado real.
```
A continuaci ́on, se representa de forma gr ́afica el c ́alculo de cada uno de ellos:

#### ?? F? F? F P F? P?

#### P P F P F P F F F P F P

```
No puede saberse su resultado real porque no se ha ejecutado, se ha saltado
```
```
Saltada
```
```
Valores reales
```
```
Valores predichos
```
```
Ejecutada PS = 4/5 * 100 = 80%
Se consideran los valores reales
```
```
Figura 4.C ́aculo delPerformance Short.
```
#### ?? F? F? F P F? P?

#### P P F P F P F F F P F P

```
Saltada
```
```
Valores reales
```
```
Valores predichos
```
```
EjecutadaPL = 8/12 * 100 = 66,66%
Se consideran los valores reales
```
```
No puede saberse su resultado real porque no se ha ejecutado, se ha saltado
```
```
Figura 5.C ́aculo delPerformance Long.
```

#### ?? F? F? F P F? P?

#### P P F P F P F F F P F P

```
No puede saberse su resultado real porque no se ha ejecutado, se ha saltado
```
```
Saltada
```
```
Valores reales
```
```
Valores predichos
```
```
Ejecutada FD = 3
Se consideran los valores reales
```
```
Build fallida
```
```
Figura 6.C ́aculo delFailure Distance.
```
### 5.4. Interfaz gr ́afica

En nuestro proyecto, hemos implementado una interfaz gr ́afica simple que permite a los usuarios interac-
tuar con la aplicaci ́on de forma intuitiva y sencilla, reduciendo as ́ı la interacci ́on a bajo nivel con la aplicaci ́on.
La interfaz se ha desarrollado conAngular, un framework de desarrollo de aplicaciones web desarrollado por
Google. La interfaz consta de dos partes fundamentales, por un lado, un formulario que permite a los usuarios
introducir la URL de un repositorio concreto deGitHuby la rama sobre la que desea predecir, y por otro
lado, una tabla que muestra los datos de cada uno de los repositorios indicando si se encuentran disponibles
sus modelos de predicci ́on o no.

Cuando un usuario introduce la URL de un repositorio y la rama sobre la que desea predecir, nuestra
aplicaci ́on internamente realiza los siguientes pasos:

1. Comprueba que la URL tiene un formato v ́alido de acuerdo a las URLs deGitHub.
2. Comprueba si el repositorio y rama introducidos ya eran conocidos anteriormente por la aplicaci ́on. Si
    estos se encuentran en la base de datos, se devuelve un mensaje informativo y se detiene la ejecuci ́on. Si
    el repositorio no existe en la aplicaci ́on, se crea la estructura de directorios necesaria para el almacena-
    miento de los datos relativos a ese repositorio:builds,features, modelos, gr ́aficos de evaluaci ́on, etc.
3. Si se contin ́ua con la ejecuci ́on, se procede a la extracci ́on de lasbuildsdel repositorio.
4. Una vez se han extra ́ıdo lasbuilds, se procede autom ́aticamente a la extracci ́on defeaturesa partir de
    estasbuilds.
5. Finalmente, se procede de forma autom ́atica al entrenamiento de los modelos de acuerdo a lasfeatures
    seleccionadas en nuestro enfoque. Esto genera unos modelos de predicci ́on listos para predecir.

Es importante mencionar que, todos los pasos anteriormente descritos se realizan de forma as ́ıncrona, es
decir, el usuario no tiene que esperar a que se complete un paso para poder seguir con el siguiente. Esto
ofrece la posibilidad de introducir varios repositorios a analizar de forma simult ́anea. Adem ́as, cuando se
ha realizado la extracci ́on defeatures, el programa genera autom ́aticamente los modelos de predicci ́on para
todos los algoritmos de clasificaci ́on estudiados en la Secci ́on 5.1. Esto hace que el usuario no tenga que
preocuparse de seleccionar un algoritmo de clasificaci ́on en concreto, ya que la aplicaci ́on autom ́aticamente
generar ́a el modelo asociado.

A continuaci ́on, se muestra el formulario de entrada:


```
Figura 7.Formulario de entrada.
```
Como es l ́ogico, la extracci ́on de lasbuilds, lasfeaturesy el entrenamiento de los modelos, puede llevar
un tiempo considerable. Este depende de la cantidad debuildsa extraer y de la sem ́antica de cada una de
ellas, es decir, del tipo de evento que las origina y la complejidad interna de cada una. No es similar extraer
buildsoriginadas por unpull request, que probablemente contenga mayor n ́umero decommitsy archivos
modificados, que extraerbuildsoriginadas por unpushsimple. Por lo tanto, se ha dise ̃nado una peque ̃na
tabla que recoge informaci ́on sobre el estado de cada uno de los repositorios introducidos. En ella, se muestra
el nombre del repositorio, la rama sobre la que se desea predecir, el archivo donde se almacenan lasfeatures
del repositorio, el patr ́on del nombre que seguir ́an los modelos generados y, la ́ultima y m ́as importante, si
el modelo se encuentra disponible o no.

A continuaci ́on, se muestra la tabla de repositorios:

```
Figura 8.Tabla de repositorios disponibles y el estado de sus modelos.
```

### 5.5. Detalles t ́ecnicos de la implementaci ́on

En esta secci ́on, se muestran detalles t ́ecnicos de la implementaci ́on. Se explican las tecnolog ́ıas empleadas
y las caracter ́ısticas que estas nos proporcionan para la resoluci ́on de nuestro problema, los recursos que
utilizamos para extraer lasbuildsde los repositorios y, finalmente, c ́omo se realiza la extracci ́on de las
featuresa partir de estasbuilds.

5.5.1. Tecnolog ́ıas empleadas. Para la resoluci ́on de nuestro problema, hemos decidido utilizar las
siguientes tecnolog ́ıas:

```
Docker: es una plataforma de c ́odigo abierto que nos permite crear, desplegar y ejecutar aplicaciones
en contenedores. Los contenedores son entornos de ejecuci ́on que por lo general son ligeros y port ́atiles,
conteniendo todo lo necesario para que una aplicaci ́on pueda ejecutarse. En nuestra implementaci ́on,
hemos creado tres contenedores: uno para albergar la base de datos, otro para el servidorFlaskque
contiene toda la l ́ogica de nuestra aplicaci ́on y, por ́ultimo, un contenedor para el clienteAngulardonde
residir ́a la interfaz gr ́afica.
```
```
Docker Compose: es una herramienta que nos permite definir y ejecutar aplicacionesDockerde m ́ulti-
ples contenedores. Nos permite orquestar la comunicaci ́on y ejecuci ́on de los contenedores de forma
sencilla y eficiente. Para ello, se utiliza un archivo de configuraci ́on con extensi ́on.ymldonde se definen
los servicios, redes, puertos, variables de entorno, vol ́umenes que se van a utilizar, etc. Concretamente,
se han definido tres servicios, uno para la aplicaci ́onFlask, otro paraAngulary otro para la base de datos.
```
```
Flask: es un “microframework” dePythonpara el desarrollo de aplicaciones web. Se ha elegido porque
es bastante ligero y f ́acil de usar, lo que nos permite centrarnos en la l ́ogica de la aplicaci ́on sin tener que
preocuparnos de detalles de la configuraci ́on. Adem ́as, nos permite una f ́acil gesti ́on de las dependencias,
algo fundamental para el uso de librer ́ıas comoScikit-learn,PandasoMatplotlib.
```
```
Angular: es un framework de desarrollo de aplicaciones web desarrollado porGoogle. Se ha elegido por
su arquitectura modular y porque permite crear interfaces reutilizables.
```
```
PostgreSQL: es un sistema de gesti ́on de bases de datos relacional (RDBMS) de c ́odigo abierto. Se ha
elegido por su fiabilidad, escalabilidadd y por ser muy eficiente en la gesti ́on de grandes vol ́umenes de
datos. En nuestro caso, ́unicamente se ha usado para almacenar los valores de aquellos repositorios que
han sido introducidos en la aplicaci ́on.
```
5.5.2. GitHubREST API.LaGitHubREST API [1] es una interfaz de programaci ́on de aplicaciones
(API) que permite a los desarrolladores interactuar de forma program ́atica con los servicios deGitHub. Esta
API da un soporte completo para realizar operaciones como:

```
Gesti ́on de repositorios: crear, modificar y eliminar repositorios.
```
```
Administraci ́on deissuesypull requests: crear, modificar, comentar y cerrarissuesopull requests.
```
```
Gesti ́on de usuarios y organizaciones: obtener informaci ́on de usuarios, modificar ajustes de la
cuenta, manejar miembros de organizaciones o equipos de trabajo, etc.
```
```
Automatizaci ́on de flujos de trabajo: permite la integraci ́on deGitHub con otras aplicaciones y
servicios, permitiendo lanzar flujos de trabajo de forma autom ́atica.
```

Todas estas operaciones, l ́ogicamente, se podr ́an realizar siempre y cuando los usuarios est ́en correcta-
mente autenticados y tengan los permisos necesarios en relaci ́on con los recursos sobre los que desea realizar
la operaci ́on.

En nuestra soluci ́on, hemos realizado peticiones a esta API a trav ́es del uso de la librer ́ıarequestsde
Python. Esta nos proporciona todo lo necesario para realizar peticiones HTTP de forma sencilla y eficiente.
Adem ́as, para permitir un mayor n ́umero de peticiones por minuto a esta API, hemos utilizado untokende
autenticaci ́on, que va incluido en la cabecera de cada petici ́on que realizamos.

```
Tabla 2.Endpoints de GitHub API REST usados.
```
```
Endpoint Descripci ́on
https://api.github.com/repos/OWNER/REPO/pulls
Lista todos lospull requestsde un
repositorio espec ́ıfico.
https://api.github.com/repos/OWNER/REPO/pulls/PULLNUMBER Lista los detalles de unpull request
dado su identificador num ́erico.
https://api.github.com/repos/OWNER/REPO/pulls/PULLNUMBER/commits Lista loscommitsde unpull
request concreto.
https://api.github.com/repos/OWNER/REPO/pulls/PULLNUMBER/files
Lista los archivos modificados en
unpull requestconcreto.
https://api.github.com/repos/OWNER/REPO/actions/runs Lista todas lasbuildsejecutadas
en un repositorio.
https://api.github.com/repos/OWNER/REPO/actions/runs/RUNID Lista unabuildespec ́ıfica dado su
run id.
https://api.github.com/repos/OWNER/REPO/commits/COMMITSHA
Lista uncommitespec ́ıfico dado su
valor SHA.
```
En la Tabla 2, se muestran todos losendpointsde la API deGitHubque hemos utilizado en nuestra im-
plementaci ́on. Si nos fijamos, existen partes en las urls que est ́an marcadas conOWNER,REPO,PULLNUMBER,
RUNIDyCOMMITSHA. Estos valores son par ́ametros que se deben sustituir por los valores reales de los recur-
sos sobre los que se quiere realizar la operaci ́on y que significan lo siguiente:OWNER, nombre del propietario
del repositorio, ya sea una persona o una organizaci ́on;REPO, nombre del repositorio del que se quiere obtener
informaci ́on;PULLNUMBER, n ́umero identificador de unpull request;RUNID, identificador num ́erico de una
build;COMMITSHA, valor SHA de uncommit.

Obtener todas lasbuildsque se han ejecutado en un repositorio es una tarea que puede parecer sencilla,
ya que tenemos el quintoendpointque se muestra en la Tabla 2, sin embargo, no es tan trivial como parece.
Existen algunas restricciones como el l ́ımite m ́aximo de resultados que la API puede devolver, el n ́umero de
peticiones por minuto que se pueden realizar, la paginaci ́on de los resultados, etc., que hacen este proceso
m ́as complejo. En nuestra implementaci ́on, se utiliza lo que se denomina unfine-grained personal access
token, que nos permite aumentar el n ́umero de peticiones por minuto a la API. Adem ́as, se ha implementado
paginaci ́on para realizar las peticiones, ya que ́unicamente se pueden obtener un m ́aximo de 100buildspor
p ́agina y, adem ́as, al llegar a un l ́ımite de 1000builds, la API no permite obtener m ́asbuildsde forma directa.
Finalmente, se ha considerado la posibilidad de queGitHubnos deniegue el acceso a la API por superar
el l ́ımite diario de peticiones, para lo cual guardamos el estado de ejecuci ́on del programa, para reintentar
pasado un tiempo definido la misma petici ́on.

5.5.3. Procesamiento debuilds.El procesamiento de lasbuildses el paso en el que se extraen lasfeatures
de cada una de lasbuildsextra ́ıdas en el paso anterior. Para ello, una vez lasbuildshan sido extra ́ıdas del
repositorio, estas se encuentran organizadas en un formato JSON y por ficheros correspondientes a cada uno


de los meses en los que se han ejecutado. Por ejemplo, para un proyecto llamadojunit5, susbuildsquedar ́ıan
organizadas de la siguiente forma:

```
Figura 9.Organizaci ́on de lasbuildsde un proyecto.
```
Como vemos, por cada mes en el que se han ejecutadobuilds, se ha creado un fichero JSON conteniendo
la informaci ́on de todas lasbuildsejecutadas en ese mes. Adem ́as, por formato y organizaci ́on, cada archivo
est ́a nombrado con el d ́ıa de inicio y fin del mes concreto al que pertenece.

A pesar de tener extra ́ıda la informaci ́on de lasbuilds, muchos de los datos necesarios para el c ́alculo
de algunasfeaturesno se encuentran disponibles directamente en la informaci ́on extra ́ıda.Featurescomo el
n ́umero decommits(NC), el n ́umero de archivos modificados (FC), el n ́umero de l ́ıneas de c ́odigo modifi-
cadas (LC), el n ́umero de l ́ıneas de c ́odigo detestmodificadas (LT), el n ́umero de archivos a ̃nadidos (FA),
el n ́umero de archivos modificados (FM), el n ́umero de archivos eliminados (FR), el n ́umero de l ́ıneas de
c ́odigo eliminadas (LR), el n ́umero de l ́ıneas de c ́odigo a ̃nadidas (LA), si se han escrito pruebas unitarias
(UT) o el tiempo transcurrido entrecommitsde una mismabuild(CD), son necesarias inferirlas a partir de
la informaci ́on que se tiene.

## 6. Experimentaci ́on

En este apartado se realiza una explicaci ́on en profundidad de las pruebas que se han realizado para
validar y verificar la implementaci ́on descrita en apartados anteriores. Esta secci ́on incluye la explicaci ́on en
detalle de todo el dise ̃no experimental llevado a cabo, incluyendo las t ́ecnicas a comparar, la descripci ́on del
datasetutilizado para la experimentaci ́on, el procedimiento seguido para realizar el entrenamiento y prueba
de los modelos, incluyendo elk-fold cross-validation, la descripci ́on del c ́alculo de las distintas m ́etricas de
evaluaci ́on y, finalmente, los resultados obtenidos y su correspondiente an ́alisis. Adem ́as, en esta ́ultima
secci ́on, se dar ́a respuesta a las preguntas de investigaci ́on planteadas en la Secci ́on 3, lo que constituye el
objetivo principal de este estudio.


### 6.1. Dise ̃no experimental

En esta secci ́on se describe el dise ̃no experimental llevado a cabo para la validaci ́on de la implementaci ́on
propuesta.

6.1.1. T ́ecnicas a comparar.En este estudio, se propone comparar tres t ́ecnicas de predicci ́on diferentes.
Por un lado, la propuesta enSmartBuildSkip[9] que usa bosques aleatorios en su algoritmo de predicci ́on
y, por otro lado, las dos t ́ecnicas propuestas en este estudio, JAES24. A continuaci ́on, se describen las tres
t ́ecnicas a comparar:

```
SBS-Within: t ́ecnica propuesta enSmartBuildSkipque utiliza bosques aleatorios en su algoritmo de
Machine Learningpara la predicci ́on. Esta t ́ecnica tiene dos fases principales: una en la que el algoritmo
predice de forma autom ́atica que labuildfallar ́a, por encontrarse en una secuencia debuild failures, y
otra en la que utiliza predicci ́on medianteMachine Learning.
```
```
JAES24-Within: t ́ecnica propuesta en este estudio que utiliza como modelo de ML ́arboles de decisi ́on.
El algoritmo de predicci ́on se basa en la implementaci ́on propuesta deSmartBuildSkip, pero modificando
el conjunto defeaturesempleado: TF, NC, FC, LC, LA, LR, LT, WD y DH, el cual captura eventos tem-
porales al realizar lasbuildsy desgrana los cambios realizados en la misma. Adem ́as, en este algoritmo
se realiza la acumulaci ́on defeatures, lo cual permite acumular cambios para la predicci ́on cuando una
buildes saltada por el algoritmo.
```
```
JAES24-Without: t ́ecnica propuesta en este estudio que utiliza como modelo de ML ́arboles de decisi ́on.
Este modelo emplea el mismo conjunto defeaturesdescrito en el punto anterior, sin embargo, no utiliza
como base la implementaci ́on realizadaSmartBuildSkip, por lo que no se realiza acumulaci ́on de valores
en lasfeaturescuando unabuildes saltada por el algoritmo, ni tampoco tiene dos fases de predicci ́on.
En este caso, simplemente se van realizando predicciones de forma individual para cadabuild.
```
Dependiendo del contexto sobre el que se realicen las predicciones, puede ser m ́as adecuado utilizar una
t ́ecnica u otra. Por ejemplo, si el proyecto sobre el que realizamos predicciones suele tener muchosbuild fai-
luresde forma consecutiva, ser ́a m ́as beneficioso utilizar las t ́ecnicas SBS-Withino JAES24-Within, ya que
estas tienen una fase en la predicci ́on especialmente dise ̃nada para detectar secuencias debuild failures. Por
otro lado, si el proyecto tienebuild failuresproducidos m ́as aleatoriamente a lo largo del proyecto, ser ́a m ́as
beneficioso utilizar la t ́ecnica JAES24-Without, ya que esta no tiene en cuenta secuencias debuild failures
en su algoritmo de predicci ́on.

Realizar una comparaci ́on entre estas tres t ́ecnicas nos da una visi ́on m ́as amplia de los resultados
obtenidos en este estudio, permiti ́endonos identificar cual de ellas es m ́as adecuada en t ́erminos de precisi ́on,
eficiencia o adaptabilidad a las caracter ́ısticas del problema. El hecho de considerar varias t ́ecnicas mejora
la validez interna del estudio, ya que se descarta que los resultados sean atribuibles a una sola metodolog ́ıa.

6.1.2. Descripci ́on del dataset. Para realizar la experimentaci ́on, se han utilizado 20 proyectos de
c ́odigo abierto disponibles de forma p ́ublica enGitHub. Todos los proyectos est ́an basados enJavay han
sido seleccionados de forma manual. Con el objetivo de tener una experimentaci ́on diversa, se han tenido en
cuenta dos escenarios posibles:

```
1.Escenario 1: engloba a todos aquellos proyectos donde la CI falla con muy poca frecuencia. En nuestra
soluci ́on, se ha considerado a todos estos proyectos como “proyectos dif ́ıciles”, y ser ́an todos aquellos en
los que la proporci ́on debuild failureses inferior al 10 % con respecto a lasbuildsexitosas.
```
```
2.Escenario 2: engloba a todos aquellos proyectos donde la CI falla con una frecuencia “normal”. Conside-
ramos como “proyectos normales” a todos aquellos en los que el porcentaje debuild failuresse encuentra
comprendido entre el 10 % y el 25 % con respecto a lasbuildsexitosas.
```

Al incluir tanto proyectos dif ́ıciles como normales, se pretende obtener una visi ́on m ́as amplia de la
efectividad de nuestro algoritmo en diferentes condiciones y escenarios. Este enfoque es beneficioso por
varias razones:

```
Evaluaci ́on en escenarios espec ́ıficos: separar ambos escenarios nos permite analizar el comporta-
miento del modelo en cada tipo de proyecto de forma m ́as precisa.
```
```
Fortalezas y debilidades: al evaluar cada conjunto de proyectos individualmente, podemos identificar
fortalezas y debilidades del modelo en cada escenario.
```
```
Adaptabilidad del modelo: al evaluar el modelo en diferentes escenarios, podemos observar si el
modelo es capaz de adaptarse bien a ambos tipos de proyectos, o si realmente necesita un enfoque
diferente para cada uno de ellos.
```
Se ha decidido catalogarlos como “proyectos dif ́ıciles” y “proyectos normales” seg ́un la capacidad que
tendr ́a el algoritmo de aprender de losbuild failures en cada tipo de proyecto. En los proyectos dif ́ıciles,
donde se espera que la proporci ́on debuild failuressea mucho menor a la debuildsexitosas, el algoritmo
tendr ́a que aprender de un n ́umero mucho menor de ejemplos de fallos, haci ́endole la tarea de aprendizaje
m ́as dif ́ıcil. Por otro lado, en los proyectos normales, donde la proporci ́on debuild failureses m ́as alta,
el algoritmo tendr ́a m ́as ejemplos debuild failuressobre los que aprender, esperando que la capacidad de
aprendizaje sea mayor.

Como hemos mencionado anteriormente, se han seleccionado 20 proyectos de c ́odigo abierto disponibles
enGitHub. Cada uno de ellos ha sido seleccionado de forma manual, y se ha intentado que el n ́umero de
buildssea lo m ́as similar posible entre ellos. A continuaci ́on, se muestran dos gr ́aficos que describen la pro-
porci ́on debuild failuresen cada uno de los proyectos seleccionados, tanto para proyectos dif ́ıciles como para
proyectos normales.

```
Figura 10.Proporci ́on debuild failuresen proyectos dif ́ıciles
```

```
Figura 11.Proporci ́on debuild failuresen proyectos normales
```
Como vemos, en los proyectos dif ́ıciles la proporci ́on debuild failureses inferior al 10 %, mientras que en
los proyectos normales se encuentra entre el 10 % y el 25 %. En ambos casos, se ha intentado que el n ́umero
debuildssea lo m ́as similar posible entre los proyectos seleccionados.

6.1.3. Procedimiento para el entrenamiento, prueba y validaci ́on cruzadaLa evaluaci ́on de los
modelos de clasificaci ́on busca medir y analizar el desempe ̃no de los mismos en la tarea de clasificaci ́on.
Esta evaluaci ́on permite determinar la capacidad del modelo para predecir o clasificar correctamente nuevas
instancias no observadas previamente, utilizando un conjunto de datos de prueba.

Para cada uno de los 20 proyectos seleccionados, se ha realizado lo siguiente:

```
1.Conjunto de entrenamiento y prueba: se ha dividido el subconjunto debuildsen dos subconjuntos,
uno de entrenamiento y otro de prueba. El porcentaje de entrenamiento y prueba se ha fijado en 80 % y
20 % respectivamente. Se ha tenido especial cuidado en seleccionar el 80 % de lasbuildsm ́as antiguas para
el subconjunto de entrenamiento y, el 20 % de lasbuildsm ́as recientes para el subconjunto de prueba.
Esto es as ́ı por la dependencia temporal que existe en este tipo de problemas, donde no tiene sentido rea-
lizar predicciones bas ́andonos en informaci ́on futura. Adem ́as, para realizar este entrenamiento y prueba,
se ha escogido el umbral de decisi ́on por defecto, con valor 0,5.
```
```
2.K-fold cross-validation: se ha utilizado la t ́ecnica de validaci ́on cruzadak-fold cross-validationpara
evaluar el rendimiento de los modelos de clasificaci ́on propuestos. Para cada proyecto, se han seleccionado
susbuildsy se han creado 11 subconjuntos a partes iguales. A continuaci ́on, se ha realizado la validaci ́on
cruzada de la siguiente forma: se han ido seleccionando losfoldsde forma acumulativa para realizar el
entrenamiento, mientras que con elfoldsiguiente se ha realizado la parte detest. Cuando este proceso
se ha realizado con cada uno de losfolds, habr ́a un total de 10 resultados disponibles, calculando as ́ı
posteriormente la media de cada una de las m ́etricas obtenidas en cadafold. Este proceso se ha realizado
con un umbral de decisi ́on de 0,5, con el fin de contrastar los resultados obtenidos para el conjunto de
entrenamiento y prueba.
```

6.1.4. M ́etricas de evaluaci ́on Las m ́etricas de evaluaci ́on constituyen una parte esencial en nuestro
estudio, ya que gracias a ellas podemos medir y analizar el rendimiento de las t ́ecnicas propuestas. En este
estudio, se han considerado cinco m ́etricas de evaluaci ́on diferentes:accuracy,precision,recall,F1-scorey
AUC-ROC. Estas m ́etricas ya fueron descritas en la Secci ́on 3, por lo que no se describir ́an de nuevo en este
apartado.

Es importante mencionar que, para realizar el c ́alculo de estas m ́etricas, hemos hecho uso de m ́etodos de
la librer ́ıametricsdescikit-learn. Esta librer ́ıa est ́a especialmente dise ̃nada para el c ́alculo de estas m ́etricas,
y nos permite obtener los resultados de forma r ́apida y sencilla. A continuaci ́on, vamos a describir c ́omo se
realiza el c ́alculo de cada una de ellas en el procedimiento deentrenamiento y prueba:

```
Accuracy: a partir de las predicciones realizadas por el modelo para el conjunto detest(que supone el
20 % de lasbuilds), se calcula a partir de los valores de las etiquetas reales de lasbuildsy las predicciones
realizadas por el modelo (Ecuaci ́on (1)).
```
```
Precision: a partir de las etiquetas reales del conjunto detesty las etiquetas predichas por el algoritmo,
se calcula la precisi ́on del modelo (Ecuaci ́on (2)). Hemos tenido que indicar cu ́al es la clase positiva en
nuestro problema (clase 0) e incluir el valor por defecto que asigna cuando se produce una divisi ́on entre
0, en el caso de que la suma de verdaderos positivos y falsos positivos sea 0.
```
```
Recall: a partir de las etiquetas reales del conjunto detesty las etiquetas predichas por el algoritmo,
se calcula elrecalldel modelo (Ecuaci ́on (3)). Al igual que en el caso deprecision, hemos tenido que
indicar cu ́al es la clase positiva en nuestro problema (clase 0) para que el c ́alculo sea correcto y, a ̃nadir
el valor por defecto en caso de divisi ́on entre 0, en este caso, cuando la suma de verdaderos positivos y
falsos negativos sea 0.
```
```
F1-score: esta m ́etrica, podr ́ıa calcularse directamente a partir de los valores deprecisionyrecall, sin
embargo, hemos decidido utilizar el m ́etodo que nos proporciona la librer ́ıa mencionada anteriormente,
que usa al igual que los anteriores las etiquetas reales del conjunto detesty las etiquetas predichas por
el algoritmo, adem ́as de indicar cu ́al es la clase positiva y el valor en caso de divisi ́on entre 0.
```
En el caso dek-fold cross-validation, el c ́alculo en s ́ı de estas m ́etricas es similar al descrito anterior-
mente, con la caracter ́ıstica de que por cadafolddetestevaluado, se almacenan las predicciones, hasta que
finalmente se tengan los resultados dek− 1 folds, en este caso 10 folds. Una vez obtenidos estos resultados,
estos ser ́ıan las etiquetas predichas por el algoritmo.

```
Training data Test data
```
```
Fold 1 Fold 2 Fold 3 Fold 4 Fold^5 Fold 9 Fold 10 Fold 11
```
```
Figura 12.Acumulaci ́on de predicciones enk-fold cross-validation.
```
Como vemos en la Figura 12, hemos ido acumulando las predicciones hechas en cada uno de losfoldsde
test, para luego calcular las m ́etricas en funci ́on de ellas. Podemos observar, adem ́as, que el primerfoldno
se usa paratest, us ́andose ́unicamente para entrenamiento. Sucede algo similar con el ́ultimofold, que no es
usado para entrenamiento y se usa ́unicamente paratest.


### 6.2. Resultados

En este apartado, se presentan los resultados obtenidos del estudio y se responde a las preguntas de
investigaci ́on planteadas en la Secci ́on 3. A continuaci ́on, se presentan con detalle las pruebas realizadas y el
an ́alisis de los resultados obtenidos.

```
PI-1:¿Qu ́e algoritmo de predicci ́on produce los mejores resultados en la predicci ́on autom ́atica del re-
sultado de la integraci ́on continua?
```
Para responder a esta pregunta de investigaci ́on, se ha realizado un an ́alisis comparativo entre las tres
t ́ecnicas presentadas, cada uno de los cuales ha sido evaluado en los dos escenarios posibles: proyectos dif ́ıciles
y proyectos normales.

6.2.1. Escenario 1 - Proyectos dif ́ıciles.Evaluaci ́on comparativa de las tres t ́ecnicas mediante entre-
namiento y prueba, 80 % y 20 % respectivamente, con un umbral de decisi ́on de 0,5, el valor por defecto.

```
Figura 13.Recallen proyectos dif ́ıciles
```
En la Figura 13, podemos observar los valores derecallobtenidos en los proyectos dif ́ıciles. Como vemos,
no se han obtenido valores demasiado altos, sin embargo, en pr ́acticamente todos los proyectos, JAES24 ha
obtenido mejores resultados queSmartBuildSkip. A simple vista, parece que JAES24-Withoutofrece mejores
valores derecall, ya que en proyectos comocoherence,hertzbeatoNewPipees el ́unico que consigue predecir
alg ́unbuild failure. En otros, como enozoneyspring-session, es superior. Observando la gr ́afica, podemos
ver que enavrose obtienen mejores valores para SBS-Within, esto puede deberse a que en este proyecto las
featuresque usa SBS-Withinsean m ́as significativas que en otros proyectos, aunque por lo general, JAES24-
Withoutes el que mejor se comporta.


```
Figura 14.Precisionen proyectos dif ́ıciles.
```
En este caso, tenemos que elprecisiones bastante bajo para las tres t ́ecnicas, sin embargo, JAES24 ofre-
ce resultados ligeramente superiores queSmartBuildSkip. Actualmente, el modelo se equivoca prediciendo
comobuild failuresuna cantidad elevada debuildsque en realidad no lo son. Debemos recordar que, en
este escenario, el modelo tiene muy pocas instancias positivas de las que aprender, haciendo este proceso de
aprendizaje m ́as complicado. A ́un as ́ı, JAES24-Withoutes el que mejor se comporta en este aspecto.

Con el fin de validar los resultados obtenidos y clarificar cu ́al de las t ́ecnicas de JAES24 es la que mejor
se comporta, vamos a realizar las mismas gr ́aficas usandok-fold cross-validationen lugar detrainytest.
Esta validaci ́on cruzada ha sido realizada usando un umbral de decisi ́on de 0,5 y 11 particiones.

```
Figura 15.Recallen proyectos dif ́ıciles usando validaci ́on cruzada.
```

Tras realizar validaci ́on cruzada sobre nuestrodatasetde proyectos dif ́ıciles, podemos observar en la
Figura 15 que los resultados var ́ıan ligeramente a los anteriores. En este caso, se observa claramente que
JAES24-Withines la que mejor resultados obtiene en cuando arecall. Ambas t ́ecnicas, tanto JAES24-Within
como JAES24-Without, ofrecen mejores resultados queSmartBuildSkip. Si comparamos ́unicamente las t ́ecni-
cas de JAES24, podemos deducir que JAES24-Withinse comporta mejor en estedatasetde proyectos porque
probablemente exista un mayor n ́umero debuild failuresde forma consecutiva, lo cual no quiere decir que
JAES24-Withoutsea peor, simplemente que en este contexto, JAES24-Withinse comporta mejor.

```
Figura 16.Precisionen proyectos dif ́ıciles usando validaci ́on cruzada.
```
En la Figura 16, podemos observar resultados algo contradictorios, ya que en algunos casos SBS-Within
ofrece mejores resultados para elprecision, mientras que en otros, JAES24-Withoutes el que mejor se com-
porta. Sin embargo, en m ́as de la mitad de los proyectos seleccionados, JAES24-Withoutes el que mejores
resultados ofrece paraprecision.

Si nos fijamos, a pesar de que JAES24-Withinofrezca mejores resultados enrecall, JAES24-Withoutes el
que mejor se comporta enprecision. Esto nos parece adelantar dos variantes del algoritmo muy interesantes:

```
JAES24-Within: se trata de una t ́ecnica m ́as agresiva para identificar fallos. Si el desarrollador quiere
asegurarse de predecir la mayor cantidad de fallos (aunque esto implique ejecutarbuildsque en realidad
no fallar ́an), esta t ́ecnica es la m ́as adecuada.
```
```
JAES24-Without: es una t ́ecnica m ́as conservadora, pero cuando predice un fallo, es m ́as probable que sea
correcto. Si el objetivo del desarrollador es minimizar falsas alarmas y tener predicciones m ́as confiables,
esta t ́ecnica es m ́as adecuada.
```
La decisi ́on de utilizar una u otra t ́ecnica depender ́a de las necesidades del proyecto y del desarrollador. Si
la prioridad es detectar el mayor n ́umero de fallos posibles, incluso a costa de m ́as falsos positivos, JAES24-
Withines la mejor opci ́on. Si la prioridad es minimizar falsas alarmas y asegurar que cuando se predice un
fallo, realmente ocurra, entonces JAES24-Withoutes la mejor opci ́on.


6.2.2. Escenario 2 - Proyectos normales. Evaluaci ́on comparativa de las tres t ́ecnicas mediante en-
trenamiento y prueba, 80 % y 20 % respectivamente, con un umbral de decisi ́on de 0,5, el valor por defecto.

```
Figura 17.Recallen proyectos normales.
```
Observando los resultados obtenidos en la Figura 17, vemos que las tres t ́ecnicas se comportan mucho
mejor que en el Escenario 1. En este caso, los modelos tienen una mayor cantidad debuild failuressobre los
que aprender, lo que hace m ́as sencillo el proceso de aprendizaje. A simple vista, parece que JAES24-Without
es la que mejor resultados ofrece, siendo superior elrecallen ocho de los diez proyectos evaluados. En el
proyectoskywalking, vemos que JAES24-Withinofrece mejores resultados y, en el proyectobookkeeper, el
que mayor n ́umero debuild failuresposee, SBS-Withines el que mejor se comporta. Por lo general, vemos
que JAES24, en cualquiera de sus dos variantes, ofrece mejores resultados queSmartBuildSkip.

```
Figura 18.Precisionen proyectos normales.
```

Analizando los resultados deprecisionobtenidos en la Figura 18, vemos que JAES24-Withoutes el que
mejor resultados ofrece, siendo superior en seis de los diez proyectos evaluados. En otros casos, como en
spring-security,nifi eincubator-streampark es superior JAES24-Within. Este comportamiento indica que
JAES24-Withines m ́as preciso a la hora de predecirbuild failuresen los proyectos mencionados anterior-
mente, es decir, predice menor cantidad de falsos positivos que JAES24-Without.

Con el objetivo de evaluar el rendimiento de manera m ́as robusta y confiable, se ha realizadok-fold cross-
validationtambi ́en en este escenario. Esto evita el sobreajuste y garantiza que los resultados no dependan
́unicamente de una partici ́on espec ́ıfica del conjunto de datos. Para realizar una comparaci ́on justa entre
escenarios, se ha realizado con el mismo umbral de decisi ́on, 0,5 y, con 11 particiones.

```
Figura 19.Recallen proyectos normales usando validaci ́on cruzada.
```
Observando los resultados obtenidos en la Figura 19, vemos que se obtienen resultados bastante supe-
riores aSmartBuildSkip, siendo este enfoque mucho m ́as efectivo en escenarios donde el n ́umero debuild
featureses m ́as elevado. Podemos ver claramente como en casi todos los proyectos (salvo uno) los valores
derecallde JAES24 superan aSmartBuildSkip. Realizando una comparaci ́on entre las t ́ecnicas de JAES24,
en los seis primeros proyectos,JAES-Withoutdetecta mayor n ́umero debuild failures, mientras que en los
cuatro restantes, JAES24-Withinofrece mejores resultados.

Esto nos vuelve a confirmar que la elecci ́on de una u otra t ́ecnica puede depender de los h ́abitos de CI
del proyecto. Si en el proyecto detectamos que normalmente se producen fallos de forma consecutiva, ser ́a
m ́as apropiado utilizar como t ́ecnica de predicci ́on JAES24-Within, ya que esta garantiza que al encontrar
un primer fallo (first failure), se prediga de forma autom ́atica que la siguientebuildno pasar ́a. En cambio, si
detectamos que normalmente losbuild failuresse producen de forma m ́as aleatoria en el conjunto debuilds,
ser ́a m ́as apropiado utilizar JAES24-Without.


```
Figura 20.Precisionen proyectos normales usando validaci ́on cruzada.
```
Finalmente, en la Figura 20, vemos que se produce una tendencia algo distinta a la observada en el
Escenario 1. En este caso, vemos que igualmente ambas t ́ecnicas superan aSmartBuildSkip, sin embargo,
JAES24-Withines la que mejores resultados ofrece en cuanto aprecision, siendo superior en siete de los diez
proyectos evaluados. Por lo tanto, tenemos que en estedatasetde proyectos normales, la t ́ecnica JAES24-
Withines m ́as conservadora, ya que ofrece menosrecalla cambio de aumentar elprecisiony, JAES24-Without
es m ́as agresiva, ya que ofrece m ́asrecalla cambio de disminuir elprecision.

Los resultados obtenidos en este apartado confirman que lasfeatures que capturan eltiming en el
que se quiere realizar la contribuci ́on(Time Frequency,Week DayyDay Hour), y lasfeaturesque
desgranan los cambios realizadosen labuild(Lines AddedyLines Removed) son m ́as significativas que
otrasfeaturesevaluadas en otras t ́ecnicas [9]. Estas caracter ́ısticas ofrecen una mayor capacidad predictiva,
lo que sugiere que el momento en el que se ejecuta labuildy el tipo de modificaciones introducidas tienen un
impacto directo en la probabilidad de que se produzcanbuild failures. Este hallazgo subraya la importancia
de considerar, no solo aspectos t ́ecnicos del c ́odigo, sino tambi ́en el contexto temporal y la naturaleza de los
cambios realizados.

```
PI-2:¿Qu ́e caracter ́ısticas de las builds son m ́as significativas en la predicci ́on?
```
Para responder a esta pregunta de investigaci ́on, hemos aplicado un enfoque basado en el an ́alisis de
importancia de caracter ́ısticas, utilizando dos algoritmos de clasificaci ́on diferentes: ́arboles de decisi ́on y
bosques aleatorios, que son los usados por las dos t ́ecnicas propuestas en este estudio de JAES24 y,Smart-
BuildSkip, respectivamente. Para ello, hemos considerado el conjunto completo defeaturesdisponibles de la
Tabla 1 y hemos calculado la importancia de cada una de ellas para cada proyecto. Posteriormente, hemos
calculado la media de la importancia de cadafeatureen cada algoritmo de clasificaci ́on, obteniendo as ́ı una
visi ́on general de cu ́ales son lasfeaturesm ́as significativas en la predicci ́on.

A continuaci ́on, se presentan los valores medios de importancia de cadafeaturepara ́arboles de decisi ́on:


```
Figura 21.Importancia de lasfeaturesen ́arboles de decisi ́on.
```
A continuaci ́on, se presentan los valores medios de importancia de cadafeaturepara bosques aleatorios:

```
Figura 22.Importancia de lasfeaturesen bosques aleatorios.
```
Considerando todas lasfeaturesdel conjunto presentado en la Tabla 1, observamos lo siguiente:

```
Cuando se realiza el entrenamiento del modelo, lasfeaturesque tienen relaci ́on con el hist ́orico debuilds
ejecutadas anteriormente, comoPerformance short,Failure DistanceyPerformance Long, tienen una
importancia significativa a la hora de predecirbuild failures.
```
```
Lasfeaturesque describen eltimingen el que se realiza la contribuci ́on como elDay Hour,Time Fre-
quencyyWeek Daytienen una importancia significativa en la predicci ́on debuild failures.
```

```
Lasfeaturesque describen los cambios realizados, comoLines changedy otras que desgranan los cambios
realizados en labuild, comoLines AddedyLines Removed, son tambi ́en importantes en la predicci ́on de
build failures.
```
Cabe destacar que, apesar de que lasfeaturesque m ́as importancia tienen a la hora de predecirbuild
failuresson el PS, PL y FD, estasfeaturesno se han utilizado en nuestro enfoque. Esto se debe a que, en un
caso de uso real, si nos encontramos utilizando un modelo predictivo para decidir si saltar o no unabuild,
estasfeaturesno podr ́an calcularse de forma exacta, ya que no conocemos el resultado de aquellasbuilds
propuestas que se hayan predicho comopass. En nuestra implementaci ́on, se ha realizado experimentaci ́on
a ̃nadiendo este conjunto defeatures, pero los resultados obtenidos eran francamente peores que los obtenidos
sin ellas. El hecho de asumir que, cuando el algoritmo predice unabuildpropuesta comopass, esta realmente
lo ser ́a (Secci ́on 5.3), no ofrece garant ́ıas de que el modelo sea efectivo en un caso de uso real para la predicci ́on.

Podemos concluir que, lasfeaturesPL, PS y FD son las que m ́as influencia tienen a la hora de predecir
build failures, sin embargo, no son del todo aplicables a la hora de realizar una predicci ́on en un caso de
uso real. Por otro lado, vemos quefeaturesque describen eltimingen el que se realiza la contribuci ́on y las
que describen los cambios realizados, son tambi ́en importantes para la predicci ́on, confirmando una vez m ́as
nuestra hip ́otesis inicial.

Finalmente, con el objetivo de contrastar los resultados y confirmar nuestra hip ́otesis inicial, veamos la
distribuci ́on temporal debuild failuresen el conjunto de repositorios estudiados:

```
Tabla 3.Distribuci ́on temporal de losbuild failures.
```
```
D ́ıa de la semana Buildsejecutadas Buildsfallidas Proporci ́on de
buildsfallidas
Lunes 18222 836 4.59 %
Martes 17447 853 4.89 %
Mi ́ercoles 16690 825 4.94 %
Jueves 16687 877 5.26 %
Viernes 15043 818 5.44 %
S ́abado 7510 420 5.59 %
Domingo 7235 376 5.19 %
```
Estos resultados confirman nuestra hip ́otesis inicial de que eltimingen el que se quiere realizar la
contribuci ́on juega un papel importante para la predicci ́on debuild failures. En la Tabla 3 podemos observar
que la proporci ́on debuild failuresproducidos va aumentando conforme avanza la semana, siendo el viernes y
el s ́abado los dos d ́ıas en los que se producen m ́as fallos en comparaci ́on con la cantidad debuildsejecutadas.
Esto puede deberse posiblemente a la prisa de los desarrolladores por completar las tareas antes del fin de
semana o por la fatiga acumulada durante la semana laboral.

```
Tabla 4.Horas en las que se producen m ́asbuild failurespara cada d ́ıa.
```
```
D ́ıa de la semana Hora
Lunes 12:00
Martes 18:00
Mi ́ercoles 18:00
Jueves 18:00
Viernes 18:00
S ́abado 18:00
Domingo 18:00
```

En la Tabla 4, podemos observar la hora para cada uno de los d ́ıas de la semana en que se producen m ́as
build failures. En este caso, vemos que la mayor ́ıa de fallos tienen lugar a las 18:00 de la tarde, lo cual puede
ser bastante razonable, ya que es normalmente el final de la jornada laboral y, muchos sistemas de CI est ́an
configurados para lanzar lasbuildsal final del d ́ıa laboral. Adem ́as, normalmente, los desarrolladores suelen
esperar al final de la jornada para ejecutar la CI, evitando tener que esperar al resultado de la ejecuci ́on de
la misma. Por ́ultimo, observamos que para los lunes, las 12:00 de la ma ̃nana es cuando se producen m ́as
fallos, lo cual puede deberse a cambios no ejecutados o menos revisados de la semana anterior, aunque las
razones concretas requieren una mayor investigaci ́on.

## 7. Amenazas a la validez

En cualquier trabajo de investigaci ́on es crucial reconocer los factores que pueden comprometer la validez
de los resultados obtenidos. Estos factores, com ́unmente conocidos como amenazas a la validez, representan
posibles fuentes de sesgo o error que pueden afectar a la precisi ́on y generalizaci ́on de las conclusiones del
estudio. Al identificar y discutir estas amenazas, no solo hacemos m ́as transparente nuestro estudio, sino que
tambi ́en proporcionamos una base cr ́ıtica para que los lectores eval ́uen la fiabilidad de los hallazgos. En este
apartado se examinan las principales amenazas que podr ́ıan afectar a la validez de constructo, validez interna
y validez externa del presente estudio, con el fin de contextualizar los resultados y ofrecer una interpretaci ́on
m ́as solida y matizada.

Concretamente, se consideran tres tipos de amenazas a la validez: validez de constructo, validez interna
y validez externa. A continuaci ́on, explicamos en qu ́e consiste cada una de ellas:

```
Validez de constructo: son aquellos factores que ponen en duda si el estudio est ́a realmente midiendo
lo que pretende medir, es decir, si los conceptos definidos en la investigaci ́on son evaluados correctamente.
Estas amenazas pueden afectar la interpretaci ́on de los resultados en relaci ́on con los constructos te ́oricos.
```
```
Validez interna: se refiere a las amenazas que pueden afectar la relaci ́on causal entre las variables
independientes y dependientes. En otras palabras, se trata de factores que pueden distorsionar la inter-
pretaci ́on de la relaci ́on entre las variables manipuladas y las variables de respuesta.
```
```
Validez externa: son aquellas amenazas que pueden afectar la generalizaci ́on de los resultados obtenidos
en el estudio. Estas amenazas se refieren a la capacidad de generalizar los resultados a otros contextos,
poblaciones o situaciones distintas a las evaluadas en el estudio.
```
A continuaci ́on, se detallan las amenazas a la validez identificadas en el presente estudio y se discuten
las estrategias utilizadas para mitigar su impacto en los resultados obtenidos.

### 7.1. Validez de constructo

En nuestro estudio utilizamos m ́etricas como indicadores para representar la cantidad debuild failures
detectados en CI. Algunas m ́etricas, como elaccuracy, pueden ser enga ̃nosas en conjuntos de datos que
est ́an muy desbalanceados, ya que pueden reflejar un alto valor incluso cuando el modelo falla en identificar
losbuild failures. Para mitigar este problema, hemos utilizado m ́etricas comoprecision,recallyF1-score,
que proporcionan una visi ́on m ́as equilibrada del rendimiento del modelo. Adem ́as, debemos recordar que
nuestro enfoque persigue reducir el costo computacional asociado a la CI mediante la detecci ́on debuild
failures, sin embargo, no hemos considerado valores econ ́omicos espec ́ıficos asociadas a la ejecuci ́on de CI o
a la reparaci ́on de errores en el conjunto espec ́ıfico que hemos usado para la experimentaci ́on.


### 7.2. Validez interna

Para salvaguardar la validez interna, hemos realizado pruebas exhaustivas de nuestros procedimientos de
evaluaci ́on en subconjutos deldatasetempleado durante el desarrollo. Nuestro an ́alisis puede estar influen-
ciado por informaci ́on incorrecta en nuestro dataset. Por esto, siempre hemos considerado ramas principales
de los proyectos, filtrando as ́ı valores at ́ıpicos m ́as comunes en ramas secundarias o de desarrollo. Adem ́as,
nuestros resultados podr ́ıan verse afectados por pruebas inestables (flaky tests) que causan fallos de manera
err ́atica o falsa.

Por ́ultimo, la validaci ́on cruzada cronol ́ogica ha sido empleada para preservar el orden temporal de los
datos y evitar que futurasbuildsse incluyan en el conjunto de entrenamiento. Esto garantiza que los resultados
sean m ́as representativos de c ́omo el modelo funcionar ́ıa en condiciones reales, donde el entrenamiento se
realiza con datos pasados y la prueba se realiza con datos futuros. Aunque la validaci ́on cruzada cronol ́ogica
es una alternativa adecuada a la validaci ́on cruzada est ́andar, la decisi ́on de utilizar este enfoque ha sido
alineada con el objetivo de evaluar las t ́ecnicas en un escenario que respete la secuencia temporal.

### 7.3. Validez externa

Para aumentar la validez externa, hemos seleccionado 20 proyectos ampliamente conocidos deGitHub.
Todos son proyectos de c ́odigo abierto y que tienen un n ́umero considerable deforksy estrellas. Como dato
objetivo, el proyecto que menosforksy estrellas tiene escoherence, deOracle, con 70forksy 427 estrellas, y
el que m ́as,spring-boot, con 40, 500 forksy 74,400 estrellas. Los proyectos seleccionados son todos proyectos
Java, ya que necesitamos hacer una evaluaci ́on justa con otras t ́ecnicas. A pesar de que este lenguaje de
programaci ́on es uno de los m ́as utilizados en la actualidad, lenguajes de programaci ́on diferentes pueden
tener h ́abitos de Integraci ́on Continua distintos, pudiendo provocar resultados ligeramente diferentes a los
obtenidos en este estudio.

Finalmente, haber elegido proyectos de empresas muy conocidas puede haber limitado la diversidad
del conjunto de datos, ya que estos proyectos suelen seguir procesos de desarrollo desoftwarealtamente
estructurados. Esto podr ́ıa no reflejar la realidad de proyectos m ́as peque ̃nos o menos formales, pudiendo
limitar la aplicabilidad de los resultados a repositorios menos formales o con menos recursos.

## 8. Conclusiones y trabajos futuros

En este trabajo, hemos propuesto y evaluado JAES24, un enfoque novedoso para ahorrar costos en la
Integraci ́on Continua (CI) al omitirbuildsque se predice que pasar ́an. Nuestro dise ̃no de JAES24 parte de
la hip ́ostesis de que el momento en que se realiza una contribuci ́on a un proyecto desoftwareinfluye en la
probabilidad de que labuildpase la CI o no. Adem ́as, parte tambi ́en de que el desgranado de los tipos de
cambios que se realizan en unabuildson especialmente importantes para la predicci ́on de su resultado. Estu-
diamos la relaci ́on entre el momento de la contribuci ́on y el resultado de la CI y encontramos evidencia que
las apoya. Se ha descubierto que: el d ́ıa, la hora o el tiempo entre contribuciones influye en la probabilidad
de predecir unbuild failure. Adem ́as, otros cambios como el n ́umero de l ́ıneas a ̃nadidas o eliminadas, que
desgranan el tipo de cambio producido, tambi ́en tienen un impacto positivo en la predicci ́on debuild failures.

Con este conjunto de caracter ́ısticas, JAES24 mejor ́o elprecisiony elrecalldeSmartBuildSkip. Adem ́as,
se trata de un algoritmo personalizable, ya que puede configurarse con distintos umbrales de decisi ́on en
funci ́on de las necesidades de los desarrolladores y, adem ́as, cuenta con dos versiones: una m ́as conservadora
y otra m ́as agresiva. La variante conservadora, JAES24-Within, por lo general, detecta un menor n ́umero de
build failurespero mantiene unos niveles deprecisionm ́as elevados. Por otro lado, la variante m ́as agresiva,
JAES24-Without, detecta un mayor n ́umero debuild failures, sin embargo, mantiene unos niveles depreci-
sionmenores, lo cu ́al significa que a menudo predice comobuild failures buildsque en realidad pasan (falsos


positivos). Desde el punto de vista del desarrollador, que JAES24 incluya adem ́as, una interfaz gr ́afica, hace
que sea mucho m ́as f ́acil de usar y entender, convirti ́endose en un enfoque ́unico y m ́as accesible para los
desarrolladores. JAES24 proporciona una estrategia novedosa que complementa las t ́ecnicas existentes para
ahorrar costos en CI, omitiendo construcciones con cambios que no afectan al c ́odigo.

En el futuro, trabajaremos extendiendo la funcionalidad de JAES24 para que pueda realizar an ́alisis
est ́aticos en funci ́on del contenido de los cambios realizados en el c ́odigo fuente de lasbuilds. Igualmente,
otros tipos de an ́alisis como el din ́amico pueden ser considerados. Adem ́as, lo haremos extensible a otros
lenguajes de programaci ́on, estudiando los h ́abitos de CI que puedan darse en proyectossoftwarede distinta
naturaleza. Podr ́ıa realizarse un c ́odigo totalmente funcional, que permitiera a los desarrolladores integrar
JAES24 en su ciclo de desarrollosoftware, permitiendo que puedan hacer predicciones bas ́andose en su re-
positorio local. Finalmente, se realizar ́an cambios en la interfaz gr ́afica para hacerla m ́as flexible y accesible
a los desarrolladores, incluyendo nuevas funcionalidades y mejorando la usabilidad.


## Referencias

1. Github rest api documentation, 2008. [Online; accessed 4-Sep-2024].
2. Bihuan Chen, Linlin Chen, Chen Zhang, and Xin Peng. Buildfast: history-aware build outcome prediction for
    fast feedback and reduced cost in continuous integration. InProceedings of the 35th IEEE/ACM International
    Conference on Automated Software Engineering, ASE ’20, page 42–53, New York, NY, USA, 2021. Association
    for Computing Machinery.
3. Omar Elazhary, Colin Werner, Ze Li, Derek Lowlind, Neil Ernst, and Margaret-Anne Storey. Uncovering the
    benefits and challenges of continuous integration practices.IEEE Transactions on Software Engineering, PP:1–1,
    03 2021.
4. Martin Fowler and Matt Foemmel. Continuous integration, 2006. [Online; accessed 2-Aug-2024].
5. Foyzul Hassan and Xiaoyin Wang. Change-aware build prediction model for stall avoidance in continuous in-
    tegration. InProceedings of the 11th ACM/IEEE International Symposium on Empirical Software Engineering
    and Measurement, ESEM ’17, page 157–162. IEEE Press, 2017.
6. Michael Hilton, Timothy Tunnell, Kai Huang, Darko Marinov, and Danny Dig. Usage, costs, and benefits of
    continuous integration in open-source projects. InProceedings of the 31st IEEE/ACM International Conference on
    Automated Software Engineering, ASE ’16, page 426–437, New York, NY, USA, 2016. Association for Computing
    Machinery.
7. Yang Hong, Chakkrit Tantithamthavorn, Jirat Pasuksmit, Patanamon Thongtanunam, Arik Friedman, Xing
    Zhao, and Anton Krasikov. Practitioners’ challenges and perceptions of ci build failure predictions at atlassian. In
    Companion Proceedings of the 32nd ACM International Conference on the Foundations of Software Engineering,
    FSE 2024, page 370–381, New York, NY, USA, 2024. Association for Computing Machinery.
8. Md Rakibul Islam and Minhaz F. Zibran. Insights into continuous integration build failures. InProceedings of
    the 14th International Conference on Mining Software Repositories, MSR ’17, page 467–470. IEEE Press, 2017.
9. Xianhao Jin and Francisco Servant. A cost-efficient approach to building in continuous integration. In 2020
    IEEE/ACM 42nd International Conference on Software Engineering (ICSE), pages 13–25, 2020.
10. Xianhao Jin and Francisco Servant. Cibench: A dataset and collection of techniques for build and test selection
and prioritization in continuous integration. In2021 IEEE/ACM 43rd International Conference on Software
Engineering: Companion Proceedings (ICSE-Companion), pages 166–167, 2021.
11. Xianhao Jin and Francisco Servant. Which builds are really safe to skip? maximizing failure observation for build
selection in continuous integration.J. Syst. Softw., 188(C), jun 2022.
12. Xianhao Jin and Francisco Servant. Hybridcisave: A combined build and test selection approach in continuous
integration.ACM Trans. Softw. Eng. Methodol., 32(4), may 2023.
13. Eriks Klotins, Tony Gorschek, Katarina Sundelin, and Erik Falk. Towards cost-benefit evaluation for continuous
software engineering activities.Empirical Softw. Engg., 27(6), nov 2022.
14. Bohan Liu, He Zhang, Weigang Ma, Gongyuan Li, Shanshan Li, and Haifeng Shen. The why, when, what, and
how about predictive continuous integration: A simulation-based investigation.IEEE Transactions on Software
Engineering, 49(12):5223–5249, 2023.
15. Thomas Rausch, Waldemar Hummer, Philipp Leitner, and Stefan Schulte. An empirical analysis of build fai-
lures in the continuous integration workflows of java-based open-source software. InProceedings of the 14th
International Conference on Mining Software Repositories, MSR ’17, page 345–355. IEEE Press, 2017.
16. Pooya Rostami Mazrae, Tom Mens, Mehdi Golzadeh, and Alexandre Decan. On the usage, co-usage and migration
of ci/cd tools: A qualitative analysis.Empirical Softw. Engg., 28(2), mar 2023.
17. Islem Saidani, Ali Ouni, Moataz Chouchen, and Mohamed Wiem Mkaouer. Predicting continuous integration
build failures using evolutionary search.Information and Software Technology, 128:106392, 2020.
18. Islem Saidani, Ali Ouni, Moataz Chouchen, and Mohamed Wiem Mkaouer. Bf-detector: an automated tool for
ci build failure detection. InProceedings of the 29th ACM Joint Meeting on European Software Engineering
Conference and Symposium on the Foundations of Software Engineering, ESEC/FSE 2021, page 1530–1534, New
York, NY, USA, 2021. Association for Computing Machinery.
19. Islem Saidani, Ali Ouni, and Mohamed Wiem Mkaouer. Improving the prediction of continuous integration build
failures using deep learning.Automated Software Engg., 29(1), may 2022.
20. Jacek ́Sliwerski, Thomas Zimmermann, and Andreas Zeller. When do changes induce fixes? SIGSOFT Softw.
Eng. Notes, 30(4):1–5, may 2005.


