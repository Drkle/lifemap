FROM mongo:7.0
# Los scripts se copian a la imagen en lugar de montarse con bind mount: cuando Jenkins
# despliega a través del socket de Docker, las rutas de un bind mount se resolverían en el
# host y no dentro del workspace de Jenkins.
# Solo se ejecutan la PRIMERA vez que se inicializa el volumen mongo_data.
COPY init/*.js /docker-entrypoint-initdb.d/
