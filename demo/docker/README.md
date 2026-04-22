# 🐳 Guía básica de Docker (práctica y directa)

## Ejecutar demo:

1.- cd en el root
2.- Construir la imagen:
```
docker build -f demo/docker/Dockerfile -t ollama-demo .
```
3.- Crear contenedor y ejecutarlo
```
docker run --rm --add-host=host.docker.internal:host-gateway ollama-demo
```


## 🧠 Conceptos clave

- **Imagen** → plantilla inmutable (snapshot)
- **Contenedor** → instancia en ejecución de una imagen
- **Dockerfile** → receta para construir una imagen

---

## 🏗️ build → construir imágenes

```bash
docker build -f demo/docker/Dockerfile -t ollama-demo .
````

### Flags importantes

* `-f <ruta>` → especifica el Dockerfile
* `-t <nombre:tag>` → nombre de la imagen
* `.` → contexto de build (archivos accesibles)

---

## 🚀 run → ejecutar contenedores

```bash
docker run ollama-demo
```

### Flags clave

* `--name <nombre>` → nombre del contenedor
* `-p host:contenedor` → mapear puertos (ej: `-p 8000:8000`)
* `-e VAR=valor` → variables de entorno
* `--rm` → elimina el contenedor al terminar
* `-it` → modo interactivo (terminal)
* `-v host:contenedor` → montar volumen
* `--add-host=host.docker.internal:host-gateway`
  → acceso al host (necesario en Linux para Ollama)

### Ejemplo (tu caso)

```bash
docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  ollama-demo
```

---

## 🧠 modo interactivo (`-it`)

```bash
docker run -it ubuntu bash
```

* `-i` → mantiene stdin abierto (puedes escribir)
* `-t` → asigna terminal (TTY)

👉 Permite usar el contenedor como una shell real

---

## 📦 ps → ver contenedores

```bash
docker ps        # activos
docker ps -a     # todos
```

---

## 🛑 stop → parar contenedor

```bash
docker stop mi-contenedor
```

---

## ❌ rm → borrar contenedor

```bash
docker rm mi-contenedor
```

---

## 🧱 images → ver imágenes

```bash
docker images
```

---

## 🗑️ rmi → borrar imagen

```bash
docker rmi ollama-demo
```

---

## 🔍 logs → ver salida

```bash
docker logs mi-contenedor
docker logs -f mi-contenedor   # en tiempo real
```

---

## 🧪 exec → ejecutar dentro de un contenedor

```bash
docker exec -it mi-contenedor bash
```

---

## 📡 inspect → info detallada

```bash
docker inspect mi-contenedor
```

---

## 🌐 redes

```bash
docker network ls
docker network create mi-red
docker run --network mi-red ...
```

---

## 🧹 limpieza

```bash
docker container prune   # contenedores parados
docker image prune       # imágenes no usadas
docker system prune      # TODO lo no usado
```

---

## 🔁 flujo típico

```bash
docker build -t myapp .

docker run -d -p 8000:8000 --name app myapp

docker logs -f app

docker exec -it app bash

docker stop app

docker rm app
```

---

## ⚠️ errores comunes

* ❌ No encuentra archivos → problema de contexto (`.`)
* ❌ No conecta a Ollama → falta `--add-host` en Linux
* ❌ Puerto inaccesible → falta `-p`

---

## 🚀 resumen mental

* `build` → crea imagen
* `run` → ejecuta contenedor
* `ps` → ver contenedores
* `logs` → ver output
* `exec` → entrar dentro
* `rm / rmi` → limpiar
