FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/ingest
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Los datos de Kaggle viven en un volumen con nombre montado aquí (caché de descarga).
RUN mkdir -p /data

FROM base AS test
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
CMD ["python", "-m", "pytest", "-q", "tests"]

FROM base AS runtime
# Por defecto no hace nada; compose define el comando de cada rol (scheduler / worker / job).
CMD ["python", "-c", "print('Imagen de Dask lista. Definir el comando en docker-compose.')"]
