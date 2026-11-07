# Traslado de LifeMap a un servidor separado del portátil

Recurso recomendado para la primera entrega: VM Linux Ubuntu 24.04 LTS o equipo de laboratorio
con al menos 4 vCPU, 16 GB de RAM y 80 GB de disco. Para la segunda entrega conviene 24 GB.
El equipo debe permanecer encendido y con salida a GitHub, Docker Hub, Maven, Kaggle y ngrok.
No se ha contratado ni creado una VM: faltan proveedor/cuenta, host y acceso del equipo.

## Preparar el host

1. Instalar Docker Engine y Docker Compose >=2.24.4 siguiendo la documentación oficial de Docker
   para Ubuntu: https://docs.docker.com/engine/install/ubuntu/ .
2. Clonar `https://github.com/Drkle/lifemap.git` en una carpeta de usuario, no en System32.
3. Ejecutar `bash deploy/preflight.sh` desde la raíz del repositorio.
4. Copiar `.env.example` a `.env`; configurar en el host las credenciales de MongoDB, Kaggle y
   ngrok, y el canal Smee. Mantener el archivo fuera de Git. Configurar las mismas credenciales
   en Jenkins. No enviar valores por chat.

Para que TODOS los comandos Compose, incluidos los de Jenkins, usen la configuración del
servidor, fijar en `.env` y en el entorno del contenedor Jenkins:

```text
COMPOSE_FILE=docker-compose.yml:deploy/compose.servidor.yml
```

En Linux el separador es `:`. Este override limita API, Jenkins y paneles de Spark/Dask a
127.0.0.1; el túnel ngrok puede acceder por la red Docker. Mongo ya está ligado a loopback.
No publicar puertos de administración de Spark, Dask, MongoDB o Jenkins sin autenticación.
El acceso de Jenkins al socket Docker da control del host: usar un host dedicado al proyecto.

## Arranque y acceso administrativo

```bash
export COMPOSE_FILE=docker-compose.yml:deploy/compose.servidor.yml
docker compose --profile ci up -d --build jenkins smee
```

Abrir un túnel SSH desde el equipo de trabajo:

```bash
ssh -L 8080:127.0.0.1:8080 usuario@servidor
```

Luego acceder a `http://localhost:8080` en ese equipo. Completar el asistente, crear administrador
y registrar `mongo-root` (Username/password) y `kaggle-api-token` (Secret text). Registrar
`COMPOSE_FILE` como variable del entorno de Jenkins para que los shells del pipeline la hereden;
el archivo raíz y `deploy/compose.servidor.yml` deben estar en su checkout. Crear `lifemap-main`
con Git SCM, rama `*/main`, ruta `Jenkinsfile`. Mantener ENTREGA2=false y FORZAR_FALLO=false.

El primer build reconstruye imágenes, descarga Yelp y genera los datos/modelos en el servidor.
Verificar SUCCESS antes de mover la URL pública. No copiar credenciales ni volúmenes sin necesidad;
reconstruir desde Kaggle permite demostrar reproducibilidad.

## Conservar la URL y verificar

Tras aprobar la API en el servidor, detener SOLO el túnel ngrok del portátil y arrancar el túnel
del servidor con el mismo dominio y cuenta. No iniciar ambos sobre el mismo dominio a la vez.
Nunca usar `docker compose down -v` como parte de la migración.

```bash
docker compose --profile public up -d ngrok
curl -fsS https://aviation-decrease-hunger.ngrok-free.dev/health
```

Comprobar el hash de main y el modelo. Probar los seis endpoints y repetir FORZAR_FALLO=true
sin cambiar el despliegue. Registrar hora de inicio y verificar disponibilidad durante al menos
48 horas hasta terminar la sustentación. Apagar el portátil después de mover el túnel y verificar
la URL desde otra red demuestra que el servicio dejó de depender de él.

El cambio de URL/túnel debe hacerse con acceso a ambos hosts y un servidor ya validado. Esta guía
no demuestra por sí misma que el traslado haya ocurrido.
