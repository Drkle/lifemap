# syntax=docker/dockerfile:1
# Imagen OFICIAL de Apache Spark (no Bitnami: sus imágenes gratuitas se retiraron en 2025).
# Versiones fijadas: Spark 3.5 usa Scala 2.12, así que el conector debe ser _2.12.
ARG SPARK_IMAGE=apache/spark:3.5.3-scala2.12-java17-python3-ubuntu
FROM ${SPARK_IMAGE}

# MongoDB Spark Connector y sus dependencias del driver Java, descargados en una capa RUN
# cacheable (ADD remoto vuelve a consultar Maven incluso cuando la imagen ya existe).
# No se usa --packages en cada ejecución, que haría cada job dependiente de internet.
# Si cambian la versión del conector, revisar en Maven Central qué versión del driver pide.
ARG CONNECTOR_VERSION=10.4.0
ARG DRIVER_VERSION=5.1.4
ARG MAVEN=https://repo.maven.apache.org/maven2
RUN python3 -c "from urllib.request import urlretrieve; files=[('org/mongodb/spark/mongo-spark-connector_2.12/${CONNECTOR_VERSION}/mongo-spark-connector_2.12-${CONNECTOR_VERSION}.jar','mongo-spark-connector_2.12-${CONNECTOR_VERSION}.jar'),('org/mongodb/mongodb-driver-sync/${DRIVER_VERSION}/mongodb-driver-sync-${DRIVER_VERSION}.jar','mongodb-driver-sync-${DRIVER_VERSION}.jar'),('org/mongodb/mongodb-driver-core/${DRIVER_VERSION}/mongodb-driver-core-${DRIVER_VERSION}.jar','mongodb-driver-core-${DRIVER_VERSION}.jar'),('org/mongodb/bson/${DRIVER_VERSION}/bson-${DRIVER_VERSION}.jar','bson-${DRIVER_VERSION}.jar'),('org/mongodb/bson-record-codec/${DRIVER_VERSION}/bson-record-codec-${DRIVER_VERSION}.jar','bson-record-codec-${DRIVER_VERSION}.jar')]; [urlretrieve('${MAVEN}/'+src, '/opt/spark/jars/'+dst) for src,dst in files]" \
    && chmod 0644 /opt/spark/jars/*.jar

# MLlib (pyspark.ml) necesita numpy en el driver y en los executors.
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3-numpy \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /models /data/evidencias

COPY --chmod=755 jobs /opt/jobs
COPY --chmod=755 tests /opt/tests
ENV PATH="/opt/spark/bin:${PATH}"
WORKDIR /opt/jobs
