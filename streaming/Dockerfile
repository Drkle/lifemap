# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 SPARK_LOCAL_IP=127.0.0.1
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/streaming
COPY streaming/requirements.txt .
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.txt
# Dependencias oficiales Spark Kafka, fijadas y resueltas al construir, no en cada arranque.
RUN --mount=type=secret,id=proxy_ca \
    python - <<'PY'
import os, ssl
from urllib.request import urlopen
import pyspark
from pathlib import Path
ctx=ssl.create_default_context(cafile='/run/secrets/proxy_ca' if Path('/run/secrets/proxy_ca').exists() else None)
jars=Path(pyspark.__file__).parent/'jars'
files=[('org/apache/spark','spark-sql-kafka-0-10_2.12','3.5.3'),('org/apache/spark','spark-token-provider-kafka-0-10_2.12','3.5.3'),('org/apache/kafka','kafka-clients','3.4.1'),('org/apache/commons','commons-pool2','2.11.1')]
for group,name,version in files:
    with urlopen(f'https://repo.maven.apache.org/maven2/{group}/{name}/{version}/{name}-{version}.jar',context=ctx) as r:
        (jars/f'{name}-{version}.jar').write_bytes(r.read())
PY
COPY streaming/ api/app/analitica.py ingest/geohash.py ./
CMD ["python", "consumidor.py"]
