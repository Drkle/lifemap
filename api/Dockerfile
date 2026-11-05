# Etapa base: dependencias de ejecución y código de la API
FROM python:3.11-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Java para cargar el modelo de Spark en /predict (Spark local dentro de la API).
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

# Etapa de pruebas: la usa Jenkins con  docker build --target test
FROM base AS test
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY pytest.ini .
COPY tests ./tests
CMD ["pytest", "-q", "tests"]

# Etapa final: la que se despliega. El hash del commit queda grabado en la imagen.
FROM base AS runtime
ARG GIT_COMMIT=desconocido
ENV APP_COMMIT=${GIT_COMMIT}
EXPOSE 5000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=4 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:5000/health', timeout=4).status==200 else 1)"
# Un solo proceso con hilos: todos comparten la misma JVM del modelo de sentimiento.
CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "1", "--threads", "8", "--timeout", "120", "--access-logfile", "-", "app:create_app()"]
